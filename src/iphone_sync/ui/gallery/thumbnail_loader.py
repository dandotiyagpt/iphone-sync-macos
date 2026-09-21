"""Main-thread thumbnail generation (pillow-heif is not thread-safe)."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

from iphone_sync.ui.gallery.media_scanner import MediaItem, MediaKind
from iphone_sync.ui.gallery.thumbnails import THUMB_SIZE, create_image_thumbnail, create_video_thumbnail


class ThumbnailLoader(QObject):
    """Load thumbnails one at a time on the main thread."""

    thumbnail_ready = Signal(int, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._photo_queue: list[tuple[int, MediaItem]] = []
        self._video_queue: list[tuple[int, MediaItem]] = []
        self._paused = False
        self._timer = QTimer(self)
        self._timer.setInterval(5)
        self._timer.timeout.connect(self._process_next)

    def load(self, index: int, item: MediaItem) -> None:
        if item.is_video:
            self._video_queue.append((index, item))
        else:
            self._photo_queue.append((index, item))
        if not self._timer.isActive():
            self._timer.start()

    def clear(self) -> None:
        self._photo_queue.clear()
        self._video_queue.clear()
        self._timer.stop()

    def pause(self) -> None:
        """Pause while video preview is active to avoid decoder conflicts."""
        self._paused = True

    def resume(self) -> None:
        self._paused = False
        if (self._photo_queue or self._video_queue) and not self._timer.isActive():
            self._timer.start()

    def _process_next(self) -> None:
        if self._paused:
            return

        if self._photo_queue:
            index, item = self._photo_queue.pop(0)
            pixmap = create_image_thumbnail(item.path, THUMB_SIZE)
        elif self._video_queue:
            index, item = self._video_queue.pop(0)
            pixmap = create_video_thumbnail(item.path, THUMB_SIZE)
        else:
            self._timer.stop()
            return

        self.thumbnail_ready.emit(index, pixmap)

        total = len(self._photo_queue) + len(self._video_queue)
        self._timer.setInterval(1 if total > 200 else 5)
