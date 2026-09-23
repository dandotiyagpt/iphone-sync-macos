"""Compact, minimal macOS menu-bar popover widget (iStat Menus style).

Provides glanceable device telemetry, storage breakdown bar, live sync progress,
and quick action buttons in an ultra-compact floating interface.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from iphone_sync.config import Settings
from iphone_sync.ui.theme import get_theme, get_theme_stylesheet


class StorageBarWidget(QWidget):
    """Horizontal segmented bar showing device storage distribution."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(9)
        self._segments: list[tuple[str, float, str]] = [
            ("Photos", 0.45, "#0A84FF"),
            ("Files", 0.18, "#FF9F0A"),
            ("WhatsApp", 0.12, "#30D158"),
            ("Free", 0.25, "#3A3A3C"),
        ]

    def set_storage_data(
        self,
        photos_gb: float = 120.0,
        files_gb: float = 35.0,
        whatsapp_gb: float = 18.0,
        total_gb: float = 256.0,
    ) -> None:
        used = photos_gb + files_gb + whatsapp_gb
        free_gb = max(0.0, total_gb - used)
        total = max(1.0, total_gb)

        self._segments = [
            ("Photos", photos_gb / total, "#0A84FF"),
            ("Files", files_gb / total, "#FF9F0A"),
            ("WhatsApp", whatsapp_gb / total, "#30D158"),
            ("Free", free_gb / total, "#3A3A3C"),
        ]
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect()
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), 4.5, 4.5)
        painter.setClipPath(path)

        x = rect.x()
        w = rect.width()
        h = rect.height()

        for _name, ratio, color_hex in self._segments:
            seg_w = max(2, int(w * ratio))
            painter.fillRect(x, rect.y(), seg_w, h, QColor(color_hex))
            x += seg_w

        # Fill any remaining sub-pixel gap with the last color
        if x < rect.right():
            painter.fillRect(x, rect.y(), rect.right() - x + 1, h, QColor(self._segments[-1][2]))

        painter.end()


class TrayPopover(QWidget):
    """Floating menu-bar companion popover."""

    sync_requested = Signal()
    gallery_requested = Signal()
    settings_requested = Signal()
    open_dashboard_requested = Signal()

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint,
        )
        self._settings = settings
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(360)

        self._build_ui()
        self.apply_theme()

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(8, 8, 8, 8)

        # Card container with glassmorphism border and background
        self._card = QFrame()
        self._card.setObjectName("popoverCard")
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(12)

        # ----------------------------------------------------
        # 1. HEADER: Device name & live battery
        # ----------------------------------------------------
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        self._device_title = QLabel("iPhone — Disconnected")
        self._device_title.setStyleSheet("font-size: 14px; font-weight: 700; letter-spacing: -0.2px;")
        header_row.addWidget(self._device_title)

        header_row.addStretch()

        self._battery_pill = QLabel("● Waiting")
        self._battery_pill.setStyleSheet(
            "background: rgba(255, 159, 10, 0.15); color: #FF9F0A; "
            "border: 1px solid rgba(255, 159, 10, 0.3); border-radius: 9px; "
            "padding: 2px 8px; font-size: 11px; font-weight: 600;"
        )
        header_row.addWidget(self._battery_pill)
        card_layout.addLayout(header_row)

        # ----------------------------------------------------
        # 2. STORAGE USAGE SECTION
        # ----------------------------------------------------
        storage_header = QHBoxLayout()
        storage_title = QLabel("Storage Usage Bar")
        storage_title.setStyleSheet("font-size: 11px; font-weight: 600; color: #8E8E93;")
        storage_header.addWidget(storage_title)
        storage_header.addStretch()
        self._storage_total_label = QLabel("256 GB")
        self._storage_total_label.setStyleSheet("font-size: 11px; color: #636366;")
        storage_header.addWidget(self._storage_total_label)
        card_layout.addLayout(storage_header)

        self._storage_bar = StorageBarWidget()
        card_layout.addWidget(self._storage_bar)

        # Legend row
        legend_row = QHBoxLayout()
        legend_row.setSpacing(8)

        def make_legend(color: str, label_text: str) -> QLabel:
            lbl = QLabel(f"<span style='color:{color}; font-size:12px;'>●</span> {label_text}")
            lbl.setStyleSheet("font-size: 10px; color: #8E8E93;")
            return lbl

        self._legend_photos = make_legend("#0A84FF", "Photos")
        self._legend_files = make_legend("#FF9F0A", "Files")
        self._legend_whatsapp = make_legend("#30D158", "WhatsApp")
        self._legend_free = make_legend("#636366", "Free")

        legend_row.addWidget(self._legend_photos)
        legend_row.addWidget(self._legend_files)
        legend_row.addWidget(self._legend_whatsapp)
        legend_row.addWidget(self._legend_free)
        legend_row.addStretch()
        card_layout.addLayout(legend_row)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("background: rgba(255, 255, 255, 0.07); max-height: 1px;")
        card_layout.addWidget(divider)

        # ----------------------------------------------------
        # 3. SYNC STATUS & SPEEDOMETER
        # ----------------------------------------------------
        sync_header = QHBoxLayout()
        sync_title = QLabel("Sync Status")
        sync_title.setStyleSheet("font-size: 11px; font-weight: 600; color: #8E8E93;")
        sync_header.addWidget(sync_title)
        card_layout.addLayout(sync_header)

        self._sync_status_label = QLabel("Ready to sync photos, files, and WhatsApp")
        self._sync_status_label.setStyleSheet("font-size: 12px; font-weight: 500;")
        card_layout.addWidget(self._sync_status_label)

        self._progress = QProgressBar()
        self._progress.setFixedHeight(4)
        self._progress.setTextVisible(False)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        card_layout.addWidget(self._progress)

        # ----------------------------------------------------
        # 4. QUICK ACTION DOCK
        # ----------------------------------------------------
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._sync_btn = QPushButton("🔄 Sync Now")
        self._sync_btn.setProperty("btnStyle", "primary-blue")
        self._sync_btn.clicked.connect(self._on_sync_clicked)
        btn_row.addWidget(self._sync_btn)

        self._gallery_btn = QPushButton("🖼️ Gallery")
        self._gallery_btn.setProperty("btnStyle", "header-action")
        self._gallery_btn.clicked.connect(self._on_gallery_clicked)
        btn_row.addWidget(self._gallery_btn)

        self._pref_btn = QPushButton("⚙️ Settings")
        self._pref_btn.setProperty("btnStyle", "header-action")
        self._pref_btn.clicked.connect(self._on_settings_clicked)
        btn_row.addWidget(self._pref_btn)

        card_layout.addLayout(btn_row)

        # Footer dashboard link
        footer_row = QHBoxLayout()
        footer_row.setContentsMargins(0, 2, 0, 0)
        self._dashboard_link = QPushButton("Open Full Dashboard ›")
        self._dashboard_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dashboard_link.setStyleSheet(
            "background: transparent; border: none; color: #0A84FF; font-size: 11px; font-weight: 500; text-align: right;"
        )
        self._dashboard_link.clicked.connect(self._on_open_dashboard_clicked)
        footer_row.addStretch()
        footer_row.addWidget(self._dashboard_link)
        card_layout.addLayout(footer_row)

        outer_layout.addWidget(self._card)

    def apply_theme(self) -> None:
        """Apply current theme stylesheet to the popover."""
        palette = get_theme(self._settings.theme)
        card_bg = palette.card_bg
        card_border = palette.card_border
        text_color = palette.text_primary

        self._card.setStyleSheet(
            f"#popoverCard {{"
            f"  background-color: {card_bg};"
            f"  border: 1px solid {card_border};"
            f"  border-radius: 12px;"
            f"}}"
        )
        self.setStyleSheet(get_theme_stylesheet(self._settings.theme))
        self._device_title.setStyleSheet(
            f"color: {text_color}; font-size: 14px; font-weight: 700; letter-spacing: -0.2px;"
        )
        self._sync_status_label.setStyleSheet(
            f"color: {text_color}; font-size: 12px; font-weight: 500;"
        )

    def update_device(
        self,
        name: str | None,
        connected: bool,
        battery: int = 94,
        is_charging: bool = True,
    ) -> None:
        """Update live device state and battery display."""
        if connected:
            self._device_title.setText(name or "iPhone")
            bolt = " ⚡" if is_charging else ""
            self._battery_pill.setText(f"{battery}%{bolt}")
            self._battery_pill.setStyleSheet(
                "background: rgba(48, 209, 88, 0.15); color: #30D158; "
                "border: 1px solid rgba(48, 209, 88, 0.3); border-radius: 9px; "
                "padding: 2px 8px; font-size: 11px; font-weight: 600;"
            )
            self._sync_btn.setEnabled(True)
        else:
            self._device_title.setText("iPhone — Disconnected")
            self._battery_pill.setText("● Offline")
            self._battery_pill.setStyleSheet(
                "background: rgba(255, 159, 10, 0.15); color: #FF9F0A; "
                "border: 1px solid rgba(255, 159, 10, 0.3); border-radius: 9px; "
                "padding: 2px 8px; font-size: 11px; font-weight: 600;"
            )
            self._sync_btn.setEnabled(False)

    def update_sync_progress(
        self,
        status_text: str,
        percent: int = 0,
        is_active: bool = False,
    ) -> None:
        """Update live sync status text and progress bar."""
        self._sync_status_label.setText(status_text)
        self._progress.setValue(max(0, min(100, percent)))
        self._sync_btn.setText("Syncing…" if is_active else "🔄 Sync Now")
        self._sync_btn.setEnabled(not is_active)

    def update_storage(
        self,
        photos_gb: float,
        files_gb: float,
        whatsapp_gb: float,
        total_gb: float = 256.0,
    ) -> None:
        """Update storage bar distribution and legend."""
        self._storage_bar.set_storage_data(photos_gb, files_gb, whatsapp_gb, total_gb)
        self._storage_total_label.setText(f"{total_gb:.0f} GB")
        self._legend_photos.setText(f"<span style='color:#0A84FF; font-size:12px;'>●</span> Photos: {photos_gb:.1f}G")
        self._legend_files.setText(f"<span style='color:#FF9F0A; font-size:12px;'>●</span> Files: {files_gb:.1f}G")
        self._legend_whatsapp.setText(f"<span style='color:#30D158; font-size:12px;'>●</span> WA: {whatsapp_gb:.1f}G")

    def show_at_tray(self, tray_rect: QRect) -> None:
        """Position the popover directly beneath the macOS menu-bar tray item."""
        self.apply_theme()
        popover_w = self.width()
        popover_h = self.sizeHint().height()

        screen = QGuiApplication.primaryScreen()
        screen_geo = screen.availableGeometry() if screen else QRect(0, 0, 1440, 900)

        if tray_rect.isValid() and not tray_rect.isEmpty():
            x = tray_rect.center().x() - (popover_w // 2)
            y = tray_rect.bottom() + 4
        else:
            # Fallback to top-right corner if geometry is not provided by OS
            x = screen_geo.right() - popover_w - 20
            y = screen_geo.top() + 28

        # Keep inside screen bounds
        x = max(screen_geo.left() + 10, min(x, screen_geo.right() - popover_w - 10))
        y = max(screen_geo.top() + 10, min(y, screen_geo.bottom() - popover_h - 10))

        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_sync_clicked(self) -> None:
        self.sync_requested.emit()

    def _on_gallery_clicked(self) -> None:
        self.hide()
        self.gallery_requested.emit()

    def _on_settings_clicked(self) -> None:
        self.hide()
        self.settings_requested.emit()

    def _on_open_dashboard_clicked(self) -> None:
        self.hide()
        self.open_dashboard_requested.emit()


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("iPhone Sync Popover")
    settings = Settings.load()
    popover = TrayPopover(settings)
    popover.update_device("iPhone 16 Pro", connected=True, battery=94, is_charging=True)
    popover.update_storage(photos_gb=180.5, files_gb=45.2, whatsapp_gb=22.8, total_gb=512.0)
    popover.update_sync_progress("Ready to sync • 18 new photos", percent=0, is_active=False)

    screen = app.primaryScreen()
    if screen:
        geo = screen.availableGeometry()
        popover.move(geo.right() - popover.width() - 30, geo.top() + 35)

    popover.show()
    sys.exit(app.exec())

