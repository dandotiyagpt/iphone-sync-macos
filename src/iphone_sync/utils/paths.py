"""Destination folder layout and path utilities."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from iphone_sync.models.sync_record import DeviceFile

MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

IMAGE_EXTENSIONS = frozenset({"heic", "jpg", "jpeg", "png", "gif", "webp", "bmp", "tif", "tiff"})
VIDEO_EXTENSIONS = frozenset({"mov", "mp4", "m4v", "avi", "mkv"})


def sanitize_name(name: str) -> str:
    """Make a string safe for use as a folder name on Windows."""
    cleaned = re.sub(r'[<>:"/\\|?*]', "_", name.strip())
    return cleaned or "iPhone"


def sanitize_filename(filename: str) -> str:
    """Strip path separators/traversal from a device-supplied filename.

    AFC filenames come from the phone (untrusted) — reduce to a bare
    basename so a crafted name can't escape the destination folder.
    """
    cleaned = Path(filename.replace("\\", "/")).name
    cleaned = re.sub(r'[<>:"|?*]', "_", cleaned.strip())
    return cleaned or "file"


def short_udid(udid: str) -> str:
    return udid.replace("-", "")[-8:]


def device_root_folder(destination: Path, device_name: str, udid: str) -> Path:
    folder_name = f"{sanitize_name(device_name)}_{short_udid(udid)}"
    return destination / folder_name


def month_folder_name(dt: datetime) -> str:
    return MONTH_NAMES[dt.month - 1]


def resolve_dest_path(
    destination: Path,
    device_name: str,
    udid: str,
    device_file: DeviceFile,
    organize_by_date: bool,
    taken_at: datetime | None = None,
) -> Path:
    root = device_root_folder(destination, device_name, udid)

    if organize_by_date:
        dt = taken_at or datetime.fromtimestamp(device_file.mtime, tz=timezone.utc)
        root = root / f"{dt.year:04d}" / month_folder_name(dt)

    return root / sanitize_filename(device_file.filename)


def unique_path(path: Path) -> Path:
    """Return path, adding _2, _3 suffix if file already exists."""
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 2
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1
