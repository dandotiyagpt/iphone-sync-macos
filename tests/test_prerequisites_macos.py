"""Tests for macOS Apple device prerequisite checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from iphone_sync.utils import prerequisites


def test_is_usbmuxd_available_returns_false_for_missing_socket(tmp_path: Path) -> None:
    missing_socket = tmp_path / "usbmuxd.sock"

    assert prerequisites.is_usbmuxd_available(missing_socket) is False


def test_is_usbmuxd_available_returns_true_for_existing_path(tmp_path: Path) -> None:
    fake_socket = tmp_path / "usbmuxd.sock"
    fake_socket.write_text("")

    assert prerequisites.is_usbmuxd_available(fake_socket) is True


def test_prerequisite_status_reports_not_running_when_socket_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing_socket = tmp_path / "usbmuxd.sock"
    monkeypatch.setattr(
        prerequisites, "_DEFAULT_SOCKET_PATH", missing_socket
    )

    ok, message = prerequisites.prerequisite_status()

    assert ok is False
    assert "not running" in message.lower()


def test_prerequisite_status_ready_when_socket_present_and_devices_listable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_socket = tmp_path / "usbmuxd.sock"
    fake_socket.write_text("")
    monkeypatch.setattr(prerequisites, "_DEFAULT_SOCKET_PATH", fake_socket)
    monkeypatch.setattr(prerequisites, "can_list_usb_devices", lambda: True)

    ok, message = prerequisite_status_result = prerequisites.prerequisite_status()

    assert ok is True
    assert message == "Apple device support is ready."
    assert prerequisite_status_result == (True, "Apple device support is ready.")


def test_prerequisite_status_not_responding_when_listing_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_socket = tmp_path / "usbmuxd.sock"
    fake_socket.write_text("")
    monkeypatch.setattr(prerequisites, "_DEFAULT_SOCKET_PATH", fake_socket)

    def _raise() -> bool:
        raise RuntimeError("usbmuxd connection refused")

    monkeypatch.setattr(prerequisites, "can_list_usb_devices", _raise)

    ok, message = prerequisites.prerequisite_status()

    assert ok is False
    assert "not responding" in message.lower()


def test_prerequisite_status_ready_when_no_device_connected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty device list is expected/fine, not a failure condition."""
    fake_socket = tmp_path / "usbmuxd.sock"
    fake_socket.write_text("")
    monkeypatch.setattr(prerequisites, "_DEFAULT_SOCKET_PATH", fake_socket)
    monkeypatch.setattr(prerequisites, "can_list_usb_devices", lambda: True)

    ok, message = prerequisites.prerequisite_status()

    assert ok is True
    assert message == "Apple device support is ready."


# --- can_list_usb_devices: exercise the real try/except-to-bool conversion ---
#
# The tests above all monkeypatch `can_list_usb_devices` itself, so its own
# body (the asyncio.run(...) call plus the try/except) is never executed.
# These tests instead monkeypatch the lower-level `list_usbmux_devices_async`
# that `can_list_usb_devices` wraps, so the real function body runs.


def test_can_list_usb_devices_returns_true_when_listing_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A successful listing call -- even with zero devices -- means True."""

    async def _fake_list_usbmux_devices_async() -> list[object]:
        return []

    monkeypatch.setattr(
        prerequisites,
        "list_usbmux_devices_async",
        _fake_list_usbmux_devices_async,
    )

    assert prerequisites.can_list_usb_devices() is True


def test_can_list_usb_devices_returns_true_when_devices_are_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-empty device list also means True (result value itself is unused)."""

    async def _fake_list_usbmux_devices_async() -> list[str]:
        return ["iPhone-Serial-1234"]

    monkeypatch.setattr(
        prerequisites,
        "list_usbmux_devices_async",
        _fake_list_usbmux_devices_async,
    )

    assert prerequisites.can_list_usb_devices() is True


def test_can_list_usb_devices_returns_false_when_listing_raises_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The generic except Exception clause must catch and swallow the error."""

    async def _raising_list_usbmux_devices_async() -> list[object]:
        raise RuntimeError("usbmuxd connection refused")

    monkeypatch.setattr(
        prerequisites,
        "list_usbmux_devices_async",
        _raising_list_usbmux_devices_async,
    )

    assert prerequisites.can_list_usb_devices() is False


def test_can_list_usb_devices_returns_false_when_listing_raises_os_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A different exception type (OSError) is caught the same way as any other."""

    async def _raising_list_usbmux_devices_async() -> list[object]:
        raise OSError("socket unavailable")

    monkeypatch.setattr(
        prerequisites,
        "list_usbmux_devices_async",
        _raising_list_usbmux_devices_async,
    )

    assert prerequisites.can_list_usb_devices() is False


def test_can_list_usb_devices_does_not_propagate_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The function must never raise -- callers rely on a plain bool return."""

    async def _raising_list_usbmux_devices_async() -> list[object]:
        raise ValueError("unexpected protocol response")

    monkeypatch.setattr(
        prerequisites,
        "list_usbmux_devices_async",
        _raising_list_usbmux_devices_async,
    )

    try:
        result = prerequisites.can_list_usb_devices()
    except Exception as exc:  # pragma: no cover - failure path, not expected
        pytest.fail(f"can_list_usb_devices() propagated an exception: {exc}")

    assert result is False
