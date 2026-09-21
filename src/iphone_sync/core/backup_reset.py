"""Reset local backup files and sync history for a fresh start."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from iphone_sync.core.manifest import Manifest
from iphone_sync.ui.gallery.thumbnail_cache import clear_thumbnail_cache


@dataclass
class BackupResetResult:
    files_deleted: int
    manifest_cleared: bool
    thumbnails_cleared: bool
    errors: list[str]


def count_backup_files(destination: Path) -> int:
    if not destination.exists():
        return 0
    return sum(1 for path in destination.rglob("*") if path.is_file())


def reset_backup(destination: Path, manifest: Manifest) -> BackupResetResult:
    """Delete all files under the destination folder and clear sync state."""
    errors: list[str] = []
    files_deleted = 0

    if destination.exists():
        for entry in destination.iterdir():
            try:
                if entry.is_file():
                    entry.unlink()
                    files_deleted += 1
                elif entry.is_dir():
                    nested = sum(1 for p in entry.rglob("*") if p.is_file())
                    shutil.rmtree(entry)
                    files_deleted += nested
            except OSError as exc:
                errors.append(f"{entry.name}: {exc}")

    manifest_cleared = True
    try:
        manifest.clear_all()
    except OSError as exc:
        manifest_cleared = False
        errors.append(f"manifest: {exc}")

    thumbnails_cleared = True
    try:
        clear_thumbnail_cache()
    except OSError as exc:
        thumbnails_cleared = False
        errors.append(f"thumbnails: {exc}")

    return BackupResetResult(
        files_deleted=files_deleted,
        manifest_cleared=manifest_cleared,
        thumbnails_cleared=thumbnails_cleared,
        errors=errors,
    )
