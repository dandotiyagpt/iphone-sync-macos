"""Tests for destination path layout."""

from datetime import datetime, timezone
from pathlib import Path

from iphone_sync.models.sync_record import DeviceFile
from iphone_sync.utils.paths import month_folder_name, resolve_dest_path


def _file(name: str = "IMG_0001.HEIC", mtime: float = 1.0) -> DeviceFile:
    return DeviceFile(
        device_path=f"/DCIM/100APPLE/{name}",
        size_bytes=1000,
        mtime=mtime,
        filename=name,
    )


def test_month_folder_uses_name_not_number():
    dt = datetime(2026, 8, 15, tzinfo=timezone.utc)
    assert month_folder_name(dt) == "August"


def test_resolve_dest_path_year_and_month_name():
    dest = Path("C:/Photos")
    taken = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
    path = resolve_dest_path(
        dest,
        "hemant's iPhone",
        "00008140-000111E22229801C",
        _file("IMG_0001.HEIC"),
        organize_by_date=True,
        taken_at=taken,
    )
    assert path.parent.name == "March"
    assert path.parent.parent.name == "2026"
