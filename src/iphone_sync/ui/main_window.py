"""Main window — photo sync, Files app media, and WhatsApp backup.

The window is only a front-end for the menu bar agent: closing it hides it
and the app keeps watching for iPhones in the background.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from iphone_sync.config import Settings
from iphone_sync.core.backup_reset import count_backup_files, reset_backup
from iphone_sync.core.device_backup_info import (
    format_size,
    inspect_device_backup,
    list_local_backups,
)
from iphone_sync.core.device_watcher import DeviceInfo, DeviceWatcher
from iphone_sync.core.files_backup_engine import (
    FilesBackupEngine,
    FilesBackupResult,
    count_files_under,
    files_backup_root,
)
from iphone_sync.core.manifest import Manifest
from iphone_sync.core.sync_engine import SyncEngine, SyncResult
from iphone_sync.core.whatsapp_backup_engine import WhatsAppBackupEngine, WhatsAppBackupResult
from iphone_sync.ui.backup_dialogs import EncryptionPasswordDialog, RestoreBackupDialog
from iphone_sync.ui.gallery_window import GalleryWindow
from iphone_sync.ui.settings_dialog import SettingsDialog
from iphone_sync.ui.theme import get_theme_stylesheet
from iphone_sync.ui.tray_popover import TrayPopover
from iphone_sync.ui.widgets.progress import LogViewer, ProgressWidget
from iphone_sync.utils.macos_app import activate_app, set_menu_bar_only
from iphone_sync.utils.prerequisites import prerequisite_status
from iphone_sync.utils.tray_icon import make_tray_icon


def _create_badge(text: str, bg_color: str, text_color: str, border_color: str) -> QLabel:
    """Helper to create a sleek pill badge."""
    badge = QLabel(text)
    badge.setStyleSheet(
        f"background: {bg_color}; "
        f"color: {text_color}; "
        f"border: 1px solid {border_color}; "
        "border-radius: 10px; "
        "padding: 3px 10px; "
        "font-weight: 600; "
        "font-size: 11px;"
    )
    return badge


def _create_card_header(
    icon: str,
    title: str,
    gradient_start: str,
    gradient_end: str,
    trailing_widget: QWidget | None = None,
) -> QHBoxLayout:
    """Creates a standardized card header with colorful icon badge."""
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 4)
    row.setSpacing(10)

    icon_label = QLabel(icon)
    icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon_label.setFixedSize(30, 30)
    icon_label.setStyleSheet(
        f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {gradient_start}, stop:1 {gradient_end}); "
        "border-radius: 8px; "
        "color: #FFFFFF; "
        "font-size: 14px;"
    )
    row.addWidget(icon_label)

    title_label = QLabel(title)
    title_label.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: 700; letter-spacing: 0.2px;")
    row.addWidget(title_label)

    row.addStretch()

    if trailing_widget:
        row.addWidget(trailing_widget)

    return row


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings
        self._manifest = Manifest(settings.manifest_db_path())
        self._sync_engine = SyncEngine(settings, self._manifest)
        self._whatsapp_engine = WhatsAppBackupEngine(settings)
        self._files_backup_engine = FilesBackupEngine(settings)
        self._device_watcher = DeviceWatcher()
        self._connected_device: DeviceInfo | None = None
        self._active_worker = None
        self._whatsapp_worker = None
        self._files_backup_worker = None
        self._last_sync: datetime | None = None
        self._run_files_after_photos = False
        self._run_whatsapp_after_chain = False
        self._pending_encryption_then_backup = False
        self._gallery_window = None

        self.setWindowTitle("iPhone Sync")
        self.setMinimumSize(640, 430)
        self.resize(660, 470)

        # Apply global modern theme
        self.setStyleSheet(get_theme_stylesheet(self._settings.theme))

        self._build_ui()
        self._build_menu()
        self._build_tray()
        self._connect_signals()
        self._check_prerequisites()
        self._device_watcher.start()
        self._update_device_panel()
        self._refresh_whatsapp_status()
        self._refresh_files_backup_status()

    def _build_ui(self) -> None:
        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 14, 16, 14)
        main_layout.setSpacing(10)

        # ----------------------------------------------------
        # TOP HEADER BAR: Device Status & Quick Actions
        # ----------------------------------------------------
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 2)
        header_layout.setSpacing(10)

        app_icon = QLabel("📱")
        app_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_icon.setFixedSize(36, 36)
        app_icon.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0A84FF, stop:1 #5E5CE6); "
            "border-radius: 9px; "
            "font-size: 18px; "
            "border: 1px solid rgba(255, 255, 255, 0.2);"
        )
        header_layout.addWidget(app_icon)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(1)

        dev_row = QHBoxLayout()
        dev_row.setSpacing(8)
        self._device_title = QLabel("iPhone Sync")
        self._device_title.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: 700; letter-spacing: -0.2px;")
        dev_row.addWidget(self._device_title)

        self._device_status_dot = QLabel("● Disconnected")
        self._device_status_dot.setStyleSheet("color: #FF9F0A; font-size: 11px; font-weight: 600;")
        dev_row.addWidget(self._device_status_dot)
        dev_row.addStretch()
        title_vbox.addLayout(dev_row)

        self._device_sub_lbl = QLabel("Connect your iPhone via USB cable to sync")
        self._device_sub_lbl.setStyleSheet("color: #8E8E93; font-size: 11px;")
        title_vbox.addWidget(self._device_sub_lbl)
        header_layout.addLayout(title_vbox)

        header_layout.addStretch()

        # Top Quick Action Buttons
        self._gallery_btn = QPushButton("🖼️ Gallery")
        self._gallery_btn.setProperty("btnStyle", "header-action")
        self._gallery_btn.setToolTip("Open full-screen photo & video gallery viewer")
        self._gallery_btn.clicked.connect(self._open_gallery)
        header_layout.addWidget(self._gallery_btn)

        self._settings_btn = QPushButton("⚙️")
        self._settings_btn.setProperty("btnStyle", "header-action")
        self._settings_btn.setToolTip("Settings")
        self._settings_btn.setFixedWidth(34)
        self._settings_btn.clicked.connect(self._open_settings)
        header_layout.addWidget(self._settings_btn)

        # More Actions dropdown
        self._more_menu = QMenu(self)
        self._reset_action = self._more_menu.addAction("Delete Photo Backup…")
        self._reset_action.triggered.connect(self._delete_previous_backup)
        self._delete_files_action = self._more_menu.addAction("Delete Files Backup…")
        self._delete_files_action.triggered.connect(self._delete_files_backup)
        self._delete_whatsapp_action = self._more_menu.addAction("Delete WhatsApp Backup…")
        self._delete_whatsapp_action.triggered.connect(self._delete_whatsapp_backup)
        self._more_menu.addSeparator()
        prereq_act = self._more_menu.addAction("Check Prerequisites…")
        prereq_act.triggered.connect(self._check_prerequisites)

        self._more_btn = QPushButton("⋯")
        self._more_btn.setProperty("btnStyle", "header-action")
        self._more_btn.setToolTip("More actions and backup tools")
        self._more_btn.setFixedWidth(34)
        self._more_btn.setMenu(self._more_menu)
        header_layout.addWidget(self._more_btn)

        main_layout.addWidget(header_widget)

        # ====================================================
        # CARD 1: PHOTOS SYNC (Apple Blue Theme)
        # ====================================================
        photos_card = QFrame()
        photos_card.setProperty("card", "true")
        photos_layout = QHBoxLayout(photos_card)
        photos_layout.setContentsMargins(14, 11, 14, 11)
        photos_layout.setSpacing(12)

        photos_info = QVBoxLayout()
        photos_info.setSpacing(2)
        photos_title = QLabel("Photos Sync")
        photos_title.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: 700;")
        self._photos_stats_lbl = QLabel("Ready to sync photos and videos")
        self._photos_stats_lbl.setStyleSheet("color: #8E8E93; font-size: 11px;")
        photos_info.addWidget(photos_title)
        photos_info.addWidget(self._photos_stats_lbl)
        photos_layout.addLayout(photos_info)

        photos_layout.addStretch()

        photos_actions = QHBoxLayout()
        photos_actions.setSpacing(8)
        self._photos_badge = _create_badge("Idle", "rgba(255, 255, 255, 0.08)", "#9898A0", "rgba(255, 255, 255, 0.12)")
        photos_actions.addWidget(self._photos_badge, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._sync_btn = QPushButton("Sync Photos")
        self._sync_btn.setProperty("btnStyle", "primary-blue")
        self._sync_btn.setEnabled(False)
        self._sync_btn.clicked.connect(self._start_sync)
        photos_actions.addWidget(self._sync_btn)

        self._cancel_btn = QPushButton("✕")
        self._cancel_btn.setProperty("btnStyle", "header-action")
        self._cancel_btn.setToolTip("Cancel Photo Sync")
        self._cancel_btn.setFixedWidth(30)
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.setVisible(False)
        self._cancel_btn.clicked.connect(self._cancel_sync)
        photos_actions.addWidget(self._cancel_btn)

        photos_layout.addLayout(photos_actions)
        main_layout.addWidget(photos_card)

        # ====================================================
        # CARD 2: FILES APP (Apple Mint / Green Theme)
        # ====================================================
        files_card = QFrame()
        files_card.setProperty("card", "true")
        files_layout = QHBoxLayout(files_card)
        files_layout.setContentsMargins(14, 11, 14, 11)
        files_layout.setSpacing(12)

        files_info = QVBoxLayout()
        files_info.setSpacing(3)
        files_title = QLabel("Files App")
        files_title.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: 700;")

        # Scope pills row
        scope_row = QHBoxLayout()
        scope_row.setSpacing(4)
        for tag in ("Downloads", "Books", "Voice Memos"):
            pill = QLabel(tag)
            pill.setStyleSheet(
                "background: rgba(255, 255, 255, 0.06); color: #8E8E93; "
                "border-radius: 4px; padding: 1px 5px; font-size: 10px; font-weight: 500;"
            )
            scope_row.addWidget(pill)
        scope_row.addStretch()

        self._files_backup_status = QLabel("No Files backup yet")
        self._files_backup_status.setStyleSheet("color: #8E8E93; font-size: 11px;")

        files_info.addWidget(files_title)
        files_info.addLayout(scope_row)
        files_info.addWidget(self._files_backup_status)
        files_layout.addLayout(files_info)

        files_layout.addStretch()

        files_actions = QHBoxLayout()
        files_actions.setSpacing(8)
        self._files_count_badge = _create_badge(
            "0 files", "rgba(255, 255, 255, 0.08)", "#9898A0", "rgba(255, 255, 255, 0.12)"
        )
        files_actions.addWidget(self._files_count_badge, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._files_backup_btn = QPushButton("Backup Files")
        self._files_backup_btn.setProperty("btnStyle", "primary-green")
        self._files_backup_btn.setToolTip("Copy Downloads, Books, Recordings, and Documents to this Mac")
        self._files_backup_btn.setEnabled(False)
        self._files_backup_btn.clicked.connect(self._start_files_backup_clicked)
        files_actions.addWidget(self._files_backup_btn)

        files_layout.addLayout(files_actions)
        main_layout.addWidget(files_card)

        # ====================================================
        # CARD 3: WHATSAPP BACKUP (Purple Theme)
        # ====================================================
        backup_card = QFrame()
        backup_card.setProperty("card", "true")
        backup_layout = QHBoxLayout(backup_card)
        backup_layout.setContentsMargins(14, 11, 14, 11)
        backup_layout.setSpacing(12)

        backup_info = QVBoxLayout()
        backup_info.setSpacing(2)
        backup_title = QLabel("WhatsApp Backup")
        backup_title.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: 700;")

        self._whatsapp_backup_status = QLabel("No WhatsApp backup yet")
        self._whatsapp_backup_status.setStyleSheet("color: #8E8E93; font-size: 11px;")

        self._whatsapp_status = QLabel("Chats & media — encrypted backup required")
        self._whatsapp_status.setStyleSheet("color: #BF5AF2; font-size: 11px; font-weight: 500;")

        backup_info.addWidget(backup_title)
        backup_info.addWidget(self._whatsapp_backup_status)
        backup_info.addWidget(self._whatsapp_status)
        backup_layout.addLayout(backup_info)

        backup_layout.addStretch()

        backup_actions = QHBoxLayout()
        backup_actions.setSpacing(8)
        self._whatsapp_badge = _create_badge(
            "🔒 Encrypted", "rgba(255, 159, 10, 0.12)", "#FF9F0A", "rgba(255, 159, 10, 0.25)"
        )
        backup_actions.addWidget(self._whatsapp_badge, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._restore_btn = QPushButton("Restore…")
        self._restore_btn.setProperty("btnStyle", "header-action")
        self._restore_btn.setEnabled(False)
        self._restore_btn.setToolTip("Restore WhatsApp from a previous encrypted backup")
        self._restore_btn.clicked.connect(self._start_restore)
        backup_actions.addWidget(self._restore_btn)

        self._whatsapp_backup_btn = QPushButton("Backup Now")
        self._whatsapp_backup_btn.setProperty("btnStyle", "primary-purple")
        self._whatsapp_backup_btn.setEnabled(False)
        self._whatsapp_backup_btn.setMinimumWidth(104)
        self._whatsapp_backup_btn.setToolTip(
            "Capture WhatsApp chats and media in an encrypted snapshot"
        )
        self._whatsapp_backup_btn.clicked.connect(self._start_whatsapp_backup_clicked)
        backup_actions.addWidget(self._whatsapp_backup_btn)

        backup_layout.addLayout(backup_actions)
        main_layout.addWidget(backup_card)

        # ====================================================
        # UNIFIED PROGRESS BAR
        # ====================================================
        self._unified_progress = QProgressBar()
        self._unified_progress.setFixedHeight(5)
        self._unified_progress.setTextVisible(False)
        self._unified_progress.setRange(0, 100)
        self._unified_progress.setValue(0)
        self._unified_progress.setProperty("barStyle", "blue")
        main_layout.addWidget(self._unified_progress)

        # ====================================================
        # FOOTER STATUS BAR
        # ====================================================
        footer_row = QHBoxLayout()
        footer_row.setContentsMargins(2, 0, 2, 0)
        footer_row.setSpacing(8)

        self._status_label = QLabel("Waiting for iPhone connection…")
        self._status_label.setStyleSheet("color: #8E8E93; font-size: 11px;")
        footer_row.addWidget(self._status_label)

        footer_row.addStretch()

        self._last_sync_label = QLabel("Last sync: Never")
        self._last_sync_label.setStyleSheet("color: #636366; font-size: 11px;")
        footer_row.addWidget(self._last_sync_label)

        self._toggle_log_btn = QPushButton("📋 Log ▼")
        self._toggle_log_btn.setProperty("btnStyle", "header-action")
        self._toggle_log_btn.setFixedHeight(22)
        self._toggle_log_btn.setStyleSheet("font-size: 10px; padding: 2px 7px; border-radius: 4px;")
        self._toggle_log_btn.clicked.connect(self._toggle_log_drawer)
        footer_row.addWidget(self._toggle_log_btn)

        main_layout.addLayout(footer_row)

        # ====================================================
        # COLLAPSIBLE ACTIVITY LOG DRAWER
        # ====================================================
        self._log_container = QWidget()
        log_drawer_layout = QVBoxLayout(self._log_container)
        log_drawer_layout.setContentsMargins(0, 4, 0, 0)
        log_drawer_layout.setSpacing(4)

        log_hdr = QHBoxLayout()
        log_title = QLabel("Activity Log")
        log_title.setStyleSheet("color: #8E8E93; font-size: 11px; font-weight: 600;")
        clear_btn = QPushButton("Clear")
        clear_btn.setProperty("btnStyle", "header-action")
        clear_btn.setFixedHeight(20)
        clear_btn.setStyleSheet("font-size: 10px; padding: 1px 6px;")
        clear_btn.clicked.connect(lambda: self._log.clear_logs())
        log_hdr.addWidget(log_title)
        log_hdr.addStretch()
        log_hdr.addWidget(clear_btn)
        log_drawer_layout.addLayout(log_hdr)

        self._log = LogViewer()
        self._log.setMaximumHeight(120)
        log_drawer_layout.addWidget(self._log)
        self._log_container.setVisible(False)
        main_layout.addWidget(self._log_container)

        # Compatibility references
        self._device_empty_banner = QWidget()
        self._device_info_box = QWidget()
        self._device_badge = self._device_status_dot
        self._device_name = QLabel()
        self._device_status = QLabel()
        self._device_udid = QLabel()
        self._synced_count = QLabel()
        self._progress = ProgressWidget()
        self._files_backup_progress = QProgressBar()
        self._whatsapp_progress = QProgressBar()
        self._reset_btn = QPushButton("Delete Photo Backup")
        self._reset_btn.clicked.connect(self._delete_previous_backup)
        self._delete_files_backup_btn = QPushButton("Delete Files Backup")
        self._delete_files_backup_btn.clicked.connect(self._delete_files_backup)
        self._delete_whatsapp_btn = QPushButton("Delete Device Backup")
        self._delete_whatsapp_btn.clicked.connect(self._delete_whatsapp_backup)

        self.setCentralWidget(central)
        self.statusBar().hide()

    def _toggle_log_drawer(self) -> None:
        visible = not self._log_container.isVisible()
        self._log_container.setVisible(visible)
        self._toggle_log_btn.setText("📋 Log ▲" if visible else "📋 Log ▼")
        if visible:
            self.resize(self.width(), max(self.height(), 570))
        else:
            self.resize(self.width(), 460)

    def _set_unified_progress(self, value: int, style: str) -> None:
        if self._unified_progress.property("barStyle") != style:
            self._unified_progress.setProperty("barStyle", style)
            self._unified_progress.style().unpolish(self._unified_progress)
            self._unified_progress.style().polish(self._unified_progress)
        self._unified_progress.setValue(value)

    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu("File")

        gallery_action = QAction("Open Photos Gallery", self)
        gallery_action.triggered.connect(self._open_gallery)
        menu.addAction(gallery_action)

        settings_action = QAction("Settings…", self)
        settings_action.triggered.connect(self._open_settings)
        menu.addAction(settings_action)

        menu.addSeparator()

        delete_action = QAction("Delete Photo Backup…", self)
        delete_action.triggered.connect(self._delete_previous_backup)
        menu.addAction(delete_action)

        delete_files = QAction("Delete Files Backup…", self)
        delete_files.triggered.connect(self._delete_files_backup)
        menu.addAction(delete_files)

        delete_whatsapp = QAction("Delete WhatsApp Backup…", self)
        delete_whatsapp.triggered.connect(self._delete_whatsapp_backup)
        menu.addAction(delete_whatsapp)

        menu.addSeparator()

        quit_action = QAction("Quit iPhone Sync", self)
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(quit_action)

        help_menu = self.menuBar().addMenu("Help")
        prereq_action = QAction("Check Prerequisites", self)
        prereq_action.triggered.connect(self._check_prerequisites)
        help_menu.addAction(prereq_action)

    def _build_tray(self) -> None:
        """Status bar item — this, not the window, is the app's home."""
        self._tray = QSystemTrayIcon(self)
        self._tray_state = "idle"
        self._tray.setIcon(make_tray_icon("idle"))
        self._tray.setToolTip("iPhone Sync — waiting for iPhone")
        self._tray.activated.connect(self._tray_activated)

        menu = QMenu()
        self._tray_status_action = menu.addAction("Waiting for iPhone…")
        self._tray_status_action.setEnabled(False)
        menu.addSeparator()

        show_action = menu.addAction("Open iPhone Sync")
        show_action.triggered.connect(self._show_window)
        gallery_action = menu.addAction("Open Photos Gallery")
        gallery_action.triggered.connect(self._open_gallery)
        menu.addSeparator()

        sync_action = menu.addAction("Sync Photos Now")
        sync_action.triggered.connect(self._start_sync)
        files_action = menu.addAction("Backup Files Now")
        files_action.triggered.connect(self._start_files_backup_clicked)
        whatsapp_action = menu.addAction("Backup WhatsApp Now")
        whatsapp_action.triggered.connect(self._start_whatsapp_backup_clicked)
        menu.addSeparator()

        settings_action = menu.addAction("Settings…")
        settings_action.triggered.connect(self._open_settings_from_tray)
        quit_action = menu.addAction("Quit iPhone Sync")
        quit_action.triggered.connect(self._quit_app)

        # Keep a reference: a QMenu without a parent is garbage collected.
        self._tray_menu = menu
        self._tray.setContextMenu(menu)
        self._tray.show()

        # Compact menu-bar companion popover
        self._popover = TrayPopover(self._settings)
        self._popover.sync_requested.connect(self._start_sync)
        self._popover.gallery_requested.connect(self._open_gallery)
        self._popover.settings_requested.connect(self._open_settings_from_tray)
        self._popover.open_dashboard_requested.connect(self._show_window)

    def _set_tray_state(self, state: str, tooltip: str) -> None:
        if getattr(self, "_tray_state", None) != state:
            self._tray_state = state
            self._tray.setIcon(make_tray_icon(state))
        self._tray.setToolTip(f"iPhone Sync — {tooltip}")
        self._tray_status_action.setText(tooltip)

    def _notify(self, message: str, *, seconds: int = 4) -> None:
        """Menu bar notification; the window is usually hidden."""
        self._tray.showMessage(
            "iPhone Sync",
            message,
            QSystemTrayIcon.MessageIcon.Information,
            seconds * 1000,
        )

    def start_hidden(self) -> None:
        """Launch into the menu bar without showing the window (login start)."""
        self.hide()
        if self._settings.menu_bar_only:
            set_menu_bar_only(True)
        self._log.append_log("Started in the background — running in the menu bar.")

    def show_foreground(self) -> None:
        """Show the window and pull the app forward (menu bar apps don't auto-focus)."""
        self.show()
        self._show_window()
        if self._settings.menu_bar_only:
            set_menu_bar_only(True)

    def _show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()
        activate_app()

    def _open_settings_from_tray(self) -> None:
        self._show_window()
        self._open_settings()

    def _connect_signals(self) -> None:
        self._device_watcher.device_connected.connect(self._on_device_connected)
        self._device_watcher.device_disconnected.connect(self._on_device_disconnected)
        self._device_watcher.device_not_ready.connect(self._on_device_not_ready)

    def _busy(self) -> bool:
        return (
            self._sync_engine.is_running
            or self._whatsapp_engine.is_running
            or self._files_backup_engine.is_running
        )

    def _check_prerequisites(self) -> None:
        ok, message = prerequisite_status()
        if ok:
            self._log.append_log(message)
        else:
            self._log.append_log(f"Warning: {message}")
            QMessageBox.warning(self, "Prerequisites", message)

    def _on_device_connected(self, device: DeviceInfo) -> None:
        self._connected_device = device
        self._update_device_panel()
        self._refresh_whatsapp_status()
        self._log.append_log(f"iPhone connected: {device.name}")
        self._status_label.setText(f"Connected: {device.name}")
        self._set_tray_state("connected", f"Connected: {device.name}")
        self._notify(f"{device.name} connected — starting backup.", seconds=3)
        self._sync_popover_data()

        if self._busy():
            return

        self._run_files_after_photos = False
        self._run_whatsapp_after_chain = False

        if self._settings.auto_sync_on_plugin:
            self._run_files_after_photos = self._settings.auto_files_backup_on_plugin
            self._run_whatsapp_after_chain = self._settings.auto_whatsapp_backup_on_plugin
            self._start_sync()
        elif self._settings.auto_files_backup_on_plugin:
            self._run_whatsapp_after_chain = self._settings.auto_whatsapp_backup_on_plugin
            self._start_files_backup()
        elif self._settings.auto_whatsapp_backup_on_plugin:
            self._start_whatsapp_backup()

    def _on_device_disconnected(self, udid: str) -> None:
        if self._connected_device and self._connected_device.udid == udid:
            self._log.append_log("iPhone disconnected")
            self._connected_device = None
            self._update_device_panel()
            self._status_label.setText("Waiting for iPhone connection…")
            self._set_tray_state("idle", "Waiting for iPhone…")
            self._sync_popover_data()

    def _on_device_not_ready(self, reason: str) -> None:
        self._status_label.setText(reason)
        if not self._connected_device:
            self._set_tray_state("attention", reason)

    def _update_device_panel(self) -> None:
        busy = self._busy()
        if self._connected_device:
            self._device_status_dot.setText("● Connected")
            self._device_status_dot.setStyleSheet("color: #30D158; font-size: 11px; font-weight: 600;")
            self._device_title.setText(self._connected_device.name)

            count = self._manifest.count_for_device(self._connected_device.udid)
            udid_short = self._connected_device.udid[:12]
            self._device_sub_lbl.setText(f"UDID: {udid_short}… • {count:,} photos synced")
            self._photos_stats_lbl.setText(f"{count:,} photos synced safely")

            if not busy:
                self._photos_badge.setText("Ready")
                self._photos_badge.setStyleSheet(
                    "background: rgba(48, 209, 88, 0.15); color: #30D158; "
                    "border: 1px solid rgba(48, 209, 88, 0.3); border-radius: 8px; padding: 2px 7px; font-weight: 600; font-size: 11px;"
                )

            self._sync_btn.setEnabled(not busy)
            self._files_backup_btn.setEnabled(not busy)
            self._whatsapp_backup_btn.setEnabled(not busy)
            self._restore_btn.setEnabled(not busy)
        else:
            self._device_status_dot.setText("● Disconnected")
            self._device_status_dot.setStyleSheet("color: #FF9F0A; font-size: 11px; font-weight: 600;")
            self._device_title.setText("iPhone Sync")
            self._device_sub_lbl.setText("Connect your iPhone via USB cable to sync")
            self._photos_stats_lbl.setText("Connect iPhone to sync photos & videos")

            self._photos_badge.setText("Idle")
            self._photos_badge.setStyleSheet(
                "background: rgba(255, 255, 255, 0.08); color: #9898A0; "
                "border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 8px; padding: 2px 7px; font-weight: 600; font-size: 11px;"
            )

            self._sync_btn.setEnabled(False)
            self._files_backup_btn.setEnabled(False)
            self._whatsapp_backup_btn.setEnabled(False)
            self._restore_btn.setEnabled(False)

        self._reset_action.setEnabled(not busy)
        self._delete_files_action.setEnabled(not busy)
        self._delete_whatsapp_action.setEnabled(not busy)
        self._reset_btn.setEnabled(not busy)
        self._delete_files_backup_btn.setEnabled(not busy)
        self._delete_whatsapp_btn.setEnabled(not busy)
        self._cancel_btn.setEnabled(self._sync_engine.is_running)
        self._cancel_btn.setVisible(self._sync_engine.is_running)

    def _refresh_whatsapp_status(self) -> None:
        root = Path(self._settings.whatsapp_backup_folder)
        udid = self._connected_device.udid if self._connected_device else None
        info = None
        if udid:
            info = inspect_device_backup(root / udid)
        if info is None and udid is None:
            backups = list_local_backups(root)
            info = backups[0] if backups else None

        if info is None:
            self._whatsapp_backup_status.setText("No WhatsApp backup created yet")
            self._whatsapp_status.setText("Chats & media — encrypted backup required")
            self._whatsapp_badge.setText("⚠️ Required")
            self._whatsapp_badge.setStyleSheet(
                "background: rgba(255, 159, 10, 0.12); color: #FF9F0A; "
                "border: 1px solid rgba(255, 159, 10, 0.25); border-radius: 8px; padding: 2px 7px; font-weight: 600; font-size: 11px;"
            )
            return

        when = info.last_backup.strftime("%Y-%m-%d %H:%M") if info.last_backup else "unknown"
        enc = "Encrypted" if info.is_encrypted else "Unencrypted"
        self._whatsapp_backup_status.setText(f"Last backup: {when} · {format_size(info.size_bytes)} · {enc}")
        self._whatsapp_status.setText(info.whatsapp_status_label)

        if info.whatsapp_ok:
            self._whatsapp_badge.setText("🔒 Protected")
            self._whatsapp_badge.setStyleSheet(
                "background: rgba(48, 209, 88, 0.15); color: #30D158; "
                "border: 1px solid rgba(48, 209, 88, 0.3); border-radius: 8px; padding: 2px 7px; font-weight: 600; font-size: 11px;"
            )
        else:
            self._whatsapp_badge.setText("⚠️ Encryption Required")
            self._whatsapp_badge.setStyleSheet(
                "background: rgba(255, 159, 10, 0.12); color: #FF9F0A; "
                "border: 1px solid rgba(255, 159, 10, 0.25); border-radius: 8px; padding: 2px 7px; font-weight: 600; font-size: 11px;"
            )

    def _refresh_files_backup_status(self) -> None:
        root = Path(self._settings.files_backup_folder)
        if self._connected_device:
            dest = files_backup_root(
                self._settings,
                self._connected_device.name,
                self._connected_device.udid,
            )
        else:
            dest = root
            if root.exists():
                device_dirs = [p for p in root.iterdir() if p.is_dir()]
                dest = device_dirs[0] if device_dirs else root

        n = count_files_under(dest) if dest.exists() else 0
        if n == 0:
            self._files_count_badge.setText("0 files")
            self._files_count_badge.setStyleSheet(
                "background: rgba(255, 255, 255, 0.08); color: #9898A0; "
                "border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 8px; padding: 2px 7px; font-weight: 600; font-size: 11px;"
            )
            self._files_backup_status.setText("No Files backup yet")
        else:
            self._files_count_badge.setText(f"✓ {n:,} files")
            self._files_count_badge.setStyleSheet(
                "background: rgba(48, 209, 88, 0.15); color: #30D158; "
                "border: 1px solid rgba(48, 209, 88, 0.3); border-radius: 8px; padding: 2px 7px; font-weight: 600; font-size: 11px;"
            )
            self._files_backup_status.setText(f"✓ {n:,} files backed up safely")

    def _open_gallery(self) -> None:
        if self._gallery_window is None:
            self._gallery_window = GalleryWindow(self._settings)
        self._gallery_window.show()
        self._gallery_window.raise_()
        self._gallery_window.activateWindow()

    def _delete_previous_backup(self) -> None:
        if self._busy():
            QMessageBox.information(self, "Delete Photo Backup", "Wait for the current job to finish.")
            return

        dest = Path(self._settings.destination_folder)
        file_count = count_backup_files(dest)
        manifest_count = self._manifest.total_copied_count()

        if file_count == 0 and manifest_count == 0:
            QMessageBox.information(
                self,
                "Delete Photo Backup",
                "No previous photo backup found.",
            )
            return

        reply = QMessageBox.warning(
            self,
            "Delete Photo Backup",
            f"This permanently deletes copied photos and videos from your Mac.\n\n"
            f"Folder: {dest}\n"
            f"Files on disk: {file_count}\n"
            f"Sync history: {manifest_count} files\n\n"
            f"(WhatsApp is a separate backup — use Delete WhatsApp Backup.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._reset_btn.setEnabled(False)
        self._log.append_log("Deleting previous photo backup…")
        result = reset_backup(dest, self._manifest)
        self._update_device_panel()

        if result.errors:
            for err in result.errors:
                self._log.append_log(f"Warning: {err}")
            QMessageBox.warning(
                self,
                "Delete Photo Backup",
                f"Mostly cleared ({result.files_deleted} files), with some errors. See log.",
            )
        else:
            self._log.append_log(
                f"Photo backup cleared — {result.files_deleted} files removed."
            )
            QMessageBox.information(
                self,
                "Delete Photo Backup",
                f"Photo backup deleted ({result.files_deleted} files).",
            )
        self._status_label.setText("Photo backup cleared")

    def _delete_whatsapp_backup(self) -> None:
        if self._busy():
            QMessageBox.information(
                self, "Delete WhatsApp Backup", "Wait for the current job to finish."
            )
            return

        root = Path(self._settings.whatsapp_backup_folder)
        if not root.exists() or not any(root.iterdir()):
            QMessageBox.information(
                self, "Delete WhatsApp Backup", "No WhatsApp backups found."
            )
            return

        reply = QMessageBox.warning(
            self,
            "Delete WhatsApp Backup",
            f"Permanently delete all WhatsApp backup snapshots under:\n\n{root}\n\n"
            "You will not be able to restore WhatsApp chats until you back up again.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        errors: list[str] = []
        for entry in list(root.iterdir()):
            try:
                if entry.is_dir():
                    shutil.rmtree(entry)
                else:
                    entry.unlink()
            except OSError as exc:
                errors.append(str(exc))

        self._refresh_whatsapp_status()
        if errors:
            self._log.append_log("WhatsApp backup delete had errors: " + "; ".join(errors))
            QMessageBox.warning(
                self, "Delete WhatsApp Backup", "Some files could not be deleted."
            )
        else:
            self._log.append_log("WhatsApp backups deleted.")
            QMessageBox.information(
                self, "Delete WhatsApp Backup", "WhatsApp backups deleted."
            )

    def _start_sync(self) -> None:
        if self._busy():
            return
        if not self._connected_device:
            QMessageBox.information(self, "Sync", "No iPhone connected.")
            return

        dest = Path(self._settings.destination_folder)
        dest.mkdir(parents=True, exist_ok=True)

        self._progress.reset()
        self._set_unified_progress(0, "blue")
        self._status_label.setText("Starting photo sync…")
        self._photos_badge.setText("Syncing…")
        self._photos_badge.setStyleSheet(
            "background: rgba(10, 132, 255, 0.2); color: #64D2FF; "
            "border: 1px solid rgba(10, 132, 255, 0.35); border-radius: 8px; padding: 2px 7px; font-weight: 600; font-size: 11px;"
        )
        self._update_device_panel()
        self._log.append_log("Starting photo sync…")

        worker = self._sync_engine.start_sync(self._connected_device.udid)
        self._active_worker = worker
        self._update_device_panel()
        worker.progress.connect(self._on_progress)
        worker.file_progress.connect(self._progress.set_file_bytes)
        worker.log_message.connect(self._log.append_log)
        worker.error.connect(self._on_sync_error)
        worker.finished_sync.connect(self._on_sync_finished)

    def _cancel_sync(self) -> None:
        self._sync_engine.cancel_sync()
        self._log.append_log("Cancelling photo sync…")
        self._status_label.setText("Cancelling photo sync…")

    def _on_progress(self, filename: str, current: int, total: int) -> None:
        self._progress.set_overall(current, total, filename)
        pct = int((current / total) * 100) if total > 0 else 0
        self._set_unified_progress(pct, "blue")
        self._status_label.setText(f"Syncing: {filename} ({current}/{total})")
        self._photos_badge.setText(f"{pct}%")
        self._photos_badge.setStyleSheet(
            "background: rgba(10, 132, 255, 0.2); color: #64D2FF; "
            "border: 1px solid rgba(10, 132, 255, 0.35); border-radius: 8px; padding: 2px 7px; font-weight: 600; font-size: 11px;"
        )

    def _on_sync_error(self, message: str) -> None:
        self._log.append_log(f"Error: {message}")
        self._status_label.setText(f"Sync error: {message}")
        QMessageBox.warning(self, "Sync Error", message)

    def _on_sync_finished(self, result: SyncResult) -> None:
        self._active_worker = None
        self._last_sync = datetime.now()
        self._progress.reset()
        self._set_unified_progress(100, "blue")
        self._photos_badge.setText("Synced today")
        self._photos_badge.setStyleSheet(
            "background: rgba(48, 209, 88, 0.15); color: #30D158; "
            "border: 1px solid rgba(48, 209, 88, 0.3); border-radius: 8px; padding: 2px 7px; font-weight: 600; font-size: 11px;"
        )
        self._update_device_panel()

        summary = (
            f"Photo sync finished — {result.copied} copied, "
            f"{result.skipped} skipped, {result.failed} failed"
        )
        self._log.append_log(summary)
        self._status_label.setText(summary)
        self._last_sync_label.setText(f"Last sync: {self._last_sync.strftime('%H:%M')}")

        self._set_tray_state("connected", "Photos synced")
        self._notify(summary)

        if self._run_files_after_photos and self._connected_device:
            self._run_files_after_photos = False
            self._log.append_log("Starting Files app backup…")
            self._start_files_backup()
        elif self._run_whatsapp_after_chain and self._connected_device:
            self._run_whatsapp_after_chain = False
            self._log.append_log("Starting encrypted WhatsApp backup…")
            self._start_whatsapp_backup()

    def _start_files_backup_clicked(self) -> None:
        self._run_files_after_photos = False
        self._run_whatsapp_after_chain = False
        self._start_files_backup()

    def _start_files_backup(self) -> None:
        if self._busy():
            return
        if not self._connected_device:
            QMessageBox.information(self, "Files Backup", "No iPhone connected.")
            return

        Path(self._settings.files_backup_folder).mkdir(parents=True, exist_ok=True)
        self._files_backup_progress.setValue(0)
        self._set_unified_progress(0, "green")
        self._status_label.setText("Starting Files backup…")
        self._log.append_log("Starting Files app backup (Downloads, Books, Recordings…)…")

        worker = self._files_backup_engine.start_backup(self._connected_device.udid)
        self._files_backup_worker = worker
        self._update_device_panel()
        worker.progress.connect(self._on_files_backup_progress)
        worker.log_message.connect(self._log.append_log)
        worker.error.connect(lambda m: self._log.append_log(f"Files backup error: {m}"))
        worker.finished_files.connect(self._on_files_backup_finished)

    def _on_files_backup_progress(self, current: int, total: int, label: str) -> None:
        if total <= 0:
            self._files_backup_progress.setValue(0)
            self._set_unified_progress(0, "green")
            return
        pct = int((current / total) * 100)
        self._files_backup_progress.setValue(pct)
        self._set_unified_progress(pct, "green")
        self._status_label.setText(f"Files backup: {label} ({current}/{total})")
        self._files_count_badge.setText(f"{pct}%")

    def _on_files_backup_finished(self, result: FilesBackupResult) -> None:
        self._files_backup_worker = None
        self._files_backup_progress.setValue(100 if result.success else 0)
        self._set_unified_progress(100 if result.success else 0, "green")
        self._update_device_panel()
        self._refresh_files_backup_status()

        if result.success:
            msg = (
                f"Files backup finished — {result.media_files} files from "
                f"{result.folders_copied} Files app folders"
            )
            self._log.append_log(msg)
            self._status_label.setText(msg)
            self._notify(msg)
        else:
            err = result.error or "Files backup failed"
            self._log.append_log(err)
            self._status_label.setText(f"Files backup error: {err}")
            if err != "cancelled":
                QMessageBox.warning(self, "Files Backup", err)

        if self._run_whatsapp_after_chain and self._connected_device:
            self._run_whatsapp_after_chain = False
            self._log.append_log("Starting encrypted WhatsApp backup…")
            self._start_whatsapp_backup()

    def _delete_files_backup(self) -> None:
        if self._busy():
            QMessageBox.information(self, "Delete Files Backup", "Wait for the current job to finish.")
            return

        root = Path(self._settings.files_backup_folder)
        if not root.exists() or not any(root.iterdir()):
            QMessageBox.information(self, "Delete Files Backup", "No Files backups found.")
            return

        reply = QMessageBox.warning(
            self,
            "Delete Files Backup",
            f"Permanently delete all Files app backups under:\n\n{root}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        errors: list[str] = []
        for entry in list(root.iterdir()):
            try:
                if entry.is_dir():
                    shutil.rmtree(entry)
                else:
                    entry.unlink()
            except OSError as exc:
                errors.append(str(exc))

        self._refresh_files_backup_status()
        if errors:
            self._log.append_log("Files backup delete had errors: " + "; ".join(errors))
            QMessageBox.warning(self, "Delete Files Backup", "Some files could not be deleted.")
        else:
            self._log.append_log("Files backups deleted.")
            QMessageBox.information(self, "Delete Files Backup", "Files backups deleted.")

    def _start_whatsapp_backup_clicked(self) -> None:
        self._run_files_after_photos = False
        self._run_whatsapp_after_chain = False
        self._start_whatsapp_backup(full=False)

    def _start_whatsapp_backup(self, *, full: bool = False) -> None:
        if self._busy():
            return
        if not self._connected_device:
            QMessageBox.information(self, "WhatsApp Backup", "No iPhone connected.")
            return

        Path(self._settings.whatsapp_backup_folder).mkdir(parents=True, exist_ok=True)
        self._whatsapp_progress.setValue(0)
        self._set_unified_progress(0, "purple")
        self._status_label.setText("Starting WhatsApp backup…")
        self._set_tray_state("busy", "Backing up WhatsApp…")
        self._log.append_log("Starting WhatsApp backup (encrypted MobileBackup2)…")

        worker = self._whatsapp_engine.start_backup(
            self._connected_device.udid, full=full
        )
        self._whatsapp_worker = worker
        self._update_device_panel()
        worker.progress.connect(self._on_whatsapp_progress)
        worker.log_message.connect(self._log.append_log)
        worker.error.connect(self._on_whatsapp_error)
        worker.needs_encryption.connect(self._on_needs_encryption)
        worker.finished_backup.connect(self._on_whatsapp_finished)

    def _on_whatsapp_progress(self, pct: float) -> None:
        p = int(max(0, min(100, pct)))
        self._whatsapp_progress.setValue(p)
        self._set_unified_progress(p, "purple")
        self._status_label.setText(f"WhatsApp backup: {p}%")
        self._set_tray_state("busy", f"Backing up WhatsApp… {p}%")

    def _on_whatsapp_error(self, message: str) -> None:
        self._log.append_log(f"WhatsApp backup error: {message}")
        self._status_label.setText(f"WhatsApp backup error: {message}")

    def _on_needs_encryption(self) -> None:
        self._pending_encryption_then_backup = True

    def _on_whatsapp_finished(self, result: WhatsAppBackupResult) -> None:
        self._whatsapp_worker = None
        self._set_unified_progress(100 if result.success else 0, "purple")
        self._update_device_panel()
        self._refresh_whatsapp_status()

        if result.error == "encryption_required" or self._pending_encryption_then_backup:
            self._pending_encryption_then_backup = False
            self._prompt_enable_encryption_then_backup()
            return

        if result.success:
            msg = "WhatsApp backup finished."
            if result.info:
                msg += f" {result.info.whatsapp_status_label}."
            self._status_label.setText(msg)
            self._set_tray_state("connected", "WhatsApp backed up")
            self._notify(msg, seconds=5)
            if result.info and not result.info.whatsapp_ok and result.info.whatsapp_in_manifest is False:
                QMessageBox.warning(
                    self,
                    "WhatsApp",
                    "Backup finished but WhatsApp data was not found in the payload.\n"
                    "Confirm WhatsApp is installed and encryption is on, then "
                    "Backup WhatsApp again.",
                )
        else:
            err = result.error or "WhatsApp backup failed"
            self._log.append_log(err)
            self._status_label.setText(f"WhatsApp backup error: {err}")
            self._set_tray_state("attention", "WhatsApp backup failed")
            if err != "encryption_required":
                QMessageBox.warning(self, "WhatsApp Backup", err)

    def _prompt_enable_encryption_then_backup(self) -> None:
        dialog = EncryptionPasswordDialog(self)
        if dialog.exec() != EncryptionPasswordDialog.DialogCode.Accepted:
            self._log.append_log(
                "Encrypted backup skipped — WhatsApp will not restore safely without encryption."
            )
            QMessageBox.warning(
                self,
                "Encryption Required",
                "Without encrypted backups, WhatsApp chats are incomplete.\n"
                "Press Backup WhatsApp again when you are ready to set a password.",
            )
            return

        if not self._connected_device:
            return

        password = dialog.password()
        self._log.append_log("Enabling backup encryption on iPhone…")
        worker = self._whatsapp_engine.start_enable_encryption(
            self._connected_device.udid, password
        )
        self._whatsapp_worker = worker
        self._update_device_panel()
        worker.log_message.connect(self._log.append_log)
        worker.error.connect(self._on_whatsapp_error)
        worker.finished_backup.connect(self._on_encryption_enabled)

    def _on_encryption_enabled(self, result: WhatsAppBackupResult) -> None:
        self._whatsapp_worker = None
        self._update_device_panel()
        if not result.success:
            QMessageBox.warning(
                self,
                "Encryption",
                result.error or "Could not enable backup encryption.",
            )
            return
        self._log.append_log("Encryption enabled — starting WhatsApp backup…")
        self._start_whatsapp_backup(full=True)

    def _start_restore(self) -> None:
        if self._busy():
            return
        if not self._connected_device:
            QMessageBox.information(self, "Restore", "Connect the iPhone you want to restore onto.")
            return

        dialog = RestoreBackupDialog(Path(self._settings.whatsapp_backup_folder), self)
        if dialog.exec() != RestoreBackupDialog.DialogCode.Accepted:
            return
        backup = dialog.selected_backup()
        if not backup:
            return

        self._whatsapp_progress.setValue(0)
        self._log.append_log(f"Starting restore from {backup.udid[:12]}…")
        worker = self._whatsapp_engine.start_restore(
            self._connected_device.udid,
            source_udid=backup.udid,
            password=dialog.password(),
        )
        self._whatsapp_worker = worker
        self._update_device_panel()
        worker.progress.connect(self._on_whatsapp_progress)
        worker.log_message.connect(self._log.append_log)
        worker.error.connect(self._on_whatsapp_error)
        worker.finished_restore.connect(self._on_restore_finished)

    def _on_restore_finished(self, result: WhatsAppBackupResult) -> None:
        self._whatsapp_worker = None
        self._update_device_panel()
        if result.success:
            QMessageBox.information(
                self,
                "Restore",
                "Restore finished. The iPhone should reboot.\n\n"
                "After setup completes, open WhatsApp and verify your phone number if asked.",
            )
        else:
            QMessageBox.warning(
                self,
                "Restore",
                result.error or "Restore failed. See the log for details.",
            )

    def _open_settings(self) -> None:
        if SettingsDialog(self._settings, self).exec():
            self._apply_theme()
            self._refresh_whatsapp_status()
            self._refresh_files_backup_status()
            set_menu_bar_only(self._settings.menu_bar_only)

    def _apply_theme(self) -> None:
        stylesheet = get_theme_stylesheet(self._settings.theme)
        self.setStyleSheet(stylesheet)
        app = QApplication.instance()
        if app:
            app.setStyleSheet(stylesheet)
        if hasattr(self, "_popover"):
            self._popover.apply_theme()

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if hasattr(self, "_popover") and self._popover.isVisible():
                self._popover.hide()
            elif hasattr(self, "_popover"):
                self._sync_popover_data()
                self._popover.show_at_tray(self._tray.geometry())
            else:
                self._show_window()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def _sync_popover_data(self) -> None:
        if not hasattr(self, "_popover"):
            return
        device_name = self._connected_device.name if self._connected_device else None
        connected = self._connected_device is not None
        self._popover.update_device(device_name, connected=connected)

        if self._sync_engine.is_running:
            self._popover.update_sync_progress(
                "Syncing photos…", percent=self._unified_progress.value(), is_active=True
            )
        elif self._files_backup_engine.is_running:
            self._popover.update_sync_progress(
                "Backing up Files…", percent=self._unified_progress.value(), is_active=True
            )
        elif self._whatsapp_engine.is_running:
            self._popover.update_sync_progress(
                "Backing up WhatsApp…", percent=self._unified_progress.value(), is_active=True
            )
        elif connected:
            self._popover.update_sync_progress(
                "Connected • Ready to sync", percent=0, is_active=False
            )
        else:
            self._popover.update_sync_progress(
                "Waiting for iPhone connection…", percent=0, is_active=False
            )

    def closeEvent(self, event: QCloseEvent) -> None:
        """Closing the window never quits: the agent stays in the menu bar."""
        if self._settings.run_in_background:
            self._tray.show()
            event.ignore()
            self.hide()
            if self._settings.menu_bar_only:
                set_menu_bar_only(True)
            self._notify(
                "Still running in the menu bar. Plug in your iPhone to back it up.",
                seconds=3,
            )
            return
        self._device_watcher.stop()
        event.accept()

    def _quit_app(self) -> None:
        self._device_watcher.stop()
        if self._sync_engine.is_running:
            self._sync_engine.cancel_sync()
        if self._files_backup_engine.is_running:
            self._files_backup_engine.cancel()
        if self._whatsapp_engine.is_running:
            self._whatsapp_engine.cancel()
        self._tray.hide()
        QApplication.quit()
