"""Side preview player for the gallery."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
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


def _fmt(ms: int) -> str:
    ms = max(0, ms)
    s = ms // 1000
    return f"{s // 60}:{s % 60:02d}"


class PreviewPane(QWidget):
    """Right-side preview — photo, video, or Live Photo playback."""

    playback_started = Signal()
    playback_stopped = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(320)
        self.setStyleSheet("background: #000; border-radius: 8px;")
        self._item: MediaItem | None = None
        self._seeking = False
        self._build()
        self._show_placeholder()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self._caption = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._caption.setStyleSheet("color: #aeaeb2; font-size: 12px;")
        self._caption.setWordWrap(True)
        layout.addWidget(self._caption)

        self._stack = QStackedWidget()
        self._photo = QLabel("Select a photo or video", alignment=Qt.AlignmentFlag.AlignCenter)
        self._photo.setStyleSheet("color: #636366; font-size: 14px; background: #000;")
        self._photo.setMinimumHeight(200)

        video_wrap = QWidget()
        vl = QVBoxLayout(video_wrap)
        vl.setContentsMargins(0, 0, 0, 0)
        self._video = QVideoWidget()
        self._video.setStyleSheet("background: #000;")
        self._video.setMinimumHeight(200)
        vl.addWidget(self._video)

        self._stack.addWidget(self._photo)
        self._stack.addWidget(video_wrap)
        layout.addWidget(self._stack, stretch=1)

        controls = QHBoxLayout()
        self._live_btn = QPushButton("LIVE")
        self._live_btn.setToolTip("Play Live Photo motion")
        self._live_btn.clicked.connect(self.play_live)
        self._live_btn.hide()
        self._play_btn = QPushButton("▶")
        self._play_btn.setFixedWidth(40)
        self._play_btn.clicked.connect(self._toggle_playback)
        self._play_btn.hide()
        controls.addStretch()
        controls.addWidget(self._live_btn)
        controls.addWidget(self._play_btn)
        controls.addStretch()
        layout.addLayout(controls)

        timeline = QHBoxLayout()
        self._cur = QLabel("0:00")
        self._cur.setFixedWidth(40)
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 0)
        self._slider.hide()
        self._total = QLabel("0:00")
        self._total.setFixedWidth(40)
        timeline.addWidget(self._cur)
        timeline.addWidget(self._slider, stretch=1)
        timeline.addWidget(self._total)
        layout.addLayout(timeline)

        self._player = QMediaPlayer()
        self._audio = QAudioOutput()
        self._player.setAudioOutput(self._audio)
        self._player.setVideoOutput(self._video)
        self._player.positionChanged.connect(self._on_pos)
        self._player.durationChanged.connect(self._on_dur)
        self._player.playbackStateChanged.connect(self._on_playback_state)
        self._slider.sliderPressed.connect(lambda: setattr(self, "_seeking", True))
        self._slider.sliderReleased.connect(self._on_seek)
        self._slider.valueChanged.connect(
            lambda v: self._cur.setText(_fmt(v)) if self._seeking else None
        )

    def _show_placeholder(self) -> None:
        self._stack.setCurrentIndex(0)
        self._photo.clear()
        self._photo.setText("Select a photo or video")
        self._caption.setText("")
        self._slider.hide()
        self._live_btn.hide()
        self._play_btn.hide()

    def _reset_player(self) -> None:
        self._player.stop()
        self._player.setSource(QUrl())

    def show_item(self, item: MediaItem | None) -> None:
        self._reset_player()
        self._item = item
        if item is None:
            self._show_placeholder()
            self.playback_stopped.emit()
            return

        kind = "Photo"
        if item.is_live_photo:
            kind = "Live Photo"
        elif item.is_video:
            kind = "Video"
        self._caption.setText(
            f"{kind} · {item.filename}\n{item.taken_at.strftime('%b %d, %Y %H:%M')}"
        )

        if item.kind == MediaKind.VIDEO:
            self._stack.setCurrentIndex(1)
            self._slider.show()
            self._play_btn.show()
            self._live_btn.hide()
            self.playback_started.emit()
            self._player.setSource(QUrl.fromLocalFile(str(item.path.resolve())))
            self._player.play()
        elif item.is_live_photo:
            self._stack.setCurrentIndex(0)
            self._slider.hide()
            self._play_btn.hide()
            self._live_btn.show()
            self._show_photo(item.path)
            self.playback_stopped.emit()
        else:
            self._stack.setCurrentIndex(0)
            self._slider.hide()
            self._play_btn.hide()
            self._live_btn.hide()
            self._show_photo(item.path)
            self.playback_stopped.emit()

    def play_live(self) -> None:
        if not self._item or not self._item.is_live_photo or not self._item.live_video_path:
            return
        self._stack.setCurrentIndex(1)
        self._slider.show()
        self._play_btn.show()
        self.playback_started.emit()
        self._player.setSource(QUrl.fromLocalFile(str(self._item.live_video_path.resolve())))
        self._player.play()

    def _show_photo(self, path) -> None:
        self._stack.setCurrentIndex(0)
        pixmap = load_image_pixmap(path, max_size=1600)
        if pixmap.isNull():
            self._photo.setText(f"Unable to preview\n{path.name}")
            return
        self._photo.setText("")
        scaled = pixmap.scaled(
            self._photo.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._photo.setPixmap(scaled)

    def _toggle_playback(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _on_playback_state(self, state) -> None:
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._play_btn.setText("⏸")
            self.playback_started.emit()
        else:
            self._play_btn.setText("▶")
            if state == QMediaPlayer.PlaybackState.StoppedState:
                self.playback_stopped.emit()

    def _on_pos(self, pos: int) -> None:
        if not self._seeking:
            self._slider.setValue(pos)
        self._cur.setText(_fmt(pos))

    def _on_dur(self, dur: int) -> None:
        self._slider.setRange(0, max(0, dur))
        self._total.setText(_fmt(dur))

    def _on_seek(self) -> None:
        self._seeking = False
        self._player.setPosition(self._slider.value())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if (
            self._item
            and self._item.kind != MediaKind.VIDEO
            and self._stack.currentIndex() == 0
        ):
            self._show_photo(self._item.path)

    def stop(self) -> None:
        self._reset_player()
        self.playback_stopped.emit()
