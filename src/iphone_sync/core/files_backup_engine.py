"""Copy Files app–visible media folders (Downloads, Books, Recordings, …).

Per-app document sandboxes ("On My iPhone" app folders) are deliberately not
touched: WhatsApp has its own dedicated backup entity, and no other app's
data is backed up by this tool.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QMutex, QMutexLocker, QThread, Signal

from iphone_sync.config import Settings
from iphone_sync.utils.paths import device_root_folder
from iphone_sync.utils.usbmux_helpers import create_lockdown

# AFC Media folders commonly shown in the Files app (not DCIM — photos are separate).
FILES_MEDIA_FOLDERS = (
    "Downloads",
    "Books",
    "Recordings",
    "Podcasts",
    "Purchases",
)


@dataclass
class FilesBackupResult:
    udid: str = ""
    device_name: str = ""
    success: bool = False
    media_files: int = 0
    folders_copied: int = 0
    folders_skipped: int = 0
    dest_path: str = ""
    error: str = ""
    errors: list[str] = field(default_factory=list)


def files_backup_root(settings: Settings, device_name: str, udid: str) -> Path:
    return device_root_folder(Path(settings.files_backup_folder), device_name, udid)


def count_files_under(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for p in path.rglob("*") if p.is_file())


class FilesBackupWorker(QThread):
    progress = Signal(int, int, str)  # current, total, label
    log_message = Signal(str)
    error = Signal(str)
    finished_files = Signal(object)  # FilesBackupResult

    def __init__(
        self,
        settings: Settings,
        udid: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._udid = udid
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
            result = loop.run_until_complete(self._run())
            self.finished_files.emit(result)
        except Exception as exc:
            result = FilesBackupResult(error=str(exc), errors=[str(exc)])
            self.error.emit(str(exc))
            self.finished_files.emit(result)
        finally:
            loop.close()

    async def _run(self) -> FilesBackupResult:
        from pymobiledevice3.services.afc import AfcService

        result = FilesBackupResult()
        lockdown = await create_lockdown(self._udid)
        result.udid = lockdown.udid
        result.device_name = lockdown.all_values.get("DeviceName", "iPhone")

        dest_root = files_backup_root(self._settings, result.device_name, result.udid)
        dest_root.mkdir(parents=True, exist_ok=True)
        result.dest_path = str(dest_root)
        self.log_message.emit(f"Files backup → {dest_root}")

        # --- Media folders (Downloads, Books, …) via AFC ---
        media_dest = dest_root / "Media"
        media_dest.mkdir(parents=True, exist_ok=True)

        total = len(FILES_MEDIA_FOLDERS)
        async with AfcService(lockdown) as afc:
            for idx, folder in enumerate(FILES_MEDIA_FOLDERS, start=1):
                if self._is_cancelled():
                    result.error = "cancelled"
                    return result
                self.progress.emit(idx, total, folder)
                remote = f"/{folder}"
                try:
                    if not await afc.exists(remote):
                        result.folders_skipped += 1
                        continue
                    self.log_message.emit(f"Copying Files/{folder}…")
                    await afc.pull(
                        remote,
                        str(media_dest),
                        ignore_errors=True,
                        progress_bar=False,
                    )
                    result.folders_copied += 1
                    self.log_message.emit(f"  {folder}: synced")
                except Exception as exc:
                    msg = f"{folder}: {exc}"
                    result.errors.append(msg)
                    result.folders_skipped += 1
                    self.log_message.emit(f"  Skipped {folder}: {exc}")

        result.media_files = count_files_under(media_dest)

        result.success = result.error != "cancelled"
        if result.success:
            self.log_message.emit(
                f"Files backup complete — {result.media_files} files from "
                f"{result.folders_copied} Files app folders"
            )
        return result


class FilesBackupEngine:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._worker: FilesBackupWorker | None = None

    @property
    def is_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def start_backup(self, udid: str | None = None) -> FilesBackupWorker:
        if self.is_running:
            raise RuntimeError("Files backup already in progress")
        self._worker = FilesBackupWorker(self._settings, udid)
        self._worker.start()
        return self._worker

    def cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
