"""Table built from widgets, for rows that hold badges, buttons or progress bars.

Used by the Queue, History and Tracks screens. Clicking a row reports it; selected rows are
tinted.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QFont, QMouseEvent, QPaintEvent
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QWidget

from radio_video.ui import theme
from radio_video.ui.theme import fonts
from radio_video.ui.widgets.painting import antialiased, follow_theme

CELL_PADDING_X = 10
CELL_PADDING_Y = 8
HEADER_HEIGHT = 34


@dataclass(frozen=True)
class Column:
    title: str
    width: int | None = None  # None stretches


def header_font() -> QFont:
    font = fonts.make_font(11, QFont.Weight.DemiBold)
    font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 106)
    font.setCapitalization(QFont.Capitalization.AllUppercase)
    return font


class GridTable(QWidget):
    # The clicked row, counted from 0 below the header.
    row_clicked = Signal(int)

    def __init__(
        self, columns: list[Column], *, on_surface: bool = False, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.columns = columns
        self._on_surface = on_surface
        self._rows = 0
        self._selected: set[int] = set()
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(0)
        self._grid.setVerticalSpacing(1)
        for index, column in enumerate(columns):
            title = QLabel(column.title)
            title.setFont(header_font())
            title.setProperty("tone", "secondary")
            self._grid.addWidget(self._cell(title, index, header=True), 0, index)
            self._grid.setColumnStretch(index, 0 if column.width else 1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        follow_theme(self)

    def _cell(self, widget: QWidget, column: int, *, header: bool = False) -> QWidget:
        cell = QWidget()
        layout = QHBoxLayout(cell)
        bottom = CELL_PADDING_Y + (2 if header else 0)
        layout.setContentsMargins(CELL_PADDING_X, CELL_PADDING_Y, CELL_PADDING_X, bottom)
        layout.addWidget(widget, 1, Qt.AlignmentFlag.AlignVCenter)
        width = self.columns[column].width
        if width:
            cell.setFixedWidth(width)
        else:
            cell.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        if header:
            cell.setFixedHeight(HEADER_HEIGHT)
        return cell

    def row_count(self) -> int:
        return self._rows

    def add_row(self, cells: list[QWidget], *, selected: bool = False) -> None:
        self._rows += 1
        for column, widget in enumerate(cells):
            self._grid.addWidget(self._cell(widget, column), self._rows, column)
        if selected:
            self._selected.add(self._rows)

    def set_selected(self, rows: set[int]) -> None:
        """Tint these rows, counted from 0 below the header."""
        self._selected = {row + 1 for row in rows}
        self.update()

    def row_at(self, y: float) -> int | None:
        for row in range(1, self._rows + 1):
            span = self._row_span(row)
            if span is not None and span[0] <= y <= span[1] + 1:
                return row - 1
        return None

    def _row_span(self, row: int) -> tuple[int, int] | None:
        top = bottom = None
        for column in range(len(self.columns)):
            item = self._grid.itemAtPosition(row, column)
            cell = item.widget() if item is not None else None
            if cell is None:
                continue
            geometry = cell.geometry()
            top = geometry.top() if top is None else min(top, geometry.top())
            bottom = geometry.bottom() if bottom is None else max(bottom, geometry.bottom())
        if top is None or bottom is None:
            return None
        return top, bottom

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        row = self.row_at(event.position().y())
        if row is not None and event.button() == Qt.MouseButton.LeftButton:
            self.row_clicked.emit(row)
        super().mousePressEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        p = theme.palette()
        width = float(self.width())
        for row in range(self._rows + 1):
            span = self._row_span(row)
            if span is None:
                continue
            top, bottom = span
            if row == 0:
                painter.fillRect(
                    QRectF(0, top, width, bottom - top + 1), p.surface if self._on_surface else p.bg
                )
                painter.fillRect(QRectF(0, bottom - 1, width, 2), p.rule)
            else:
                if row in self._selected:
                    painter.fillRect(QRectF(0, top, width, bottom - top + 1), p.accent_tint)
                painter.fillRect(QRectF(0, bottom + 1, width, 1), p.border)
