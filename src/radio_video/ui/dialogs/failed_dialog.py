"""Conversion failed: what happened, what to do, reassurance and technical details."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication, QKeyEvent
from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget

from radio_video.ui import strings as s
from radio_video.ui.dialogs.base import Dialog
from radio_video.ui.errors_map import ErrorReport
from radio_video.ui.strings import tr
from radio_video.ui.theme import fonts
from radio_video.ui.theme.fonts import TextStyle
from radio_video.ui.widgets.button import Button, ButtonKind, Expander
from radio_video.ui.widgets.frames import Note
from radio_video.ui.widgets.labels import label

LOG_MAX_HEIGHT = 180
COPIED_MS = 3000


class FailedDialog(Dialog):
    """``accept()`` means the primary next step was chosen; ``reject()`` means Close."""

    def __init__(
        self,
        report: ErrorReport,
        title: str | None = None,
        *,
        reassure: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            title or tr(s.FAILED_TITLE), icon="CircleX", tone="danger", width=540, parent=parent
        )
        self.report = report
        for heading, text in (
            (s.WHAT_HAPPENED, report.what_happened),
            (s.WHAT_TO_DO, report.what_to_do),
        ):
            block = QVBoxLayout()
            block.setSpacing(0)
            block.addWidget(label(tr(heading), TextStyle.BODY_STRONG))
            block.addWidget(label(text, tone="secondary", wrap=True, selectable=True))
            self.body.addLayout(block)
        if reassure:
            self.body.addWidget(Note(tr(s.FAILED_REASSURANCE), "ShieldCheck"))

        self.expander = Expander(tr(s.TECHNICAL_DETAILS))
        self.log = QPlainTextEdit(report.details)
        self.log.setObjectName("Log")
        self.log.setReadOnly(True)
        self.log.setFont(fonts.font(TextStyle.MONO_SMALL))
        self.log.setMaximumHeight(LOG_MAX_HEIGHT)
        self.log.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.log.setAccessibleName(tr(s.TECHNICAL_DETAILS))
        self.log.hide()
        self.expander.toggled.connect(self._toggle_log)
        self.body.addWidget(self.expander)
        self.body.addWidget(self.log)

        self.copy_button = self.add_button(
            Button(tr(s.COPY_DETAILS), ButtonKind.SUBTLE, icon="Copy"), leading=True
        )
        self.copy_button.setToolTip(tr(s.COPY_DETAILS_TOOLTIP))
        self.copy_button.clicked.connect(self.copy_details)
        self.close_button = self.add_button(Button(tr(s.CLOSE)))
        self.close_button.clicked.connect(self.reject)
        self.action_button = self.add_button(Button(report.action_text, ButtonKind.PRIMARY))
        self.action_button.clicked.connect(self.accept)
        self.copied = label(tr(s.DETAILS_COPIED), TextStyle.CAPTION, "secondary", wrap=True)
        self.copied.hide()
        self.body.addWidget(self.copied)
        # Focus starts on the most likely fix.
        self.action_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def _toggle_log(self, open_: bool) -> None:
        self.log.setVisible(open_)
        self.fit_height()

    def copy_details(self) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self.report.details)
        self.copied.show()
        self.fit_height()
        QTimer.singleShot(COPIED_MS, self._hide_copied)

    def _hide_copied(self) -> None:
        self.copied.hide()
        self.fit_height()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)
