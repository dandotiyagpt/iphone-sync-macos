"""Wrap pymobiledevice3 AFC calls for DCIM media access."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Iterator

from pymobiledevice3.services.afc import AfcService

from iphone_sync.models.sync_record import DeviceFile
from iphone_sync.utils.usbmux_helpers import create_lockdown

MEDIA_EXTENSIONS = frozenset(
    {"heic", "jpg", "jpeg", "png", "mov", "mp4", "aae", "m4v", "gif", "webp"}
)

DCIM_ROOT = "/DCIM"


@dataclass
class ConnectedDevice:
    udid: str
    name: str
    lockdown: object
    afc: AfcService


class AfcClient:
    """AFC client with a persistent asyncio loop for the connection lifetime."""

    def __init__(self, udid: str | None = None) -> None:
        self._udid = udid
        self._device: ConnectedDevice | None = None
        self._loop = asyncio.new_event_loop()

    def _run(self, coro):
        return self._loop.run_until_complete(coro)

    @property
    def is_connected(self) -> bool:
        return self._device is not None

    @property
    def device(self) -> ConnectedDevice | None:
        return self._device

    def connect(self, udid: str | None = None) -> ConnectedDevice:
        target = udid or self._udid
        self._device = self._run(self._connect_async(target))
        self._udid = self._device.udid
        return self._device

    async def _connect_async(self, serial: str | None) -> ConnectedDevice:
        lockdown = await create_lockdown(serial)
        afc = AfcService(lockdown)
        await afc.__aenter__()
        info = lockdown.all_values
        return ConnectedDevice(
            udid=lockdown.udid,
            name=info.get("DeviceName", "iPhone"),
            lockdown=lockdown,
            afc=afc,
        )

    def disconnect(self) -> None:
        if self._device:
            try:
                self._run(self._disconnect_async())
            finally:
                self._device = None
        if self._loop and not self._loop.is_closed():
            self._loop.close()
        self._loop = asyncio.new_event_loop()

    async def _disconnect_async(self) -> None:
        if self._device:
            await self._device.afc.aclose()

    def list_media_files(self) -> list[DeviceFile]:
        if not self._device:
            raise RuntimeError("Not connected to a device")
        return self._run(self._list_media_async(self._device.afc))

    async def _list_media_async(self, afc: AfcService) -> list[DeviceFile]:
        files: list[DeviceFile] = []
        async for item in self._walk_dcim_async(afc, DCIM_ROOT):
            files.append(item)
        return files

    def read_file(self, device_path: str) -> bytes:
        if not self._device:
            raise RuntimeError("Not connected to a device")
        return self._run(self._device.afc.get_file_contents(device_path))

    def read_file_chunks(self, device_path: str, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
        if not self._device:
            raise RuntimeError("Not connected to a device")
        data = self.read_file(device_path)
        for i in range(0, len(data), chunk_size):
            yield data[i : i + chunk_size]

    async def _walk_dcim_async(self, afc: AfcService, path: str):
        try:
            entries = await afc.listdir(path)
        except Exception:
            return

        for name in entries:
            if name in (".", ".."):
                continue
            full_path = f"{path.rstrip('/')}/{name}"
            try:
                info = await afc.stat(full_path)
            except Exception:
                continue

            mode = info.get("st_ifmt", "")
            if mode == "S_IFDIR":
                async for item in self._walk_dcim_async(afc, full_path):
                    yield item
                continue

            if mode != "S_IFREG":
                continue

            ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            if ext not in MEDIA_EXTENSIONS:
                continue

            mtime_val = info.get("st_mtime", 0)
            if hasattr(mtime_val, "timestamp"):
                mtime = mtime_val.timestamp()
            else:
                mtime = float(mtime_val)
            size = int(info.get("st_size", 0))
            yield DeviceFile(
                device_path=full_path,
                size_bytes=size,
                mtime=mtime,
                filename=name,
            )


def list_connected_devices() -> list[dict]:
    """Return basic info for all usbmux-connected devices."""
    from iphone_sync.utils.usbmux_helpers import list_usbmux_devices

    devices = []
    for dev in list_usbmux_devices():
        devices.append({"serial": dev.serial, "connection_type": dev.connection_type})
    return devices
