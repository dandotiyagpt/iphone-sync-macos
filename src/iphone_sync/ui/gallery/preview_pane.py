"""Side preview player and metadata inspector for the gallery."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
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


def _fmt_time(ms: int) -> str:
    ms = max(0, ms)
    s = ms // 1000
    return f"{s // 60}:{s % 60:02d}"


def _fmt_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    elif num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    return f"{num_bytes / (1024 * 1024 * 1024):.2f} GB"


class PreviewPane(QWidget):
    """Right-side preview — photo, video, or Live Photo playback with metadata inspector."""

    playback_started = Signal()
    playback_stopped = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(320)
        self.setStyleSheet("background: #1c1c1e; border-radius: 8px;")
        self._item: MediaItem | None = None
        self._current_pixmap: QPixmap | None = None
        self._seeking = False
        self._build()
        self._show_placeholder()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Header title
        self._title = QLabel("Preview", alignment=Qt.AlignmentFlag.AlignLeft)
        self._title.setStyleSheet("color: #aeaeb2; font-size: 13px; font-weight: 600;")
        layout.addWidget(self._title)

        # Stacked viewer (Photo or Video)
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: #000; border-radius: 6px;")

        self._photo = QLabel("Select a photo or video", alignment=Qt.AlignmentFlag.AlignCenter)
        self._photo.setStyleSheet("color: #636366; font-size: 14px; background: #000;")
        self._photo.setMinimumHeight(240)

        video_wrap = QWidget()
        vl = QVBoxLayout(video_wrap)
        vl.setContentsMargins(0, 0, 0, 0)
        self._video = QVideoWidget()
        self._video.setStyleSheet("background: #000;")
        self._video.setMinimumHeight(240)
        vl.addWidget(self._video)

        self._stack.addWidget(self._photo)
        self._stack.addWidget(video_wrap)
        layout.addWidget(self._stack, stretch=1)

        # Video / Live controls
        controls = QHBoxLayout()
        self._live_btn = QPushButton("✨ LIVE")
        self._live_btn.setToolTip("Play Live Photo motion")
        self._live_btn.setStyleSheet(
            "background: #2c2c2e; color: #f2f2f7; border-radius: 6px; padding: 4px 12px; font-size: 12px; font-weight: 600;"
        )
        self._live_btn.clicked.connect(self.play_live)
        self._live_btn.hide()

        self._play_btn = QPushButton("▶")
        self._play_btn.setFixedWidth(44)
        self._play_btn.setStyleSheet(
            "background: #2c2c2e; color: #f2f2f7; border-radius: 6px; padding: 4px 12px; font-size: 14px;"
        )
        self._play_btn.clicked.connect(self._toggle_playback)
        self._play_btn.hide()

        controls.addStretch()
        controls.addWidget(self._live_btn)
        controls.addWidget(self._play_btn)
        controls.addStretch()
        layout.addLayout(controls)

        # Scrubber timeline
        timeline = QHBoxLayout()
        self._cur = QLabel("0:00")
        self._cur.setFixedWidth(40)
        self._cur.setStyleSheet("color: #8e8e93; font-size: 11px;")
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 0)
        self._slider.hide()
        self._total = QLabel("0:00")
        self._total.setFixedWidth(40)
        self._total.setStyleSheet("color: #8e8e93; font-size: 11px;")
        timeline.addWidget(self._cur)
        timeline.addWidget(self._slider, stretch=1)
        timeline.addWidget(self._total)
        layout.addLayout(timeline)

        # Metadata Card
        self._info_card = QFrame()
        self._info_card.setStyleSheet("background: #2c2c2e; border-radius: 8px; padding: 6px;")
        card_layout = QVBoxLayout(self._info_card)
        card_layout.setContentsMargins(10, 8, 10, 8)
        card_layout.setSpacing(6)

        self._info_filename = QLabel("")
        self._info_filename.setStyleSheet("font-size: 13px; font-weight: 600; color: #ffffff;")
        self._info_filename.setWordWrap(True)
        card_layout.addWidget(self._info_filename)

        info_grid = QGridLayout()
        info_grid.setHorizontalSpacing(10)
        info_grid.setVerticalSpacing(4)

        lbl_date = QLabel("Date:")
        lbl_date.setStyleSheet("color: #8e8e93; font-size: 11px;")
        self._val_date = QLabel("—")
        self._val_date.setStyleSheet("color: #e5e5ea; font-size: 11px;")

        lbl_kind = QLabel("Type:")
        lbl_kind.setStyleSheet("color: #8e8e93; font-size: 11px;")
        self._val_kind = QLabel("—")
        self._val_kind.setStyleSheet("color: #e5e5ea; font-size: 11px;")

        lbl_size = QLabel("Size:")
        lbl_size.setStyleSheet("color: #8e8e93; font-size: 11px;")
        self._val_size = QLabel("—")
        self._val_size.setStyleSheet("color: #e5e5ea; font-size: 11px;")

        info_grid.addWidget(lbl_kind, 0, 0)
        info_grid.addWidget(self._val_kind, 0, 1)
        info_grid.addWidget(lbl_date, 1, 0)
        info_grid.addWidget(self._val_date, 1, 1)
        info_grid.addWidget(lbl_size, 2, 0)
        info_grid.addWidget(self._val_size, 2, 1)
        card_layout.addLayout(info_grid)

        # Action buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self._reveal_btn = QPushButton("Reveal in Finder")
        self._reveal_btn.setStyleSheet(
            "background: #3a3a3c; color: #f2f2f7; border: none; border-radius: 6px; padding: 5px 10px; font-size: 11px;"
        )
        self._reveal_btn.clicked.connect(self._on_reveal_clicked)

        self._copy_btn = QPushButton("Copy Path")
        self._copy_btn.setStyleSheet(
            "background: #3a3a3c; color: #f2f2f7; border: none; border-radius: 6px; padding: 5px 10px; font-size: 11px;"
        )
        self._copy_btn.clicked.connect(self._on_copy_path_clicked)

        btn_layout.addWidget(self._reveal_btn)
        btn_layout.addWidget(self._copy_btn)
        card_layout.addLayout(btn_layout)

        layout.addWidget(self._info_card)

        # Media Player setup
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
            lambda v: self._cur.setText(_fmt_time(v)) if self._seeking else None
        )

    def _show_placeholder(self) -> None:
        self._current_pixmap = None
        self._stack.setCurrentIndex(0)
        self._photo.clear()
        self._photo.setText("Select a photo or video")
        self._slider.hide()
        self._cur.hide()
        self._total.hide()
        self._live_btn.hide()
        self._play_btn.hide()
        self._info_card.hide()

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

        # Update metadata card
        self._info_card.show()
        self._info_filename.setText(item.filename)
        self._val_date.setText(item.taken_at.strftime("%b %d, %Y %H:%M"))

        kind_str = "Photo"
        if item.is_live_photo:
            kind_str = "Live Photo"
        elif item.is_video:
            kind_str = "Video"
        self._val_kind.setText(kind_str)

        try:
            sz = item.path.stat().st_size
            self._val_size.setText(_fmt_size(sz))
        except OSError:
            self._val_size.setText("—")

        if item.kind == MediaKind.VIDEO:
            self._current_pixmap = None
            self._stack.setCurrentIndex(1)
            self._slider.show()
            self._cur.show()
            self._total.show()
            self._play_btn.show()
            self._live_btn.hide()
            self.playback_started.emit()
            self._player.setSource(QUrl.fromLocalFile(str(item.path.resolve())))
            self._player.play()
        elif item.is_live_photo:
            self._slider.hide()
            self._cur.hide()
            self._total.hide()
            self._play_btn.hide()
            self._live_btn.show()
            self._show_photo(item.path)
            self.playback_stopped.emit()
        else:
            self._slider.hide()
            self._cur.hide()
            self._total.hide()
            self._play_btn.hide()
            self._live_btn.hide()
            self._show_photo(item.path)
            self.playback_stopped.emit()

    def play_live(self) -> None:
        if not self._item or not self._item.is_live_photo or not self._item.live_video_path:
            return
        self._current_pixmap = None
        self._stack.setCurrentIndex(1)
        self._slider.show()
        self._cur.show()
        self._total.show()
        self._play_btn.show()
        self.playback_started.emit()
        self._player.setSource(QUrl.fromLocalFile(str(self._item.live_video_path.resolve())))
        self._player.play()

    def _show_photo(self, path: Path) -> None:
        self._stack.setCurrentIndex(0)
        pixmap = load_image_pixmap(path, max_size=1600)
        self._current_pixmap = pixmap
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

    def _on_reveal_clicked(self) -> None:
        if not self._item or not self._item.path.exists():
            return
        p = str(self._item.path.resolve())
        if sys.platform == "darwin":
            subprocess.run(["open", "-R", p], check=False)
        elif sys.platform == "win32":
            subprocess.run(["explorer", f"/select,{p}"], check=False)
        else:
            subprocess.run(["xdg-open", str(self._item.path.parent)], check=False)

    def _on_copy_path_clicked(self) -> None:
        if not self._item:
            return
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(str(self._item.path.resolve()))
            self._copy_btn.setText("Copied!")
            from PySide6.QtCore import QTimer

            QTimer.singleShot(1500, lambda: self._copy_btn.setText("Copy Path"))

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
        self._cur.setText(_fmt_time(pos))

    def _on_dur(self, dur: int) -> None:
        self._slider.setRange(0, max(0, dur))
        self._total.setText(_fmt_time(dur))

    def _on_seek(self) -> None:
        self._seeking = False
        self._player.setPosition(self._slider.value())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if (
            self._item
            and self._item.kind != MediaKind.VIDEO
            and self._stack.currentIndex() == 0
            and self._current_pixmap
            and not self._current_pixmap.isNull()
        ):
            # Fast rescale without re-decoding from disk
            scaled = self._current_pixmap.scaled(
                self._photo.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._photo.setPixmap(scaled)

    def stop(self) -> None:
        self._reset_player()
        self.playback_stopped.emit()
