"""Reusable UI widgets."""

from PySide6.QtWidgets import QProgressBar, QTextEdit, QVBoxLayout, QWidget, QLabel


class ProgressWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._file_label = QLabel("No sync in progress")
        self._overall = QProgressBar()
        self._overall.setRange(0, 100)
        self._overall.setValue(0)
        self._file_progress = QProgressBar()
        self._file_progress.setRange(0, 100)
        self._file_progress.setValue(0)
        self._file_progress.setVisible(False)

        layout.addWidget(self._file_label)
        layout.addWidget(self._overall)
        layout.addWidget(self._file_progress)

    def reset(self) -> None:
        self._file_label.setText("No sync in progress")
        self._overall.setValue(0)
        self._file_progress.setVisible(False)
        self._file_progress.setValue(0)

    def set_overall(self, current: int, total: int, filename: str) -> None:
        if total <= 0:
            self._overall.setValue(0)
            self._file_label.setText("No sync in progress")
            return
        pct = int((current / total) * 100)
        self._overall.setValue(pct)
        self._file_label.setText(f"Copying {filename} ({current}/{total})")

    def set_file_bytes(self, transferred: int, total: int) -> None:
        if total <= 0:
            self._file_progress.setVisible(False)
            return
        self._file_progress.setVisible(True)
        pct = int((transferred / total) * 100)
        self._file_progress.setValue(pct)


class LogViewer(QTextEdit):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)

    def append_log(self, message: str) -> None:
        from datetime import datetime

        ts = datetime.now().strftime("%H:%M:%S")
        self.append(f"[{ts}] {message}")
