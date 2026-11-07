"""Offered once an update has downloaded: restart now, or install it on the way out."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from radio_video.ui import strings as s
from radio_video.ui.dialogs.base import Dialog
from radio_video.ui.strings import tr
from radio_video.ui.widgets.button import Button, ButtonKind
from radio_video.ui.widgets.labels import label


class UpdateDialog(Dialog):
    """``accept()`` restarts and installs; ``reject()`` keeps working."""

    def __init__(self, version: str, parent: QWidget | None = None) -> None:
        super().__init__(
            tr(s.UPDATES_READY_TITLE).format(version=version), icon="ArrowDownToLine", parent=parent
        )
        self.text = label(tr(s.UPDATES_READY_TEXT), tone="secondary", wrap=True)
        self.body.addWidget(self.text)
        self.later_button = self.add_button(Button(tr(s.UPDATES_LATER)))
        self.later_button.clicked.connect(self.reject)
        self.restart_button = self.add_button(Button(tr(s.UPDATES_RESTART), ButtonKind.PRIMARY))
        self.restart_button.clicked.connect(self.accept)
        self.restart_button.setFocus(Qt.FocusReason.OtherFocusReason)
