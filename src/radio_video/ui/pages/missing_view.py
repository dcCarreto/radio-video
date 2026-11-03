"""One-time setup page shown instead of the start screen when FFmpeg is missing."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from radio_video.ffmpeg.locator import FFMPEG_ENV, FFPROBE_ENV
from radio_video.ui import strings as s
from radio_video.ui.dialogs.base import IconTile
from radio_video.ui.strings import tr
from radio_video.ui.theme import fonts
from radio_video.ui.theme.fonts import TextStyle
from radio_video.ui.widgets.badge import Badge, BadgeTone
from radio_video.ui.widgets.button import Button, ButtonKind, ButtonSize
from radio_video.ui.widgets.frames import Card, CodeBlock, Note, NumberBox
from radio_video.ui.widgets.labels import kicker, label

MAX_WIDTH = 820
BODY_MAX_WIDTH = 640
COPIED_MS = 2000
EXAMPLE_FOLDER = "C:\\Tools\\ffmpeg\\bin"


def _option_header(number: int, title: str, badge: Badge | None = None) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(8)
    row.addWidget(NumberBox(number))
    row.addWidget(label(title, TextStyle.SUBTITLE))
    if badge is not None:
        row.addWidget(badge)
    row.addStretch()
    return row


class EngineMissingView(QScrollArea):
    check_again = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        content.setProperty("transparent", True)
        self.setWidget(content)

        self.title = label(tr(s.MISSING_TITLE), TextStyle.TITLE_LARGE, wrap=True)
        heading = QVBoxLayout()
        heading.setSpacing(8)
        heading.addWidget(kicker(tr(s.MISSING_KICKER)))
        heading.addWidget(self.title)
        body = label(tr(s.MISSING_BODY), tone="secondary", wrap=True)
        body.setMaximumWidth(BODY_MAX_WIDTH)
        heading.addWidget(body)

        winget = Card()
        winget_layout = QVBoxLayout(winget)
        winget_layout.setContentsMargins(20, 16, 20, 16)
        winget_layout.setSpacing(10)
        winget_layout.addLayout(
            _option_header(
                1, tr(s.MISSING_OPTION1_TITLE), Badge(tr(s.BADGE_RECOMMENDED), BadgeTone.ACCENT)
            )
        )
        winget_layout.addWidget(label(tr(s.MISSING_OPTION1_TEXT), tone="secondary", wrap=True))
        self.command = CodeBlock(s.MISSING_COMMAND)
        self.copy_button = self.command.add_copy_button(tr(s.COPY), tr(s.COPY_COMMAND_TOOLTIP))
        self.copy_button.clicked.connect(self.copy_command)
        winget_layout.addWidget(self.command)
        winget_layout.addWidget(
            label(tr(s.MISSING_OPTION1_HELP), TextStyle.CAPTION, "secondary", wrap=True)
        )

        variables = Card()
        variables_layout = QVBoxLayout(variables)
        variables_layout.setContentsMargins(20, 16, 20, 16)
        variables_layout.setSpacing(10)
        variables_layout.addLayout(_option_header(2, tr(s.MISSING_OPTION2_TITLE)))
        variables_layout.addWidget(label(tr(s.MISSING_OPTION2_TEXT), tone="secondary", wrap=True))
        for name, exe in ((FFMPEG_ENV, "ffmpeg.exe"), (FFPROBE_ENV, "ffprobe.exe")):
            variables_layout.addWidget(CodeBlock(f"{name} = {EXAMPLE_FOLDER}\\{exe}"))

        self.check_button = Button(
            tr(s.CHECK_AGAIN), ButtonKind.PRIMARY, icon="RefreshCw", size=ButtonSize.LARGE
        )
        self.check_button.clicked.connect(self.check_again)
        check_row = QHBoxLayout()
        check_row.setSpacing(12)
        check_row.addWidget(self.check_button)
        check_row.addWidget(
            label(tr(s.CHECK_AGAIN_HELP), TextStyle.CAPTION, "secondary", wrap=True), 1
        )
        self.still_missing = Note(tr(s.STILL_NOT_FOUND), "TriangleAlert", "warning")
        self.still_missing.hide()

        self._layout = QVBoxLayout(content)
        self._layout.addWidget(IconTile("TriangleAlert", "warning", size=48, icon_size=24))
        self._layout.addLayout(heading)
        self._layout.addWidget(winget)
        self._layout.addWidget(variables)
        self._layout.addLayout(check_row)
        self._layout.addWidget(self.still_missing)
        self._layout.addStretch(1)
        self.copied = False
        self.set_compact(False)

    def set_compact(self, compact: bool) -> None:
        self._layout.setContentsMargins(*(32, 28, 32, 28) if compact else (48, 40, 48, 40))
        self._layout.setSpacing(16 if compact else 20)
        if compact:
            fonts.apply(self.title, TextStyle.TITLE_LARGE)
        else:
            self.title.setFont(fonts.make_font(32, fonts.TextStyle.DISPLAY.value.weight))
        content = self.widget()
        if content is not None:
            content.setMaximumWidth(MAX_WIDTH)

    def show_still_missing(self) -> None:
        self.still_missing.show()

    def copy_command(self) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(s.MISSING_COMMAND)
        self.copy_button.setText(tr(s.COPIED))
        self.copy_button.updateGeometry()
        self.copied = True
        QTimer.singleShot(COPIED_MS, self._restore_copy)

    def _restore_copy(self) -> None:
        self.copy_button.setText(tr(s.COPY))
        self.copy_button.updateGeometry()
        self.copied = False
