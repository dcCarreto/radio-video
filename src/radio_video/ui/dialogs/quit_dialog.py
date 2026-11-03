"""Quit confirmations. The safe choice (keep going) is the default and what Esc does."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from radio_video.ui import strings as s
from radio_video.ui.dialogs.base import Dialog
from radio_video.ui.strings import tr
from radio_video.ui.widgets.button import Button, ButtonKind
from radio_video.ui.widgets.labels import label


class QuitDialog(Dialog):
    """``accept()`` stops and quits; ``reject()`` keeps working."""

    def __init__(
        self,
        title: str,
        text: str,
        keep_text: str,
        quit_text: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, icon="TriangleAlert", tone="warning", parent=parent)
        self.text = label(text, tone="secondary", wrap=True)
        self.body.addWidget(self.text)
        self.keep_button = self.add_button(Button(keep_text, ButtonKind.PRIMARY))
        self.keep_button.clicked.connect(self.reject)
        self.quit_button = self.add_button(Button(quit_text, ButtonKind.DANGER))
        self.quit_button.clicked.connect(self.accept)
        self.keep_button.setFocus(Qt.FocusReason.OtherFocusReason)

    @classmethod
    def for_conversion(cls, name: str, percent: int, parent: QWidget | None = None) -> QuitDialog:
        return cls(
            tr(s.QUIT_TITLE),
            tr(s.QUIT_TEXT).format(name=name, percent=percent),
            tr(s.KEEP_CONVERTING),
            tr(s.STOP_AND_QUIT),
            parent,
        )

    @classmethod
    def for_preview(cls, parent: QWidget | None = None) -> QuitDialog:
        return cls(
            tr(s.QUIT_PREVIEW_TITLE),
            tr(s.QUIT_PREVIEW_TEXT),
            tr(s.KEEP_WORKING),
            tr(s.QUIT),
            parent,
        )
