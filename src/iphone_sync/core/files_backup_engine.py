"""Copy Files app–visible data: Media folders + On My iPhone Documents."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QMutex, QMutexLocker, QThread, Signal

from iphone_sync.config import Settings
from iphone_sync.utils.paths import device_root_folder, sanitize_name
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
    app_files: int = 0
    apps_backed_up: int = 0
    apps_skipped: int = 0
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
        from pymobiledevice3.services.house_arrest import HouseArrestService
        from pymobiledevice3.services.installation_proxy import InstallationProxyService

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

        async with AfcService(lockdown) as afc:
            for folder in FILES_MEDIA_FOLDERS:
                if self._is_cancelled():
                    result.error = "cancelled"
                    return result
                remote = f"/{folder}"
                try:
                    if not await afc.exists(remote):
                        continue
                    self.log_message.emit(f"Copying Files/{folder}…")
                    await afc.pull(
                        remote,
                        str(media_dest),
                        ignore_errors=True,
                        progress_bar=False,
                    )
                    self.log_message.emit(f"  {folder}: synced")
                except Exception as exc:
                    msg = f"{folder}: {exc}"
                    result.errors.append(msg)
                    self.log_message.emit(f"  Skipped {folder}: {exc}")

        result.media_files = count_files_under(media_dest)

        # --- On My iPhone: app Documents via House Arrest ---
        on_my = dest_root / "On My iPhone"
        on_my.mkdir(parents=True, exist_ok=True)

        apps: list[tuple[str, str, bool]] = []
        async with InstallationProxyService(lockdown) as ip:
            listed = await ip.browse(
                options={"ApplicationType": "User"},
                attributes=[
                    "CFBundleIdentifier",
                    "CFBundleDisplayName",
                    "CFBundleName",
                    "UIFileSharingEnabled",
                ],
            )
            for app in listed:
                bundle_id = app.get("CFBundleIdentifier")
                if not bundle_id:
                    continue
                name = (
                    app.get("CFBundleDisplayName")
                    or app.get("CFBundleName")
                    or bundle_id
                )
                sharing = bool(app.get("UIFileSharingEnabled"))
                apps.append((bundle_id, str(name), sharing))

        # Prefer file-sharing apps first; still try others with VendDocuments
        apps.sort(key=lambda a: (not a[2], a[1].lower()))
        total = len(apps)
        self.log_message.emit(f"Checking {total} apps for On My iPhone Documents…")

        for idx, (bundle_id, name, sharing) in enumerate(apps, start=1):
            if self._is_cancelled():
                result.error = "cancelled"
                return result

            self.progress.emit(idx, total, name)
            folder_label = f"{sanitize_name(name)}_{sanitize_name(bundle_id)}"
            app_dest = on_my / folder_label

            try:
                async with await HouseArrestService.create(
                    lockdown, bundle_id, documents_only=True
                ) as ha:
                    # documents_only: contents under /Documents
                    if not await ha.exists("/Documents"):
                        result.apps_skipped += 1
                        continue
                    entries = [
                        e
                        for e in await ha.listdir("/Documents")
                        if e not in (".", "..")
                    ]
                    if not entries:
                        result.apps_skipped += 1
                        continue

                    app_dest.mkdir(parents=True, exist_ok=True)
                    await ha.pull(
                        "/Documents",
                        str(app_dest),
                        ignore_errors=True,
                        progress_bar=False,
                    )
                    # pull creates app_dest/Documents — flatten
                    nested = app_dest / "Documents"
                    if nested.is_dir():
                        for item in list(nested.iterdir()):
                            target = app_dest / item.name
                            if not target.exists():
                                item.rename(target)
                        try:
                            nested.rmdir()
                        except OSError:
                            pass

                    n = count_files_under(app_dest)
                    if n == 0:
                        try:
                            if app_dest.exists() and not any(app_dest.iterdir()):
                                app_dest.rmdir()
                        except OSError:
                            pass
                        result.apps_skipped += 1
                    else:
                        result.app_files += n
                        result.apps_backed_up += 1
                        self.log_message.emit(f"  {name}: {n} files")
            except Exception:
                result.apps_skipped += 1
                if sharing:
                    result.errors.append(f"{name} ({bundle_id}): could not read Documents")

        result.success = result.error != "cancelled"
        if result.success:
            self.log_message.emit(
                f"Files backup complete — Media: {result.media_files} files, "
                f"On My iPhone: {result.app_files} files from {result.apps_backed_up} apps"
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
