"""Application settings persisted under ~/Library/Application Support/iPhoneSync."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

_home_override: Path | None = None


def _home_dir() -> Path:
    """Return the user's home directory, honoring the test-only override."""
    if _home_override is not None:
        return _home_override
    return Path.home()


def _app_data_dir() -> Path:
    path = _home_dir() / "Library" / "Application Support" / "iPhoneSync"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _app_cache_dir() -> Path:
    path = _home_dir() / "Library" / "Caches" / "iPhoneSync"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _default_destination() -> str:
    return str(_home_dir() / "Pictures" / "iPhone Sync")


def _default_device_backup_folder() -> str:
    return str(_home_dir() / "Documents" / "iPhone Device Backups")


def _default_files_backup_folder() -> str:
    return str(_home_dir() / "Documents" / "iPhone Files Backup")


@dataclass
class Settings:
    destination_folder: str = field(default_factory=_default_destination)
    device_backup_folder: str = field(default_factory=_default_device_backup_folder)
    files_backup_folder: str = field(default_factory=_default_files_backup_folder)
    auto_sync_on_plugin: bool = True
    auto_device_backup_on_plugin: bool = True
    auto_files_backup_on_plugin: bool = True
    start_at_login: bool = True
    minimize_to_tray: bool = True
    organize_by_date: bool = True

    @classmethod
    def load(cls) -> Settings:
        path = _app_data_dir() / "settings.json"
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except (json.JSONDecodeError, TypeError):
            return cls()

    def save(self) -> None:
        path = _app_data_dir() / "settings.json"
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @staticmethod
    def manifest_db_path() -> Path:
        return _app_data_dir() / "manifest.db"

    @staticmethod
    def app_data_dir() -> Path:
        return _app_data_dir()

    @staticmethod
    def app_cache_dir() -> Path:
        return _app_cache_dir()

    @staticmethod
    def set_home_override(home_dir: Path | None) -> None:
        """Test-only hook to redirect all path resolution under a fake home."""
        global _home_override
        _home_override = home_dir


def app_cache_dir() -> Path:
    """Standalone accessor re-exported for modules that only need the cache dir."""
    return Settings.app_cache_dir()
