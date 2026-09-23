"""Standalone gallery application entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from iphone_sync.config import Settings
from iphone_sync.ui.gallery_window import GalleryWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("iPhone Photos")
    app.setOrganizationName("iPhoneSync")

    settings = Settings.load()

    from iphone_sync.ui.theme import get_theme_stylesheet
    app.setStyleSheet(get_theme_stylesheet(settings.theme))

    window = GalleryWindow(settings)
    window.show()

    sys.exit(app.exec())
