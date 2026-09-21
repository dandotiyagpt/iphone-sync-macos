"""Tests for SQLite manifest."""

import tempfile
from pathlib import Path

import pytest

from iphone_sync.core.manifest import Manifest
from iphone_sync.models.sync_record import DeviceFile


def _file(path: str, size: int = 1000, mtime: float = 1.0) -> DeviceFile:
    return DeviceFile(
        device_path=path,
        size_bytes=size,
        mtime=mtime,
        filename=path.rsplit("/", 1)[-1],
    )


@pytest.fixture
def manifest(tmp_path: Path) -> Manifest:
    m = Manifest(tmp_path / "manifest.db")
    yield m
    m.close()


def test_should_skip_copied_file_with_same_size(manifest: Manifest):
    f = _file("/DCIM/100APPLE/IMG_0001.HEIC", size=5000)
    manifest.mark_copied("udid1", f, "/dest/IMG_0001.HEIC")
    assert manifest.should_skip("udid1", f) is True


def test_needs_copy_when_size_differs(manifest: Manifest):
    f = _file("/DCIM/100APPLE/IMG_0001.HEIC", size=5000)
    manifest.mark_copied("udid1", f, "/dest/IMG_0001.HEIC")
    changed = _file("/DCIM/100APPLE/IMG_0001.HEIC", size=6000)
    assert manifest.should_skip("udid1", changed) is False


def test_needs_copy_for_new_file(manifest: Manifest):
    f = _file("/DCIM/100APPLE/IMG_0002.HEIC")
    assert manifest.needs_copy("udid1", f) is True


def test_partial_status_not_skipped(manifest: Manifest):
    f = _file("/DCIM/100APPLE/IMG_0003.HEIC", size=3000)
    manifest.mark_partial("udid1", f, "/dest/IMG_0003.HEIC.partial")
    assert manifest.should_skip("udid1", f) is False


def test_count_for_device(manifest: Manifest):
    f1 = _file("/DCIM/100APPLE/A.HEIC")
    f2 = _file("/DCIM/100APPLE/B.MOV")
    manifest.mark_copied("udid1", f1, "/dest/A.HEIC")
    manifest.mark_copied("udid1", f2, "/dest/B.MOV")
    manifest.mark_failed("udid1", _file("/DCIM/100APPLE/C.JPG"), "/dest/C.JPG")
    assert manifest.count_for_device("udid1") == 2
