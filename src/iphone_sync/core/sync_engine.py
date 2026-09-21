"""Orchestrates incremental photo/video sync from iPhone."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QMutex, QMutexLocker, QThread, Signal

from iphone_sync.config import Settings
from iphone_sync.core.afc_client import AfcClient
from iphone_sync.core.manifest import Manifest
from iphone_sync.models.sync_record import DeviceFile
from iphone_sync.utils.atomic_copy import atomic_write
from iphone_sync.utils.paths import resolve_dest_path, unique_path


@dataclass
class SyncResult:
    device_udid: str
    device_name: str
    copied: int = 0
    skipped: int = 0
    failed: int = 0
    total_bytes: int = 0
    errors: list[str] | None = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


class SyncWorker(QThread):
    progress = Signal(str, int, int)  # current_file, current_index, total
    file_progress = Signal(int, int)  # bytes_transferred, total_bytes
    finished_sync = Signal(object)  # SyncResult
    log_message = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        settings: Settings,
        manifest: Manifest,
        udid: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._manifest = manifest
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
        result = SyncResult(device_udid="", device_name="")
        client = AfcClient(self._udid)

        try:
            device = client.connect(self._udid)
            result.device_udid = device.udid
            result.device_name = device.name
            self.log_message.emit(f"Connected to {device.name}")

            files = client.list_media_files()
            self.log_message.emit(f"Found {len(files)} media files on device")

            to_copy: list[DeviceFile] = []
            skipped = 0
            for f in files:
                if self._manifest.should_skip(device.udid, f):
                    skipped += 1
                else:
                    to_copy.append(f)

            result.skipped = skipped
            total = len(to_copy)

            if len(files) == 0:
                self.log_message.emit(
                    "No photos or videos found on device. "
                    "If you use iCloud Photos, set Storage to "
                    "'Download and Keep Originals' and wait for downloads to finish."
                )
                self.finished_sync.emit(result)
                return

            if total == 0:
                self.log_message.emit(f"All {len(files)} files already synced")
                self.finished_sync.emit(result)
                return

            self.log_message.emit(f"Copying {total} new/changed files...")
            dest_root = Path(self._settings.destination_folder)

            for idx, device_file in enumerate(to_copy, start=1):
                if self._is_cancelled():
                    self.log_message.emit("Sync cancelled")
                    break

                self.progress.emit(device_file.filename, idx, total)

                try:
                    dest = unique_path(
                        resolve_dest_path(
                            dest_root,
                            device.name,
                            device.udid,
                            device_file,
                            self._settings.organize_by_date,
                        )
                    )

                    data = client.read_file(device_file.device_path)
                    total_bytes = len(data)

                    # Use EXIF date from image data when organizing by date
                    if (
                        self._settings.organize_by_date
                        and device_file.extension in ("heic", "jpg", "jpeg", "png")
                    ):
                        from iphone_sync.utils.exif import exif_datetime

                        taken = exif_datetime(data)
                        if taken:
                            dest = unique_path(
                                resolve_dest_path(
                                    dest_root,
                                    device.name,
                                    device.udid,
                                    device_file,
                                    True,
                                    taken,
                                )
                            )

                    def on_bytes(n: int) -> None:
                        self.file_progress.emit(n, total_bytes)

                    on_bytes(0)
                    atomic_write(dest, data, device_file.size_bytes)
                    on_bytes(total_bytes)

                    self._manifest.mark_copied(device.udid, device_file, str(dest))
                    result.copied += 1
                    result.total_bytes += device_file.size_bytes

                except Exception as exc:
                    msg = f"Failed to copy {device_file.filename}: {exc}"
                    self.log_message.emit(msg)
                    result.errors.append(msg)
                    result.failed += 1
                    try:
                        dest_str = str(
                            resolve_dest_path(
                                dest_root,
                                device.name,
                                device.udid,
                                device_file,
                                self._settings.organize_by_date,
                            )
                        )
                        self._manifest.mark_failed(device.udid, device_file, dest_str)
                    except Exception:
                        pass

            self.log_message.emit(
                f"Sync complete: {result.copied} copied, {result.skipped} skipped, {result.failed} failed"
            )
            self.finished_sync.emit(result)

        except Exception as exc:
            self.error.emit(str(exc))
            result.errors.append(str(exc))
            self.finished_sync.emit(result)
        finally:
            client.disconnect()


class SyncEngine:
    """Manages sync worker lifecycle."""

    def __init__(self, settings: Settings, manifest: Manifest) -> None:
        self._settings = settings
        self._manifest = manifest
        self._worker: SyncWorker | None = None

    @property
    def is_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def start_sync(self, udid: str | None = None) -> SyncWorker:
        if self.is_running:
            raise RuntimeError("Sync already in progress")
        self._worker = SyncWorker(self._settings, self._manifest, udid)
        self._worker.start()
        return self._worker

    def cancel_sync(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
