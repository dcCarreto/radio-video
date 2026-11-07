"""Queue tab: files converted one after another, each with its own format and quality.

The table keeps one set of widgets per entry and updates them in place, so progress ticks
never rebuild it; it is rebuilt only when entries are added, removed or reordered.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

from radio_video.models.advanced import resolve
from radio_video.models.estimate import estimate_output_size
from radio_video.models.presets import format_by_key
from radio_video.services.queue import QueueCounts, QueueEntry, QueueStatus
from radio_video.ui import strings as s
from radio_video.ui import viewmodel as vm
from radio_video.ui.errors_map import Failure, describe
from radio_video.ui.icons import IconName
from radio_video.ui.pages.page_parts import (
    STATUS_BADGES,
    FooterBand,
    Page,
    PageHeader,
    elided,
    page_scroll,
)
from radio_video.ui.state import Progress
from radio_video.ui.strings import tr
from radio_video.ui.theme.fonts import TextStyle
from radio_video.ui.widgets.badge import Badge
from radio_video.ui.widgets.button import Button, ButtonKind, ButtonSize
from radio_video.ui.widgets.checks import CheckBox
from radio_video.ui.widgets.frames import Rule
from radio_video.ui.widgets.grid_table import Column, GridTable
from radio_video.ui.widgets.labels import ElidedLabel, label
from radio_video.ui.widgets.progress import ProgressBar, StatusIcon
from radio_video.utils.formatting import format_duration, format_size

FOOTER_BAR_WIDTH = 240


@dataclass(frozen=True)
class QueueRowView:
    entry_id: int
    file: str
    target: str
    status: QueueStatus
    progress_text: str
    fraction: float
    size: str
    error: str = ""
    can_retry: bool = False


def row_view(entry: QueueEntry) -> QueueRowView:
    """How an entry reads in the table."""
    fmt = format_by_key(entry.format_key)
    what = vm.format_and_quality(fmt, entry.quality)
    target = what if entry.choices.is_default else tr(s.QUEUE_CUSTOM).format(what=what)
    status = entry.status
    size = vm.NO_VALUE
    error = ""
    if status is QueueStatus.WAITING:
        text = tr(s.STATUS_WAITING)
        if entry.media is not None:
            recipe = resolve(fmt, entry.quality, entry.media, entry.choices)
            calculated = estimate_output_size(recipe.settings, entry.media, recipe.streams)
            if calculated is not None:
                size = tr(s.ESTIMATE_VALUE).format(size=vm.format_estimate_size(calculated))
    elif status is QueueStatus.CONVERTING:
        text = vm.progress_detail(Progress(entry.fraction, entry.speed, entry.remaining))
    elif status is QueueStatus.DONE:
        text = tr(s.QUEUE_SAVED).format(time=format_duration(entry.took))
        size = format_size(entry.size)
    elif status is QueueStatus.CANCELED:
        text = tr(s.QUEUE_CANCELED_AT).format(percent=vm.percent(entry.fraction))
    elif entry.media is None:
        text = tr(s.QUEUE_CANT_READ)
        error = entry.error
    else:
        report = describe(Failure(details=entry.error, source=entry.path))
        text = report.what_happened
        error = entry.error
    return QueueRowView(
        entry_id=entry.id,
        file=entry.path.name,
        target=target,
        status=status,
        progress_text=text,
        fraction=entry.fraction,
        size=size,
        error=error,
        can_retry=entry.readable and status in (QueueStatus.FAILED, QueueStatus.CANCELED),
    )


def counts_text(counts: QueueCounts) -> str:
    parts = [
        (counts.done, s.QUEUE_DONE_PART),
        (counts.converting, s.QUEUE_CONVERTING_PART),
        (counts.waiting, s.QUEUE_WAITING_PART),
        (counts.failed, s.QUEUE_FAILED_PART),
        (counts.canceled, s.QUEUE_CANCELED_PART),
    ]
    return " · ".join(tr(text).format(count=count) for count, text in parts if count)


@dataclass(frozen=True)
class QueueView:
    rows: tuple[QueueRowView, ...]
    running: bool
    can_start: bool
    # Why Start is unavailable, for its tooltip.
    start_blocked: str
    pause_after: bool
    current: int | None
    total: int
    fraction: float
    counts: str


class _Row:
    """The widgets of one table row, updated in place."""

    def __init__(self, page: QueuePage, view: QueueRowView, number: int, compact: bool) -> None:
        self.number = label(str(number), tone="secondary")
        self.file = elided(view.file)
        self.target = elided(view.target)
        self.badge = Badge("")
        self.text = label("", TextStyle.CAPTION, "secondary")
        self.bar = ProgressBar()
        bar_box = QWidget()
        bar_layout = QVBoxLayout(bar_box)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(4)
        bar_layout.addWidget(self.bar)
        bar_layout.addWidget(self.text)
        self.plain = ElidedLabel("", tone="secondary")
        self.error = ElidedLabel("", tone="danger")
        self.retry = Button(
            tr(s.QUEUE_RETRY), ButtonKind.SUBTLE, icon="RotateCcw", size=ButtonSize.SMALL
        )
        self.retry.clicked.connect(lambda: page.retry_requested.emit(view.entry_id))
        error_box = QWidget()
        error_layout = QHBoxLayout(error_box)
        error_layout.setContentsMargins(0, 0, 0, 0)
        error_layout.addWidget(self.error, 1)
        error_layout.addWidget(self.retry)
        self.progress = QStackedWidget()
        for widget in (self.plain, bar_box, error_box):
            self.progress.addWidget(widget)
        self.size = label("")
        self.cells: list[QWidget] = [
            self.number,
            self.file,
            self.target,
            self.badge,
            self.progress,
        ]
        if not compact:
            self.cells.append(self.size)
        self.update(view)

    def update(self, view: QueueRowView) -> None:
        tone, icon, text = STATUS_BADGES[view.status.value]
        self.badge.set_badge(tr(text), tone, icon)
        self.target.setText(view.target)
        self.size.setText(view.size)
        if view.status is QueueStatus.CONVERTING:
            self.bar.set_fraction(view.fraction)
            self.text.setText(view.progress_text)
            self.progress.setCurrentIndex(1)
        elif view.status is QueueStatus.FAILED:
            self.error.setText(view.progress_text)
            self.error.setToolTip(view.error or view.progress_text)
            self.retry.setVisible(view.can_retry)
            self.progress.setCurrentIndex(2)
        else:
            self.plain.setText(view.progress_text)
            self.progress.setCurrentIndex(0)


class QueuePage(Page):
    add_requested = Signal()
    start_requested = Signal()
    stop_requested = Signal()
    pause_toggled = Signal(bool)
    move_requested = Signal(int, int)
    retry_requested = Signal(int)
    remove_requested = Signal(int)
    clear_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view: QueueView | None = None
        self.selected: int | None = None
        self._compact = False
        self._order: tuple[int, ...] | None = None
        self._rows: dict[int, _Row] = {}
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.pause = CheckBox(tr(s.QUEUE_PAUSE_AFTER))
        self.pause.toggled.connect(self.pause_toggled)
        self.run_button = Button(tr(s.QUEUE_START), ButtonKind.PRIMARY, icon="Play")
        self.run_button.clicked.connect(self._on_run)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(20, 8, 20, 8)
        toolbar.setSpacing(4)
        self.add_button = self._tool(toolbar, s.QUEUE_ADD, "Plus", self.add_requested.emit)
        toolbar.addWidget(Rule(hairline=True, vertical=True))
        self.up_button = self._tool(toolbar, s.QUEUE_UP, "ArrowUp", lambda: self._move(-1))
        self.down_button = self._tool(toolbar, s.QUEUE_DOWN, "ArrowDown", lambda: self._move(1))
        toolbar.addWidget(Rule(hairline=True, vertical=True))
        self.retry_button = self._tool(toolbar, s.QUEUE_RETRY, "RotateCcw", self._retry)
        self.remove_button = self._tool(toolbar, s.QUEUE_REMOVE, "Trash2", self._remove)
        self.clear_button = self._tool(toolbar, s.QUEUE_CLEAR, "Eraser", self.clear_requested.emit)
        toolbar.addStretch()
        self.shortcuts = label(tr(s.QUEUE_SHORTCUTS), TextStyle.CAPTION, "secondary")
        toolbar.addWidget(self.shortcuts)
        self.toolbar = QWidget()
        self.toolbar.setLayout(toolbar)

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

        footer = QHBoxLayout()
        footer.setContentsMargins(24, 12, 24, 12)
        footer.setSpacing(16)
        self.file_of = label("", TextStyle.BODY_STRONG)
        self.overall = ProgressBar()
        self.overall.setFixedWidth(FOOTER_BAR_WIDTH)
        self.counts = label("", TextStyle.CAPTION, "secondary")
        footer.addWidget(self.file_of)
        footer.addWidget(self.overall)
        footer.addWidget(self.counts, 1)
        self.footer = FooterBand()
        self.footer.setLayout(footer)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(
            PageHeader(tr(s.QUEUE_TITLE), tr(s.QUEUE_TEXT), [self.pause, self.run_button])
        )
        layout.addWidget(self.toolbar)
        layout.addWidget(Rule(hairline=True))
        layout.addWidget(page_scroll(content), 1)
        layout.addWidget(self.footer)
        self.show_view(
            QueueView((), False, False, tr(s.QUEUE_NOTHING_WAITING), False, None, 0, 0.0, "")
        )

    def _tool(self, layout: QHBoxLayout, text: object, icon: IconName, slot: object) -> Button:
        button = Button(tr(text), ButtonKind.SUBTLE, icon=icon)
        button.clicked.connect(slot)
        layout.addWidget(button)
        return button

    def _make_empty(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 40, 0, 40)
        layout.setSpacing(8)
        icon = StatusIcon(40)
        icon.set_icon("ListOrdered")
        layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignHCenter)
        title = label(tr(s.QUEUE_EMPTY_TITLE), TextStyle.SUBTITLE)
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title)
        text = label(tr(s.QUEUE_EMPTY_TEXT), tone="secondary", wrap=True)
        text.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        # Centred with stretches: an alignment flag would drop height-for-width and clip text.
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(text, 4)
        row.addStretch(1)
        layout.addLayout(row)
        return box

    # Showing
    def show_view(self, view: QueueView) -> None:
        self.view = view
        order = tuple(row.entry_id for row in view.rows)
        if self.selected not in order:
            self.selected = None
        if order != self._order:
            self._order = order
            self._rebuild(view)
        else:
            for row in view.rows:
                self._rows[row.entry_id].update(row)
        if view.running:
            self.run_button.setText(tr(s.QUEUE_STOP))
            self.run_button.set_kind(ButtonKind.DANGER)
            self.run_button.set_icon_name("Square")
            self.run_button.setEnabled(True)
            self.run_button.setToolTip("")
        else:
            self.run_button.setText(tr(s.QUEUE_START))
            self.run_button.set_kind(ButtonKind.PRIMARY)
            self.run_button.set_icon_name("Play")
            self.run_button.setEnabled(view.can_start)
            self.run_button.setToolTip("" if view.can_start else view.start_blocked)
        self.pause.blockSignals(True)
        self.pause.setChecked(view.pause_after)
        self.pause.blockSignals(False)
        self.pause.setEnabled(view.running)
        has_rows = bool(view.rows)
        self.footer.setVisible(has_rows)
        if view.current is not None:
            self.file_of.setText(tr(s.QUEUE_FILE_OF).format(current=view.current, total=view.total))
        else:
            self.file_of.setText(tr(s.QUEUE_TITLE))
        self.overall.set_fraction(view.fraction)
        self.counts.setText(view.counts)
        self.clear_button.setEnabled(any(r.status in _FINISHED for r in view.rows))
        self._render_selection()

    def update_row(self, row: QueueRowView, fraction: float) -> None:
        """Fast path for progress: one row and the footer bar."""
        widgets = self._rows.get(row.entry_id)
        if widgets is not None:
            widgets.update(row)
        self.overall.set_fraction(fraction)

    def _rebuild(self, view: QueueView) -> None:
        if self.table is not None:
            # Hidden at once: deleteLater only runs when control returns to the event loop.
            self.table.hide()
            self.table_box.removeWidget(self.table)
            self.table.deleteLater()
            self.table = None
        self._rows = {}
        self.empty.setVisible(not view.rows)
        if not view.rows:
            return
        titles = [tr(t) for t in s.QUEUE_COLUMNS]
        compact = self._compact
        columns = [
            Column(titles[0], 36),
            Column(titles[1]),
            Column(titles[2], 170 if compact else 240),
            Column(titles[3], 124),
            Column(titles[4], 180 if compact else 260),
        ]
        if not compact:
            columns.append(Column(titles[5], 100))
        table = GridTable(columns)
        table.row_clicked.connect(self._on_row_clicked)
        for number, row in enumerate(view.rows, start=1):
            widgets = _Row(self, row, number, compact)
            self._rows[row.entry_id] = widgets
            table.add_row(widgets.cells)
        self.table = table
        self.table_box.addWidget(table)

    def _render_selection(self) -> None:
        view = self.view
        rows = view.rows if view is not None else ()
        index = next((i for i, r in enumerate(rows) if r.entry_id == self.selected), None)
        if self.table is not None:
            self.table.set_selected(set() if index is None else {index})
        chosen = rows[index] if index is not None else None
        self.up_button.setEnabled(index is not None and index > 0)
        self.down_button.setEnabled(index is not None and index < len(rows) - 1)
        self.retry_button.setEnabled(chosen is not None and chosen.can_retry)
        self.remove_button.setEnabled(chosen is not None)

    # Actions
    def select(self, entry_id: int | None) -> None:
        self.selected = entry_id
        self._render_selection()

    def _on_row_clicked(self, index: int) -> None:
        if self.view is not None and index < len(self.view.rows):
            self.select(self.view.rows[index].entry_id)
            self.setFocus(Qt.FocusReason.MouseFocusReason)

    def _on_run(self) -> None:
        if self.view is not None and self.view.running:
            self.stop_requested.emit()
        else:
            self.start_requested.emit()

    def _move(self, delta: int) -> None:
        if self.selected is not None:
            self.move_requested.emit(self.selected, delta)

    def _retry(self) -> None:
        if self.selected is not None:
            self.retry_requested.emit(self.selected)

    def _remove(self) -> None:
        if self.selected is not None:
            self.remove_requested.emit(self.selected)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        alt = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
        if key == Qt.Key.Key_Delete and self.selected is not None:
            self._remove()
        elif alt and key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            self._move(-1 if key == Qt.Key.Key_Up else 1)
        elif key in (Qt.Key.Key_Up, Qt.Key.Key_Down) and self.view is not None and self.view.rows:
            ids = [row.entry_id for row in self.view.rows]
            if self.selected is None:
                self.select(ids[0])
            else:
                step = -1 if key == Qt.Key.Key_Up else 1
                index = min(max(ids.index(self.selected) + step, 0), len(ids) - 1)
                self.select(ids[index])
        else:
            super().keyPressEvent(event)
            return
        event.accept()

    def set_compact(self, compact: bool) -> None:
        if compact != self._compact:
            self._compact = compact
            self.shortcuts.setVisible(not compact)
            if self.view is not None:
                self._order = None
                self.show_view(self.view)


_FINISHED = (QueueStatus.DONE, QueueStatus.FAILED, QueueStatus.CANCELED)
