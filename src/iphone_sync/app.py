"""QApplication bootstrap."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from iphone_sync.config import Settings
from iphone_sync.ui.main_window import MainWindow
from iphone_sync.utils.startup import set_start_at_login


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("iPhone Sync")
    app.setOrganizationName("iPhoneSync")
    app.setQuitOnLastWindowClosed(False)

    settings = Settings.load()

    # Sync startup registry with saved setting
    set_start_at_login(settings.start_at_login)

    window = MainWindow(settings)
    window.show()

    sys.exit(app.exec())
