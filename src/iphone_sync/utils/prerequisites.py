"""Check for macOS Apple device support (usbmuxd) prerequisites.

macOS ships usbmuxd built into the OS, so unlike Windows there is no
separate driver-install check to perform. The only signals worth checking
are whether the usbmuxd unix socket exists and whether it actually
responds to a device listing request.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from iphone_sync.utils.usbmux_helpers import list_usbmux_devices_async

_DEFAULT_SOCKET_PATH = Path("/var/run/usbmuxd")

_NOT_RUNNING_MESSAGE = (
    "macOS device support (usbmuxd) is not running. "
    "Restart your Mac or reconnect your iPhone."
)
_NOT_RESPONDING_MESSAGE = (
    "usbmuxd is running but not responding. "
    "Reconnect your iPhone and tap 'Trust This Computer'."
)
_READY_MESSAGE = "Apple device support is ready."


def is_usbmuxd_available(socket_path: Path | str | None = None) -> bool:
    """True if the usbmuxd unix socket exists on disk."""
    path = Path(socket_path) if socket_path is not None else _DEFAULT_SOCKET_PATH
    return path.exists()


def can_list_usb_devices() -> bool:
    """Attempt to list connected devices via pymobiledevice3's usbmux helpers.

    Returns True/False without raising; callers that need to distinguish
    "usbmuxd unreachable" from "no device connected" should catch
    exceptions separately instead of calling this function.
    """
    try:
        asyncio.run(list_usbmux_devices_async())
        return True
    except Exception:
        return False


def prerequisite_status() -> tuple[bool, str]:
    """Resolve overall Apple device support readiness.

    Never raises: any unexpected exception is treated as "not responding".
    """
    if not is_usbmuxd_available(_DEFAULT_SOCKET_PATH):
        return False, _NOT_RUNNING_MESSAGE

    try:
        if not can_list_usb_devices():
            return False, _NOT_RESPONDING_MESSAGE
    except Exception:
        return False, _NOT_RESPONDING_MESSAGE

    return True, _READY_MESSAGE
