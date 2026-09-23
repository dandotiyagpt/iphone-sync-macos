"""Tests for compact TrayPopover menu-bar companion widget."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication

from iphone_sync.config import Settings
from iphone_sync.ui.tray_popover import StorageBarWidget, TrayPopover


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_storage_bar_widget_set_data(qapp) -> None:
    widget = StorageBarWidget()
    widget.set_storage_data(photos_gb=100.0, files_gb=20.0, whatsapp_gb=10.0, total_gb=256.0)
    assert len(widget._segments) == 4
    # Ensure ratios sum approximately to 1.0
    total_ratio = sum(s[1] for s in widget._segments)
    assert pytest.approx(total_ratio, rel=1e-2) == 1.0


def test_tray_popover_init_and_signals(qapp) -> None:
    settings = Settings()
    popover = TrayPopover(settings)

    sync_called = []
    gallery_called = []
    settings_called = []
    dashboard_called = []

    popover.sync_requested.connect(lambda: sync_called.append(True))
    popover.gallery_requested.connect(lambda: gallery_called.append(True))
    popover.settings_requested.connect(lambda: settings_called.append(True))
    popover.open_dashboard_requested.connect(lambda: dashboard_called.append(True))

    popover.update_device("iPhone 16 Pro", connected=True, battery=94, is_charging=True)
    assert "iPhone 16 Pro" in popover._device_title.text()
    assert "94%" in popover._battery_pill.text()
    assert popover._sync_btn.isEnabled()

    popover.update_sync_progress("Syncing 10 photos", percent=50, is_active=True)
    assert popover._progress.value() == 50
    assert "Syncing" in popover._sync_btn.text()

    popover.update_storage(120.0, 30.0, 15.0, 256.0)
    assert "256 GB" in popover._storage_total_label.text()

    # Enable sync button by finishing active sync
    popover.update_sync_progress("Ready to sync", percent=100, is_active=False)

    # Trigger action buttons
    popover._sync_btn.click()
    popover._gallery_btn.click()
    popover._pref_btn.click()
    popover._dashboard_link.click()

    assert sync_called == [True]
    assert gallery_called == [True]
    assert settings_called == [True]
    assert dashboard_called == [True]


def test_tray_popover_offline_state(qapp) -> None:
    settings = Settings()
    popover = TrayPopover(settings)
    popover.update_device(None, connected=False)

    assert "Disconnected" in popover._device_title.text()
    assert "Offline" in popover._battery_pill.text()
    assert not popover._sync_btn.isEnabled()


def test_tray_popover_theme_switch(qapp) -> None:
    settings = Settings()
    popover = TrayPopover(settings)

    settings.theme = "midnight_navy"
    popover.apply_theme()
    assert popover._settings.theme == "midnight_navy"

    settings.theme = "cupertino_light"
    popover.apply_theme()
    assert popover._settings.theme == "cupertino_light"
