"""Drop zone: idle, drag-over and unavailable states, with drag-and-drop rules.

Accepts exactly one local file. Several files, folders, or a drop while opening files is not
allowed show the unavailable state with the reason; a drop is never silently ignored.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from pathlib import Path

from PySide6.QtCore import QRectF, Signal
from PySide6.QtGui import (
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QPaintEvent,
    QResizeEvent,
)
from PySide6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget

from radio_video.ui import icons, theme
from radio_video.ui.icons import IconName
from radio_video.ui.theme.fonts import TextStyle
from radio_video.ui.widgets.button import Button, ButtonKind, ButtonSize
from radio_video.ui.widgets.labels import label
from radio_video.ui.widgets.painting import antialiased, fill_rounded, follow_theme
from radio_video.ui.widgets.progress import ProgressBar
from radio_video.ui.widgets.stack import fit_stack_height


class DropState(Enum):
    IDLE = "idle"
    OVER = "over"
    BLOCKED = "blocked"
    READING = "reading"


ICONS: dict[DropState, IconName] = {
    DropState.IDLE: "Upload",
    DropState.OVER: "ArrowDownToLine",
    DropState.BLOCKED: "Ban",
    DropState.READING: "Upload",
}


def dropped_paths(event: QDragEnterEvent | QDragMoveEvent | QDropEvent) -> list[Path]:
    mime = event.mimeData()
    if not mime.hasUrls():
        return []
    return [Path(url.toLocalFile()) for url in mime.urls() if url.isLocalFile()]


class DropRefusal(Enum):
    SEVERAL_FILES = "several"
    FOLDER = "folder"
    BUSY = "busy"


def check_drop(paths: list[Path], busy: bool) -> DropRefusal | None:
    """Why a drop is refused, or None. One file opens; several files go to the queue,
    which also works while a conversion runs. Folders are never accepted."""
    if not paths:
        return DropRefusal.SEVERAL_FILES
    if any(path.is_dir() for path in paths):
        return DropRefusal.FOLDER
    if len(paths) == 1 and busy:
        return DropRefusal.BUSY
    return None


class _IconTile(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state = DropState.IDLE
        self.setFixedSize(56, 56)
        follow_theme(self)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        p = theme.palette()
        fill, color = {
            DropState.IDLE: (p.sunken, p.text),
            DropState.OVER: (p.accent, p.on_accent),
            DropState.BLOCKED: (p.raised, p.danger),
            DropState.READING: (p.sunken, p.text),
        }[self.state]
        fill_rounded(painter, QRectF(self.rect()), 6, fill)
        icons.paint_icon(painter, QRectF(14, 14, 28, 28), ICONS[self.state], color)


class DropZone(QFrame):
    """``refusal_text`` maps refusals to the reason shown; ``is_busy`` reports a conversion."""

    file_dropped = Signal(Path)
    # Several files, for the queue.
    files_dropped = Signal(list)
    open_requested = Signal()
    state_changed = Signal(DropState)

    def __init__(
        self,
        *,
        titles: dict[DropState, str],
        idle_hint: str,
        idle_help: str,
        over_text: str,
        reading_text: str,
        open_text: str,
        open_shortcut: str,
        refusal_text: Callable[[DropRefusal], str],
        is_busy: Callable[[], bool] = lambda: False,
        show_open_button: bool = True,
        queue_title: Callable[[int], str] | None = None,
        queue_text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._titles = titles
        self._over_text = over_text
        self._queue_title = queue_title
        self._queue_text = queue_text
        self._refusal_text = refusal_text
        self._is_busy = is_busy
        self._state = DropState.IDLE
        self.setAcceptDrops(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.tile = _IconTile()
        self.title = label(titles[DropState.IDLE], TextStyle.TITLE, wrap=True)

        idle = QWidget()
        idle_layout = QVBoxLayout(idle)
        idle_layout.setContentsMargins(0, 0, 0, 0)
        idle_layout.setSpacing(12)
        row = QHBoxLayout()
        row.setSpacing(12)
        self.open_button = Button(
            open_text,
            ButtonKind.PRIMARY,
            icon="FolderOpen",
            shortcut_hint=open_shortcut,
            size=ButtonSize.LARGE,
        )
        self.open_button.clicked.connect(self.open_requested)
        self.open_button.setVisible(show_open_button)
        row.addWidget(self.open_button)
        row.addWidget(label(idle_hint, tone="secondary", wrap=True), 1)
        idle_layout.addLayout(row)
        idle_layout.addWidget(label(idle_help, TextStyle.CAPTION, "secondary", wrap=True))

        self.over_text = label(over_text, tone="secondary", wrap=True)
        self.blocked_text = label("", tone="secondary", wrap=True)
        reading = QWidget()
        reading_layout = QVBoxLayout(reading)
        reading_layout.setContentsMargins(0, 0, 0, 0)
        reading_layout.setSpacing(12)
        reading_layout.addWidget(label(reading_text, tone="secondary", wrap=True))
        self.reading_bar = ProgressBar()
        self.reading_bar.set_indeterminate(True)
        reading_layout.addWidget(self.reading_bar)
        self.details = QStackedWidget()
        for page in (idle, self.over_text, self.blocked_text, reading):
            self.details.addWidget(page)
        self.details.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(12)
        layout.addStretch(1)
        layout.addWidget(self.tile)
        layout.addSpacing(4)
        layout.addWidget(self.title)
        layout.addWidget(self.details)
        follow_theme(self)
        self.set_state(DropState.IDLE)

    @property
    def state(self) -> DropState:
        return self._state

    def set_state(self, state: DropState, reason: str = "", count: int = 1) -> None:
        """``count`` above one means several files dragged over, which go to the queue."""
        self._state = state
        self.tile.state = state
        title = self._titles[state]
        several = state is DropState.OVER and count > 1 and self._queue_title is not None
        if several and self._queue_title is not None:
            title = self._queue_title(count)
        self.title.setText(title)
        self.over_text.setText(self._queue_text if several else self._over_text)
        if state is DropState.BLOCKED:
            self.blocked_text.setText(reason)
        self.details.setCurrentIndex(list(DropState).index(state))
        fit_stack_height(self.details)
        self.setAccessibleDescription(f"{title}. {reason}" if reason else title)
        self.tile.update()
        self.update()
        self.state_changed.emit(state)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        fit_stack_height(self.details)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if not event.mimeData().hasUrls():
            return
        # Accept the enter even when refusing, so the reason shows and dragLeave arrives.
        event.accept()
        paths = dropped_paths(event)
        refusal = check_drop(paths, self._is_busy())
        if refusal is None:
            self.set_state(DropState.OVER, count=len(paths))
        else:
            self.set_state(DropState.BLOCKED, self._refusal_text(refusal))

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802
        if self._state is DropState.OVER:
            event.acceptProposedAction()
        else:
            event.ignore()  # "not allowed" cursor

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:  # noqa: N802
        self.set_state(DropState.IDLE)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        paths = dropped_paths(event)
        refusal = check_drop(paths, self._is_busy())
        self.set_state(DropState.IDLE)
        if refusal is None:
            event.acceptProposedAction()
            if len(paths) > 1:
                self.files_dropped.emit(paths)
            else:
                self.file_dropped.emit(paths[0])
        else:
            event.ignore()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        p = theme.palette()
        fill, border, dashed = {
            DropState.IDLE: (p.surface, p.border_ctl, True),
            DropState.OVER: (p.accent_tint, p.accent, False),
            DropState.BLOCKED: (p.danger_tint, p.danger, True),
            DropState.READING: (p.surface, p.border_ctl, True),
        }[self._state]
        fill_rounded(painter, QRectF(self.rect()), 6, fill, border, 2, dashed=dashed)
