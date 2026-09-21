"""Tests for Files app backup helpers."""

from pathlib import Path

from iphone_sync.config import Settings
from iphone_sync.core.files_backup_engine import (
    FILES_MEDIA_FOLDERS,
    count_files_under,
    files_backup_root,
)


def test_files_media_folders_include_downloads():
    assert "Downloads" in FILES_MEDIA_FOLDERS
    assert "Books" in FILES_MEDIA_FOLDERS


def test_count_files_under(tmp_path: Path):
    (tmp_path / "a.txt").write_text("x")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.bin").write_bytes(b"yy")
    assert count_files_under(tmp_path) == 2
    assert count_files_under(tmp_path / "missing") == 0


def test_files_backup_root_uses_device_folder(tmp_path: Path):
    settings = Settings(files_backup_folder=str(tmp_path / "files"))
    root = files_backup_root(settings, "hemant's iPhone", "2229801C-AAAA-BBBB")
    assert root.parent == tmp_path / "files"
    assert "hemant" in root.name.lower() or "iphone" in root.name.lower()
    assert "AAAABBBB" in root.name or root.name.endswith("_AAAABBBB")
