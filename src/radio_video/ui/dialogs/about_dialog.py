"""About Radio/Video: version, license, third-party notices and the source link."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from radio_video import __version__
from radio_video.ui import strings as s
from radio_video.ui.dialogs.base import Dialog
from radio_video.ui.strings import tr
from radio_video.ui.theme.fonts import TextStyle
from radio_video.ui.widgets.app_icon import AppIcon
from radio_video.ui.widgets.button import Button
from radio_video.ui.widgets.frames import Rule
from radio_video.ui.widgets.labels import label
from radio_video.ui.widgets.progress import StatusIcon

REPOSITORY_URL = "https://github.com/dcCarreto/radio-video"
LABEL_WIDTH = 110


class AboutDialog(Dialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)
        header = QHBoxLayout()
        header.setSpacing(16)
        header.addWidget(AppIcon(64))
        names = QVBoxLayout()
        names.setSpacing(0)
        names.addWidget(label(tr(s.APP_NAME), TextStyle.TITLE_LARGE))
        names.addWidget(label(tr(s.ABOUT_VERSION).format(version=__version__), tone="secondary"))
        header.addLayout(names, 1)
        self.body.setContentsMargins(24, 28, 24, 24)
        self.body.addLayout(header)
        self.body.addWidget(label(tr(s.ABOUT_TAGLINE), wrap=True))
        self.body.addWidget(Rule())

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        grid.setColumnMinimumWidth(0, LABEL_WIDTH)
        rows = (
            (s.ABOUT_LICENSE_LABEL, label(tr(s.ABOUT_LICENSE), wrap=True)),
            (s.ABOUT_THIRD_PARTY_LABEL, label(tr(s.ABOUT_THIRD_PARTY), wrap=True)),
        )
        for row, (title, value) in enumerate(rows):
            grid.addWidget(label(tr(title), tone="secondary"), row, 0, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(value, row, 1)
        self.source_link = label(f'<a href="{REPOSITORY_URL}">{tr(s.ABOUT_SOURCE)}</a>')
        self.source_link.setTextFormat(Qt.TextFormat.RichText)
        self.source_link.setOpenExternalLinks(True)
        self.source_link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.source_link.setToolTip(REPOSITORY_URL)
        link_icon = StatusIcon(14)
        link_icon.set_icon("ExternalLink", "accent_text")
        link_row = QHBoxLayout()
        link_row.setSpacing(4)
        link_row.addWidget(self.source_link)
        link_row.addWidget(link_icon)
        link_row.addStretch()
        grid.addWidget(label(tr(s.ABOUT_SOURCE_LABEL), tone="secondary"), len(rows), 0)
        grid.addLayout(link_row, len(rows), 1)
        grid.setColumnStretch(1, 1)
        self.body.addLayout(grid)

        self.close_button = self.add_button(Button(tr(s.CLOSE)))
        self.close_button.clicked.connect(self.accept)
        self.close_button.setDefault(True)
        self.close_button.setFocus(Qt.FocusReason.OtherFocusReason)
