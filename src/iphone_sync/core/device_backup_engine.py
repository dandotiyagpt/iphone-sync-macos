"""Full encrypted MobileBackup2 backup / restore (Finder/iTunes-style)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QMutex, QMutexLocker, QThread, Signal

from iphone_sync.config import Settings
from iphone_sync.core.device_backup_info import LocalBackupInfo, inspect_device_backup
from iphone_sync.utils.usbmux_helpers import create_lockdown


@dataclass
class DeviceBackupResult:
    udid: str = ""
    device_name: str = ""
    success: bool = False
    cancelled: bool = False
    encryption_enabled: bool = False
    info: LocalBackupInfo | None = None
    error: str = ""
    errors: list[str] = field(default_factory=list)


class DeviceBackupWorker(QThread):
    progress = Signal(float)  # 0-100
    log_message = Signal(str)
    error = Signal(str)
    finished_backup = Signal(object)  # DeviceBackupResult
    needs_encryption = Signal()  # encryption off — UI must set password then retry
    finished_restore = Signal(object)  # DeviceBackupResult

    def __init__(
        self,
        settings: Settings,
        udid: str | None = None,
        *,
        mode: str = "backup",
        full: bool = False,
        password: str = "",
        enable_encryption_password: str = "",
        source_udid: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._udid = udid
        self._mode = mode  # backup | restore | enable_encryption
        self._full = full
        self._password = password
        self._enable_encryption_password = enable_encryption_password
        self._source_udid = source_udid
        self._cancelled = False
        self._mutex = QMutex()

    def cancel(self) -> None:
        with QMutexLocker(self._mutex):
            self._cancelled = True

    def _is_cancelled(self) -> bool:
        with QMutexLocker(self._mutex):
            return self._cancelled

    def run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            if self._mode == "backup":
                result = loop.run_until_complete(self._run_backup())
                self.finished_backup.emit(result)
            elif self._mode == "restore":
                result = loop.run_until_complete(self._run_restore())
                self.finished_restore.emit(result)
            elif self._mode == "enable_encryption":
                result = loop.run_until_complete(self._run_enable_encryption())
                self.finished_backup.emit(result)
            else:
                result = DeviceBackupResult(error=f"Unknown mode: {self._mode}")
                self.finished_backup.emit(result)
        except Exception as exc:
            result = DeviceBackupResult(error=str(exc), errors=[str(exc)])
            self.error.emit(str(exc))
            if self._mode == "restore":
                self.finished_restore.emit(result)
            else:
                self.finished_backup.emit(result)
        finally:
            loop.close()

    def _on_progress(self, pct: float) -> None:
        try:
            self.progress.emit(float(pct))
        except Exception:
            pass

    async def _run_enable_encryption(self) -> DeviceBackupResult:
        from pymobiledevice3.services.mobilebackup2 import Mobilebackup2Service

        result = DeviceBackupResult()
        backup_root = Path(self._settings.device_backup_folder)
        backup_root.mkdir(parents=True, exist_ok=True)

        lockdown = await create_lockdown(self._udid)
        result.udid = lockdown.udid
        result.device_name = lockdown.all_values.get("DeviceName", "iPhone")

        async with Mobilebackup2Service(lockdown) as client:
            if await client.get_will_encrypt():
                result.encryption_enabled = True
                result.success = True
                self.log_message.emit("Backup encryption already enabled")
                return result
            if not self._enable_encryption_password:
                result.error = "Password required to enable encryption"
                return result
            self.log_message.emit("Enabling encrypted backups on device…")
            await client.change_password(str(backup_root), new=self._enable_encryption_password)
            result.encryption_enabled = await client.get_will_encrypt()
            result.success = result.encryption_enabled
            if result.success:
                self.log_message.emit("Encrypted backups enabled")
            else:
                result.error = "Failed to enable backup encryption"
        return result

    async def _run_backup(self) -> DeviceBackupResult:
        from pymobiledevice3.services.mobilebackup2 import Mobilebackup2Service

        result = DeviceBackupResult()
        backup_root = Path(self._settings.device_backup_folder)
        backup_root.mkdir(parents=True, exist_ok=True)

        lockdown = await create_lockdown(self._udid)
        result.udid = lockdown.udid
        result.device_name = lockdown.all_values.get("DeviceName", "iPhone")
        self.log_message.emit(f"Starting device backup for {result.device_name}…")

        async with Mobilebackup2Service(lockdown) as client:
            will_encrypt = await client.get_will_encrypt()
            result.encryption_enabled = will_encrypt
            if not will_encrypt:
                self.log_message.emit(
                    "Backup encryption is OFF — WhatsApp and most app data will be incomplete."
                )
                self.needs_encryption.emit()
                result.error = "encryption_required"
                result.success = False
                return result

            self.log_message.emit(
                "Encrypted backup ON — starting "
                + ("full" if self._full else "incremental")
                + " backup…"
            )
            self.log_message.emit("Unlock your iPhone if prompted for the passcode.")

            await client.backup(
                full=self._full,
                backup_directory=str(backup_root),
                progress_callback=self._on_progress,
            )

        device_dir = backup_root / result.udid
        info = inspect_device_backup(device_dir)
        result.info = info
        if info is None:
            result.error = "Backup finished but local folder could not be read"
            result.success = False
            return result

        self.log_message.emit(info.whatsapp_status_label)
        if not info.is_encrypted:
            result.error = "Backup is not encrypted — WhatsApp not safe to restore"
            result.success = False
            result.errors.append(result.error)
            return result

        if not info.whatsapp_installed:
            self.log_message.emit(
                "Warning: WhatsApp was not listed as installed at backup time."
            )
            result.errors.append("WhatsApp not in Installed Applications")

        if info.whatsapp_in_manifest is False:
            result.error = "WhatsApp data missing from backup payload"
            result.success = False
            result.errors.append(result.error)
            return result

        result.success = True
        self.log_message.emit(
            f"Device backup complete ({info.device_name}). "
            f"{info.whatsapp_status_label}."
        )
        return result

    async def _run_restore(self) -> DeviceBackupResult:
        from pymobiledevice3.services.mobilebackup2 import Mobilebackup2Service

        result = DeviceBackupResult()
        backup_root = Path(self._settings.device_backup_folder)
        source = self._source_udid

        lockdown = await create_lockdown(self._udid)
        result.udid = lockdown.udid
        result.device_name = lockdown.all_values.get("DeviceName", "iPhone")

        if not source:
            result.error = "No backup selected"
            return result

        info = inspect_device_backup(backup_root / source)
        result.info = info
        if info is None:
            result.error = f"Backup not found: {source}"
            return result

        if info.is_encrypted and not self._password:
            result.error = "Backup password required"
            return result

        self.log_message.emit(
            f"Restoring backup from {info.device_name} ({source[:8]}…) "
            f"onto {result.device_name}…"
        )
        self.log_message.emit("Keep the iPhone unlocked and connected. Do not unplug.")

        async with Mobilebackup2Service(lockdown) as client:
            await client.restore(
                backup_directory=str(backup_root),
                system=False,
                reboot=True,
                copy=False,
                settings=True,
                remove=False,
                password=self._password,
                source=source,
                progress_callback=self._on_progress,
                skip_apps=False,
            )

        result.success = True
        self.log_message.emit(
            "Restore finished — the iPhone should reboot. "
            "After setup, open WhatsApp and verify your number if asked."
        )
        return result


class DeviceBackupEngine:
    """Manages device backup / restore worker lifecycle."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._worker: DeviceBackupWorker | None = None

    @property
    def is_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def start_backup(
        self,
        udid: str | None = None,
        *,
        full: bool = False,
    ) -> DeviceBackupWorker:
        if self.is_running:
            raise RuntimeError("Device backup already in progress")
        self._worker = DeviceBackupWorker(
            self._settings, udid, mode="backup", full=full
        )
        self._worker.start()
        return self._worker

    def start_enable_encryption(
        self, udid: str | None, password: str
    ) -> DeviceBackupWorker:
        if self.is_running:
            raise RuntimeError("Device backup already in progress")
        self._worker = DeviceBackupWorker(
            self._settings,
            udid,
            mode="enable_encryption",
            enable_encryption_password=password,
        )
        self._worker.start()
        return self._worker

    def start_restore(
        self,
        udid: str | None,
        *,
        source_udid: str,
        password: str = "",
    ) -> DeviceBackupWorker:
        if self.is_running:
            raise RuntimeError("Device backup already in progress")
        self._worker = DeviceBackupWorker(
            self._settings,
            udid,
            mode="restore",
            password=password,
            source_udid=source_udid,
        )
        self._worker.start()
        return self._worker

    def cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
