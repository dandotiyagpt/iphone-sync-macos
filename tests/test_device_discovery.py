"""Tests for iPhone device discovery under sync destination and backup roots."""

from __future__ import annotations

from pathlib import Path
import pytest

from iphone_sync.ui.gallery.device_discovery import (
    DeviceSource,
    _count_media_files,
    discover_device_sources,
)


def test_device_source_display_label():
    src = DeviceSource(
        id="dev1",
        name="Jyoti’s iPhone 16",
        raw_name="Jyoti’s iPhone 16_2EF2801C",
        path=Path("/tmp/fake"),
        item_count=856,
        is_all=False,
    )
    assert "Jyoti’s iPhone 16" in src.display_label
    assert "856" in src.display_label


def test_discover_device_sources_multiple_iphones(tmp_path: Path):
    dest = tmp_path / "iPhone Sync"
    dest.mkdir()

    iphone1 = dest / "Jyoti’s iPhone 16_2EF2801C"
    iphone1.mkdir()
    (iphone1 / "2026" / "02 - February").mkdir(parents=True)
    (iphone1 / "2026" / "02 - February" / "photo1.jpg").write_bytes(b"image")
    (iphone1 / "2026" / "02 - February" / "photo2.heic").write_bytes(b"image")

    iphone2 = dest / "hemant’s iPhone_2229801C"
    iphone2.mkdir()
    (iphone2 / "2025" / "12 - December").mkdir(parents=True)
    (iphone2 / "2025" / "12 - December" / "photo3.mov").write_bytes(b"video")

    sources = discover_device_sources(dest)

    # Should have "All iPhones" first, then both phones
    assert len(sources) == 3
    assert sources[0].id == "all"
    assert sources[0].is_all is True
    assert sources[0].item_count == 3

    names = [s.name for s in sources]
    assert "All iPhones" in names
    assert "Jyoti’s iPhone 16" in names
    assert "hemant’s iPhone" in names


def test_discover_device_sources_single_device(tmp_path: Path):
    dest = tmp_path / "iPhone Sync"
    dest.mkdir()

    iphone1 = dest / "Single iPhone"
    iphone1.mkdir()
    (iphone1 / "photo1.jpg").write_bytes(b"image")

    sources = discover_device_sources(dest)
    assert len(sources) == 1
    assert sources[0].name == "Single iPhone"
    assert sources[0].item_count == 1


def test_discover_device_sources_flat_library(tmp_path: Path):
    dest = tmp_path / "Photos"
    dest.mkdir()
    (dest / "photo1.jpg").write_bytes(b"image")
    (dest / "photo2.png").write_bytes(b"image")

    sources = discover_device_sources(dest)
    assert len(sources) == 1
    assert sources[0].id == "library"
    assert sources[0].item_count == 2
