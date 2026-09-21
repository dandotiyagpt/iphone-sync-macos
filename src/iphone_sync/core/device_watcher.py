"""USB device arrival detection and usbmux polling (macOS)."""

from __future__ import annotations

import plistlib
import socket
import struct
import time
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QObject, QThread, Signal

_DEFAULT_USBMUXD_SOCKET_PATH = "/var/run/usbmuxd"

# usbmuxd wire protocol: a fixed 16-byte header (all fields little-endian
# uint32) followed by a plist payload when using the plist protocol.
# struct usbmuxd_header { uint32_t length; uint32_t version; uint32_t message; uint32_t tag; }
_USBMUX_HEADER_SIZE = 16
_USBMUX_PROTOCOL_VERSION = 1
_USBMUX_MESSAGE_TYPE_PLIST = 8
_USBMUX_LISTEN_TAG = 1

# Real Attached/Detached/Listen response frames are tiny (a small plist).
# Reject any frame claiming a payload larger than this to avoid a
# corrupted/hostile response forcing a huge allocation.
_MAX_FRAME_PAYLOAD_SIZE = 1_048_576  # 1 MiB


@dataclass
class DeviceInfo:
    udid: str
    name: str


class UsbMuxPoller(QThread):
    """Poll usbmux for connected/paired iPhones."""

    device_ready = Signal(object)  # DeviceInfo
    device_lost = Signal(str)  # udid
    device_not_ready = Signal(str)  # reason

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._running = True
        self._known: dict[str, DeviceInfo] = {}
        self._poll_interval = 2.0

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        while self._running:
            self._poll_once()
            time.sleep(self._poll_interval)

    def poll_now(self) -> None:
        self._poll_once()

    def _poll_once(self) -> None:
        from pymobiledevice3.exceptions import NoDeviceConnectedError, PyMobileDevice3Exception

        from iphone_sync.utils.usbmux_helpers import create_lockdown_sync, list_usbmux_devices

        current: dict[str, DeviceInfo] = {}

        try:
            devices = list_usbmux_devices()
        except Exception:
            devices = []

        usb_serials = {d.serial for d in devices if d.connection_type == "USB"}

        for serial in usb_serials:
            try:
                lockdown = create_lockdown_sync(serial=serial)
                name = lockdown.all_values.get("DeviceName", "iPhone")
                info = DeviceInfo(udid=lockdown.udid, name=name)
                current[info.udid] = info

                if info.udid not in self._known:
                    self.device_ready.emit(info)

            except NoDeviceConnectedError:
                self.device_not_ready.emit("No device connected")
            except PyMobileDevice3Exception as exc:
                msg = str(exc).lower()
                if "trust" in msg or "pair" in msg or "password" in msg:
                    self.device_not_ready.emit(
                        "Unlock your iPhone and tap 'Trust This Computer'"
                    )
                else:
                    self.device_not_ready.emit(str(exc))
            except Exception as exc:
                self.device_not_ready.emit(str(exc))

        for udid in list(self._known.keys()):
            if udid not in current:
                self.device_lost.emit(udid)

        self._known = current


class _UsbmuxListener(QThread):
    """Low-latency accelerator: subscribes to usbmuxd's real-time Listen protocol.

    Connects to the usbmuxd unix domain socket, sends a ``Listen`` request, and
    reads length-prefixed plist frames in a loop. On an ``Attached`` message it
    invokes ``on_attach`` so the caller can trigger an immediate poll instead of
    waiting for the 2-second ``UsbMuxPoller`` interval. The poller remains the
    safety net, so any socket failure here is swallowed and the thread simply
    stops.
    """

    def __init__(
        self,
        on_attach: Callable[[], None],
        socket_path: str = _DEFAULT_USBMUXD_SOCKET_PATH,
        connect_factory: Callable[[], object] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._on_attach = on_attach
        self._socket_path = socket_path
        self._connect_factory = connect_factory
        self._running = True
        self._sock = None

    def stop(self) -> None:
        self._running = False
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass  # best-effort cleanup

    def run(self) -> None:
        try:
            self._sock = self._connect()
            self._sock.sendall(self._listen_request())
            self._read_loop()
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            return  # UsbMuxPoller's 2s poll is the fallback
        except Exception:
            return  # never crash the accelerator thread

    def _connect(self):
        if self._connect_factory is not None:
            sock = self._connect_factory()
            sock.connect(self._socket_path)
            return sock

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(self._socket_path)
        return sock

    def _listen_request(self) -> bytes:
        body = plistlib.dumps({"MessageType": "Listen"})
        header = struct.pack(
            "<IIII",
            _USBMUX_HEADER_SIZE + len(body),
            _USBMUX_PROTOCOL_VERSION,
            _USBMUX_MESSAGE_TYPE_PLIST,
            _USBMUX_LISTEN_TAG,
        )
        return header + body

    def _read_loop(self) -> None:
        while self._running:
            frame = self._read_frame()
            if frame is None:
                return
            self._handle_frame(frame)

    def _read_frame(self) -> dict | None:
        header_bytes = self._recv_exact(_USBMUX_HEADER_SIZE)
        if header_bytes is None:
            return None

        length, _version, _message, _tag = struct.unpack("<IIII", header_bytes)
        payload_length = length - _USBMUX_HEADER_SIZE
        if payload_length < 0 or payload_length > _MAX_FRAME_PAYLOAD_SIZE:
            return None  # malformed or hostile frame; stop the loop gracefully

        body = self._recv_exact(payload_length)
        if body is None:
            return None

        try:
            return plistlib.loads(body)
        except Exception:
            return None

    def _recv_exact(self, size: int) -> bytes | None:
        if size == 0:
            return b""

        chunks = bytearray()
        while len(chunks) < size:
            chunk = self._sock.recv(size - len(chunks))
            if not chunk:
                return None
            chunks.extend(chunk)
        return bytes(chunks)

    def _handle_frame(self, frame: dict) -> None:
        if frame.get("MessageType") == "Attached":
            self._on_attach()


class DeviceWatcher(QObject):
    device_connected = Signal(object)  # DeviceInfo
    device_disconnected = Signal(str)  # udid
    device_not_ready = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._poller = UsbMuxPoller()
        self._poller.device_ready.connect(self.device_connected.emit)
        self._poller.device_lost.connect(self.device_disconnected.emit)
        self._poller.device_not_ready.connect(self.device_not_ready.emit)
        self._listener: _UsbmuxListener | None = None

    def start(self) -> None:
        self._poller.start()
        self._listener = _UsbmuxListener(on_attach=self._on_usb_arrival)
        self._listener.start()

    def stop(self) -> None:
        self._poller.stop()
        self._poller.wait(3000)
        if self._listener is not None:
            self._listener.stop()
            self._listener.wait(3000)

    def _on_usb_arrival(self) -> None:
        self._poller.poll_now()
