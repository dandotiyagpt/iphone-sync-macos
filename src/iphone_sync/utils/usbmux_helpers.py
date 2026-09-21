"""Shared helpers for pymobiledevice3 async APIs used from sync Qt code."""

from __future__ import annotations

import asyncio
from typing import Any, Coroutine, TypeVar

T = TypeVar("T")


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run an async pymobiledevice3 coroutine from synchronous code."""
    return asyncio.run(coro)


async def list_usbmux_devices_async():
    from pymobiledevice3.usbmux import list_devices

    return await list_devices()


def list_usbmux_devices():
    return run_async(list_usbmux_devices_async())


async def create_lockdown(serial: str | None = None):
    from pymobiledevice3.lockdown import create_using_usbmux

    if serial:
        return await create_using_usbmux(serial=serial)
    return await create_using_usbmux()


def create_lockdown_sync(serial: str | None = None):
    return run_async(create_lockdown(serial))
