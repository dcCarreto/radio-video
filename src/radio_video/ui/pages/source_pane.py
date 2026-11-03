"""Left pane: the source file's name, plain summary, facts and every track."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPaintEvent
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from radio_video.models.media import MediaInfo
from radio_video.ui import strings as s
from radio_video.ui import theme
from radio_video.ui import viewmodel as vm
from radio_video.ui.strings import tr
from radio_video.ui.theme.fonts import TextStyle
from radio_video.ui.widgets.badge import Badge
from radio_video.ui.widgets.button import Button
from radio_video.ui.widgets.facts_grid import FactsGrid
from radio_video.ui.widgets.flow_layout import FlowLayout
from radio_video.ui.widgets.labels import ElidedLabel, kicker, label
from radio_video.ui.widgets.painting import antialiased, follow_theme
from radio_video.ui.widgets.streams_table import StreamsTable


class SourcePane(QWidget):
    open_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.name = ElidedLabel("", TextStyle.TITLE, mode=Qt.TextElideMode.ElideMiddle)
        self.summary = label("", tone="secondary", wrap=True)
        names = QVBoxLayout()
        names.setSpacing(4)
        names.addWidget(kicker(tr(s.SOURCE_KICKER)))
        names.addWidget(self.name)
        names.addWidget(self.summary)

        self.open_button = Button(
            tr(s.OPEN_ANOTHER), icon="FolderOpen", shortcut_hint=tr(s.SHORTCUT_OPEN)
        )
        self.open_button.setToolTip(tr(s.OPEN_ANOTHER_TOOLTIP))
        self.open_button.clicked.connect(self.open_requested)
        self.paused = label(tr(s.OPEN_PAUSED), TextStyle.CAPTION, "secondary")
        self.paused.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.paused.hide()
        actions = QVBoxLayout()
        actions.setSpacing(4)
        actions.addWidget(self.open_button, 0, Qt.AlignmentFlag.AlignRight)
        actions.addWidget(self.paused, 0, Qt.AlignmentFlag.AlignRight)
        actions.addStretch()

        header = QHBoxLayout()
        header.setContentsMargins(24, 20, 24, 16)
        header.setSpacing(16)
        header.addLayout(names, 1)
        header.addLayout(actions)

        self.facts = FactsGrid(
            [tr(s.FACT_CONTAINER), tr(s.FACT_DURATION), tr(s.FACT_SIZE), tr(s.FACT_BITRATE)],
            tr(s.FACT_TITLE),
        )

        self.inside = kicker("", tone=None)
        # The header and chips wrap like text, so narrow panes don't force a minimum width.
        self.section = FlowLayout(spacing=12, line_spacing=8)
        self.section.setContentsMargins(24, 16, 24, 8)
        self.section.addWidget(self.inside)
        self.chips: list[Badge] = []

        self.table = StreamsTable([tr(c) for c in s.STREAM_COLUMNS])
        self.table.delegate.default_text = tr(s.BADGE_DEFAULT)
        table_box = QVBoxLayout()
        table_box.setContentsMargins(24, 0, 24, 16)
        table_box.addWidget(self.table)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(header)
        layout.addWidget(self.facts)
        layout.addLayout(self.section)
        layout.addLayout(table_box, 1)
        follow_theme(self)

    def set_media(self, media: MediaInfo) -> None:
        self.name.setText(media.path.name)
        self.summary.setText(vm.source_summary(media))
        values, title = vm.facts(media)
        self.facts.set_values(values, title)
        self.inside.setText(vm.inside_header(media))
        for chip in self.chips:
            self.section.removeWidget(chip)
            chip.deleteLater()
        self.chips = [Badge(text, icon=icon) for icon, text in vm.track_chips(media)]
        for chip in self.chips:
            self.section.addWidget(chip)
        self.table.set_rows(vm.stream_rows(media))

    def set_converting(self, converting: bool) -> None:
        self.open_button.setEnabled(not converting)
        self.open_button.setToolTip(
            tr(s.OPEN_DISABLED_TOOLTIP if converting else s.OPEN_ANOTHER_TOOLTIP)
        )
        self.paused.setVisible(converting)

    def set_compact(self, compact: bool) -> None:
        self.open_button.setText(tr(s.OPEN_SHORT if compact else s.OPEN_ANOTHER))
        self.open_button.updateGeometry()
        self.table.set_compact(compact)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        painter.fillRect(self.rect(), theme.palette().bg)
