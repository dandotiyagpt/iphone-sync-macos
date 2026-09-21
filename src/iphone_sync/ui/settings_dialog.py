"""Settings dialog."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from iphone_sync.config import Settings
from iphone_sync.utils.startup import set_start_at_login


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(520)
        self._settings = settings
        self._build_ui()
        self._load_settings()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        dest_row = QHBoxLayout()
        self._dest_edit = QLineEdit()
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_destination)
        dest_row.addWidget(self._dest_edit)
        dest_row.addWidget(browse_btn)
        form.addRow("Photo destination:", dest_row)

        files_row = QHBoxLayout()
        self._files_backup_edit = QLineEdit()
        files_browse = QPushButton("Browse…")
        files_browse.clicked.connect(self._browse_files_backup)
        files_row.addWidget(self._files_backup_edit)
        files_row.addWidget(files_browse)
        form.addRow("Files app backup folder:", files_row)

        device_row = QHBoxLayout()
        self._device_backup_edit = QLineEdit()
        device_browse = QPushButton("Browse…")
        device_browse.clicked.connect(self._browse_device_backup)
        device_row.addWidget(self._device_backup_edit)
        device_row.addWidget(device_browse)
        form.addRow("Device backup folder:", device_row)

        form.addRow(QLabel(""))

        self._auto_sync = QCheckBox("Automatically sync photos when iPhone is plugged in")
        form.addRow(self._auto_sync)

        self._auto_files_backup = QCheckBox(
            "Automatically back up Files app data (Downloads + On My iPhone Documents)"
        )
        form.addRow(self._auto_files_backup)

        self._auto_device_backup = QCheckBox(
            "Automatically run encrypted device backup (WhatsApp / apps)"
        )
        form.addRow(self._auto_device_backup)

        self._organize_by_date = QCheckBox("Organize copied photos by year/month")
        form.addRow(self._organize_by_date)

        self._start_at_login = QCheckBox("Open at Login")
        form.addRow(self._start_at_login)

        self._minimize_to_tray = QCheckBox("Keep running in menu bar")
        form.addRow(self._minimize_to_tray)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_settings(self) -> None:
        self._dest_edit.setText(self._settings.destination_folder)
        self._files_backup_edit.setText(self._settings.files_backup_folder)
        self._device_backup_edit.setText(self._settings.device_backup_folder)
        self._auto_sync.setChecked(self._settings.auto_sync_on_plugin)
        self._auto_files_backup.setChecked(self._settings.auto_files_backup_on_plugin)
        self._auto_device_backup.setChecked(self._settings.auto_device_backup_on_plugin)
        self._organize_by_date.setChecked(self._settings.organize_by_date)
        self._start_at_login.setChecked(self._settings.start_at_login)
        self._minimize_to_tray.setChecked(self._settings.minimize_to_tray)

    def _browse_destination(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select photo destination folder", self._dest_edit.text()
        )
        if path:
            self._dest_edit.setText(path)

    def _browse_files_backup(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select Files app backup folder", self._files_backup_edit.text()
        )
        if path:
            self._files_backup_edit.setText(path)

    def _browse_device_backup(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select device backup folder", self._device_backup_edit.text()
        )
        if path:
            self._device_backup_edit.setText(path)

    def _save_and_close(self) -> None:
        dest = self._dest_edit.text().strip()
        if dest:
            Path(dest).mkdir(parents=True, exist_ok=True)
            self._settings.destination_folder = dest

        files_dest = self._files_backup_edit.text().strip()
        if files_dest:
            Path(files_dest).mkdir(parents=True, exist_ok=True)
            self._settings.files_backup_folder = files_dest

        device_dest = self._device_backup_edit.text().strip()
        if device_dest:
            Path(device_dest).mkdir(parents=True, exist_ok=True)
            self._settings.device_backup_folder = device_dest

        self._settings.auto_sync_on_plugin = self._auto_sync.isChecked()
        self._settings.auto_files_backup_on_plugin = self._auto_files_backup.isChecked()
        self._settings.auto_device_backup_on_plugin = self._auto_device_backup.isChecked()
        self._settings.organize_by_date = self._organize_by_date.isChecked()
        self._settings.start_at_login = self._start_at_login.isChecked()
        self._settings.minimize_to_tray = self._minimize_to_tray.isChecked()
        self._settings.save()

        set_start_at_login(self._settings.start_at_login)
        self.accept()
