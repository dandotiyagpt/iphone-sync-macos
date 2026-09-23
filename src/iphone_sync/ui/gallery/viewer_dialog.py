"""Full-screen media viewer with timeline scrubber and Live Photo playback."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from iphone_sync.ui.gallery.image_loader import load_image_pixmap
from iphone_sync.ui.gallery.media_scanner import MediaItem, MediaKind


def _format_ms(ms: int) -> str:
    if ms < 0:
        ms = 0
    seconds = ms // 1000
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes}:{seconds:02d}"


class MediaViewerDialog(QDialog):
    def __init__(self, items: list[MediaItem], start_index: int = 0, parent=None) -> None:
        super().__init__(parent)
        self._items = items
        self._index = start_index
        self._seeking = False
        self._current_pixmap: QPixmap | None = None
        self._live_timer = QTimer(self)
        self._live_timer.setSingleShot(True)
        self._live_timer.timeout.connect(self._play_live_photo)

        self.setWindowTitle("Photos")
        self.setMinimumSize(960, 700)
        self.setStyleSheet(
            "QDialog { background: #1c1c1e; color: #f2f2f7; }"
            "QLabel { color: #f2f2f7; }"
            "QPushButton { background: #2c2c2e; color: #f2f2f7; border: none; "
            "padding: 8px 16px; border-radius: 8px; }"
            "QPushButton:hover { background: #3a3a3c; }"
            "QPushButton:disabled { color: #636366; background: #1c1c1e; }"
            "QSlider::groove:horizontal { height: 4px; background: #48484a; border-radius: 2px; }"
            "QSlider::handle:horizontal { width: 14px; height: 14px; margin: -5px 0; "
            "background: #ffffff; border-radius: 7px; }"
            "QSlider::sub-page:horizontal { background: #0a84ff; border-radius: 2px; }"
        )
        self._build_ui()
        self._wire_player()
        self._show_current()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: #000; border-radius: 8px;")

        # Photo / Live Photo still frame
        self._photo_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._photo_label.setStyleSheet("background: #000;")
        self._photo_label.setMinimumHeight(420)
        self._photo_label.mousePressEvent = self._photo_mouse_press  # type: ignore[method-assign]
        self._photo_label.mouseReleaseEvent = self._photo_mouse_release  # type: ignore[method-assign]

        # Video + Live Photo motion
        video_container = QWidget()
        video_layout = QVBoxLayout(video_container)
        video_layout.setContentsMargins(0, 0, 0, 0)
        self._video_widget = QVideoWidget()
        self._video_widget.setStyleSheet("background: #000;")
        video_layout.addWidget(self._video_widget)

        self._stack.addWidget(self._photo_label)
        self._stack.addWidget(video_container)
        layout.addWidget(self._stack, stretch=1)

        # Timeline (videos and live photo playback)
        timeline_row = QHBoxLayout()
        self._time_current = QLabel("0:00")
        self._time_current.setFixedWidth(44)
        self._timeline = QSlider(Qt.Orientation.Horizontal)
        self._timeline.setRange(0, 0)
        self._timeline.setEnabled(False)
        self._time_total = QLabel("0:00")
        self._time_total.setFixedWidth(44)
        timeline_row.addWidget(self._time_current)
        timeline_row.addWidget(self._timeline, stretch=1)
        timeline_row.addWidget(self._time_total)
        layout.addLayout(timeline_row)
        self._timeline_container = timeline_row  # for show/hide

        self._caption = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._caption.setStyleSheet("color: #aeaeb2; font-size: 13px;")
        layout.addWidget(self._caption)

        controls = QHBoxLayout()
        self._prev_btn = QPushButton("◀")
        self._prev_btn.setFixedWidth(48)
        self._prev_btn.clicked.connect(self._show_previous)

        self._play_btn = QPushButton("▶")
        self._play_btn.setFixedWidth(64)
        self._play_btn.clicked.connect(self._toggle_playback)

        self._live_btn = QPushButton("LIVE")
        self._live_btn.setToolTip("Play Live Photo (or hold photo)")
        self._live_btn.clicked.connect(self._play_live_photo)
        self._live_btn.hide()

        self._next_btn = QPushButton("⏭")
        self._next_btn.setFixedWidth(48)
        self._next_btn.clicked.connect(self._show_next)

        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.close)

        controls.addWidget(self._prev_btn)
        controls.addStretch()
        controls.addWidget(self._live_btn)
        controls.addWidget(self._play_btn)
        controls.addStretch()
        controls.addWidget(self._next_btn)
        controls.addWidget(self._close_btn)
        layout.addLayout(controls)

        self._player = QMediaPlayer()
        self._audio = QAudioOutput()
        self._player.setAudioOutput(self._audio)
        self._player.setVideoOutput(self._video_widget)

    def _wire_player(self) -> None:
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)
        self._timeline.sliderPressed.connect(lambda: setattr(self, "_seeking", True))
        self._timeline.sliderReleased.connect(self._on_seek_released)
        self._timeline.valueChanged.connect(self._on_slider_moved)

    def _photo_mouse_press(self, event) -> None:
        if self._current_item().is_live_photo:
            self._live_timer.start(300)
        QLabel.mousePressEvent(self._photo_label, event)

    def _photo_mouse_release(self, event) -> None:
        self._live_timer.stop()
        if self._stack.currentIndex() == 1 and self._current_item().is_live_photo:
            self._on_live_photo_released()
        QLabel.mouseReleaseEvent(self._photo_label, event)

    def _current_item(self) -> MediaItem:
        return self._items[self._index]

    def _show_current(self) -> None:
        if not self._items:
            return

        item = self._current_item()
        self._player.stop()
        self._timeline.setValue(0)
        self._time_current.setText("0:00")
        self._time_total.setText("0:00")

        kind_label = {"photo": "Photo", "video": "Video", "live_photo": "Live Photo"}
        self._caption.setText(
            f"{kind_label.get(item.kind.value, 'Media')}  ·  "
            f"{item.taken_at.strftime('%b %d, %Y %H:%M')}  ·  "
            f"{self._index + 1} of {len(self._items)}"
        )
        self._prev_btn.setEnabled(self._index > 0)
        self._next_btn.setEnabled(self._index < len(self._items) - 1)

        is_video = item.kind == MediaKind.VIDEO
        is_live = item.kind == MediaKind.LIVE_PHOTO

        self._play_btn.setVisible(is_video)
        self._live_btn.setVisible(is_live)
        self._set_timeline_visible(is_video)

        if is_video:
            self._stack.setCurrentIndex(1)
            self._player.setSource(QUrl.fromLocalFile(str(item.path.resolve())))
            self._player.play()
        elif is_live:
            self._stack.setCurrentIndex(0)
            self._show_photo(item.path)
            self._set_timeline_visible(False)
        else:
            self._stack.setCurrentIndex(0)
            self._show_photo(item.path)
            self._set_timeline_visible(False)

    def _set_timeline_visible(self, visible: bool) -> None:
        self._timeline.setVisible(visible)
        self._time_current.setVisible(visible)
        self._time_total.setVisible(visible)

    def _show_photo(self, path) -> None:
        pixmap = load_image_pixmap(path, max_size=2400)
        self._current_pixmap = pixmap
        if pixmap.isNull():
            self._photo_label.setText(f"Unable to preview\n{path}")
            return
        self._photo_label.setText("")
        self._scale_photo(pixmap)

    def _scale_photo(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            return
        scaled = pixmap.scaled(
            self._photo_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._photo_label.setPixmap(scaled)

    def _play_live_photo(self) -> None:
        item = self._current_item()
        if not item.is_live_photo or not item.live_video_path:
            return
        self._current_pixmap = None
        self._stack.setCurrentIndex(1)
        self._set_timeline_visible(True)
        self._play_btn.setVisible(True)
        self._player.setSource(QUrl.fromLocalFile(str(item.live_video_path.resolve())))
        self._player.play()

    def _on_live_photo_released(self) -> None:
        if self._current_item().is_live_photo:
            self._player.pause()
            self._stack.setCurrentIndex(0)
            self._set_timeline_visible(False)
            self._play_btn.setVisible(False)

    def _toggle_playback(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _on_position_changed(self, position: int) -> None:
        if not self._seeking:
            self._timeline.setValue(position)
        self._time_current.setText(_format_ms(position))

    def _on_duration_changed(self, duration: int) -> None:
        self._timeline.setRange(0, max(0, duration))
        self._timeline.setEnabled(duration > 0)
        self._time_total.setText(_format_ms(duration))

    def _on_playback_state_changed(self, state) -> None:
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._play_btn.setText("⏸")
        else:
            self._play_btn.setText("▶")

    def _on_slider_moved(self, value: int) -> None:
        if self._seeking:
            self._time_current.setText(_format_ms(value))

    def _on_seek_released(self) -> None:
        self._seeking = False
        self._player.setPosition(self._timeline.value())

    def _show_previous(self) -> None:
        if self._index > 0:
            self._index -= 1
            self._show_current()

    def _show_next(self) -> None:
        if self._index < len(self._items) - 1:
            self._index += 1
            self._show_current()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        item = self._current_item() if self._items else None
        if item and item.kind != MediaKind.VIDEO and self._stack.currentIndex() == 0:
            if self._current_pixmap and not self._current_pixmap.isNull():
                self._scale_photo(self._current_pixmap)

    def mouseReleaseEvent(self, event) -> None:
        if self._current_item().is_live_photo and self._stack.currentIndex() == 1:
            self._on_live_photo_released()
        super().mouseReleaseEvent(event)

    def closeEvent(self, event) -> None:
        self._player.stop()
        super().closeEvent(event)

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key.Key_Left:
            self._show_previous()
        elif key == Qt.Key.Key_Right:
            self._show_next()
        elif key in (Qt.Key.Key_Space, Qt.Key.Key_P):
            item = self._current_item()
            if item.kind == MediaKind.VIDEO or (
                item.is_live_photo and self._stack.currentIndex() == 1
            ):
                self._toggle_playback()
            elif item.is_live_photo:
                self._play_live_photo()
        else:
            super().keyPressEvent(event)
