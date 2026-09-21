"""Main application window — photo sync + encrypted device backup."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from iphone_sync.config import Settings
from iphone_sync.core.backup_reset import count_backup_files, reset_backup
from iphone_sync.core.device_backup_engine import DeviceBackupEngine, DeviceBackupResult
from iphone_sync.core.device_backup_info import format_size, inspect_device_backup
from iphone_sync.core.device_watcher import DeviceInfo, DeviceWatcher
from iphone_sync.core.files_backup_engine import (
    FilesBackupEngine,
    FilesBackupResult,
    count_files_under,
    files_backup_root,
)
from iphone_sync.core.manifest import Manifest
from iphone_sync.core.sync_engine import SyncEngine, SyncResult
from iphone_sync.ui.backup_dialogs import EncryptionPasswordDialog, RestoreBackupDialog
from iphone_sync.ui.settings_dialog import SettingsDialog
from iphone_sync.ui.widgets.progress import LogViewer, ProgressWidget
from iphone_sync.utils.prerequisites import prerequisite_status


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings
        self._manifest = Manifest(settings.manifest_db_path())
        self._sync_engine = SyncEngine(settings, self._manifest)
        self._device_backup_engine = DeviceBackupEngine(settings)
        self._files_backup_engine = FilesBackupEngine(settings)
        self._device_watcher = DeviceWatcher()
        self._connected_device: DeviceInfo | None = None
        self._active_worker = None
        self._device_backup_worker = None
        self._files_backup_worker = None
        self._last_sync: datetime | None = None
        self._run_files_after_photos = False
        self._run_device_backup_after_chain = False
        self._pending_encryption_then_backup = False

        self.setWindowTitle("iPhone Sync")
        self.setMinimumSize(720, 720)
        self._build_ui()
        self._build_menu()
        self._build_tray()
        self._connect_signals()
        self._check_prerequisites()
        self._device_watcher.start()
        self._update_device_panel()
        self._refresh_device_backup_status()
        self._refresh_files_backup_status()

    def _build_ui(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)

        device_group = QGroupBox("Device")
        device_layout = QVBoxLayout(device_group)
        self._device_status = QLabel("No iPhone connected")
        self._device_name = QLabel("")
        self._device_udid = QLabel("")
        self._synced_count = QLabel("")
        device_layout.addWidget(self._device_status)
        device_layout.addWidget(self._device_name)
        device_layout.addWidget(self._device_udid)
        device_layout.addWidget(self._synced_count)

        btn_row = QHBoxLayout()
        self._sync_btn = QPushButton("Sync Photos Now")
        self._sync_btn.setEnabled(False)
        self._sync_btn.clicked.connect(self._start_sync)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._cancel_sync)
        self._reset_btn = QPushButton("Delete Photo Backup")
        self._reset_btn.setToolTip(
            "Remove all copied photos/videos and sync history, then press Sync Photos Now"
        )
        self._reset_btn.setEnabled(True)
        self._reset_btn.clicked.connect(self._delete_previous_backup)
        btn_row.addWidget(self._sync_btn)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addStretch()
        device_layout.addLayout(btn_row)

        reset_row = QHBoxLayout()
        reset_row.addWidget(self._reset_btn)
        reset_row.addStretch()
        device_layout.addLayout(reset_row)
        layout.addWidget(device_group)

        # Files app data (Downloads + On My iPhone Documents)
        files_group = QGroupBox("Files App Backup")
        files_layout = QVBoxLayout(files_group)
        self._files_backup_status = QLabel("No Files backup yet")
        self._files_backup_status.setWordWrap(True)
        files_layout.addWidget(self._files_backup_status)
        self._files_backup_progress = QProgressBar()
        self._files_backup_progress.setRange(0, 100)
        self._files_backup_progress.setValue(0)
        files_layout.addWidget(self._files_backup_progress)
        files_btns = QHBoxLayout()
        self._files_backup_btn = QPushButton("Backup Files Now")
        self._files_backup_btn.setToolTip(
            "Copy Downloads and On My iPhone Documents folders to this PC"
        )
        self._files_backup_btn.clicked.connect(self._start_files_backup_clicked)
        self._delete_files_backup_btn = QPushButton("Delete Files Backup")
        self._delete_files_backup_btn.clicked.connect(self._delete_files_backup)
        files_btns.addWidget(self._files_backup_btn)
        files_btns.addWidget(self._delete_files_backup_btn)
        files_btns.addStretch()
        files_layout.addLayout(files_btns)
        layout.addWidget(files_group)

        # Device backup (WhatsApp / apps)
        backup_group = QGroupBox("Device Backup (WhatsApp & apps)")
        backup_layout = QVBoxLayout(backup_group)
        self._device_backup_status = QLabel("No device backup yet")
        self._device_backup_status.setWordWrap(True)
        self._whatsapp_status = QLabel("")
        self._whatsapp_status.setWordWrap(True)
        backup_layout.addWidget(self._device_backup_status)
        backup_layout.addWidget(self._whatsapp_status)

        self._device_backup_progress = QProgressBar()
        self._device_backup_progress.setRange(0, 100)
        self._device_backup_progress.setValue(0)
        backup_layout.addWidget(self._device_backup_progress)

        backup_btns = QHBoxLayout()
        self._device_backup_btn = QPushButton("Backup Now")
        self._device_backup_btn.setToolTip(
            "Full encrypted Finder/iTunes-style backup (required for WhatsApp restore)"
        )
        self._device_backup_btn.clicked.connect(self._start_device_backup_clicked)
        self._restore_btn = QPushButton("Restore…")
        self._restore_btn.setToolTip("Restore a previous encrypted backup onto the connected iPhone")
        self._restore_btn.clicked.connect(self._start_restore)
        self._delete_device_backup_btn = QPushButton("Delete Device Backup")
        self._delete_device_backup_btn.clicked.connect(self._delete_device_backup)
        backup_btns.addWidget(self._device_backup_btn)
        backup_btns.addWidget(self._restore_btn)
        backup_btns.addWidget(self._delete_device_backup_btn)
        backup_btns.addStretch()
        backup_layout.addLayout(backup_btns)
        layout.addWidget(backup_group)

        progress_group = QGroupBox("Photo Sync Progress")
        progress_layout = QVBoxLayout(progress_group)
        self._progress = ProgressWidget()
        progress_layout.addWidget(self._progress)
        layout.addWidget(progress_group)

        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)
        self._log = LogViewer()
        log_layout.addWidget(self._log)
        layout.addWidget(log_group, stretch=1)

        self.setCentralWidget(central)
        self.statusBar().showMessage("Waiting for iPhone…")

    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu("File")
        settings_action = QAction("Settings…", self)
        settings_action.triggered.connect(self._open_settings)
        menu.addAction(settings_action)
        delete_action = QAction("Delete Photo Backup…", self)
        delete_action.triggered.connect(self._delete_previous_backup)
        menu.addAction(delete_action)
        delete_files = QAction("Delete Files Backup…", self)
        delete_files.triggered.connect(self._delete_files_backup)
        menu.addAction(delete_files)
        delete_device = QAction("Delete Device Backup…", self)
        delete_device.triggered.connect(self._delete_device_backup)
        menu.addAction(delete_device)
        menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(quit_action)

        help_menu = self.menuBar().addMenu("Help")
        prereq_action = QAction("Check Prerequisites", self)
        prereq_action.triggered.connect(self._check_prerequisites)
        help_menu.addAction(prereq_action)

    def _build_tray(self) -> None:
        self._tray = QSystemTrayIcon(self)
        self._tray.setToolTip("iPhone Sync")
        self._tray.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))
        self._tray.activated.connect(self._tray_activated)

        from PySide6.QtWidgets import QMenu

        menu = QMenu()
        show_action = menu.addAction("Show")
        show_action.triggered.connect(self.showNormal)
        sync_action = menu.addAction("Sync Photos Now")
        sync_action.triggered.connect(self._start_sync)
        files_action = menu.addAction("Backup Files Now")
        files_action.triggered.connect(self._start_files_backup_clicked)
        backup_action = menu.addAction("Device Backup Now")
        backup_action.triggered.connect(self._start_device_backup_clicked)
        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self._quit_app)
        self._tray.setContextMenu(menu)
        self._tray.show()

    def _connect_signals(self) -> None:
        self._device_watcher.device_connected.connect(self._on_device_connected)
        self._device_watcher.device_disconnected.connect(self._on_device_disconnected)
        self._device_watcher.device_not_ready.connect(self._on_device_not_ready)

    def _busy(self) -> bool:
        return (
            self._sync_engine.is_running
            or self._device_backup_engine.is_running
            or self._files_backup_engine.is_running
        )

    def _check_prerequisites(self) -> None:
        ok, message = prerequisite_status()
        if ok:
            self._log.append_log(message)
        else:
            self._log.append_log(f"Warning: {message}")
            QMessageBox.warning(self, "Prerequisites", message)

    def _on_device_connected(self, device: DeviceInfo) -> None:
        self._connected_device = device
        self._update_device_panel()
        self._refresh_device_backup_status()
        self._log.append_log(f"iPhone connected: {device.name}")
        self.statusBar().showMessage(f"Connected: {device.name}")

        if self._busy():
            return

        self._run_files_after_photos = False
        self._run_device_backup_after_chain = False

        if self._settings.auto_sync_on_plugin:
            self._run_files_after_photos = self._settings.auto_files_backup_on_plugin
            self._run_device_backup_after_chain = self._settings.auto_device_backup_on_plugin
            self._start_sync()
        elif self._settings.auto_files_backup_on_plugin:
            self._run_device_backup_after_chain = self._settings.auto_device_backup_on_plugin
            self._start_files_backup()
        elif self._settings.auto_device_backup_on_plugin:
            self._start_device_backup()

    def _on_device_disconnected(self, udid: str) -> None:
        if self._connected_device and self._connected_device.udid == udid:
            self._log.append_log("iPhone disconnected")
            self._connected_device = None
            self._update_device_panel()
            self.statusBar().showMessage("Waiting for iPhone…")

    def _on_device_not_ready(self, reason: str) -> None:
        self.statusBar().showMessage(reason)

    def _update_device_panel(self) -> None:
        busy = self._busy()
        if self._connected_device:
            self._device_status.setText("Status: Connected")
            self._device_name.setText(f"Name: {self._connected_device.name}")
            self._device_udid.setText(f"UDID: {self._connected_device.udid[:8]}…")
            count = self._manifest.count_for_device(self._connected_device.udid)
            self._synced_count.setText(f"Previously synced photos: {count} files")
            self._sync_btn.setEnabled(not busy)
            self._files_backup_btn.setEnabled(not busy)
            self._device_backup_btn.setEnabled(not busy)
            self._restore_btn.setEnabled(not busy)
        else:
            self._device_status.setText("Status: Not connected")
            self._device_name.setText("")
            self._device_udid.setText("")
            self._synced_count.setText("")
            self._sync_btn.setEnabled(False)
            self._files_backup_btn.setEnabled(False)
            self._device_backup_btn.setEnabled(False)
            self._restore_btn.setEnabled(False)

        self._reset_btn.setEnabled(not busy)
        self._delete_files_backup_btn.setEnabled(not busy)
        self._delete_device_backup_btn.setEnabled(not busy)
        self._cancel_btn.setEnabled(self._sync_engine.is_running)

    def _refresh_device_backup_status(self) -> None:
        root = Path(self._settings.device_backup_folder)
        udid = self._connected_device.udid if self._connected_device else None
        info = None
        if udid:
            info = inspect_device_backup(root / udid)
        if info is None and udid is None:
            # Show newest backup if any
            from iphone_sync.core.device_backup_info import list_local_backups

            backups = list_local_backups(root)
            info = backups[0] if backups else None

        if info is None:
            self._device_backup_status.setText(
                f"No device backup yet\nFolder: {root}"
            )
            self._whatsapp_status.setText(
                "WhatsApp: not backed up — run Backup Now (encryption required)"
            )
            return

        when = (
            info.last_backup.strftime("%Y-%m-%d %H:%M")
            if info.last_backup
            else "unknown"
        )
        enc = "encrypted" if info.is_encrypted else "NOT encrypted"
        self._device_backup_status.setText(
            f"Last backup: {when}  ·  {format_size(info.size_bytes)}  ·  {enc}\n"
            f"{info.device_name} (iOS {info.product_version or '?'})\n"
            f"{info.path}"
        )
        self._whatsapp_status.setText(info.whatsapp_status_label)

    def _refresh_files_backup_status(self) -> None:
        root = Path(self._settings.files_backup_folder)
        if self._connected_device:
            dest = files_backup_root(
                self._settings,
                self._connected_device.name,
                self._connected_device.udid,
            )
        else:
            dest = root
            if root.exists():
                device_dirs = [p for p in root.iterdir() if p.is_dir()]
                dest = device_dirs[0] if device_dirs else root

        n = count_files_under(dest) if dest.exists() else 0
        if n == 0:
            self._files_backup_status.setText(
                f"No Files backup yet\nFolder: {root}\n"
                "Copies Downloads, Books, Recordings, and On My iPhone Documents."
            )
        else:
            self._files_backup_status.setText(
                f"{n} files backed up\n{dest}"
            )

    def _delete_previous_backup(self) -> None:
        if self._busy():
            QMessageBox.information(self, "Delete Photo Backup", "Wait for the current job to finish.")
            return

        dest = Path(self._settings.destination_folder)
        file_count = count_backup_files(dest)
        manifest_count = self._manifest.total_copied_count()

        if file_count == 0 and manifest_count == 0:
            QMessageBox.information(
                self,
                "Delete Photo Backup",
                "No previous photo backup found.",
            )
            return

        reply = QMessageBox.warning(
            self,
            "Delete Photo Backup",
            f"This permanently deletes copied photos and videos from your PC.\n\n"
            f"Folder: {dest}\n"
            f"Files on disk: {file_count}\n"
            f"Sync history: {manifest_count} files\n\n"
            f"(Device backup for WhatsApp is separate — use Delete Device Backup.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._reset_btn.setEnabled(False)
        self._log.append_log("Deleting previous photo backup…")
        result = reset_backup(dest, self._manifest)
        self._update_device_panel()

        if result.errors:
            for err in result.errors:
                self._log.append_log(f"Warning: {err}")
            QMessageBox.warning(
                self,
                "Delete Photo Backup",
                f"Mostly cleared ({result.files_deleted} files), with some errors. See log.",
            )
        else:
            self._log.append_log(
                f"Photo backup cleared — {result.files_deleted} files removed."
            )
            QMessageBox.information(
                self,
                "Delete Photo Backup",
                f"Photo backup deleted ({result.files_deleted} files).",
            )
        self.statusBar().showMessage("Photo backup cleared")

    def _delete_device_backup(self) -> None:
        if self._busy():
            QMessageBox.information(self, "Delete Device Backup", "Wait for the current job to finish.")
            return

        root = Path(self._settings.device_backup_folder)
        if not root.exists() or not any(root.iterdir()):
            QMessageBox.information(self, "Delete Device Backup", "No device backups found.")
            return

        reply = QMessageBox.warning(
            self,
            "Delete Device Backup",
            f"Permanently delete all Finder/iTunes-style device backups under:\n\n{root}\n\n"
            "This removes WhatsApp restore capability until you backup again.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        import shutil

        errors: list[str] = []
        for entry in list(root.iterdir()):
            try:
                if entry.is_dir():
                    shutil.rmtree(entry)
                else:
                    entry.unlink()
            except OSError as exc:
                errors.append(str(exc))

        self._refresh_device_backup_status()
        if errors:
            self._log.append_log("Device backup delete had errors: " + "; ".join(errors))
            QMessageBox.warning(self, "Delete Device Backup", "Some files could not be deleted.")
        else:
            self._log.append_log("Device backups deleted.")
            QMessageBox.information(self, "Delete Device Backup", "Device backups deleted.")

    def _start_sync(self) -> None:
        if self._busy():
            return
        if not self._connected_device:
            QMessageBox.information(self, "Sync", "No iPhone connected.")
            return

        dest = Path(self._settings.destination_folder)
        dest.mkdir(parents=True, exist_ok=True)

        self._progress.reset()
        self._update_device_panel()
        self._log.append_log("Starting photo sync…")

        worker = self._sync_engine.start_sync(self._connected_device.udid)
        self._active_worker = worker
        self._update_device_panel()
        worker.progress.connect(self._on_progress)
        worker.file_progress.connect(self._progress.set_file_bytes)
        worker.log_message.connect(self._log.append_log)
        worker.error.connect(self._on_sync_error)
        worker.finished_sync.connect(self._on_sync_finished)

    def _cancel_sync(self) -> None:
        self._sync_engine.cancel_sync()
        self._log.append_log("Cancelling photo sync…")

    def _on_progress(self, filename: str, current: int, total: int) -> None:
        self._progress.set_overall(current, total, filename)

    def _on_sync_error(self, message: str) -> None:
        self._log.append_log(f"Error: {message}")
        QMessageBox.warning(self, "Sync Error", message)

    def _on_sync_finished(self, result: SyncResult) -> None:
        self._active_worker = None
        self._last_sync = datetime.now()
        self._progress.reset()
        self._update_device_panel()

        summary = (
            f"Photo sync finished — {result.copied} copied, "
            f"{result.skipped} skipped, {result.failed} failed"
        )
        self._log.append_log(summary)
        self.statusBar().showMessage(summary)

        if self._settings.minimize_to_tray:
            self._tray.showMessage(
                "iPhone Sync",
                summary,
                QSystemTrayIcon.MessageIcon.Information,
                4000,
            )

        if self._run_files_after_photos and self._connected_device:
            self._run_files_after_photos = False
            self._log.append_log("Starting Files app backup…")
            self._start_files_backup()
        elif self._run_device_backup_after_chain and self._connected_device:
            self._run_device_backup_after_chain = False
            self._log.append_log("Starting encrypted device backup…")
            self._start_device_backup()

    def _start_files_backup_clicked(self) -> None:
        self._run_files_after_photos = False
        # Manual run: still chain device backup only if user wants via settings? No — manual is files only.
        self._run_device_backup_after_chain = False
        self._start_files_backup()

    def _start_files_backup(self) -> None:
        if self._busy():
            return
        if not self._connected_device:
            QMessageBox.information(self, "Files Backup", "No iPhone connected.")
            return

        Path(self._settings.files_backup_folder).mkdir(parents=True, exist_ok=True)
        self._files_backup_progress.setValue(0)
        self._log.append_log("Starting Files app backup (Downloads + On My iPhone)…")

        worker = self._files_backup_engine.start_backup(self._connected_device.udid)
        self._files_backup_worker = worker
        self._update_device_panel()
        worker.progress.connect(self._on_files_backup_progress)
        worker.log_message.connect(self._log.append_log)
        worker.error.connect(lambda m: self._log.append_log(f"Files backup error: {m}"))
        worker.finished_files.connect(self._on_files_backup_finished)

    def _on_files_backup_progress(self, current: int, total: int, label: str) -> None:
        if total <= 0:
            self._files_backup_progress.setValue(0)
            return
        self._files_backup_progress.setValue(int((current / total) * 100))
        self.statusBar().showMessage(f"Files backup: {label} ({current}/{total})")

    def _on_files_backup_finished(self, result: FilesBackupResult) -> None:
        self._files_backup_worker = None
        self._files_backup_progress.setValue(100 if result.success else 0)
        self._update_device_panel()
        self._refresh_files_backup_status()

        if result.success:
            msg = (
                f"Files backup finished — Media: {result.media_files}, "
                f"On My iPhone: {result.app_files} files "
                f"({result.apps_backed_up} apps)"
            )
            self._log.append_log(msg)
            self.statusBar().showMessage(msg)
            if self._settings.minimize_to_tray:
                self._tray.showMessage(
                    "iPhone Sync",
                    msg,
                    QSystemTrayIcon.MessageIcon.Information,
                    4000,
                )
        else:
            err = result.error or "Files backup failed"
            self._log.append_log(err)
            if err != "cancelled":
                QMessageBox.warning(self, "Files Backup", err)

        if self._run_device_backup_after_chain and self._connected_device:
            self._run_device_backup_after_chain = False
            self._log.append_log("Starting encrypted device backup…")
            self._start_device_backup()

    def _delete_files_backup(self) -> None:
        if self._busy():
            QMessageBox.information(self, "Delete Files Backup", "Wait for the current job to finish.")
            return

        root = Path(self._settings.files_backup_folder)
        if not root.exists() or not any(root.iterdir()):
            QMessageBox.information(self, "Delete Files Backup", "No Files backups found.")
            return

        reply = QMessageBox.warning(
            self,
            "Delete Files Backup",
            f"Permanently delete all Files app backups under:\n\n{root}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        import shutil

        errors: list[str] = []
        for entry in list(root.iterdir()):
            try:
                if entry.is_dir():
                    shutil.rmtree(entry)
                else:
                    entry.unlink()
            except OSError as exc:
                errors.append(str(exc))

        self._refresh_files_backup_status()
        if errors:
            self._log.append_log("Files backup delete had errors: " + "; ".join(errors))
            QMessageBox.warning(self, "Delete Files Backup", "Some files could not be deleted.")
        else:
            self._log.append_log("Files backups deleted.")
            QMessageBox.information(self, "Delete Files Backup", "Files backups deleted.")

    def _start_device_backup_clicked(self) -> None:
        self._run_files_after_photos = False
        self._run_device_backup_after_chain = False
        self._start_device_backup(full=False)

    def _start_device_backup(self, *, full: bool = False) -> None:
        if self._busy():
            return
        if not self._connected_device:
            QMessageBox.information(self, "Device Backup", "No iPhone connected.")
            return

        Path(self._settings.device_backup_folder).mkdir(parents=True, exist_ok=True)
        self._device_backup_progress.setValue(0)
        self._log.append_log("Starting device backup (encrypted MobileBackup2)…")

        worker = self._device_backup_engine.start_backup(
            self._connected_device.udid, full=full
        )
        self._device_backup_worker = worker
        self._update_device_panel()
        worker.progress.connect(self._on_device_backup_progress)
        worker.log_message.connect(self._log.append_log)
        worker.error.connect(self._on_device_backup_error)
        worker.needs_encryption.connect(self._on_needs_encryption)
        worker.finished_backup.connect(self._on_device_backup_finished)

    def _on_device_backup_progress(self, pct: float) -> None:
        self._device_backup_progress.setValue(int(max(0, min(100, pct))))

    def _on_device_backup_error(self, message: str) -> None:
        self._log.append_log(f"Device backup error: {message}")

    def _on_needs_encryption(self) -> None:
        self._pending_encryption_then_backup = True

    def _on_device_backup_finished(self, result: DeviceBackupResult) -> None:
        self._device_backup_worker = None
        self._update_device_panel()
        self._refresh_device_backup_status()

        if result.error == "encryption_required" or self._pending_encryption_then_backup:
            self._pending_encryption_then_backup = False
            self._prompt_enable_encryption_then_backup()
            return

        if result.success:
            msg = "Device backup finished."
            if result.info:
                msg += f" {result.info.whatsapp_status_label}."
            self.statusBar().showMessage(msg)
            if self._settings.minimize_to_tray:
                self._tray.showMessage(
                    "iPhone Sync",
                    msg,
                    QSystemTrayIcon.MessageIcon.Information,
                    5000,
                )
            if result.info and not result.info.whatsapp_ok and result.info.whatsapp_in_manifest is False:
                QMessageBox.warning(
                    self,
                    "WhatsApp",
                    "Backup finished but WhatsApp data was not found in the payload.\n"
                    "Confirm WhatsApp is installed and encryption is on, then Backup Now again.",
                )
        else:
            err = result.error or "Device backup failed"
            self._log.append_log(err)
            if err != "encryption_required":
                QMessageBox.warning(self, "Device Backup", err)

    def _prompt_enable_encryption_then_backup(self) -> None:
        dialog = EncryptionPasswordDialog(self)
        if dialog.exec() != EncryptionPasswordDialog.DialogCode.Accepted:
            self._log.append_log(
                "Encrypted backup skipped — WhatsApp will not restore safely without encryption."
            )
            QMessageBox.warning(
                self,
                "Encryption Required",
                "Without encrypted backups, WhatsApp chats are incomplete.\n"
                "Press Backup Now again when you are ready to set a password.",
            )
            return

        if not self._connected_device:
            return

        password = dialog.password()
        self._log.append_log("Enabling backup encryption on iPhone…")
        worker = self._device_backup_engine.start_enable_encryption(
            self._connected_device.udid, password
        )
        self._device_backup_worker = worker
        self._update_device_panel()
        worker.log_message.connect(self._log.append_log)
        worker.error.connect(self._on_device_backup_error)
        worker.finished_backup.connect(self._on_encryption_enabled)

    def _on_encryption_enabled(self, result: DeviceBackupResult) -> None:
        self._device_backup_worker = None
        self._update_device_panel()
        if not result.success:
            QMessageBox.warning(
                self,
                "Encryption",
                result.error or "Could not enable backup encryption.",
            )
            return
        self._log.append_log("Encryption enabled — starting device backup…")
        self._start_device_backup(full=True)

    def _start_restore(self) -> None:
        if self._busy():
            return
        if not self._connected_device:
            QMessageBox.information(self, "Restore", "Connect the iPhone you want to restore onto.")
            return

        dialog = RestoreBackupDialog(Path(self._settings.device_backup_folder), self)
        if dialog.exec() != RestoreBackupDialog.DialogCode.Accepted:
            return
        backup = dialog.selected_backup()
        if not backup:
            return

        self._device_backup_progress.setValue(0)
        self._log.append_log(f"Starting restore from {backup.udid[:12]}…")
        worker = self._device_backup_engine.start_restore(
            self._connected_device.udid,
            source_udid=backup.udid,
            password=dialog.password(),
        )
        self._device_backup_worker = worker
        self._update_device_panel()
        worker.progress.connect(self._on_device_backup_progress)
        worker.log_message.connect(self._log.append_log)
        worker.error.connect(self._on_device_backup_error)
        worker.finished_restore.connect(self._on_restore_finished)

    def _on_restore_finished(self, result: DeviceBackupResult) -> None:
        self._device_backup_worker = None
        self._update_device_panel()
        if result.success:
            QMessageBox.information(
                self,
                "Restore",
                "Restore finished. The iPhone should reboot.\n\n"
                "After setup completes, open WhatsApp and verify your phone number if asked.",
            )
        else:
            QMessageBox.warning(
                self,
                "Restore",
                result.error or "Restore failed. See the log for details.",
            )

    def _open_settings(self) -> None:
        if SettingsDialog(self._settings, self).exec():
            self._refresh_device_backup_status()
            self._refresh_files_backup_status()

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.showNormal()
            self.activateWindow()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._settings.minimize_to_tray and self._tray.isVisible():
            event.ignore()
            self.hide()
            self._tray.showMessage(
                "iPhone Sync",
                "Running in the system tray. Plug in your iPhone to sync.",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )
        else:
            self._device_watcher.stop()
            event.accept()

    def _quit_app(self) -> None:
        self._device_watcher.stop()
        if self._sync_engine.is_running:
            self._sync_engine.cancel_sync()
        if self._files_backup_engine.is_running:
            self._files_backup_engine.cancel()
        if self._device_backup_engine.is_running:
            self._device_backup_engine.cancel()
        self._tray.hide()
        from PySide6.QtWidgets import QApplication

        QApplication.quit()
