"""Tests for gallery widget, device switching, filtering, and thumbnail loader."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import QApplication
import pytest

from iphone_sync.ui.gallery.device_discovery import DeviceSource
from iphone_sync.ui.gallery.gallery_widget import GalleryWidget
from iphone_sync.ui.gallery.media_scanner import MediaItem, MediaKind
from iphone_sync.ui.gallery.thumbnail_loader import ThumbnailLoader
from iphone_sync.ui.gallery.thumbnails import (
    create_image_thumbnail,
    create_image_thumbnail_bytes,
)


def test_create_image_thumbnail_bytes_and_pixmap(tmp_path: Path):
    from PIL import Image

    img_path = tmp_path / "test.jpg"
    img = Image.new("RGB", (400, 300), color="blue")
    img.save(img_path)

    # Raw bytes
    data = create_image_thumbnail_bytes(img_path, size=100)
    assert data is not None
    assert len(data) > 0

    # Pixmap
    pixmap = create_image_thumbnail(img_path, size=100)
    assert not pixmap.isNull()
    assert pixmap.width() == 100
    assert pixmap.height() == 100


def test_thumbnail_loader_memory_cache(qapp, tmp_path: Path):
    from PIL import Image
    from datetime import datetime

    img_path = tmp_path / "test2.jpg"
    img = Image.new("RGB", (200, 200), color="red")
    img.save(img_path)

    item = MediaItem(
        path=img_path,
        kind=MediaKind.PHOTO,
        taken_at=datetime.now(),
        filename=img_path.name,
    )

    loader = ThumbnailLoader()
    results = []
    loader.thumbnail_ready.connect(lambda idx, pix: results.append((idx, pix)))

    # First load
    loader.load(0, item)
    loader.wait_done(1000)
    qapp.processEvents()

    # In-memory cache should be populated
    assert img_path in loader._pixmap_cache

    # Second load hits cache synchronously
    initial_len = len(results)
    loader.load(1, item)
    assert len(results) == initial_len + 1
    assert results[-1][0] == 1
    assert not results[-1][1].isNull()
    loader.wait_done(1000)


def test_gallery_widget_filtering_and_device_switching(qapp, tmp_path: Path):
    from PIL import Image

    dest = tmp_path / "iPhone Sync"
    dest.mkdir()

    phone1 = dest / "iPhone 16_1234"
    phone1.mkdir()
    (phone1 / "2026").mkdir()
    p1 = phone1 / "2026" / "IMG_0001.JPG"
    p2 = phone1 / "2026" / "IMG_0002.MOV"
    Image.new("RGB", (100, 100), "green").save(p1)
    p2.write_bytes(b"dummy video")

    phone2 = dest / "iPhone 15_5678"
    phone2.mkdir()
    p3 = phone2 / "IMG_0003.JPG"
    Image.new("RGB", (100, 100), "yellow").save(p3)

    widget = GalleryWidget(dest)

    # Devices discovered
    assert len(widget._device_sources) >= 3  # All, phone1, phone2
    assert len(widget._all_items) == 3

    # Test filtering by kind
    widget._set_filter_kind("video")
    assert len(widget._items) == 1
    assert widget._items[0].kind == MediaKind.VIDEO

    widget._set_filter_kind("photo")
    assert len(widget._items) == 2
    assert all(i.kind == MediaKind.PHOTO for i in widget._items)

    widget._set_filter_kind("all")
    assert len(widget._items) == 3

    # Test search filtering
    widget._search_query = "0002"
    widget._apply_filter()
    assert len(widget._items) == 1
    assert widget._items[0].filename == "IMG_0002.MOV"

    widget._search_query = ""
    widget._apply_filter()
    assert len(widget._items) == 3

    # Test switching device to phone2
    phone2_src = next(s for s in widget._device_sources if "15" in s.name)
    widget._destination = phone2_src.path
    widget.refresh()
    assert len(widget._all_items) == 1
    assert widget._all_items[0].filename == "IMG_0003.JPG"

    widget.stop_preview()
    widget._loader.wait_done(1000)
    widget.deleteLater()
    qapp.processEvents()
