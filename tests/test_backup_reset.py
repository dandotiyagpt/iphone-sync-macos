"""Tests for backup reset."""

from pathlib import Path

from iphone_sync.core.backup_reset import count_backup_files, reset_backup
from iphone_sync.core.manifest import Manifest
from iphone_sync.models.sync_record import DeviceFile


def _file(path: str) -> DeviceFile:
    return DeviceFile(
        device_path=path,
        size_bytes=100,
        mtime=1.0,
        filename=path.rsplit("/", 1)[-1],
    )


def test_count_backup_files(tmp_path: Path):
    folder = tmp_path / "backup"
    folder.mkdir()
    (folder / "a.jpg").write_bytes(b"x")
    (folder / "device" / "2026").mkdir(parents=True)
    (folder / "device" / "2026" / "b.heic").write_bytes(b"y")

    assert count_backup_files(folder) == 2
    assert count_backup_files(tmp_path / "missing") == 0


def test_reset_backup_clears_files_and_manifest(tmp_path: Path):
    dest = tmp_path / "backup"
    device_dir = dest / "iPhone_ABCD1234" / "2026" / "August"
    device_dir.mkdir(parents=True)
    (device_dir / "IMG_0001.HEIC").write_bytes(b"photo")

    manifest = Manifest(tmp_path / "manifest.db")
    manifest.mark_copied("udid1", _file("/DCIM/IMG_0001.HEIC"), str(device_dir / "IMG_0001.HEIC"))
    assert manifest.count_for_device("udid1") == 1

    result = reset_backup(dest, manifest)

    assert result.files_deleted == 1
    assert result.manifest_cleared is True
    assert result.errors == []
    assert count_backup_files(dest) == 0
    assert manifest.total_copied_count() == 0
    assert not list(dest.iterdir()) if dest.exists() else True
