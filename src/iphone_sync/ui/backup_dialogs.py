"""Dialogs for encrypted backup password and restore."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QVBoxLayout,
)

from iphone_sync.core.device_backup_info import LocalBackupInfo, format_size, list_local_backups


class EncryptionPasswordDialog(QDialog):
    """Prompt to enable encrypted device backups (required for WhatsApp)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Enable Encrypted Backup")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)

        layout.addWidget(
            QLabel(
                "Encrypted backups are required for WhatsApp chats and most app data.\n"
                "Choose a password you will remember — without it, restore will fail."
            )
        )

        form = QFormLayout()
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm = QLineEdit()
        self._confirm.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Password:", self._password)
        form.addRow("Confirm:", self._confirm)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate(self) -> None:
        pwd = self._password.text()
        if len(pwd) < 4:
            QMessageBox.warning(self, "Password", "Use at least 4 characters.")
            return
        if pwd != self._confirm.text():
            QMessageBox.warning(self, "Password", "Passwords do not match.")
            return
        self.accept()

    def password(self) -> str:
        return self._password.text()


class RestoreBackupDialog(QDialog):
    """Pick a local device backup and enter password for restore."""

    def __init__(self, backup_root: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Restore Device Backup")
        self.setMinimumSize(520, 360)
        self._backups = list_local_backups(backup_root)
        self._selected: LocalBackupInfo | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "This replaces data on the connected iPhone (like Finder/iTunes restore).\n"
                "Use a new or erased phone, or accept that existing data will be overwritten.\n"
                "WhatsApp will restore with the backup if encryption was enabled."
            )
        )

        self._list = QListWidget()
        if not self._backups:
            self._list.addItem("No local device backups found.")
            self._list.setEnabled(False)
        else:
            for backup in self._backups:
                when = (
                    backup.last_backup.strftime("%Y-%m-%d %H:%M")
                    if backup.last_backup
                    else "unknown date"
                )
                text = (
                    f"{backup.device_name}  ·  iOS {backup.product_version or '?'}  ·  "
                    f"{when}  ·  {format_size(backup.size_bytes)}\n"
                    f"{backup.udid[:12]}…  ·  "
                    f"{'encrypted' if backup.is_encrypted else 'NOT encrypted'}  ·  "
                    f"{backup.whatsapp_status_label}"
                )
                item = QListWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, backup)
                self._list.addItem(item)
            self._list.setCurrentRow(0)
        layout.addWidget(self._list)

        form = QFormLayout()
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setPlaceholderText("Required if backup is encrypted")
        form.addRow("Backup password:", self._password)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Restore…")
        buttons.accepted.connect(self._confirm)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if not self._backups:
            buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

    def _confirm(self) -> None:
        item = self._list.currentItem()
        if not item or not self._list.isEnabled():
            return
        backup: LocalBackupInfo = item.data(Qt.ItemDataRole.UserRole)
        if backup.is_encrypted and not self._password.text():
            QMessageBox.warning(self, "Password", "Enter the backup encryption password.")
            return

        reply = QMessageBox.warning(
            self,
            "Confirm Restore",
            f"Restore backup of “{backup.device_name}” onto the connected iPhone?\n\n"
            f"{backup.whatsapp_status_label}\n\n"
            "This can overwrite phone data. The device will reboot when finished.\n"
            "Keep the cable connected until restore completes.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._selected = backup
        self.accept()

    def selected_backup(self) -> LocalBackupInfo | None:
        return self._selected

    def password(self) -> str:
        return self._password.text()
