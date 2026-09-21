"""Disk-backed thumbnail cache for gallery performance."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from iphone_sync.config import Settings


def _cache_dir() -> Path:
    path = Settings.app_cache_dir() / "thumbnails"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cache_key(source: Path) -> str:
    stat = source.stat()
    digest = f"{source.resolve()}|{stat.st_size}|{stat.st_mtime_ns}"
    return hashlib.sha256(digest.encode()).hexdigest()


def cached_thumbnail_path(source: Path) -> Path:
    return _cache_dir() / f"{_cache_key(source)}.jpg"


def load_cached_thumbnail(source: Path) -> bytes | None:
    cache = cached_thumbnail_path(source)
    if cache.exists() and cache.stat().st_mtime >= source.stat().st_mtime:
        return cache.read_bytes()
    return None


def save_cached_thumbnail(source: Path, jpeg_data: bytes) -> None:
    cached_thumbnail_path(source).write_bytes(jpeg_data)


def clear_thumbnail_cache() -> None:
    cache = _cache_dir()
    if not cache.exists():
        return
    for entry in cache.iterdir():
        if entry.is_file():
            entry.unlink()
        elif entry.is_dir():
            shutil.rmtree(entry)
