"""Tests for menu bar residency: tray icon, single instance, background start."""

from __future__ import annotations

from pathlib import Path

from iphone_sync.app import _parse_args
from iphone_sync.utils.single_instance import InstanceLock, lock_path
from iphone_sync.utils.tray_icon import make_tray_icon


def test_background_flag_is_parsed() -> None:
    assert _parse_args(["--background"]).background is True
    assert _parse_args([]).background is False


def test_unknown_args_do_not_crash_launch() -> None:
    # macOS can append arguments such as -psn_0_12345 when opening a bundle.
    assert _parse_args(["-psn_0_12345", "--background"]).background is True


def test_tray_icon_renders_for_every_state() -> None:
    for state in ("idle", "connected", "busy", "attention"):
        icon = make_tray_icon(state)
        assert not icon.isNull()


def test_unknown_tray_state_falls_back_to_idle_icon() -> None:
    assert not make_tray_icon("nonsense-state").isNull()


def test_second_instance_cannot_take_the_lock(tmp_path: Path) -> None:
    path = lock_path(tmp_path)

    first = InstanceLock(path)
    second = InstanceLock(path)

    assert first.acquire() is True
    assert second.acquire() is False

    first.release()
    assert second.acquire() is True
    second.release()


def test_lock_file_records_the_holder_pid(tmp_path: Path) -> None:
    import os

    lock = InstanceLock(lock_path(tmp_path))
    assert lock.acquire() is True

    assert lock_path(tmp_path).read_text(encoding="utf-8") == str(os.getpid())
    lock.release()


def test_release_without_acquire_is_safe(tmp_path: Path) -> None:
    InstanceLock(lock_path(tmp_path)).release()
