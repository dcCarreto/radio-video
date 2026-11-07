"""Settings, planned: they show how the features will work, with example
rows, under a banner that says they aren't built yet. Nothing on them acts."""

from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QPaintEvent
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from radio_video.ffmpeg.locator import FFmpegTools
from radio_video.ui import strings as s
from radio_video.ui import theme
from radio_video.ui import viewmodel as vm
from radio_video.ui.icons import IconName
from radio_video.ui.pages.page_parts import (
    Page,
    elided,
    page_scroll,
)
from radio_video.ui.strings import tr
from radio_video.ui.theme.fonts import TextStyle
from radio_video.ui.widgets.badge import Badge, BadgeTone
from radio_video.ui.widgets.button import Button
from radio_video.ui.widgets.checks import RadioButton, Switch
from radio_video.ui.widgets.frames import ComboFace, FieldBox, PlannedBanner
from radio_video.ui.widgets.labels import label
from radio_video.ui.widgets.painting import antialiased, follow_theme
from radio_video.ui.widgets.segmented import SegmentedControl, SegmentOption

SETTINGS_MAX_WIDTH = 1000
SECTION_LABEL_WIDTH = 240
ROWS_MAX_WIDTH = 620


# Queue

# Settings


class _Section(QWidget):
    def __init__(self, title: str, text: str, rows: list[QWidget]) -> None:
        super().__init__()
        self.title = QWidget()
        title_layout = QVBoxLayout(self.title)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(4)
        title_layout.addWidget(label(title, TextStyle.SUBTITLE))
        title_layout.addWidget(label(text, TextStyle.CAPTION, "secondary", wrap=True))
        title_layout.addStretch()
        self.rows = QWidget()
        self.rows.setMaximumWidth(ROWS_MAX_WIDTH)
        rows_layout = QVBoxLayout(self.rows)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(16)
        for row in rows:
            rows_layout.addWidget(row)
        # Keep the rows flush left at their maximum width without losing height-for-width.
        self.holder = QWidget()
        holder_layout = QHBoxLayout(self.holder)
        holder_layout.setContentsMargins(0, 0, 0, 0)
        holder_layout.addWidget(self.rows, 1)
        holder_layout.addStretch()
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 22, 0, 20)
        self.set_compact(False)
        follow_theme(self)

    def set_compact(self, compact: bool) -> None:
        self._grid.removeWidget(self.title)
        self._grid.removeWidget(self.holder)
        left = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        if compact:
            self._grid.setHorizontalSpacing(0)
            self._grid.setVerticalSpacing(12)
            self._grid.addWidget(self.title, 0, 0, left)
            self._grid.addWidget(self.holder, 1, 0)
            self._grid.setColumnMinimumWidth(0, 0)
            self._grid.setColumnStretch(0, 1)
            self._grid.setColumnStretch(1, 0)
        else:
            self._grid.setHorizontalSpacing(24)
            self._grid.addWidget(self.title, 0, 0, left)
            self._grid.addWidget(self.holder, 0, 1)
            self._grid.setColumnStretch(0, 0)
            self._grid.setColumnStretch(1, 1)
            self._grid.setColumnMinimumWidth(0, SECTION_LABEL_WIDTH)
            self.title.setFixedWidth(SECTION_LABEL_WIDTH)
        if compact:
            self.title.setMinimumWidth(0)
            self.title.setMaximumWidth(16777215)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        painter.fillRect(QRectF(0, 0, self.width(), 2), theme.palette().rule)


def _setting(title: str, control: QWidget, help_text: str = "") -> QWidget:
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    layout.addWidget(label(title, TextStyle.BODY_STRONG))
    layout.addWidget(control)
    if help_text:
        layout.addWidget(label(help_text, TextStyle.CAPTION, "secondary", wrap=True))
    return box


def _path_row(path: str, icon: IconName | None = None) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    layout.addWidget(FieldBox(path, icon), 1)
    layout.addWidget(Button(tr(s.BROWSE)))
    return row


class SettingsPage(Page):
    """Settings; only the Performance switch acts so far."""

    hardware_changed = Signal(bool)

    def __init__(
        self,
        tools: FFmpegTools | None = None,
        version: str | None = None,
        save_folder: Path | None = None,
        hardware_enabled: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        engine_rows: list[QWidget] = []
        if tools is not None:
            status = QWidget()
            status_layout = QHBoxLayout(status)
            status_layout.setContentsMargins(0, 0, 0, 0)
            status_layout.setSpacing(8)
            status_layout.addWidget(Badge(tr(s.SETTINGS_WORKING), BadgeTone.SUCCESS, "CircleCheck"))
            status_layout.addWidget(
                elided(
                    tr(s.SETTINGS_FOUND).format(
                        version=version or "", folder=str(tools.ffmpeg.parent)
                    )
                ),
                1,
            )
            engine_rows.append(status)
            engine_rows.append(_setting("ffmpeg.exe", _path_row(str(tools.ffmpeg))))
            engine_rows.append(_setting("ffprobe.exe", _path_row(str(tools.ffprobe))))
        engine_rows.append(_left(Button(tr(s.CHECK_AGAIN), icon="RefreshCw")))

        folder_choice = QWidget()
        folder_layout = QVBoxLayout(folder_choice)
        folder_layout.setContentsMargins(0, 0, 0, 0)
        folder_layout.setSpacing(8)
        same = RadioButton(tr(s.SETTINGS_SAME_FOLDER))
        this = RadioButton(tr(s.SETTINGS_THIS_FOLDER))
        this.setChecked(True)
        folder_layout.addWidget(same)
        folder_layout.addWidget(this)
        folder_row = _path_row(str(save_folder or Path.home() / "Videos"), "Folder")
        folder_row.setContentsMargins(28, 0, 0, 0)
        folder_layout.addWidget(folder_row)
        quality = SegmentedControl(vm.quality_options(), accessible_name=tr(s.FIELD_QUALITY))
        quality.set_value("balanced")

        hardware = QWidget()
        hardware_layout = QHBoxLayout(hardware)
        hardware_layout.setContentsMargins(0, 0, 0, 0)
        hardware_layout.setSpacing(12)
        self.hardware_switch = Switch()
        self.hardware_switch.setChecked(hardware_enabled)
        self.hardware_switch.setAccessibleName(tr(s.SETTINGS_HARDWARE))
        self.hardware_switch.toggled.connect(self.hardware_changed)
        hardware_layout.addWidget(self.hardware_switch, 0, Qt.AlignmentFlag.AlignTop)
        hardware_text = QVBoxLayout()
        hardware_text.setSpacing(0)
        hardware_text.addWidget(label(tr(s.SETTINGS_HARDWARE), TextStyle.BODY_STRONG, wrap=True))
        self.hardware_help = label(
            tr(s.SETTINGS_HARDWARE_HELP), TextStyle.CAPTION, "secondary", wrap=True
        )
        hardware_text.addWidget(self.hardware_help)
        hardware_layout.addLayout(hardware_text, 1)

        appearance = SegmentedControl(
            [
                SegmentOption("system", tr(s.SETTINGS_THEME_SYSTEM)),
                SegmentOption("light", tr(s.SETTINGS_THEME_LIGHT)),
                SegmentOption("dark", tr(s.SETTINGS_THEME_DARK)),
            ],
            accessible_name=tr(s.SETTINGS_THEME),
        )
        appearance.set_value("system")

        self.sections = [
            _Section(tr(s.SETTINGS_ENGINE), tr(s.SETTINGS_ENGINE_TEXT), engine_rows),
            _Section(
                tr(s.SETTINGS_DEFAULTS),
                tr(s.SETTINGS_DEFAULTS_TEXT),
                [
                    _setting(tr(s.SETTINGS_SAVE_TO), folder_choice),
                    _setting(tr(s.SETTINGS_VIDEO_FORMAT), ComboFace("MP4 (H.264 + AAC)")),
                    _setting(tr(s.SETTINGS_AUDIO_FORMAT), ComboFace("MP3")),
                    _setting(tr(s.FIELD_QUALITY), quality),
                ],
            ),
            _Section(tr(s.SETTINGS_PERFORMANCE), tr(s.SETTINGS_PERFORMANCE_TEXT), [hardware]),
            _Section(
                tr(s.SETTINGS_TEMP),
                tr(s.SETTINGS_TEMP_TEXT),
                [
                    _setting(
                        tr(s.SETTINGS_LOCATION),
                        _path_row(str(Path(tempfile.gettempdir()) / "RadioVideo")),
                        tr(s.SETTINGS_LOCATION_HELP),
                    )
                ],
            ),
            _Section(
                tr(s.SETTINGS_APPEARANCE),
                tr(s.SETTINGS_APPEARANCE_TEXT),
                [_setting(tr(s.SETTINGS_THEME), appearance)],
            ),
        ]

        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(24, 20, 24, 32)
        body.setSpacing(0)
        body.addWidget(label(tr(s.SETTINGS_TITLE), TextStyle.TITLE_LARGE))
        body.addSpacing(4)
        body.addWidget(label(tr(s.SETTINGS_TEXT), tone="secondary"))
        body.addSpacing(20)
        for section in self.sections:
            body.addWidget(section)
        body.addStretch()
        content.setMaximumWidth(SETTINGS_MAX_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(PlannedBanner(tr(s.PLANNED_SETTINGS), tr(s.BADGE_PLANNED)))
        layout.addWidget(page_scroll(content), 1)

    def set_hardware_text(self, text: str) -> None:
        self.hardware_help.setText(text)
        self.hardware_switch.setAccessibleDescription(text)

    def set_compact(self, compact: bool) -> None:
        for section in self.sections:
            section.set_compact(compact)


def _left(widget: QWidget) -> QWidget:
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(widget)
    layout.addStretch()
    return box
