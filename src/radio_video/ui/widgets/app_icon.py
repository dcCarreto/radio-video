"""The painted app icon at any size."""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from radio_video.ui import icons


class AppIcon(QWidget):
    def __init__(self, size: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setAccessibleName("Radio/Video")

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        icons.paint_app_icon(painter, QRectF(self.rect()))
        painter.end()
