"""Settings dialog."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from iphone_sync.config import Settings
from iphone_sync.ui.theme import list_themes
from iphone_sync.utils.startup import set_start_at_login


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(640)
        self._settings = settings
        self._build_ui()
        self._load_settings()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        header.setSpacing(12)
        icon_lbl = QLabel("⚙️")
        icon_lbl.setFixedSize(38, 38)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet(
            "background: rgba(255, 255, 255, 0.08); "
            "border-radius: 10px; "
            "font-size: 20px; "
            "border: 1px solid rgba(255, 255, 255, 0.12);"
        )
        header.addWidget(icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        title_lbl = QLabel("Settings")
        title_lbl.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: 700;")
        sub_lbl = QLabel("Backup folders, automation, and menu bar behavior")
        sub_lbl.setStyleSheet("color: #8E8E93; font-size: 12px;")
        title_vbox.addWidget(title_lbl)
        title_vbox.addWidget(sub_lbl)
        header.addLayout(title_vbox)
        header.addStretch()
        layout.addLayout(header)

        form = QFormLayout()
        form.setVerticalSpacing(12)
        form.setHorizontalSpacing(14)

        dest_row = QHBoxLayout()
        self._dest_edit = QLineEdit()
        self._dest_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_destination)
        dest_row.addWidget(self._dest_edit)
        dest_row.addWidget(browse_btn)
        form.addRow("Photo destination:", dest_row)

        files_row = QHBoxLayout()
        self._files_backup_edit = QLineEdit()
        self._files_backup_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        files_browse = QPushButton("Browse…")
        files_browse.clicked.connect(self._browse_files_backup)
        files_row.addWidget(self._files_backup_edit)
        files_row.addWidget(files_browse)
        form.addRow("Files backup folder:", files_row)

        whatsapp_row = QHBoxLayout()
        self._whatsapp_backup_edit = QLineEdit()
        self._whatsapp_backup_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        whatsapp_browse = QPushButton("Browse…")
        whatsapp_browse.clicked.connect(self._browse_whatsapp_backup)
        whatsapp_row.addWidget(self._whatsapp_backup_edit)
        whatsapp_row.addWidget(whatsapp_browse)
        form.addRow("WhatsApp backup folder:", whatsapp_row)

        form.addRow(QLabel(""))

        self._auto_sync = QCheckBox("Automatically sync photos when iPhone is plugged in")
        form.addRow(self._auto_sync)

        self._auto_files_backup = QCheckBox(
            "Automatically back up Files app media (Downloads, Books, Recordings…)"
        )
        form.addRow(self._auto_files_backup)

        self._auto_whatsapp_backup = QCheckBox(
            "Automatically back up WhatsApp chats when iPhone is plugged in"
        )
        form.addRow(self._auto_whatsapp_backup)

        self._organize_by_date = QCheckBox("Organize copied photos by year/month")
        form.addRow(self._organize_by_date)

        self._start_at_login = QCheckBox(
            "Start automatically when you log in (hidden in the menu bar)"
        )
        form.addRow(self._start_at_login)

        self._run_in_background = QCheckBox(
            "Keep running in the menu bar when the window is closed"
        )
        form.addRow(self._run_in_background)

        self._menu_bar_only = QCheckBox("Menu bar only — hide the Dock icon")
        form.addRow(self._menu_bar_only)

        form.addRow(QLabel(""))
        theme_row = QHBoxLayout()
        self._theme_combo = QComboBox()
        for theme_id, display_name, _desc in list_themes():
            self._theme_combo.addItem(display_name, theme_id)
        theme_row.addWidget(self._theme_combo)
        form.addRow("Visual theme:", theme_row)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setProperty("btnStyle", "primary-blue")
        ok_btn.setText("Save Changes")
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_btn.setProperty("btnStyle", "header-action")

        buttons.accepted.connect(self._save_and_close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_settings(self) -> None:
        self._dest_edit.setText(self._settings.destination_folder)
        self._files_backup_edit.setText(self._settings.files_backup_folder)
        self._whatsapp_backup_edit.setText(self._settings.whatsapp_backup_folder)
        self._auto_sync.setChecked(self._settings.auto_sync_on_plugin)
        self._auto_files_backup.setChecked(self._settings.auto_files_backup_on_plugin)
        self._auto_whatsapp_backup.setChecked(self._settings.auto_whatsapp_backup_on_plugin)
        self._organize_by_date.setChecked(self._settings.organize_by_date)
        self._start_at_login.setChecked(self._settings.start_at_login)
        self._run_in_background.setChecked(self._settings.run_in_background)
        self._menu_bar_only.setChecked(self._settings.menu_bar_only)
        theme_idx = self._theme_combo.findData(getattr(self._settings, "theme", "obsidian_dark"))
        if theme_idx >= 0:
            self._theme_combo.setCurrentIndex(theme_idx)

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

    def _browse_whatsapp_backup(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select WhatsApp backup folder", self._whatsapp_backup_edit.text()
        )
        if path:
            self._whatsapp_backup_edit.setText(path)

    def _save_and_close(self) -> None:
        dest = self._dest_edit.text().strip()
        if dest:
            Path(dest).mkdir(parents=True, exist_ok=True)
            self._settings.destination_folder = dest

        files_dest = self._files_backup_edit.text().strip()
        if files_dest:
            Path(files_dest).mkdir(parents=True, exist_ok=True)
            self._settings.files_backup_folder = files_dest

        whatsapp_dest = self._whatsapp_backup_edit.text().strip()
        if whatsapp_dest:
            Path(whatsapp_dest).mkdir(parents=True, exist_ok=True)
            self._settings.whatsapp_backup_folder = whatsapp_dest

        self._settings.auto_sync_on_plugin = self._auto_sync.isChecked()
        self._settings.auto_files_backup_on_plugin = self._auto_files_backup.isChecked()
        self._settings.auto_whatsapp_backup_on_plugin = self._auto_whatsapp_backup.isChecked()
        self._settings.organize_by_date = self._organize_by_date.isChecked()
        self._settings.start_at_login = self._start_at_login.isChecked()
        self._settings.run_in_background = self._run_in_background.isChecked()
        self._settings.menu_bar_only = self._menu_bar_only.isChecked()
        self._settings.theme = self._theme_combo.currentData() or "obsidian_dark"
        self._settings.save()

        set_start_at_login(self._settings.start_at_login)
        self.accept()
