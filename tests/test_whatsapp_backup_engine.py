"""Tests for the WhatsApp backup entity (folder isolation + worker wiring)."""

from __future__ import annotations

from pathlib import Path

import pytest

from iphone_sync.config import Settings
from iphone_sync.core.whatsapp_backup_engine import (
    WhatsAppBackupEngine,
    WhatsAppBackupResult,
    WhatsAppBackupWorker,
)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        destination_folder=str(tmp_path / "photos"),
        files_backup_folder=str(tmp_path / "files"),
        whatsapp_backup_folder=str(tmp_path / "whatsapp"),
    )


def test_worker_writes_into_the_whatsapp_folder(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    worker = WhatsAppBackupWorker(settings, "UDID", mode="backup")

    assert worker._backup_root() == tmp_path / "whatsapp"


def test_whatsapp_folder_is_separate_from_photos_and_files(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    assert settings.whatsapp_backup_folder != settings.destination_folder
    assert settings.whatsapp_backup_folder != settings.files_backup_folder


def test_engine_starts_idle(tmp_path: Path) -> None:
    engine = WhatsAppBackupEngine(_settings(tmp_path))

    assert engine.is_running is False
    # Cancelling with no worker must stay a no-op, not raise.
    engine.cancel()


def test_result_defaults_are_unsuccessful() -> None:
    result = WhatsAppBackupResult()

    assert result.success is False
    assert result.info is None
    assert result.errors == []


@pytest.mark.parametrize("mode", ["backup", "restore", "enable_encryption"])
def test_supported_worker_modes_construct(tmp_path: Path, mode: str) -> None:
    worker = WhatsAppBackupWorker(_settings(tmp_path), "UDID", mode=mode)

    assert worker._mode == mode
