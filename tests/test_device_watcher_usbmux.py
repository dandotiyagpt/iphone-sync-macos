"""Tests for the macOS usbmuxd Listen-protocol accelerator and DeviceWatcher wiring."""

from __future__ import annotations

import plistlib
import struct
import sys
import types
from dataclasses import dataclass
from typing import Callable

import pytest

import iphone_sync.utils.usbmux_helpers as usbmux_helpers
from iphone_sync.core.device_watcher import (
    DeviceInfo,
    DeviceWatcher,
    UsbMuxPoller,
    _UsbmuxListener,
)

# usbmuxd wire protocol: 16-byte header (length, version, message, tag; all
# little-endian uint32) followed by the plist payload. `length` is the TOTAL
# frame length including the 16-byte header itself.
_HEADER_SIZE = 16
_PROTOCOL_VERSION = 1
_MESSAGE_TYPE_PLIST = 8


def _encode_frame(payload: dict, tag: int = 0) -> bytes:
    body = plistlib.dumps(payload)
    header = struct.pack(
        "<IIII", _HEADER_SIZE + len(body), _PROTOCOL_VERSION, _MESSAGE_TYPE_PLIST, tag
    )
    return header + body


class _FakeSocket:
    """Minimal socket-like fake: .connect() / .sendall() / .recv(n) / .close()."""

    def __init__(self, frames: bytes = b"") -> None:
        self._buffer = frames
        self.connected = False
        self.closed = False
        self.sent: list[bytes] = []

    def connect(self, *_args, **_kwargs) -> None:
        self.connected = True

    def sendall(self, data: bytes) -> None:
        self.sent.append(data)

    def recv(self, n: int) -> bytes:
        chunk = self._buffer[:n]
        self._buffer = self._buffer[n:]
        return chunk

    def close(self) -> None:
        self.closed = True


def _factory_for(fake_socket: _FakeSocket) -> Callable[[], _FakeSocket]:
    return lambda: fake_socket


def test_listen_request_produces_correctly_shaped_frame() -> None:
    listener = _UsbmuxListener(on_attach=lambda: None)

    frame = listener._listen_request()
    header, payload = frame[:_HEADER_SIZE], frame[_HEADER_SIZE:]
    length, version, message, _tag = struct.unpack("<IIII", header)

    assert version == 1
    assert message == 8
    assert length == _HEADER_SIZE + len(payload)
    assert plistlib.loads(payload) == {"MessageType": "Listen"}


def test_attached_frame_triggers_on_attach_once() -> None:
    frame = _encode_frame({"MessageType": "Attached"})
    fake_socket = _FakeSocket(frame)
    calls: list[None] = []

    listener = _UsbmuxListener(
        on_attach=lambda: calls.append(None),
        connect_factory=_factory_for(fake_socket),
    )
    listener.run()

    assert len(calls) == 1


def test_detached_frame_does_not_trigger_on_attach() -> None:
    frames = _encode_frame({"MessageType": "Attached"}) + _encode_frame(
        {"MessageType": "Detached"}
    )
    fake_socket = _FakeSocket(frames)
    calls: list[None] = []

    listener = _UsbmuxListener(
        on_attach=lambda: calls.append(None),
        connect_factory=_factory_for(fake_socket),
    )
    listener.run()

    assert len(calls) == 1


def test_truncated_frame_exits_gracefully_without_raising() -> None:
    body = plistlib.dumps({"MessageType": "Attached"})
    # Claim a longer length than what's actually available (but still under
    # the sanity cap), so the header parses fine but the payload read fails.
    truncated = struct.pack("<IIII", _HEADER_SIZE + len(body) + 100, 1, 8, 0) + body
    fake_socket = _FakeSocket(truncated)
    calls: list[None] = []

    listener = _UsbmuxListener(
        on_attach=lambda: calls.append(None),
        connect_factory=_factory_for(fake_socket),
    )

    listener.run()  # must not raise

    assert calls == []


def test_oversized_length_prefix_is_rejected_without_large_read() -> None:
    """A hostile/corrupted length field must never trigger a huge allocation."""
    huge_payload_length = 50 * 1024 * 1024
    header = struct.pack("<IIII", _HEADER_SIZE + huge_payload_length, 1, 8, 0)
    fake_socket = _FakeSocket(header)  # no payload bytes follow
    calls: list[None] = []

    listener = _UsbmuxListener(
        on_attach=lambda: calls.append(None),
        connect_factory=_factory_for(fake_socket),
    )

    recv_sizes: list[int] = []
    original_recv_exact = listener._recv_exact

    def _tracking_recv_exact(size: int):
        recv_sizes.append(size)
        return original_recv_exact(size)

    listener._recv_exact = _tracking_recv_exact  # type: ignore[method-assign]

    listener.run()  # must not raise and must not attempt a 50MB read

    assert calls == []
    assert recv_sizes == [_HEADER_SIZE]


def test_empty_recv_exits_loop_gracefully() -> None:
    fake_socket = _FakeSocket(b"")
    calls: list[None] = []

    listener = _UsbmuxListener(
        on_attach=lambda: calls.append(None),
        connect_factory=_factory_for(fake_socket),
    )

    listener.run()  # must not raise

    assert calls == []


def test_connect_refused_does_not_raise() -> None:
    def _raising_factory() -> _FakeSocket:
        raise ConnectionRefusedError("no usbmuxd")

    listener = _UsbmuxListener(
        on_attach=lambda: None,
        connect_factory=_raising_factory,
    )

    listener.run()  # must not raise


def test_file_not_found_does_not_raise() -> None:
    def _raising_factory() -> _FakeSocket:
        raise FileNotFoundError("/var/run/usbmuxd missing")

    listener = _UsbmuxListener(
        on_attach=lambda: None,
        connect_factory=_raising_factory,
    )

    listener.run()  # must not raise


def test_device_watcher_stop_is_safe_without_start() -> None:
    watcher = DeviceWatcher()

    watcher.stop()  # must not raise / AttributeError


def test_device_watcher_wires_device_ready_to_device_connected() -> None:
    watcher = DeviceWatcher()
    received: list[DeviceInfo] = []
    watcher.device_connected.connect(lambda info: received.append(info))

    info = DeviceInfo(udid="abc123", name="Test iPhone")
    watcher._poller.device_ready.emit(info)

    assert received == [info]


@pytest.mark.skipif(sys.platform != "darwin", reason="requires a real AF_UNIX socket")
def test_real_socket_module_import_only_on_darwin() -> None:
    import socket

    assert hasattr(socket, "AF_UNIX")


# ---------------------------------------------------------------------------
# UsbMuxPoller._poll_once coverage
# ---------------------------------------------------------------------------


@dataclass
class _FakeUsbmuxDevice:
    serial: str
    connection_type: str


class _FakeLockdown:
    def __init__(self, udid: str, name: str) -> None:
        self.udid = udid
        self.all_values = {"DeviceName": name}


def _install_fake_pymobiledevice3_exceptions(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[type[Exception], type[Exception]]:
    """Stub `pymobiledevice3.exceptions` in sys.modules.

    ``_poll_once`` lazily does ``from pymobiledevice3.exceptions import
    NoDeviceConnectedError, PyMobileDevice3Exception`` on every call. The
    real package isn't installed in every dev/CI environment, so we inject
    minimal stand-in exception classes via sys.modules for the duration of
    the test (monkeypatch restores the previous state automatically).
    """

    class _NoDeviceConnectedError(Exception):
        pass

    class _PyMobileDevice3Exception(Exception):
        pass

    fake_exceptions_module = types.ModuleType("pymobiledevice3.exceptions")
    fake_exceptions_module.NoDeviceConnectedError = _NoDeviceConnectedError  # type: ignore[attr-defined]
    fake_exceptions_module.PyMobileDevice3Exception = _PyMobileDevice3Exception  # type: ignore[attr-defined]

    fake_package = types.ModuleType("pymobiledevice3")
    fake_package.exceptions = fake_exceptions_module  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "pymobiledevice3", fake_package)
    monkeypatch.setitem(sys.modules, "pymobiledevice3.exceptions", fake_exceptions_module)

    return _NoDeviceConnectedError, _PyMobileDevice3Exception


def test_poll_once_emits_device_ready_for_new_device(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_pymobiledevice3_exceptions(monkeypatch)
    device = _FakeUsbmuxDevice(serial="S1", connection_type="USB")
    lockdown = _FakeLockdown(udid="U1", name="Hemant's iPhone")

    monkeypatch.setattr(usbmux_helpers, "list_usbmux_devices", lambda: [device])
    monkeypatch.setattr(usbmux_helpers, "create_lockdown_sync", lambda serial=None: lockdown)

    poller = UsbMuxPoller()
    ready: list[DeviceInfo] = []
    poller.device_ready.connect(lambda info: ready.append(info))

    poller._poll_once()

    assert ready == [DeviceInfo(udid="U1", name="Hemant's iPhone")]
    assert poller._known == {"U1": DeviceInfo(udid="U1", name="Hemant's iPhone")}


def test_poll_once_emits_device_lost_for_disappeared_device(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_pymobiledevice3_exceptions(monkeypatch)
    monkeypatch.setattr(usbmux_helpers, "list_usbmux_devices", lambda: [])
    monkeypatch.setattr(usbmux_helpers, "create_lockdown_sync", lambda serial=None: None)

    poller = UsbMuxPoller()
    poller._known = {"U1": DeviceInfo(udid="U1", name="Old iPhone")}
    lost: list[str] = []
    poller.device_lost.connect(lambda udid: lost.append(udid))

    poller._poll_once()

    assert lost == ["U1"]
    assert poller._known == {}


def test_poll_once_emits_device_not_ready_when_no_device_connected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    no_device_error, _pmd3_exc = _install_fake_pymobiledevice3_exceptions(monkeypatch)
    device = _FakeUsbmuxDevice(serial="S1", connection_type="USB")
    monkeypatch.setattr(usbmux_helpers, "list_usbmux_devices", lambda: [device])

    def _raise_no_device(serial: str | None = None):
        raise no_device_error("no device connected")

    monkeypatch.setattr(usbmux_helpers, "create_lockdown_sync", _raise_no_device)

    poller = UsbMuxPoller()
    reasons: list[str] = []
    poller.device_not_ready.connect(lambda reason: reasons.append(reason))

    poller._poll_once()

    assert reasons == ["No device connected"]


def test_poll_once_emits_trust_prompt_for_trust_related_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _no_device_error, pmd3_exc = _install_fake_pymobiledevice3_exceptions(monkeypatch)
    device = _FakeUsbmuxDevice(serial="S1", connection_type="USB")
    monkeypatch.setattr(usbmux_helpers, "list_usbmux_devices", lambda: [device])

    def _raise_trust(serial: str | None = None):
        raise pmd3_exc("Please Trust This Computer to continue pairing")

    monkeypatch.setattr(usbmux_helpers, "create_lockdown_sync", _raise_trust)

    poller = UsbMuxPoller()
    reasons: list[str] = []
    poller.device_not_ready.connect(lambda reason: reasons.append(reason))

    poller._poll_once()

    assert reasons == ["Unlock your iPhone and tap 'Trust This Computer'"]


def test_poll_once_emits_raw_message_for_non_trust_pymobiledevice3_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _no_device_error, pmd3_exc = _install_fake_pymobiledevice3_exceptions(monkeypatch)
    device = _FakeUsbmuxDevice(serial="S1", connection_type="USB")
    monkeypatch.setattr(usbmux_helpers, "list_usbmux_devices", lambda: [device])

    def _raise_other(serial: str | None = None):
        raise pmd3_exc("lockdown handshake failed")

    monkeypatch.setattr(usbmux_helpers, "create_lockdown_sync", _raise_other)

    poller = UsbMuxPoller()
    reasons: list[str] = []
    poller.device_not_ready.connect(lambda reason: reasons.append(reason))

    poller._poll_once()

    assert reasons == ["lockdown handshake failed"]


def test_poll_once_emits_raw_message_for_generic_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_pymobiledevice3_exceptions(monkeypatch)
    device = _FakeUsbmuxDevice(serial="S1", connection_type="USB")
    monkeypatch.setattr(usbmux_helpers, "list_usbmux_devices", lambda: [device])

    def _raise_generic(serial: str | None = None):
        raise RuntimeError("something else broke")

    monkeypatch.setattr(usbmux_helpers, "create_lockdown_sync", _raise_generic)

    poller = UsbMuxPoller()
    reasons: list[str] = []
    poller.device_not_ready.connect(lambda reason: reasons.append(reason))

    poller._poll_once()

    assert reasons == ["something else broke"]


def test_poll_once_treats_list_devices_failure_as_no_devices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_pymobiledevice3_exceptions(monkeypatch)

    def _raise_list_failure():
        raise OSError("usbmuxd socket unavailable")

    monkeypatch.setattr(usbmux_helpers, "list_usbmux_devices", _raise_list_failure)

    poller = UsbMuxPoller()
    poller._known = {"U1": DeviceInfo(udid="U1", name="Old iPhone")}
    lost: list[str] = []
    poller.device_lost.connect(lambda udid: lost.append(udid))

    poller._poll_once()  # must not raise

    assert lost == ["U1"]
    assert poller._known == {}
