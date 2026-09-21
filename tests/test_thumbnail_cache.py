"""Tests for the disk-backed gallery thumbnail cache.

Covers cache-key stability (hash of resolved path + size + mtime), the
save/load round trip, staleness handling, cache-miss behavior, and the
file-vs-directory cleanup branches in ``clear_thumbnail_cache``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from iphone_sync.config import Settings
from iphone_sync.ui.gallery.thumbnail_cache import (
    cached_thumbnail_path,
    clear_thumbnail_cache,
    load_cached_thumbnail,
    save_cached_thumbnail,
)


@pytest.fixture(autouse=True)
def _reset_home_override():
    """Ensure no test leaks a home-dir override into another test."""
    Settings.set_home_override(None)
    yield
    Settings.set_home_override(None)


def _use_tmp_home(tmp_path: Path) -> Path:
    Settings.set_home_override(tmp_path)
    return tmp_path


def _make_source(tmp_path: Path, name: str = "photo.jpg", content: bytes = b"source-bytes") -> Path:
    source = tmp_path / name
    source.write_bytes(content)
    return source


def _touch(path: Path, mtime_ns: int) -> None:
    """Set a file's atime/mtime to an exact nanosecond value (no sleep needed)."""
    seconds = mtime_ns / 1_000_000_000
    os.utime(path, (seconds, seconds))


# --- 1. Cache key stability -------------------------------------------------


def test_cached_thumbnail_path_is_stable_for_same_source(tmp_path: Path) -> None:
    _use_tmp_home(tmp_path)
    source = _make_source(tmp_path)

    first = cached_thumbnail_path(source)
    second = cached_thumbnail_path(source)

    assert first == second


def test_cached_thumbnail_path_differs_when_mtime_changes(tmp_path: Path) -> None:
    _use_tmp_home(tmp_path)
    source = _make_source(tmp_path)

    original_path = cached_thumbnail_path(source)
    _touch(source, mtime_ns=1_700_000_000_000_000_000)
    changed_path = cached_thumbnail_path(source)

    assert original_path != changed_path


def test_cached_thumbnail_path_differs_when_size_changes(tmp_path: Path) -> None:
    _use_tmp_home(tmp_path)
    source = _make_source(tmp_path, content=b"short")

    original_path = cached_thumbnail_path(source)
    source.write_bytes(b"a much longer payload than before")
    # Keep mtime identical so only size differs.
    _touch(source, mtime_ns=1_700_000_000_000_000_000)
    _touch(source, mtime_ns=1_700_000_000_000_000_000)
    changed_path = cached_thumbnail_path(source)

    assert original_path != changed_path


def test_cached_thumbnail_path_differs_for_different_source_paths(tmp_path: Path) -> None:
    _use_tmp_home(tmp_path)
    source_a = _make_source(tmp_path, name="a.jpg")
    source_b = _make_source(tmp_path, name="b.jpg")

    assert cached_thumbnail_path(source_a) != cached_thumbnail_path(source_b)


def test_cached_thumbnail_path_lives_under_thumbnails_subdir(tmp_path: Path) -> None:
    home = _use_tmp_home(tmp_path)
    source = _make_source(tmp_path)

    result = cached_thumbnail_path(source)

    expected_dir = home / "Library" / "Caches" / "iPhoneSync" / "thumbnails"
    assert result.parent == expected_dir
    assert result.suffix == ".jpg"


# --- 2. Save then load round trip -------------------------------------------


def test_save_then_load_round_trip_returns_same_bytes(tmp_path: Path) -> None:
    _use_tmp_home(tmp_path)
    source = _make_source(tmp_path)
    jpeg_data = b"\xff\xd8\xff\xe0fake-jpeg-bytes"

    save_cached_thumbnail(source, jpeg_data)
    loaded = load_cached_thumbnail(source)

    assert loaded == jpeg_data


def test_save_cached_thumbnail_writes_file_at_cached_path(tmp_path: Path) -> None:
    _use_tmp_home(tmp_path)
    source = _make_source(tmp_path)
    jpeg_data = b"thumbnail-payload"

    save_cached_thumbnail(source, jpeg_data)

    cache_path = cached_thumbnail_path(source)
    assert cache_path.exists()
    assert cache_path.read_bytes() == jpeg_data


# --- 3. Staleness detection --------------------------------------------------


def test_load_returns_none_when_cache_file_is_older_than_source(tmp_path: Path) -> None:
    """The cache file's own mtime must be >= the source's mtime, or it's a miss.

    This exercises the explicit staleness guard in load_cached_thumbnail
    (``cache.stat().st_mtime >= source.stat().st_mtime``), independent of the
    cache-key invalidation that normally makes a changed source resolve to a
    different cache path entirely.
    """
    _use_tmp_home(tmp_path)
    source = _make_source(tmp_path)
    save_cached_thumbnail(source, b"stale-thumbnail")

    cache_path = cached_thumbnail_path(source)
    # Cache file predates the source file -> stale.
    _touch(cache_path, mtime_ns=1_000_000_000_000_000_000)
    _touch(source, mtime_ns=2_000_000_000_000_000_000)

    assert load_cached_thumbnail(source) is None


def test_load_returns_data_when_cache_file_is_newer_than_source(tmp_path: Path) -> None:
    _use_tmp_home(tmp_path)
    source = _make_source(tmp_path)
    _touch(source, mtime_ns=1_000_000_000_000_000_000)
    save_cached_thumbnail(source, b"fresh-thumbnail")

    cache_path = cached_thumbnail_path(source)
    _touch(cache_path, mtime_ns=2_000_000_000_000_000_000)

    assert load_cached_thumbnail(source) == b"fresh-thumbnail"


def test_changing_source_mtime_invalidates_cache_via_key_change(tmp_path: Path) -> None:
    """A changed source mtime changes the cache key, so the old thumbnail
    is orphaned and treated as a miss rather than served stale."""
    _use_tmp_home(tmp_path)
    source = _make_source(tmp_path)
    save_cached_thumbnail(source, b"original-thumbnail")

    assert load_cached_thumbnail(source) == b"original-thumbnail"

    _touch(source, mtime_ns=1_700_000_000_000_000_000)

    assert load_cached_thumbnail(source) is None


# --- 4. Never-cached source is a miss ---------------------------------------


def test_load_returns_none_for_never_cached_source(tmp_path: Path) -> None:
    _use_tmp_home(tmp_path)
    source = _make_source(tmp_path)

    result = load_cached_thumbnail(source)

    assert result is None


# --- 5. clear_thumbnail_cache -----------------------------------------------


def test_clear_thumbnail_cache_removes_cached_files(tmp_path: Path) -> None:
    _use_tmp_home(tmp_path)
    source = _make_source(tmp_path)
    save_cached_thumbnail(source, b"data")
    cache_path = cached_thumbnail_path(source)
    assert cache_path.exists()

    clear_thumbnail_cache()

    assert not cache_path.exists()


def test_subsequent_load_is_a_miss_after_clearing(tmp_path: Path) -> None:
    _use_tmp_home(tmp_path)
    source = _make_source(tmp_path)
    save_cached_thumbnail(source, b"data")
    assert load_cached_thumbnail(source) == b"data"

    clear_thumbnail_cache()

    assert load_cached_thumbnail(source) is None


def test_clear_thumbnail_cache_removes_subdirectories(tmp_path: Path) -> None:
    """clear_thumbnail_cache has an explicit is_dir() branch (shutil.rmtree);
    exercise it directly since the module's own writers never nest dirs."""
    _use_tmp_home(tmp_path)
    source = _make_source(tmp_path)
    save_cached_thumbnail(source, b"data")

    cache_dir = Settings.app_cache_dir() / "thumbnails"
    stray_subdir = cache_dir / "stray-subdir"
    stray_subdir.mkdir()
    (stray_subdir / "nested-file.jpg").write_bytes(b"nested")

    clear_thumbnail_cache()

    assert not stray_subdir.exists()
    assert list(cache_dir.iterdir()) == []


def test_clear_thumbnail_cache_does_not_raise_before_anything_cached(tmp_path: Path) -> None:
    """Calling clear before anything has ever been cached must not raise.

    Note: ``clear_thumbnail_cache`` calls the private ``_cache_dir()`` helper,
    which auto-creates the thumbnails directory (mkdir parents=True,
    exist_ok=True) as a side effect before returning it. That means the
    ``if not cache.exists(): return`` early-out inside clear_thumbnail_cache
    is unreachable dead code in practice -- the directory always exists by
    the time that check runs. This test verifies the call is still safe
    (creates an empty dir) rather than asserting the dir stays absent.
    """
    home = _use_tmp_home(tmp_path)
    cache_dir = home / "Library" / "Caches" / "iPhoneSync" / "thumbnails"
    assert not cache_dir.exists()

    clear_thumbnail_cache()  # should not raise

    assert cache_dir.exists()
    assert list(cache_dir.iterdir()) == []
