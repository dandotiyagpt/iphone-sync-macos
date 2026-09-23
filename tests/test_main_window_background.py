"""Behavioral tests for the resident menu bar window."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QCloseEvent

from iphone_sync.config import Settings
from iphone_sync.ui.main_window import MainWindow


@pytest.fixture
def window(tmp_path: Path, qapp, monkeypatch):
    Settings.set_home_override(tmp_path)
    # The real watcher polls usbmuxd in a thread; not wanted under test.
    monkeypatch.setattr(
        "iphone_sync.core.device_watcher.DeviceWatcher.start", lambda self: None
    )
    monkeypatch.setattr(
        "iphone_sync.core.device_watcher.DeviceWatcher.stop", lambda self: None
    )
    monkeypatch.setattr(
        "iphone_sync.ui.main_window.prerequisite_status", lambda: (True, "ready")
    )

    settings = Settings(
        destination_folder=str(tmp_path / "photos"),
        files_backup_folder=str(tmp_path / "files"),
        whatsapp_backup_folder=str(tmp_path / "whatsapp"),
    )
    win = MainWindow(settings)
    yield win
    win.close()
    Settings.set_home_override(None)


def test_start_hidden_keeps_window_closed(window) -> None:
    window.start_hidden()

    assert window.isVisible() is False


def test_closing_the_window_does_not_stop_the_agent(window, monkeypatch) -> None:
    stopped: list[bool] = []
    monkeypatch.setattr(
        window._device_watcher, "stop", lambda: stopped.append(True)
    )
    window.show()

    event = QCloseEvent()
    window.closeEvent(event)

    assert event.isAccepted() is False  # close was refused
    assert window.isVisible() is False  # hidden instead
    assert stopped == []  # watcher still running


def test_closing_quits_when_background_mode_is_off(window, monkeypatch) -> None:
    stopped: list[bool] = []
    monkeypatch.setattr(window._device_watcher, "stop", lambda: stopped.append(True))
    window._settings.run_in_background = False

    event = QCloseEvent()
    window.closeEvent(event)

    assert event.isAccepted() is True
    assert stopped == [True]


def test_whatsapp_is_its_own_backup_entity(window) -> None:
    assert window._whatsapp_engine is not None
    assert window._files_backup_engine is not window._whatsapp_engine
    assert "WhatsApp" in window._whatsapp_backup_btn.toolTip()


def test_whatsapp_button_text_is_not_clipped(window) -> None:
    button = window._whatsapp_backup_btn
    needed = button.fontMetrics().horizontalAdvance(button.text())

    assert button.minimumWidth() >= needed


def test_tray_menu_exposes_separate_backup_actions(window) -> None:
    labels = [action.text() for action in window._tray_menu.actions()]

    assert "Sync Photos Now" in labels
    assert "Backup Files Now" in labels
    assert "Backup WhatsApp Now" in labels
    assert "Quit iPhone Sync" in labels


def test_tray_state_updates_tooltip_and_status_entry(window) -> None:
    window._set_tray_state("busy", "Backing up WhatsApp… 40%")

    assert window._tray_status_action.text() == "Backing up WhatsApp… 40%"
    assert "Backing up WhatsApp" in window._tray.toolTip()
