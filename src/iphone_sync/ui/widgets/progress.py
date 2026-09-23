"""Reusable UI widgets — progress display and rich-colored activity log."""

from __future__ import annotations

import html
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class ProgressWidget(QWidget):
    """Modern progress widget with dual progress bars and percentage indicators."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header row: Status label on left, percentage badge on right
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)

        self._file_label = QLabel("No sync in progress")
        self._file_label.setStyleSheet("color: #E5E5EA; font-weight: 500; font-size: 13px;")

        self._pct_badge = QLabel("0%")
        self._pct_badge.setStyleSheet(
            "background: rgba(255, 159, 10, 0.15); "
            "color: #FF9F0A; "
            "font-weight: 700; "
            "font-size: 11px; "
            "padding: 2px 8px; "
            "border-radius: 6px; "
            "border: 1px solid rgba(255, 159, 10, 0.25);"
        )
        self._pct_badge.setVisible(False)

        header_row.addWidget(self._file_label)
        header_row.addStretch()
        header_row.addWidget(self._pct_badge)
        layout.addLayout(header_row)

        # Overall progress bar
        self._overall = QProgressBar()
        self._overall.setRange(0, 100)
        self._overall.setValue(0)
        self._overall.setProperty("barStyle", "coral")
        layout.addWidget(self._overall)

        # File bytes sub-row
        self._file_box = QWidget()
        file_box_layout = QVBoxLayout(self._file_box)
        file_box_layout.setContentsMargins(0, 4, 0, 0)
        file_box_layout.setSpacing(4)

        self._file_detail_label = QLabel("Active file transfer…")
        self._file_detail_label.setStyleSheet("color: #9898A0; font-size: 11px;")
        file_box_layout.addWidget(self._file_detail_label)

        self._file_progress = QProgressBar()
        self._file_progress.setRange(0, 100)
        self._file_progress.setValue(0)
        self._file_progress.setProperty("barStyle", "blue")
        file_box_layout.addWidget(self._file_progress)

        self._file_box.setVisible(False)
        layout.addWidget(self._file_box)

    def reset(self) -> None:
        self._file_label.setText("No sync in progress")
        self._pct_badge.setText("0%")
        self._pct_badge.setVisible(False)
        self._overall.setValue(0)
        self._file_box.setVisible(False)
        self._file_progress.setValue(0)

    def set_overall(self, current: int, total: int, filename: str) -> None:
        if total <= 0:
            self.reset()
            return
        pct = int((current / total) * 100)
        self._overall.setValue(pct)
        self._file_label.setText(f"Copying {filename} ({current}/{total})")
        self._pct_badge.setText(f"{pct}%")
        self._pct_badge.setVisible(True)

    def set_file_bytes(self, transferred: int, total: int) -> None:
        if total <= 0:
            self._file_box.setVisible(False)
            return
        self._file_box.setVisible(True)
        pct = int((transferred / total) * 100)
        self._file_progress.setValue(pct)
        self._file_detail_label.setText(f"Current file: {pct}% ({transferred // 1024} KB / {total // 1024} KB)")


class LogViewer(QTextEdit):
    """High-contrast rich terminal log viewer with syntax-colored events."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setMinimumHeight(120)

    def append_log(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        escaped_msg = html.escape(message)

        # Intelligent color-coding based on message tone
        lower = message.lower()
        if any(k in lower for k in ("error", "failed", "broken pipe", "exception")):
            color = "#FF6961"  # Apple Red
            prefix = "✖ "
        elif any(k in lower for k in ("complete", "finished", "success", "cleared", "backed up", "ready.")):
            color = "#30D158"  # Apple Emerald Green
            prefix = "✔ "
        elif any(k in lower for k in ("warning", "caution", "skipped", "not ready")):
            color = "#FFD60A"  # Apple Yellow
            prefix = "▲ "
        elif any(k in lower for k in ("connected", "starting", "enabling", "restoring")):
            color = "#64D2FF"  # Apple Cyan
            prefix = "● "
        else:
            color = "#D1D5DB"  # Clean Light Gray
            prefix = ""

        formatted_html = (
            f'<div style="margin: 2px 0; font-family: Menlo, Monaco, Consolas, monospace; font-size: 11px;">'
            f'<span style="color: #636366; font-weight: 600;">[{ts}]</span> '
            f'<span style="color: {color};">{prefix}{escaped_msg}</span>'
            f'</div>'
        )
        self.append(formatted_html)
        # Auto-scroll to bottom
        sb = self.verticalScrollBar()
        sb.setValue(sb.maximum())

    def clear_logs(self) -> None:
        self.clear()
