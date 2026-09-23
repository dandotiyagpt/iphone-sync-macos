"""Photo/video gallery styled like Apple Photos with device selection and smooth performance."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from iphone_sync.ui.gallery.device_discovery import DeviceSource, discover_device_sources
from iphone_sync.ui.gallery.media_scanner import (
    MediaItem,
    MediaKind,
    build_year_month_navigation,
    group_by_month_year,
    scan_media_folder,
)
from iphone_sync.ui.gallery.preview_pane import PreviewPane
from iphone_sync.ui.gallery.thumbnail_loader import ThumbnailLoader
from iphone_sync.ui.gallery.thumbnails import THUMB_SIZE, video_placeholder_icon
from iphone_sync.ui.gallery.viewer_dialog import MediaViewerDialog

DEFAULT_THUMB_SIZE = 180


class _GalleryTile(QWidget):
    clicked_item = Signal(int)
    double_clicked_item = Signal(int)

    def __init__(self, index: int, item: MediaItem, size: int = DEFAULT_THUMB_SIZE, parent=None) -> None:
        super().__init__(parent)
        self._index = index
        self._item = item
        self._size = size
        self._selected = False
        self._pixmap: QPixmap | None = None

        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._image = QLabel()
        self._image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image.setStyleSheet("background: #252528; border-radius: 6px; color: #636366;")
        self._image.setText("…")
        layout.addWidget(self._image)

        self._badge = QLabel(self)
        self._badge.hide()

    def _apply_style(self) -> None:
        if self._selected:
            self.setStyleSheet(
                "background: #2c2c2e; border: 3px solid #0a84ff; border-radius: 8px;"
            )
        else:
            self.setStyleSheet(
                "_GalleryTile { background: #252528; border: 1px solid rgba(255,255,255,0.06); border-radius: 6px; }"
                "_GalleryTile:hover { border: 1px solid rgba(255,255,255,0.25); }"
            )

    def set_size(self, size: int) -> None:
        if self._size == size:
            return
        self._size = size
        self.setFixedSize(size, size)
        if self._pixmap and not self._pixmap.isNull():
            self._image.setPixmap(
                self._pixmap.scaled(
                    size,
                    size,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        self._update_badge_position()

    def set_selected(self, selected: bool) -> None:
        if self._selected == selected:
            return
        self._selected = selected
        self._apply_style()

    def set_thumbnail(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        self._image.setText("")
        if pixmap.isNull():
            if self._item.is_video:
                icon = video_placeholder_icon().pixmap(self._size // 3, self._size // 3)
                self._image.setPixmap(icon)
            else:
                self._image.setText("?")
            return

        self._image.setPixmap(
            pixmap.scaled(
                self._size,
                self._size,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self._show_badge()

    def _update_badge_position(self) -> None:
        if self._badge.isVisible():
            self._badge.adjustSize()
            self._badge.move(6, self._size - self._badge.height() - 6)

    def _show_badge(self) -> None:
        if self._item.is_live_photo:
            text = "✨ LIVE"
        elif self._item.is_video:
            text = "▶ VIDEO"
        else:
            return
        self._badge.setText(text)
        self._badge.setStyleSheet(
            "background: rgba(0,0,0,0.7); color: #ffffff; padding: 2px 6px; "
            "border-radius: 4px; font-size: 10px; font-weight: 700; border: none;"
        )
        self._badge.adjustSize()
        self._update_badge_position()
        self._badge.show()
        self._badge.raise_()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked_item.emit(self._index)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked_item.emit(self._index)
        super().mouseDoubleClickEvent(event)


class GalleryWidget(QWidget):
    source_changed = Signal(str)
    device_changed = Signal(object)

    def __init__(
        self,
        destination: Path,
        backup_root: Path | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._destination = destination
        self._backup_root = backup_root
        self._device_sources: list[DeviceSource] = []
        self._current_source: DeviceSource | None = None

        self._all_items: list[MediaItem] = []
        self._items: list[MediaItem] = []
        self._filter_kind: str = "all"  # "all" | "photo" | "live" | "video"
        self._search_query: str = ""

        self._thumb_size = DEFAULT_THUMB_SIZE
        self._selected_index = -1
        self._columns = 0

        self._tiles: dict[int, _GalleryTile] = {}
        self._section_headers: dict[str, QLabel] = {}
        self._section_grids: list[tuple[QLabel, QWidget, QGridLayout, list[int]]] = []

        self._loader = ThumbnailLoader(self)
        self._loader.thumbnail_ready.connect(self._on_thumbnail_ready)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(100)
        self._search_timer.timeout.connect(self._apply_filter)

        self.setStyleSheet("background: #1c1c1e; color: #f2f2f7;")
        self._build_ui()
        self._load_devices()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # 1. Top Modern macOS Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        # iPhone Device Selector
        dev_label = QLabel("Source:")
        dev_label.setStyleSheet("color: #8e8e93; font-size: 12px; font-weight: 500;")
        self._device_combo = QComboBox()
        self._device_combo.setMinimumWidth(220)
        self._device_combo.setStyleSheet(
            "QComboBox { background: #2c2c2e; color: #ffffff; border: 1px solid #3a3a3c; "
            "border-radius: 6px; padding: 4px 10px; font-size: 12px; font-weight: 500; } "
            "QComboBox::drop-down { border: none; width: 20px; } "
            "QComboBox QAbstractItemView { background: #2c2c2e; color: #ffffff; "
            "selection-background-color: #0a84ff; selection-color: #ffffff; border-radius: 6px; }"
        )
        self._device_combo.currentIndexChanged.connect(self._on_device_selection_changed)

        toolbar.addWidget(dev_label)
        toolbar.addWidget(self._device_combo)

        # Filter Pills (All / Photos / Live / Videos)
        pill_box = QHBoxLayout()
        pill_box.setSpacing(4)
        self._pills: dict[str, QPushButton] = {}
        filters = [
            ("all", "All"),
            ("photo", "Photos"),
            ("live", "✨ Live"),
            ("video", "🎥 Videos"),
        ]
        for key, name in filters:
            btn = QPushButton(name)
            btn.setFixedHeight(26)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._set_filter_kind(k))
            self._pills[key] = btn
            pill_box.addWidget(btn)
        self._update_pill_styles()
        toolbar.addLayout(pill_box)

        toolbar.addStretch(1)

        # Search box
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("🔍 Filter date, name…")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setFixedWidth(180)
        self._search_input.setStyleSheet(
            "QLineEdit { background: #2c2c2e; color: #ffffff; border: 1px solid #3a3a3c; "
            "border-radius: 6px; padding: 4px 8px; font-size: 12px; } "
            "QLineEdit:focus { border: 1px solid #0a84ff; }"
        )
        self._search_input.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self._search_input)

        # Thumbnail zoom slider
        zoom_label = QLabel("Size:")
        zoom_label.setStyleSheet("color: #8e8e93; font-size: 11px;")
        self._zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self._zoom_slider.setRange(120, 260)
        self._zoom_slider.setValue(DEFAULT_THUMB_SIZE)
        self._zoom_slider.setFixedWidth(80)
        self._zoom_slider.setToolTip("Adjust thumbnail size")
        self._zoom_slider.valueChanged.connect(self._on_zoom_changed)
        toolbar.addWidget(zoom_label)
        toolbar.addWidget(self._zoom_slider)

        # Refresh button
        self._refresh_btn = QPushButton("⟳")
        self._refresh_btn.setFixedSize(28, 28)
        self._refresh_btn.setToolTip("Refresh Library")
        self._refresh_btn.setStyleSheet(
            "QPushButton { background: #2c2c2e; color: #f2f2f7; border: 1px solid #3a3a3c; "
            "border-radius: 6px; font-size: 14px; font-weight: bold; } "
            "QPushButton:hover { background: #3a3a3c; }"
        )
        self._refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(self._refresh_btn)

        layout.addLayout(toolbar)

        # 2. Main split view: nav sidebar | grid scroll | preview inspector
        body = QSplitter(Qt.Orientation.Horizontal)

        # Navigation sidebar
        self._nav = QListWidget()
        self._nav.setFixedWidth(175)
        self._nav.setStyleSheet(
            "QListWidget { background: #242426; border: 1px solid rgba(255,255,255,0.06); "
            "border-radius: 8px; padding: 6px; color: #f2f2f7; font-size: 12px; } "
            "QListWidget::item { padding: 5px 8px; border-radius: 6px; margin: 1px 0; } "
            "QListWidget::item:selected { background: #0a84ff; color: #ffffff; font-weight: 600; } "
            "QListWidget::item:hover:!selected { background: #323235; }"
        )
        self._nav.itemClicked.connect(self._on_nav_clicked)
        body.addWidget(self._nav)

        # Grid scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            "QScrollArea { border: 1px solid rgba(255,255,255,0.06); background: #1c1c1e; border-radius: 8px; }"
        )

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._content_layout.setContentsMargins(14, 10, 14, 14)
        self._content_layout.setSpacing(16)
        self._scroll.setWidget(self._content)
        body.addWidget(self._scroll)

        # Preview inspector pane
        self._preview = PreviewPane()
        self._preview.playback_started.connect(self._loader.pause)
        self._preview.playback_stopped.connect(self._loader.resume)
        body.addWidget(self._preview)

        body.setStretchFactor(0, 0)
        body.setStretchFactor(1, 3)
        body.setStretchFactor(2, 2)
        body.setSizes([175, 620, 360])
        layout.addWidget(body, stretch=1)

        # Bottom status count label
        self._status_bar = QLabel("")
        self._status_bar.setStyleSheet("color: #8e8e93; font-size: 11px; padding: 2px 4px;")
        layout.addWidget(self._status_bar)

        # Empty state message
        self._empty_label = QLabel(
            "No media found in selected iPhone backup.\nConnect your iPhone to sync photos.",
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        self._empty_label.setStyleSheet("color: #8e8e93; font-size: 14px; padding: 60px;")
        layout.addWidget(self._empty_label)
        self._empty_label.hide()

    def _load_devices(self) -> None:
        self._device_combo.blockSignals(True)
        self._device_combo.clear()

        # Discover devices under destination parent or destination
        root = self._destination.parent if self._destination.is_dir() else self._destination
        self._device_sources = discover_device_sources(
            self._destination if self._destination.is_dir() else root,
            self._backup_root,
        )

        selected_index = 0
        for i, src in enumerate(self._device_sources):
            self._device_combo.addItem(src.display_label, src.id)
            if src.path == self._destination or (src.is_all and self._destination == src.path):
                selected_index = i

        self._device_combo.insertSeparator(self._device_combo.count())
        self._device_combo.addItem("📁 Choose Folder…", "custom")

        self._device_combo.setCurrentIndex(selected_index)
        self._device_combo.blockSignals(False)

        if self._device_sources:
            self._current_source = self._device_sources[selected_index]

    def _on_device_selection_changed(self, index: int) -> None:
        data = self._device_combo.currentData()
        if data == "custom":
            folder = QFileDialog.getExistingDirectory(
                self,
                "Select iPhone Backup or Photos Folder",
                str(self._destination),
            )
            if folder:
                self.set_destination(Path(folder))
            else:
                # Revert selection
                self._load_devices()
            return

        for src in self._device_sources:
            if src.id == data:
                self._current_source = src
                self._destination = src.path
                self.source_changed.emit(str(src.path))
                self.device_changed.emit(src)
                self.refresh()
                break

    def set_destination(self, destination: Path) -> None:
        self._destination = destination
        self._load_devices()
        self.refresh()

    def _set_filter_kind(self, kind: str) -> None:
        if self._filter_kind == kind:
            return
        self._filter_kind = kind
        self._update_pill_styles()
        self._apply_filter()

    def _update_pill_styles(self) -> None:
        for key, btn in self._pills.items():
            if key == self._filter_kind:
                btn.setStyleSheet(
                    "background: #0a84ff; color: #ffffff; font-weight: 600; "
                    "border: none; border-radius: 6px; padding: 4px 10px; font-size: 11px;"
                )
            else:
                btn.setStyleSheet(
                    "background: #2c2c2e; color: #aeaeb2; font-weight: 500; "
                    "border: 1px solid #3a3a3c; border-radius: 6px; padding: 4px 10px; font-size: 11px;"
                )

    def _on_search_changed(self, text: str) -> None:
        self._search_query = text
        self._search_timer.start()

    def _on_zoom_changed(self, value: int) -> None:
        self._thumb_size = value
        for tile in self._tiles.values():
            tile.set_size(value)
        self._columns = 0  # force re-layout
        self._relayout_grid()

    def refresh(self) -> None:
        self._preview.stop()
        self._loader.clear()
        self._all_items = scan_media_folder(self._destination)
        self.source_changed.emit(str(self._destination))

        photos = sum(1 for i in self._all_items if i.kind == MediaKind.PHOTO)
        live = sum(1 for i in self._all_items if i.kind == MediaKind.LIVE_PHOTO)
        videos = sum(1 for i in self._all_items if i.kind == MediaKind.VIDEO)

        # Update pill labels with real counts
        self._pills["all"].setText(f"All ({len(self._all_items)})")
        self._pills["photo"].setText(f"Photos ({photos})")
        self._pills["live"].setText(f"✨ Live ({live})")
        self._pills["video"].setText(f"🎥 Videos ({videos})")

        self._apply_filter()

    def _apply_filter(self) -> None:
        q = self._search_query.strip().lower()
        res = []
        for item in self._all_items:
            # Filter kind
            if self._filter_kind == "photo" and item.kind != MediaKind.PHOTO:
                continue
            elif self._filter_kind == "live" and not item.is_live_photo:
                continue
            elif self._filter_kind == "video" and item.kind != MediaKind.VIDEO:
                continue

            # Filter search query
            if q:
                date_str = item.taken_at.strftime("%Y %B %b %d %m").lower()
                if q not in item.filename.lower() and q not in date_str:
                    continue
            res.append(item)

        self._items = res
        self._selected_index = -1
        self._preview.show_item(None)

        # Update status
        self._status_bar.setText(
            f"Showing {len(self._items):,} of {len(self._all_items):,} items · Path: {self._destination.name}"
        )

        self._rebuild_nav()
        self._rebuild_grid()

    def _rebuild_nav(self) -> None:
        self._nav.clear()

        # Section 1: Library quick filters
        header_lib = QListWidgetItem("LIBRARY")
        header_lib.setFlags(Qt.ItemFlag.NoItemFlags)
        f_bold = header_lib.font()
        f_bold.setBold(True)
        f_bold.setPointSize(10)
        header_lib.setFont(f_bold)
        header_lib.setForeground(QColor("#8e8e93"))
        self._nav.addItem(header_lib)

        all_item = QListWidgetItem("  📱 All Media")
        all_item.setData(Qt.ItemDataRole.UserRole, "__all__")
        self._nav.addItem(all_item)

        photos_item = QListWidgetItem("  📷 Photos")
        photos_item.setData(Qt.ItemDataRole.UserRole, "__photos__")
        self._nav.addItem(photos_item)

        live_item = QListWidgetItem("  ✨ Live Photos")
        live_item.setData(Qt.ItemDataRole.UserRole, "__live__")
        self._nav.addItem(live_item)

        video_item = QListWidgetItem("  🎥 Videos")
        video_item.setData(Qt.ItemDataRole.UserRole, "__videos__")
        self._nav.addItem(video_item)

        # Section 2: Timeline
        if self._items:
            nav_groups = build_year_month_navigation(self._items)
            if nav_groups:
                header_time = QListWidgetItem("\nTIMELINE")
                header_time.setFlags(Qt.ItemFlag.NoItemFlags)
                header_time.setFont(f_bold)
                header_time.setForeground(QColor("#8e8e93"))
                self._nav.addItem(header_time)

                for key, label, level in nav_groups:
                    prefix = "  " if level == 0 else "    "
                    item = QListWidgetItem(f"{prefix}{label}")
                    item.setData(Qt.ItemDataRole.UserRole, key)
                    if level == 0:
                        f = item.font()
                        f.setBold(True)
                        item.setFont(f)
                    self._nav.addItem(item)

    def _on_nav_clicked(self, item: QListWidgetItem) -> None:
        key = item.data(Qt.ItemDataRole.UserRole)
        if not key:
            return
        if key == "__all__":
            self._set_filter_kind("all")
        elif key == "__photos__":
            self._set_filter_kind("photo")
        elif key == "__live__":
            self._set_filter_kind("live")
        elif key == "__videos__":
            self._set_filter_kind("video")
        else:
            self._scroll_to_section(key)

    def _scroll_to_section(self, key: str) -> None:
        header = self._section_headers.get(key)
        if header is None and len(key) == 4:
            for section_key, widget in self._section_headers.items():
                if section_key.startswith(key):
                    header = widget
                    break
        if header is not None:
            self._scroll.ensureWidgetVisible(header, 0)

    def _clear_content(self) -> None:
        self._tiles.clear()
        self._section_headers.clear()
        self._section_grids.clear()
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                w = item.widget()
                w.setParent(None)
                w.deleteLater()

    def _calculate_columns(self) -> int:
        viewport_w = self._scroll.viewport().width()
        available_w = max(100, viewport_w - 28)
        return max(2, available_w // (self._thumb_size + 8))

    def _rebuild_grid(self) -> None:
        self._clear_content()

        if not self._items:
            self._preview.hide()
            self._scroll.hide()
            self._nav.hide()
            self._empty_label.show()
            return

        self._preview.show()
        self._scroll.show()
        self._nav.show()
        self._empty_label.hide()

        columns = self._calculate_columns()
        self._columns = columns

        index_lookup = {id(item): idx for idx, item in enumerate(self._items)}

        for section_key, section_label, section_items in group_by_month_year(self._items):
            header = QLabel(section_label)
            header.setStyleSheet(
                "font-size: 15px; font-weight: 600; color: #ffffff; padding: 10px 0 2px 2px;"
            )
            self._section_headers[section_key] = header
            self._content_layout.addWidget(header)

            grid_host = QWidget()
            grid = QGridLayout(grid_host)
            grid.setSpacing(6)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

            indices_in_section: list[int] = []
            for pos, media in enumerate(section_items):
                idx = index_lookup[id(media)]
                indices_in_section.append(idx)
                tile = _GalleryTile(idx, media, size=self._thumb_size)
                tile.clicked_item.connect(self._select_item)
                tile.double_clicked_item.connect(self._open_viewer)
                self._tiles[idx] = tile
                self._loader.load(idx, media)
                grid.addWidget(tile, pos // columns, pos % columns)

            self._section_grids.append((header, grid_host, grid, indices_in_section))
            self._content_layout.addWidget(grid_host)

        self._content_layout.addStretch(1)

        # Select first item if available
        if self._items:
            self._select_item(0)

    def _relayout_grid(self) -> None:
        """Fast rearrange of existing widgets when columns change, without destroying widgets."""
        columns = self._calculate_columns()
        if columns == self._columns:
            return
        self._columns = columns

        for header, host, grid, indices in self._section_grids:
            for pos, idx in enumerate(indices):
                tile = self._tiles.get(idx)
                if tile:
                    grid.addWidget(tile, pos // columns, pos % columns)

    def _select_item(self, index: int) -> None:
        if not (0 <= index < len(self._items)):
            return

        # Deselect old
        if self._selected_index in self._tiles:
            self._tiles[self._selected_index].set_selected(False)

        self._selected_index = index
        tile = self._tiles.get(index)
        if tile:
            tile.set_selected(True)
            self._scroll.ensureWidgetVisible(tile)

        self._preview.show_item(self._items[index])

    def _on_thumbnail_ready(self, index: int, pixmap: QPixmap) -> None:
        tile = self._tiles.get(index)
        if tile:
            tile.set_thumbnail(pixmap)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self._items:
            return
        # Dynamically reposition existing tiles only when column count changes
        self._relayout_grid()

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if not self._items:
            super().keyPressEvent(event)
            return

        if key == Qt.Key.Key_Left:
            self._select_item(max(0, self._selected_index - 1))
        elif key == Qt.Key.Key_Right:
            self._select_item(min(len(self._items) - 1, self._selected_index + 1))
        elif key == Qt.Key.Key_Up:
            cols = max(1, self._columns)
            self._select_item(max(0, self._selected_index - cols))
        elif key == Qt.Key.Key_Down:
            cols = max(1, self._columns)
            self._select_item(min(len(self._items) - 1, self._selected_index + cols))
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            if 0 <= self._selected_index < len(self._items):
                self._open_viewer(self._selected_index)
        elif key == Qt.Key.Key_Escape:
            self._preview.stop()
        else:
            super().keyPressEvent(event)

    def _open_viewer(self, index: int) -> None:
        self._loader.pause()
        dialog = MediaViewerDialog(self._items, index, self)
        dialog.exec()
        self._loader.resume()

    def stop_preview(self) -> None:
        self._preview.stop()
