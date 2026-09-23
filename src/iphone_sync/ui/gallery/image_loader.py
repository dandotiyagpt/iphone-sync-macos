"""Load images including HEIC for gallery display."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from iphone_sync.utils.paths import IMAGE_EXTENSIONS

_heif_registered = False


def register_heif_opener() -> None:
    global _heif_registered
    if _heif_registered:
        return
    try:
        import pillow_heif

        pillow_heif.register_heif_opener()
        _heif_registered = True
    except ImportError:
        pass


def load_image_pixmap(path: Path, max_size: int | None = None) -> QPixmap:
    """Load a photo file into QPixmap, including HEIC/HEIF."""
    register_heif_opener()
    ext = path.suffix.lower().lstrip(".")

    if ext in IMAGE_EXTENSIONS:
        try:
            with Image.open(path) as img:
                if max_size:
                    img.thumbnail((max_size, max_size), Image.Resampling.BILINEAR)
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGB")
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=90)
                pixmap = QPixmap()
                if pixmap.loadFromData(buffer.getvalue(), "JPEG"):
                    return pixmap
        except Exception:
            pass

    pixmap = QPixmap(str(path))
    if pixmap.isNull() or max_size is None:
        return pixmap

    return pixmap.scaled(
        max_size,
        max_size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
