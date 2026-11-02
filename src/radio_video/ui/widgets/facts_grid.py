"""Facts grid: Container · Duration · Size · Bitrate · Title, separated by hairlines.

Wide: one row, the title cell twice as wide. Narrow: the title moves to its own row.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPaintEvent, QResizeEvent
from PySide6.QtWidgets import QGridLayout, QSizePolicy, QVBoxLayout, QWidget

from radio_video.ui import theme
from radio_video.ui.theme.fonts import TextStyle
from radio_video.ui.widgets.labels import ElidedLabel, kicker
from radio_video.ui.widgets.painting import antialiased, follow_theme

NARROW_BELOW = 760
PADDING_X = 16
FIRST_PADDING_X = 24
PADDING_Y = 10


class FactCell(QWidget):
    def __init__(self, title: str, value: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = kicker(title)
        self.value = ElidedLabel(value, TextStyle.BODY_STRONG)
        self._layout = QVBoxLayout(self)
        layout = self._layout
        layout.setContentsMargins(PADDING_X, PADDING_Y, PADDING_X, PADDING_Y)
        layout.setSpacing(0)
        layout.addWidget(self.title)
        layout.addWidget(self.value)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

    def set_value(self, value: str) -> None:
        self.value.setText(value)
        self.setAccessibleName(f"{self.title.text()}: {value}")

    def set_first(self, first: bool) -> None:
        left = FIRST_PADDING_X if first else PADDING_X
        self._layout.setContentsMargins(left, PADDING_Y, PADDING_X, PADDING_Y)


class FactsGrid(QWidget):
    def __init__(self, titles: list[str], wide_title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.cells = [FactCell(title, "—") for title in titles]
        self.wide = FactCell(wide_title, "—")
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 1, 0, 1)
        self._grid.setHorizontalSpacing(1)
        self._grid.setVerticalSpacing(1)
        self._narrow: bool | None = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        follow_theme(self)
        self._relayout(narrow=False)

    def set_values(self, values: list[str], wide_value: str) -> None:
        for cell, value in zip(self.cells, values, strict=True):
            cell.set_value(value)
        self.wide.set_value(wide_value)

    def is_narrow(self) -> bool:
        return bool(self._narrow)

    def _relayout(self, *, narrow: bool) -> None:
        if narrow == self._narrow:
            return
        self._narrow = narrow
        for cell in [*self.cells, self.wide]:
            self._grid.removeWidget(cell)
        count = len(self.cells)
        for column, cell in enumerate(self.cells):
            self._grid.addWidget(cell, 0, column)
            self._grid.setColumnStretch(column, 1)
            cell.set_first(column == 0)
        if narrow:
            self._grid.addWidget(self.wide, 1, 0, 1, count)
            self._grid.setColumnStretch(count, 0)
            self.wide.set_first(True)
        else:
            self._grid.addWidget(self.wide, 0, count)
            self._grid.setColumnStretch(count, 2)
            self.wide.set_first(False)
        self.update()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._relayout(narrow=event.size().width() < NARROW_BELOW)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        p = theme.palette()
        width = float(self.width())
        painter.fillRect(QRectF(0, 0, width, 1), p.border)
        painter.fillRect(QRectF(0, self.height() - 1, width, 1), p.border)
        for cell in [*self.cells[1:], self.wide]:
            geometry = cell.geometry()
            if self._narrow and cell is self.wide:
                painter.fillRect(QRectF(0, geometry.top() - 1, width, 1), p.border)
            else:
                painter.fillRect(
                    QRectF(geometry.left() - 1, geometry.top(), 1, geometry.height()), p.border
                )
