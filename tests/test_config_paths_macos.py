"""Tests for macOS-specific config path resolution and Settings persistence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from iphone_sync.config import Settings


@pytest.fixture(autouse=True)
def _reset_home_override():
    """Ensure no test leaks a home-dir override into another test."""
    Settings.set_home_override(None)
    yield
    Settings.set_home_override(None)


def _use_tmp_home(tmp_path: Path) -> Path:
    Settings.set_home_override(tmp_path)
    return tmp_path


def test_app_data_dir_resolves_under_application_support(tmp_path: Path) -> None:
    home = _use_tmp_home(tmp_path)

    result = Settings.app_data_dir()

    expected = home / "Library" / "Application Support" / "iPhoneSync"
    assert result == expected


def test_app_data_dir_is_auto_created(tmp_path: Path) -> None:
    home = _use_tmp_home(tmp_path)

    result = Settings.app_data_dir()

    assert result.is_dir()
    assert result == home / "Library" / "Application Support" / "iPhoneSync"


def test_app_cache_dir_resolves_under_library_caches(tmp_path: Path) -> None:
    home = _use_tmp_home(tmp_path)

    result = Settings.app_cache_dir()

    expected = home / "Library" / "Caches" / "iPhoneSync"
    assert result == expected


def test_app_cache_dir_is_auto_created(tmp_path: Path) -> None:
    _use_tmp_home(tmp_path)

    result = Settings.app_cache_dir()

    assert result.is_dir()


def test_manifest_db_path_sits_beside_settings_json(tmp_path: Path) -> None:
    _use_tmp_home(tmp_path)

    manifest_path = Settings.manifest_db_path()

    assert manifest_path.parent == Settings.app_data_dir()
    assert manifest_path.name == "manifest.db"


def test_save_load_round_trip_preserves_all_fields(tmp_path: Path) -> None:
    _use_tmp_home(tmp_path)

    original = Settings(
        destination_folder="/tmp/dest",
        device_backup_folder="/tmp/device-backup",
        files_backup_folder="/tmp/files-backup",
        auto_sync_on_plugin=False,
        auto_device_backup_on_plugin=False,
        auto_files_backup_on_plugin=False,
        start_at_login=False,
        minimize_to_tray=False,
        organize_by_date=False,
    )
    original.save()

    loaded = Settings.load()

    assert loaded == original


def test_start_at_login_field_defaults_true(tmp_path: Path) -> None:
    _use_tmp_home(tmp_path)

    settings = Settings()

    assert settings.start_at_login is True


def test_missing_settings_file_returns_defaults(tmp_path: Path) -> None:
    _use_tmp_home(tmp_path)

    settings_path = Settings.app_data_dir() / "settings.json"
    assert not settings_path.exists()

    loaded = Settings.load()

    assert loaded == Settings()


def test_corrupt_json_falls_back_to_defaults(tmp_path: Path) -> None:
    _use_tmp_home(tmp_path)

    settings_path = Settings.app_data_dir() / "settings.json"
    settings_path.write_text("{not valid json!!", encoding="utf-8")

    loaded = Settings.load()

    assert loaded == Settings()


def test_unknown_json_keys_are_silently_ignored_on_load(tmp_path: Path) -> None:
    _use_tmp_home(tmp_path)

    settings_path = Settings.app_data_dir() / "settings.json"
    payload = {
        "destination_folder": "/tmp/dest",
        "totally_unknown_field": "should be ignored",
        "another_bogus_key": 123,
    }
    settings_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = Settings.load()

    assert loaded.destination_folder == "/tmp/dest"
    assert not hasattr(loaded, "totally_unknown_field")
