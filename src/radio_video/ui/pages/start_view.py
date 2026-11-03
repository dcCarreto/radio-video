"""Start screen: what the app does, one drop zone, and three reassurances."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPaintEvent
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from radio_video.ui import strings as s
from radio_video.ui import theme
from radio_video.ui.icons import IconName
from radio_video.ui.strings import tr
from radio_video.ui.theme import fonts
from radio_video.ui.theme.fonts import TextStyle
from radio_video.ui.widgets.drop_zone import DropRefusal, DropState, DropZone
from radio_video.ui.widgets.labels import label
from radio_video.ui.widgets.painting import antialiased, follow_theme
from radio_video.ui.widgets.progress import StatusIcon

HERO_MAX_WIDTH = 820
INTRO_MAX_WIDTH = 680

REFUSALS = {
    DropRefusal.SEVERAL_FILES: s.DROP_BLOCKED_SEVERAL,
    DropRefusal.FOLDER: s.DROP_BLOCKED_SEVERAL,
    DropRefusal.BUSY: s.DROP_BLOCKED_CONVERTING,
}


def make_drop_zone(
    is_busy: Callable[[], bool] = lambda: False, *, show_open_button: bool = True
) -> DropZone:
    return DropZone(
        titles={
            DropState.IDLE: tr(s.DROP_IDLE_TITLE),
            DropState.OVER: tr(s.DROP_OVER_TITLE),
            DropState.BLOCKED: tr(s.DROP_BLOCKED_TITLE),
            DropState.READING: tr(s.ANALYZING_TITLE),
        },
        idle_hint=tr(s.DROP_IDLE_HINT),
        idle_help=tr(s.DROP_IDLE_HELP),
        over_text=tr(s.DROP_OVER_TEXT),
        reading_text=tr(s.ANALYZING_TEXT),
        open_text=tr(s.ACTION_OPEN),
        open_shortcut=tr(s.SHORTCUT_OPEN),
        refusal_text=lambda refusal: tr(REFUSALS[refusal]),
        is_busy=is_busy,
        show_open_button=show_open_button,
    )


class _Cells(QWidget):
    """Three reassurance cells under a 2 px rule, separated by hairlines. Not focusable."""

    def __init__(self) -> None:
        super().__init__()
        cells: tuple[tuple[IconName, object, object], ...] = (
            ("ShieldCheck", s.CELL_ORIGINAL_TITLE, s.CELL_ORIGINAL_TEXT),
            ("Files", s.CELL_OVERWRITE_TITLE, s.CELL_OVERWRITE_TEXT),
            ("Eraser", s.CELL_LEFTOVERS_TITLE, s.CELL_LEFTOVERS_TEXT),
        )
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 2, 0, 0)
        grid.setHorizontalSpacing(1)
        self._cells: list[QWidget] = []
        for column, (icon, title, text) in enumerate(cells):
            cell = QWidget()
            row = QHBoxLayout(cell)
            row.setContentsMargins(0 if column == 0 else 16, 14, 16, 0)
            row.setSpacing(10)
            status = StatusIcon(20)
            status.set_icon(icon)
            column_layout = QVBoxLayout()
            column_layout.setSpacing(0)
            column_layout.addWidget(label(tr(title), TextStyle.BODY_STRONG, wrap=True))
            column_layout.addWidget(label(tr(text), TextStyle.CAPTION, "secondary", wrap=True))
            row.addWidget(status, 0, Qt.AlignmentFlag.AlignTop)
            row.addLayout(column_layout, 1)
            grid.addWidget(cell, 0, column)
            grid.setColumnStretch(column, 1)
            self._cells.append(cell)
        follow_theme(self)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        p = theme.palette()
        painter.fillRect(QRectF(0, 0, self.width(), 2), p.rule)
        for cell in self._cells[1:]:
            painter.fillRect(QRectF(cell.x() - 1, 2, 1, self.height() - 2), p.border)


class StartView(QWidget):
    def __init__(self, drop_zone: DropZone, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.headline = label(tr(s.START_HEADLINE), TextStyle.DISPLAY, wrap=True)
        self.headline.setMaximumWidth(HERO_MAX_WIDTH)
        self.intro = label(tr(s.START_INTRO), tone="secondary", wrap=True)
        self.intro.setMaximumWidth(INTRO_MAX_WIDTH)
        self.drop_zone = drop_zone
        self.cells = _Cells()

        heading = QVBoxLayout()
        heading.setSpacing(8)
        heading.addWidget(self.headline)
        heading.addWidget(self.intro)

        self._layout = QVBoxLayout(self)
        self._layout.addLayout(heading)
        self._layout.addWidget(self.drop_zone, 1)
        self._layout.addWidget(self.cells)
        self.set_compact(False)

    def set_compact(self, compact: bool) -> None:
        """At 960 px the hero shrinks to the large title size and padding tightens."""
        if compact:
            self._layout.setContentsMargins(24, 24, 24, 24)
            self._layout.setSpacing(20)
            fonts.apply(self.headline, TextStyle.TITLE_LARGE)
            fonts.apply(self.intro, TextStyle.BODY)
        else:
            self._layout.setContentsMargins(40, 32, 40, 32)
            self._layout.setSpacing(24)
            fonts.apply(self.headline, TextStyle.DISPLAY)
            self.intro.setFont(fonts.make_font(16))
