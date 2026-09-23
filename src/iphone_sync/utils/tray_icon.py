"""Menu bar (status bar) icon rendering.

Qt's built-in standard icons look out of place in the macOS menu bar, so the
status item glyph is drawn here: a simple phone outline whose accent dot
reflects the current state (idle / connected / working / attention).
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

TrayState = str  # "idle" | "connected" | "busy" | "attention"

_STATE_COLORS: dict[str, str] = {
    "idle": "#8E8E93",
    "connected": "#30D158",
    "busy": "#0A84FF",
    "attention": "#FF9F0A",
}

_ICON_SIZE = 44  # rendered large, Qt scales down for the menu bar


def _dot_color(state: TrayState) -> QColor:
    return QColor(_STATE_COLORS.get(state, _STATE_COLORS["idle"]))


def make_tray_icon(state: TrayState = "idle") -> QIcon:
    """Return a menu bar icon: phone outline plus a state-colored dot."""
    pixmap = QPixmap(_ICON_SIZE, _ICON_SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    body = QRectF(13.0, 5.0, 18.0, 30.0)
    pen = QPen(QColor("#FFFFFF"))
    pen.setWidthF(2.4)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(body, 4.5, 4.5)

    # Home indicator line at the bottom of the phone.
    painter.drawLine(19, 31, 25, 31)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_dot_color(state))
    painter.drawEllipse(QRectF(25.0, 26.0, 13.0, 13.0))

    painter.end()

    icon = QIcon(pixmap)
    icon.setIsMask(False)
    return icon
