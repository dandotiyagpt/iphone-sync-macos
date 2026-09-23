"""Dialogs for encrypted backup password and restore with modern macOS styling."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
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
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        # Header
        header = QHBoxLayout()
        header.setSpacing(12)
        icon_lbl = QLabel("🔐")
        icon_lbl.setFixedSize(38, 38)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #BF5AF2, stop:1 #5E5CE6); "
            "border-radius: 10px; "
            "font-size: 18px;"
        )
        header.addWidget(icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        title_lbl = QLabel("Enable Encrypted Backup")
        title_lbl.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: 700;")
        sub_lbl = QLabel("Required for WhatsApp chats, health data & app settings")
        sub_lbl.setStyleSheet("color: #8E8E93; font-size: 12px;")
        title_vbox.addWidget(title_lbl)
        title_vbox.addWidget(sub_lbl)
        header.addLayout(title_vbox)
        header.addStretch()
        layout.addLayout(header)

        # Notice Card
        notice_card = QFrame()
        notice_card.setStyleSheet(
            "background: rgba(255, 159, 10, 0.08); "
            "border: 1px solid rgba(255, 159, 10, 0.22); "
            "border-radius: 8px; "
            "padding: 10px;"
        )
        notice_layout = QVBoxLayout(notice_card)
        notice_layout.setContentsMargins(10, 8, 10, 8)
        notice_text = QLabel(
            "Encrypted backups are mandatory for WhatsApp chat history.\n"
            "Choose a password you will remember — without it, future restore will be impossible."
        )
        notice_text.setStyleSheet("color: #FFD60A; font-size: 12px; line-height: 1.4; border: none; background: transparent;")
        notice_text.setWordWrap(True)
        notice_layout.addWidget(notice_text)
        layout.addWidget(notice_card)

        form = QFormLayout()
        form.setVerticalSpacing(10)
        self._password = QLineEdit()
        self._password.setMinimumWidth(280)
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setPlaceholderText("Enter at least 4 characters")
        self._confirm = QLineEdit()
        self._confirm.setMinimumWidth(280)
        self._confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm.setPlaceholderText("Re-enter password to confirm")
        form.addRow("Password:", self._password)
        form.addRow("Confirm:", self._confirm)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setProperty("btnStyle", "primary-purple")
        ok_btn.setText("Enable Encryption")
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_btn.setProperty("btnStyle", "header-action")

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
        self.setMinimumSize(560, 420)
        self._backups = list_local_backups(backup_root)
        self._selected: LocalBackupInfo | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        # Header
        header = QHBoxLayout()
        header.setSpacing(12)
        icon_lbl = QLabel("🔄")
        icon_lbl.setFixedSize(38, 38)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #BF5AF2, stop:1 #5E5CE6); "
            "border-radius: 10px; "
            "font-size: 18px;"
        )
        header.addWidget(icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        title_lbl = QLabel("Restore Device Backup")
        title_lbl.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: 700;")
        sub_lbl = QLabel("Restore WhatsApp, apps, and settings onto the connected iPhone")
        sub_lbl.setStyleSheet("color: #8E8E93; font-size: 12px;")
        title_vbox.addWidget(title_lbl)
        title_vbox.addWidget(sub_lbl)
        header.addLayout(title_vbox)
        header.addStretch()
        layout.addLayout(header)

        # Warning Card
        warning_card = QFrame()
        warning_card.setStyleSheet(
            "background: rgba(255, 69, 58, 0.08); "
            "border: 1px solid rgba(255, 69, 58, 0.2); "
            "border-radius: 8px; "
            "padding: 10px;"
        )
        w_layout = QVBoxLayout(warning_card)
        w_layout.setContentsMargins(10, 8, 10, 8)
        w_text = QLabel(
            "⚠️ This replaces data on the connected iPhone (standard Finder / iTunes restore).\n"
            "WhatsApp and apps will be restored if backup encryption was enabled."
        )
        w_text.setStyleSheet("color: #FF8079; font-size: 12px; line-height: 1.4; border: none; background: transparent;")
        w_text.setWordWrap(True)
        w_layout.addWidget(w_text)
        layout.addWidget(warning_card)

        # List
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
                    f"📱 {backup.device_name}  ·  iOS {backup.product_version or '?'}  ·  "
                    f"{when}  ·  {format_size(backup.size_bytes)}\n"
                    f"UDID: {backup.udid[:14]}…  ·  "
                    f"{'🔒 Encrypted' if backup.is_encrypted else '⚠️ NOT encrypted'}  ·  "
                    f"{backup.whatsapp_status_label}"
                )
                item = QListWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, backup)
                self._list.addItem(item)
            self._list.setCurrentRow(0)
        layout.addWidget(self._list)

        form = QFormLayout()
        self._password = QLineEdit()
        self._password.setMinimumWidth(320)
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setPlaceholderText("Required if backup is encrypted")
        form.addRow("Backup password:", self._password)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setProperty("btnStyle", "primary-purple")
        ok_btn.setText("Restore onto iPhone…")
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_btn.setProperty("btnStyle", "header-action")

        buttons.accepted.connect(self._confirm)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if not self._backups:
            ok_btn.setEnabled(False)

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
