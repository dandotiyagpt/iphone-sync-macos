"""Load and crop square thumbnails from local backup files."""

from __future__ import annotations

import io
import shutil
import subprocess
from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from iphone_sync.ui.gallery.image_loader import register_heif_opener
from iphone_sync.ui.gallery.thumbnail_cache import load_cached_thumbnail, save_cached_thumbnail
from iphone_sync.utils.paths import IMAGE_EXTENSIONS

THUMB_SIZE = 200


def _crop_center_square(img: Image.Image, size: int) -> Image.Image:
    width, height = img.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    cropped = img.crop((left, top, left + side, top + side))
    return cropped.resize((size, size), Image.Resampling.LANCZOS)


def _pil_to_jpeg(img: Image.Image) -> bytes:
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


def _jpeg_to_pixmap(data: bytes) -> QPixmap:
    pixmap = QPixmap()
    pixmap.loadFromData(data, "JPEG")
    return pixmap


def _save_pixmap_cache(source: Path, pixmap: QPixmap) -> None:
    from PySide6.QtCore import QBuffer, QIODevice

    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, "JPEG", quality=85)
    save_cached_thumbnail(source, bytes(buffer.data()))


def _cache_and_return(source: Path, jpeg: bytes) -> QPixmap:
    save_cached_thumbnail(source, jpeg)
    return _jpeg_to_pixmap(jpeg)


def create_image_thumbnail(source: Path, size: int = THUMB_SIZE) -> QPixmap:
    """Create thumbnail from a local image file on the main thread."""
    if not source.exists():
        return QPixmap()

    cached = load_cached_thumbnail(source)
    if cached:
        pixmap = _jpeg_to_pixmap(cached)
        if not pixmap.isNull():
            return pixmap

    register_heif_opener()
    ext = source.suffix.lower().lstrip(".")
    if ext in IMAGE_EXTENSIONS:
        try:
            with Image.open(source) as img:
                square = _crop_center_square(img, size)
                return _cache_and_return(source, _pil_to_jpeg(square))
        except Exception:
            pass

    pixmap = QPixmap(str(source))
    if not pixmap.isNull():
        scaled = pixmap.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        _save_pixmap_cache(source, scaled)
        return scaled

    return QPixmap()


def _video_thumbnail_pyav(source: Path, size: int) -> QPixmap | None:
    try:
        import av
    except ImportError:
        return None

    try:
        with av.open(str(source)) as container:
            stream = container.streams.video[0]
            stream.thread_type = "AUTO"
            for frame in container.decode(stream):
                img = frame.to_image()
                square = _crop_center_square(img, size)
                return _cache_and_return(source, _pil_to_jpeg(square))
    except Exception:
        return None
    return None


def _video_thumbnail_ffmpeg(source: Path, size: int) -> QPixmap | None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None

    try:
        result = subprocess.run(
            [
                ffmpeg,
                "-ss",
                "0.5",
                "-i",
                str(source.resolve()),
                "-vframes",
                "1",
                "-f",
                "image2pipe",
                "-vcodec",
                "mjpeg",
                "-",
            ],
            capture_output=True,
            timeout=15,
            check=False,
        )
        if result.returncode == 0 and result.stdout:
            pixmap = QPixmap()
            if pixmap.loadFromData(result.stdout, "JPEG") and not pixmap.isNull():
                scaled = pixmap.scaled(
                    size,
                    size,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                _save_pixmap_cache(source, scaled)
                return scaled
    except Exception:
        pass
    return None


def create_video_thumbnail(source: Path, size: int = THUMB_SIZE) -> QPixmap:
    """Create thumbnail from a local video file without QMediaPlayer."""
    if not source.exists():
        return QPixmap()

    cached = load_cached_thumbnail(source)
    if cached:
        pixmap = _jpeg_to_pixmap(cached)
        if not pixmap.isNull():
            return pixmap

    pixmap = _video_thumbnail_pyav(source, size)
    if pixmap and not pixmap.isNull():
        return pixmap

    pixmap = _video_thumbnail_ffmpeg(source, size)
    if pixmap and not pixmap.isNull():
        return pixmap

    return QPixmap()


def video_placeholder_icon():
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QStyle

    app = QApplication.instance()
    if app:
        return app.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
    return QIcon()
