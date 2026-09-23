"""Scan synced media files for the gallery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from iphone_sync.utils.exif import exif_datetime
from iphone_sync.utils.paths import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS


class MediaKind(str, Enum):
    PHOTO = "photo"
    VIDEO = "video"
    LIVE_PHOTO = "live_photo"


@dataclass
class MediaItem:
    path: Path
    filename: str
    taken_at: datetime
    kind: MediaKind
    live_video_path: Path | None = None

    @property
    def is_video(self) -> bool:
        return self.kind == MediaKind.VIDEO

    @property
    def is_live_photo(self) -> bool:
        return self.kind == MediaKind.LIVE_PHOTO

    @property
    def extension(self) -> str:
        return self.path.suffix.lower().lstrip(".")


MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def _media_datetime(path: Path) -> datetime:
    # 1. Fast path: check if path is organized like .../<year>/<month_name>/<filename>
    parent = path.parent
    month_num = MONTH_MAP.get(parent.name.lower())
    if month_num and parent.parent.name.isdigit() and len(parent.parent.name) == 4:
        try:
            mtime = path.stat().st_mtime
            file_dt = datetime.fromtimestamp(mtime)
            year = int(parent.parent.name)
            if file_dt.year == year and file_dt.month == month_num:
                return file_dt
            day = min(file_dt.day, 28)
            return datetime(year, month_num, day, file_dt.hour, file_dt.minute, file_dt.second)
        except OSError:
            pass

    # 2. EXIF reading: open file with limit to 64KB for speed
    ext = path.suffix.lower().lstrip(".")
    if ext in IMAGE_EXTENSIONS:
        try:
            with open(path, "rb") as f:
                head = f.read(65536)
            taken = exif_datetime(head)
            if taken:
                return taken
        except Exception:
            pass
    try:
        return datetime.fromtimestamp(path.stat().st_mtime)
    except OSError:
        return datetime.now()


def _find_live_video(image_path: Path) -> Path | None:
    """Return paired MOV for a Live Photo if present."""
    for suffix in (".MOV", ".mov", ".MP4", ".mp4"):
        candidate = image_path.with_suffix(suffix)
        if candidate.exists() and candidate != image_path:
            return candidate
    return None


def scan_media_folder(root: Path) -> list[MediaItem]:
    if not root.exists():
        return []

    allowed = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
    all_files: list[Path] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        ext = path.suffix.lower().lstrip(".")
        if ext not in allowed:
            continue
        if path.name.endswith(".partial"):
            continue
        all_files.append(path)

    # Map stems to image paths for Live Photo pairing
    image_by_key: dict[tuple[Path, str], Path] = {}
    for path in all_files:
        ext = path.suffix.lower().lstrip(".")
        if ext in IMAGE_EXTENSIONS:
            image_by_key[(path.parent, path.stem.upper())] = path

    live_video_paths: set[Path] = set()
    items: list[MediaItem] = []

    for path in all_files:
        ext = path.suffix.lower().lstrip(".")
        if ext in IMAGE_EXTENSIONS:
            live_video = _find_live_video(path)
            if live_video:
                live_video_paths.add(live_video)
                items.append(
                    MediaItem(
                        path=path,
                        filename=path.name,
                        taken_at=_media_datetime(path),
                        kind=MediaKind.LIVE_PHOTO,
                        live_video_path=live_video,
                    )
                )
            else:
                items.append(
                    MediaItem(
                        path=path,
                        filename=path.name,
                        taken_at=_media_datetime(path),
                        kind=MediaKind.PHOTO,
                    )
                )

    for path in all_files:
        ext = path.suffix.lower().lstrip(".")
        if ext not in VIDEO_EXTENSIONS:
            continue
        if path in live_video_paths:
            continue
        items.append(
            MediaItem(
                path=path,
                filename=path.name,
                taken_at=_media_datetime(path),
                kind=MediaKind.VIDEO,
            )
        )

    items.sort(key=lambda item: item.taken_at, reverse=True)
    return items


def group_by_month_year(items: list[MediaItem]) -> list[tuple[str, str, list[MediaItem]]]:
    """Group items by month/year sections (newest first).

    Returns list of (section_key, section_label, items).
    section_key format: 'YYYY-MM' for scrolling.
    """
    from collections import OrderedDict

    from iphone_sync.utils.paths import MONTH_NAMES

    groups: OrderedDict[str, list[MediaItem]] = OrderedDict()

    for item in items:
        key = f"{item.taken_at.year:04d}-{item.taken_at.month:02d}"
        groups.setdefault(key, []).append(item)

    result: list[tuple[str, str, list[MediaItem]]] = []
    for key, group_items in groups.items():
        year_str, month_str = key.split("-")
        month_name = MONTH_NAMES[int(month_str) - 1]
        label = f"{month_name} {year_str}"
        result.append((key, label, group_items))
    return result


def build_year_month_navigation(
    items: list[MediaItem],
) -> list[tuple[str, str, int | None]]:
    """Build sidebar navigation entries.

    Returns list of (key, label, level) where level 0=year header, 1=month item.
    key is scroll target: 'YYYY' for year, 'YYYY-MM' for month.
    """
    from collections import OrderedDict

    from iphone_sync.utils.paths import MONTH_NAMES

    years: OrderedDict[int, dict[int, int]] = OrderedDict()
    for item in items:
        y = item.taken_at.year
        m = item.taken_at.month
        if y not in years:
            years[y] = {}
        years[y][m] = years[y].get(m, 0) + 1

    nav: list[tuple[str, str, int | None]] = []
    for year, months in years.items():
        total = sum(months.values())
        nav.append((f"{year:04d}", f"{year}  ({total})", 0))
        for month, count in months.items():
            key = f"{year:04d}-{month:02d}"
            label = f"  {MONTH_NAMES[month - 1]}  ({count})"
            nav.append((key, label, 1))
    return nav


def group_by_date(items: list[MediaItem]) -> list[tuple[str, list[MediaItem]]]:
    """Group items by calendar day for Apple Photos-style sections."""
    from collections import OrderedDict

    groups: OrderedDict[str, list[MediaItem]] = OrderedDict()
    today = datetime.now().date()
    yesterday = today.fromordinal(today.toordinal() - 1)

    for item in items:
        day = item.taken_at.date()
        if day == today:
            label = "Today"
        elif day == yesterday:
            label = "Yesterday"
        else:
            label = item.taken_at.strftime("%B %d, %Y")
        groups.setdefault(label, []).append(item)

    return list(groups.items())
