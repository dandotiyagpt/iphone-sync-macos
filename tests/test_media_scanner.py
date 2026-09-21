"""Tests for gallery media scanning."""

from datetime import datetime
from pathlib import Path

from iphone_sync.ui.gallery.media_scanner import MediaKind, scan_media_folder


def test_live_photo_pairs_image_and_hides_mov(tmp_path: Path):
    folder = tmp_path / "2026" / "August"
    folder.mkdir(parents=True)
    (folder / "IMG_0001.HEIC").write_bytes(b"fake")
    (folder / "IMG_0001.MOV").write_bytes(b"fake-video")
    (folder / "VID_0002.MOV").write_bytes(b"standalone-video")

    items = scan_media_folder(tmp_path)
    kinds = {item.filename: item.kind for item in items}

    assert kinds["IMG_0001.HEIC"] == MediaKind.LIVE_PHOTO
    assert "IMG_0001.MOV" not in kinds
    assert kinds["VID_0002.MOV"] == MediaKind.VIDEO
    assert len(items) == 2

    live = next(i for i in items if i.filename == "IMG_0001.HEIC")
    assert live.live_video_path == folder / "IMG_0001.MOV"
