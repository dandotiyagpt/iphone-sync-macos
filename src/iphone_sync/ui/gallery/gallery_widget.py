"""Photo/video gallery styled like Apple Photos."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

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


class _GalleryTile(QWidget):
    clicked_item = Signal(int)
    double_clicked_item = Signal(int)

    def __init__(self, index: int, item: MediaItem, parent=None) -> None:
        super().__init__(parent)
        self._index = index
        self._item = item
        self.setFixedSize(THUMB_SIZE, THUMB_SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("background: #2c2c2e; border-radius: 4px;")

        self._image = QLabel(self)
        self._image.setGeometry(0, 0, THUMB_SIZE, THUMB_SIZE)
        self._image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image.setStyleSheet("color: #636366; background: #2c2c2e;")
        self._image.setText("…")

        self._badge = QLabel(self)
        self._badge.hide()

    def set_thumbnail(self, pixmap: QPixmap) -> None:
        self._image.setText("")
        if pixmap.isNull():
            if self._item.is_video:
                icon = video_placeholder_icon().pixmap(THUMB_SIZE // 3, THUMB_SIZE // 3)
                self._image.setPixmap(icon)
            else:
                self._image.setText("?")
            return
        self._image.setPixmap(
            pixmap.scaled(
                THUMB_SIZE,
                THUMB_SIZE,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self._show_badge()

    def _show_badge(self) -> None:
        if self._item.is_live_photo:
            text = "LIVE"
        elif self._item.is_video:
            text = "▶"
        else:
            return
        self._badge.setText(text)
        self._badge.setStyleSheet(
            "background: rgba(0,0,0,0.6); color: white; padding: 2px 6px; "
            "border-radius: 4px; font-size: 10px; font-weight: 600;"
        )
        self._badge.adjustSize()
        self._badge.move(6, THUMB_SIZE - self._badge.height() - 6)
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

    def __init__(self, destination: Path, parent=None) -> None:
        super().__init__(parent)
        self._destination = destination
        self._items: list[MediaItem] = []
        self._tiles: dict[int, _GalleryTile] = {}
        self._section_headers: dict[str, QLabel] = {}
        self._columns = 0
        self._loader = ThumbnailLoader(self)
        self._loader.thumbnail_ready.connect(self._on_thumbnail_ready)
        self.setStyleSheet("background: #1c1c1e; color: #f2f2f7;")
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("Library")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        self._count_label = QLabel()
        self._count_label.setStyleSheet("color: #aeaeb2; font-size: 12px;")
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setFixedHeight(28)
        self._refresh_btn.setStyleSheet(
            "background: #2c2c2e; color: #f2f2f7; border: none; "
            "padding: 4px 12px; border-radius: 6px;"
        )
        self._refresh_btn.clicked.connect(self.refresh)
        header.addWidget(title)
        header.addWidget(self._count_label)
        header.addStretch()
        header.addWidget(self._refresh_btn)
        layout.addLayout(header)

        # Side-by-side: nav | grid | preview
        body = QSplitter(Qt.Orientation.Horizontal)

        self._nav = QListWidget()
        self._nav.setFixedWidth(170)
        self._nav.setStyleSheet(
            "QListWidget { background: #2c2c2e; border: none; border-radius: 8px; "
            "padding: 4px; color: #f2f2f7; font-size: 12px; }"
            "QListWidget::item { padding: 6px 8px; border-radius: 6px; }"
            "QListWidget::item:selected { background: #0a84ff; }"
            "QListWidget::item:hover { background: #3a3a3c; }"
        )
        self._nav.itemClicked.connect(self._on_nav_clicked)
        body.addWidget(self._nav)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: #1c1c1e; }")

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._content_layout.setSpacing(12)
        self._scroll.setWidget(self._content)
        body.addWidget(self._scroll)

        self._preview = PreviewPane()
        self._preview.playback_started.connect(self._loader.pause)
        self._preview.playback_stopped.connect(self._loader.resume)
        body.addWidget(self._preview)

        body.setStretchFactor(0, 0)
        body.setStretchFactor(1, 3)
        body.setStretchFactor(2, 2)
        body.setSizes([170, 600, 380])
        layout.addWidget(body, stretch=1)

        self._empty_label = QLabel(
            "No photos yet — sync your iPhone first, then open run-gallery.bat.",
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        self._empty_label.setStyleSheet("color: #636366; padding: 40px;")
        layout.addWidget(self._empty_label)
        self._empty_label.hide()

    def set_destination(self, destination: Path) -> None:
        self._destination = destination
        self.refresh()

    def refresh(self) -> None:
        self._preview.stop()
        self._loader.clear()
        self._items = scan_media_folder(self._destination)
        self.source_changed.emit(str(self._destination))

        photos = sum(1 for i in self._items if i.kind == MediaKind.PHOTO)
        live = sum(1 for i in self._items if i.kind == MediaKind.LIVE_PHOTO)
        videos = sum(1 for i in self._items if i.kind == MediaKind.VIDEO)
        self._count_label.setText(
            f"{len(self._items)} items · {photos} photos · {live} live · {videos} videos"
        )
        self._rebuild_nav()
        self._rebuild_grid()

    def _rebuild_nav(self) -> None:
        self._nav.clear()
        for key, label, level in build_year_month_navigation(self._items):
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, key)
            if level == 0:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self._nav.addItem(item)

    def _on_nav_clicked(self, item: QListWidgetItem) -> None:
        self._scroll_to_section(item.data(Qt.ItemDataRole.UserRole))

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
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

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

        index_lookup = {id(item): idx for idx, item in enumerate(self._items)}
        columns = max(2, max(1, self._scroll.width() - 16) // (THUMB_SIZE + 4))
        self._columns = columns

        for section_key, section_label, section_items in group_by_month_year(self._items):
            header = QLabel(section_label)
            header.setStyleSheet(
                "font-size: 16px; font-weight: 600; color: #f2f2f7; padding: 8px 0 4px 0;"
            )
            self._section_headers[section_key] = header
            self._content_layout.addWidget(header)

            grid_host = QWidget()
            grid = QGridLayout(grid_host)
            grid.setSpacing(3)
            grid.setContentsMargins(0, 0, 0, 0)

            for pos, media in enumerate(section_items):
                idx = index_lookup[id(media)]
                tile = _GalleryTile(idx, media)
                tile.clicked_item.connect(self._on_tile_clicked)
                tile.double_clicked_item.connect(self._open_viewer)
                self._tiles[idx] = tile
                self._loader.load(idx, media)
                grid.addWidget(tile, pos // columns, pos % columns)

            self._content_layout.addWidget(grid_host)

        self._content_layout.addStretch()

    def _on_tile_clicked(self, index: int) -> None:
        if 0 <= index < len(self._items):
            self._preview.show_item(self._items[index])

    def _on_thumbnail_ready(self, index: int, pixmap: QPixmap) -> None:
        tile = self._tiles.get(index)
        if tile:
            tile.set_thumbnail(pixmap)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self._items:
            return
        columns = max(2, max(1, self._scroll.width() - 16) // (THUMB_SIZE + 4))
        if columns != self._columns:
            self._columns = columns
            self._rebuild_grid()

    def _open_viewer(self, index: int) -> None:
        self._loader.pause()
        dialog = MediaViewerDialog(self._items, index, self)
        dialog.exec()
        self._loader.resume()

    def stop_preview(self) -> None:
        self._preview.stop()
