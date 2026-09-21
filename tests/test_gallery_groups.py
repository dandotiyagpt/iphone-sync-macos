"""Tests for month/year gallery grouping."""

from datetime import datetime

from iphone_sync.ui.gallery.media_scanner import MediaItem, MediaKind, build_year_month_navigation, group_by_month_year


def _item(name: str, year: int, month: int) -> MediaItem:
    return MediaItem(
        path=__import__("pathlib").Path(f"/tmp/{name}"),
        filename=name,
        taken_at=datetime(year, month, 15),
        kind=MediaKind.PHOTO,
    )


def test_group_by_month_year():
    items = [
        _item("a.heic", 2026, 8),
        _item("b.heic", 2026, 8),
        _item("c.heic", 2025, 12),
    ]
    groups = group_by_month_year(items)
    assert groups[0][0] == "2026-08"
    assert groups[0][1] == "August 2026"
    assert len(groups[0][2]) == 2


def test_build_year_month_navigation():
    items = [
        _item("a.heic", 2026, 8),
        _item("b.heic", 2025, 12),
    ]
    nav = build_year_month_navigation(items)
    assert nav[0][0] == "2026"
    assert nav[1][0] == "2026-08"
    assert nav[2][0] == "2025"
