"""Extract DateTimeOriginal from image EXIF when available."""

from __future__ import annotations

import io
from datetime import datetime

from PIL import Image


def exif_datetime(data: bytes) -> datetime | None:
    try:
        with Image.open(io.BytesIO(data)) as img:
            exif = img.getexif()
            if not exif:
                return None
            # DateTimeOriginal = 36867, DateTime = 306
            dt_str = exif.get(36867) or exif.get(306)
            if not dt_str:
                return None
            return datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
    except Exception:
        return None
