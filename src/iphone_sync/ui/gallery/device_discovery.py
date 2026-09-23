"""Discover synced iPhone photo libraries and backups."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from iphone_sync.core.device_backup_info import inspect_device_backup
from iphone_sync.utils.paths import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS

ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS


@dataclass
class DeviceSource:
    """Represents a selectable iPhone photo source."""

    id: str
    name: str
    raw_name: str
    path: Path
    item_count: int = 0
    is_all: bool = False
    source_type: str = "sync"  # "sync" | "backup" | "custom"

    @property
    def display_label(self) -> str:
        count_str = f" ({self.item_count:,} items)" if self.item_count > 0 else ""
        icon = "📱" if not self.is_all else "📱"
        return f"{icon} {self.name}{count_str}"


def _count_media_files(folder: Path, max_depth: int = 4) -> int:
    """Fast count of media files under a folder."""
    if not folder.exists():
        return 0
    count = 0
    try:
        for entry in folder.rglob("*"):
            if entry.is_file():
                ext = entry.suffix.lower().lstrip(".")
                if ext in ALLOWED_EXTENSIONS and not entry.name.endswith(".partial"):
                    count += 1
    except OSError:
        pass
    return count


def discover_device_sources(
    destination: Path,
    device_backup_root: Path | None = None,
) -> list[DeviceSource]:
    """Scans for available iPhone photo folders under destination and backup root."""
    sources: list[DeviceSource] = []
    device_dirs: list[tuple[str, str, Path, int]] = []

    # 1. Scan destination_folder for iPhone subdirectories
    if destination.exists() and destination.is_dir():
        try:
            for sub in sorted(destination.iterdir()):
                if sub.is_dir() and not sub.name.startswith("."):
                    # Check if directory contains media or year folders (e.g. 2024, 2025, 2026)
                    count = _count_media_files(sub)
                    if count > 0 or any(sub.glob("20*")):
                        # Format clean display name (strip trailing _short_udid if present)
                        clean_name = sub.name.rsplit("_", 1)[0] if "_" in sub.name else sub.name
                        device_dirs.append((clean_name, sub.name, sub, count))
        except OSError:
            pass

    # If multiple devices or any device folder exists, provide "All iPhones" option first
    if len(device_dirs) > 1:
        total = sum(c for _, _, _, c in device_dirs)
        sources.append(
            DeviceSource(
                id="all",
                name="All iPhones",
                raw_name="all",
                path=destination,
                item_count=total,
                is_all=True,
                source_type="sync",
            )
        )

    # Add individual synced iPhone sources
    for clean_name, raw_name, path, count in device_dirs:
        sources.append(
            DeviceSource(
                id=raw_name,
                name=clean_name,
                raw_name=raw_name,
                path=path,
                item_count=count,
                is_all=False,
                source_type="sync",
            )
        )

    # If no device subfolders found but destination itself has media, add destination
    if not device_dirs and destination.exists():
        count = _count_media_files(destination)
        sources.append(
            DeviceSource(
                id="library",
                name="Photo Library",
                raw_name=destination.name,
                path=destination,
                item_count=count,
                is_all=True,
                source_type="sync",
            )
        )

    # 2. Check device_backup_root if provided
    if device_backup_root and device_backup_root.exists() and device_backup_root.is_dir():
        try:
            for sub in sorted(device_backup_root.iterdir()):
                if sub.is_dir() and not sub.name.startswith("."):
                    info = inspect_device_backup(sub)
                    if info:
                        # Check if any media files or CameraRollDomain exists
                        b_count = _count_media_files(sub)
                        if b_count > 0:
                            sources.append(
                                DeviceSource(
                                    id=f"backup:{info.udid}",
                                    name=f"{info.device_name} (Backup)",
                                    raw_name=sub.name,
                                    path=sub,
                                    item_count=b_count,
                                    is_all=False,
                                    source_type="backup",
                                )
                            )
        except OSError:
            pass

    return sources
