"""Standalone photo library window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog, QMainWindow, QMessageBox

from iphone_sync.config import Settings
from iphone_sync.ui.gallery.gallery_widget import GalleryWidget


class GalleryWindow(QMainWindow):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings
        self.setWindowTitle("iPhone Photos")
        self.setMinimumSize(1100, 650)
        self.resize(1280, 800)

        self._gallery = GalleryWidget(Path(self._settings.destination_folder))
        self._gallery.source_changed.connect(self._on_source_changed)
        self.setCentralWidget(self._gallery)

        self._build_menu()
        self.statusBar().showMessage(f"Library: {self._settings.destination_folder}")

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")

        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self._gallery.refresh)
        file_menu.addAction(refresh_action)

        folder_action = QAction("Change folder…", self)
        folder_action.triggered.connect(self._change_folder)
        file_menu.addAction(folder_action)

        file_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

    def _on_source_changed(self, path: str) -> None:
        self.statusBar().showMessage(f"Library: {path}")

    def _change_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Select photo library folder",
            self._settings.destination_folder,
        )
        if not path:
            return
        self._settings.destination_folder = path
        self._settings.save()
        self._gallery.set_destination(Path(path))

    def closeEvent(self, event) -> None:
        self._gallery.stop_preview()
        super().closeEvent(event)
