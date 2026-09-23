"""Tests for theme engine and palette stylesheets."""

from __future__ import annotations

from iphone_sync.ui.theme import (
    APP_STYLESHEET,
    THEMES,
    ThemePalette,
    get_theme,
    get_theme_stylesheet,
    list_themes,
)


def test_theme_palettes_exist() -> None:
    expected = {"obsidian_dark", "midnight_navy", "cupertino_light", "titanium_amber"}
    assert set(THEMES.keys()) == expected


def test_get_theme_defaults_to_obsidian_dark() -> None:
    theme = get_theme("non_existent_theme")
    assert theme.id == "obsidian_dark"
    assert theme.display_name == "Apple Dark Obsidian"

    theme_none = get_theme(None)
    assert theme_none.id == "obsidian_dark"


def test_list_themes_returns_all_metadata() -> None:
    themes = list_themes()
    assert len(themes) == 4
    ids = [t[0] for t in themes]
    assert "obsidian_dark" in ids
    assert "midnight_navy" in ids
    assert "cupertino_light" in ids
    assert "titanium_amber" in ids


def test_get_theme_stylesheet_contains_theme_colors() -> None:
    obsidian_css = get_theme_stylesheet("obsidian_dark")
    assert "#121316" in obsidian_css
    assert "QPushButton" in obsidian_css

    navy_css = get_theme_stylesheet("midnight_navy")
    assert "#0D1424" in navy_css
    assert "#2F81F7" in navy_css

    light_css = get_theme_stylesheet("cupertino_light")
    assert "#F5F5F7" in light_css
    assert "#FFFFFF" in light_css

    amber_css = get_theme_stylesheet("titanium_amber")
    assert "#1E1E1E" in amber_css
    assert "#FF9F0A" in amber_css


def test_app_stylesheet_backwards_compatible() -> None:
    assert isinstance(APP_STYLESHEET, str)
    assert len(APP_STYLESHEET) > 100
    assert "#121316" in APP_STYLESHEET
