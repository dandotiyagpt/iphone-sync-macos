"""Asynchronous background thumbnail loader with multi-tier caching."""

from __future__ import annotations

from collections import deque
import os
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtGui import QPixmap

from iphone_sync.ui.gallery.media_scanner import MediaItem
from iphone_sync.ui.gallery.thumbnail_cache import load_cached_thumbnail
from iphone_sync.ui.gallery.thumbnails import (
    THUMB_SIZE,
    create_image_thumbnail_bytes,
    create_video_thumbnail_bytes,
)


class _ThumbnailWorkerSignals(QObject):
    finished = Signal(int, Path, object, int)


class _ThumbnailWorker(QRunnable):
    def __init__(
        self,
        index: int,
        item: MediaItem,
        generation: int,
        signals: _ThumbnailWorkerSignals,
    ) -> None:
        super().__init__()
        self.index = index
        self.item = item
        self.generation = generation
        self.signals = signals
        self.setAutoDelete(True)

    def run(self) -> None:
        try:
            if self.item.is_video:
                data = create_video_thumbnail_bytes(self.item.path, THUMB_SIZE)
            else:
                data = create_image_thumbnail_bytes(self.item.path, THUMB_SIZE)
        except Exception:
            data = None

        try:
            self.signals.finished.emit(self.index, self.item.path, data, self.generation)
        except (RuntimeError, AttributeError):
            pass


class ThumbnailLoader(QObject):
    """Load thumbnails asynchronously using a background thread pool."""

    thumbnail_ready = Signal(int, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._queue: deque[tuple[int, MediaItem, int]] = deque()
        self._pixmap_cache: dict[Path, QPixmap] = {}
        self._generation = 0
        self._active_workers = 0
        self._max_workers = min(8, max(2, os.cpu_count() or 4))
        self._paused = False
        self._pool = QThreadPool.globalInstance()
        self._signals = _ThumbnailWorkerSignals(self)
        self._signals.finished.connect(self._on_worker_finished)

    def wait_done(self, msecs: int = 2000) -> bool:
        """Wait for active background tasks to finish (useful during teardown)."""
        return self._pool.waitForDone(msecs)

    def load(self, index: int, item: MediaItem) -> None:
        # 1. Memory cache hit: instant response
        if item.path in self._pixmap_cache:
            self.thumbnail_ready.emit(index, self._pixmap_cache[item.path])
            return

        # 2. Disk cache hit: load pixmap on main thread immediately
        cached = load_cached_thumbnail(item.path)
        if cached:
            pixmap = QPixmap()
            if pixmap.loadFromData(cached, "JPEG") and not pixmap.isNull():
                self._pixmap_cache[item.path] = pixmap
                self.thumbnail_ready.emit(index, pixmap)
                return

        # 3. Offload decoding to background thread pool
        self._queue.append((index, item, self._generation))
        self._dispatch()

    def clear(self) -> None:
        self._generation += 1
        self._queue.clear()

    def pause(self) -> None:
        """Pause while video preview is active to avoid decoder conflicts."""
        self._paused = True

    def resume(self) -> None:
        self._paused = False
        self._dispatch()

    def _dispatch(self) -> None:
        if self._paused:
            return
        while self._queue and self._active_workers < self._max_workers:
            index, item, gen = self._queue.popleft()
            if gen != self._generation:
                continue
            self._active_workers += 1
            worker = _ThumbnailWorker(index, item, gen, self._signals)
            self._pool.start(worker)

    def _on_worker_finished(
        self, index: int, path: Path, data: bytes | None, generation: int
    ) -> None:
        self._active_workers = max(0, self._active_workers - 1)
        if generation == self._generation:
            pixmap = QPixmap()
            if data:
                pixmap.loadFromData(data, "JPEG")
            if not pixmap.isNull():
                self._pixmap_cache[path] = pixmap
            self.thumbnail_ready.emit(index, pixmap)
        self._dispatch()
