"""History tab: past conversions with the settings used, stored only on this computer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from PySide6.QtCore import Qt, Signal, SignalInstance
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from radio_video.models.presets import Quality, format_by_key
from radio_video.services.history import HistoryRecord, HistoryResult, output_missing
from radio_video.ui import strings as s
from radio_video.ui import viewmodel as vm
from radio_video.ui.icons import IconName
from radio_video.ui.pages.page_parts import Page, PageHeader, elided, page_scroll, status_badge
from radio_video.ui.strings import tr
from radio_video.ui.theme.fonts import TextStyle
from radio_video.ui.widgets.badge import Badge, BadgeTone
from radio_video.ui.widgets.button import Button, ButtonKind, ButtonSize
from radio_video.ui.widgets.grid_table import Column, GridTable
from radio_video.ui.widgets.labels import label
from radio_video.ui.widgets.progress import StatusIcon
from radio_video.utils.formatting import format_duration, format_size

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def when_text(when: datetime, today: date | None = None) -> str:
    """ "Today, 14:32", "Yesterday, 09:47" or "3 Oct 2026, 16:10"."""
    today = today or date.today()
    time = f"{when:%H:%M}"
    if when.date() == today:
        return tr(s.HISTORY_TODAY).format(time=time)
    if when.date() == today - timedelta(days=1):
        return tr(s.HISTORY_YESTERDAY).format(time=time)
    day = f"{when.day} {MONTHS[when.month - 1]} {when.year}"
    return tr(s.HISTORY_DATE).format(date=day, time=time)


def target_text(record: HistoryRecord) -> str:
    try:
        fmt = format_by_key(record.format_key)
    except KeyError:
        return record.format_key
    if record.quality is None or fmt.lossless:
        what = fmt.label
    else:
        try:
            what = vm.format_and_quality(fmt, Quality(record.quality))
        except ValueError:
            what = fmt.label
    return tr(s.QUEUE_CUSTOM).format(what=what) if record.custom else what


@dataclass(frozen=True)
class HistoryRowView:
    index: int
    when: str
    source: str
    output: str
    target: str
    result: HistoryResult
    moved: bool
    size: str
    took: str


def row_view(index: int, record: HistoryRecord, today: date | None = None) -> HistoryRowView:
    moved = output_missing(record)
    if record.result is HistoryResult.SAVED and record.output is not None:
        output = f"→ {record.output.name}"
    elif record.result is HistoryResult.CANCELED:
        output = tr(s.HISTORY_CANCELED_AT).format(percent=vm.percent(record.fraction))
    else:
        output = tr(s.HISTORY_NO_FILE)
    return HistoryRowView(
        index=index,
        when=when_text(record.when, today),
        source=record.source.name,
        output=output,
        target=target_text(record),
        result=record.result,
        moved=moved,
        size=format_size(record.size) if record.result is HistoryResult.SAVED else vm.NO_VALUE,
        took=format_duration(record.took),
    )


class HistoryPage(Page):
    # Indices into the rows last shown, newest first.
    open_requested = Signal(int)
    show_requested = Signal(int)
    details_requested = Signal(int)
    clear_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.rows: tuple[HistoryRowView, ...] = ()
        self._compact = False
        self.clear_button = Button(tr(s.HISTORY_CLEAR), ButtonKind.SUBTLE, icon="Trash2")
        self.clear_button.clicked.connect(self.clear_requested)
        self.table_box = QVBoxLayout()
        self.table_box.setContentsMargins(24, 4, 24, 16)
        self.table: GridTable | None = None
        self.empty = self._make_empty()
        self.table_box.addWidget(self.empty)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addLayout(self.table_box)
        content_layout.addStretch()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(PageHeader(tr(s.HISTORY_TITLE), tr(s.HISTORY_TEXT), [self.clear_button]))
        layout.addWidget(page_scroll(content), 1)
        self._rebuild()

    def _make_empty(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 40, 0, 40)
        layout.setSpacing(8)
        icon = StatusIcon(40)
        icon.set_icon("History")
        layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignHCenter)
        text = label(tr(s.HISTORY_EMPTY), tone="secondary", wrap=True)
        text.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(text)
        return box

    def show_rows(self, rows: tuple[HistoryRowView, ...]) -> None:
        if rows == self.rows and (self.table is not None or not rows):
            return
        self.rows = rows
        self._rebuild()

    def set_compact(self, compact: bool) -> None:
        if compact != self._compact:
            self._compact = compact
            self._rebuild()

    def _rebuild(self) -> None:
        if self.table is not None:
            # Hidden at once: deleteLater only runs when control returns to the event loop.
            self.table.hide()
            self.table_box.removeWidget(self.table)
            self.table.deleteLater()
            self.table = None
        rows = self.rows
        self.empty.setVisible(not rows)
        self.clear_button.setEnabled(bool(rows))
        if not rows:
            return
        compact = self._compact
        titles = [tr(t) for t in s.HISTORY_COLUMNS]
        columns = [Column(titles[0], 128 if compact else 140), Column(titles[1])]
        if not compact:
            columns.append(Column(titles[2], 230))
        columns += [Column(titles[3], 124), Column(titles[4], 84)]
        if not compact:
            columns.append(Column(titles[5], 72))
        columns.append(Column(titles[6], 224 if compact else 240))
        table = GridTable(columns)
        for row in rows:
            file_cell = QWidget()
            file_layout = QVBoxLayout(file_cell)
            file_layout.setContentsMargins(0, 0, 0, 0)
            file_layout.setSpacing(0)
            file_layout.addWidget(elided(row.source, TextStyle.BODY_STRONG))
            second = row.output if not compact else f"{row.output} · {row.target}"
            file_layout.addWidget(elided(second, TextStyle.CAPTION, "secondary"))
            cells: list[QWidget] = [label(row.when, tone="secondary"), file_cell]
            if not compact:
                cells.append(elided(row.target))
            cells += [self._result(row), label(row.size)]
            if not compact:
                cells.append(label(row.took))
            cells.append(self._actions(row))
            table.add_row(cells)
        self.table = table
        self.table_box.addWidget(table)

    def _result(self, row: HistoryRowView) -> Badge:
        if row.moved:
            return Badge(tr(s.HISTORY_MOVED), BadgeTone.WARNING, "TriangleAlert")
        if row.result is HistoryResult.SAVED:
            return status_badge("done", s.HISTORY_SAVED)
        return status_badge(row.result.value)

    def _actions(self, row: HistoryRowView) -> QWidget:
        if row.moved:
            return label(tr(s.HISTORY_GONE), TextStyle.CAPTION, "secondary", wrap=True)
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        def small(text: object, icon: IconName, signal: SignalInstance) -> None:
            button = Button(tr(text), ButtonKind.SUBTLE, icon=icon, size=ButtonSize.SMALL)
            button.clicked.connect(lambda: signal.emit(row.index))
            layout.addWidget(button)

        if row.result is HistoryResult.SAVED:
            small(s.HISTORY_OPEN, "Play", self.open_requested)
            small(s.SHOW_IN_FOLDER, "FolderOpen", self.show_requested)
        elif row.result is HistoryResult.FAILED:
            small(s.HISTORY_DETAILS, "FileText", self.details_requested)
        layout.addStretch()
        return box
