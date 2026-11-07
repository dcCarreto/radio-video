"""Settings: the conversion engine, defaults for new files, performance, temporary files,
the theme and updates. Changes are saved as they are made."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QPaintEvent
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from radio_video.models.presets import Quality
from radio_video.ui import strings as s
from radio_video.ui import theme
from radio_video.ui import viewmodel as vm
from radio_video.ui.icons import IconName
from radio_video.ui.pages.page_parts import Page, elided, page_scroll
from radio_video.ui.strings import tr
from radio_video.ui.theme.fonts import TextStyle
from radio_video.ui.widgets.badge import Badge, BadgeTone
from radio_video.ui.widgets.button import Button, ButtonKind
from radio_video.ui.widgets.checks import RadioButton, Switch
from radio_video.ui.widgets.format_combo import Choice, ChoiceCombo
from radio_video.ui.widgets.frames import FieldBox, Note
from radio_video.ui.widgets.labels import label
from radio_video.ui.widgets.painting import antialiased, follow_theme
from radio_video.ui.widgets.segmented import SegmentedControl, SegmentOption

SETTINGS_MAX_WIDTH = 1000
SECTION_LABEL_WIDTH = 240
ROWS_MAX_WIDTH = 620
SAVE_SAME = "same"
SAVE_FOLDER = "folder"
THEMES = ("system", "light", "dark")
# What the main update button does.
UPDATE_DOWNLOAD = "download"
UPDATE_RESTART = "restart"
UPDATE_OPEN_PAGE = "open"


@dataclass(frozen=True)
class UpdateView:
    automatic: bool
    # The installed application can update itself; a copy run from source cannot.
    installable: bool
    badge: str
    tone: BadgeTone
    text: str
    checking: bool
    # UPDATE_DOWNLOAD, UPDATE_RESTART, UPDATE_OPEN_PAGE or "" for no button.
    action: str
    # A newer version is known, so its release notes can be opened.
    notes: bool


@dataclass(frozen=True)
class SettingsView:
    engine_working: bool
    engine_text: str
    ffmpeg: str
    ffprobe: str
    # The files were chosen here (not found automatically).
    engine_chosen: bool
    # Shown under the engine rows: a restart is needed, or a chosen file didn't work.
    engine_note: str
    engine_note_warning: bool
    save_mode: str
    save_folder: str
    video_formats: tuple[Choice, ...]
    video_format: str
    audio_formats: tuple[Choice, ...]
    audio_format: str
    quality: Quality
    hardware_enabled: bool
    hardware_text: str
    temp_location: str
    temp_is_default: bool
    theme: str
    update: UpdateView


UPDATE_BUTTONS: dict[str, tuple[object, IconName]] = {
    UPDATE_DOWNLOAD: (s.UPDATES_DOWNLOAD, "ArrowDownToLine"),
    UPDATE_RESTART: (s.UPDATES_RESTART, "RefreshCw"),
    UPDATE_OPEN_PAGE: (s.UPDATES_OPEN_PAGE, "ExternalLink"),
}


class _Section(QWidget):
    """A title and description on the left, the settings on the right, over a 2 px rule."""

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
            # No alignment flag here: it would drop height-for-width and clip the text.
            self._grid.addWidget(self.title, 0, 0)
            self._grid.addWidget(self.holder, 1, 0)
            self._grid.setColumnMinimumWidth(0, 0)
            self._grid.setColumnStretch(0, 1)
            self._grid.setColumnStretch(1, 0)
            self.title.setMinimumWidth(0)
            self.title.setMaximumWidth(16777215)
        else:
            self._grid.setHorizontalSpacing(24)
            self._grid.addWidget(self.title, 0, 0, left)
            self._grid.addWidget(self.holder, 0, 1)
            self._grid.setColumnStretch(0, 0)
            self._grid.setColumnStretch(1, 1)
            self._grid.setColumnMinimumWidth(0, SECTION_LABEL_WIDTH)
            self.title.setFixedWidth(SECTION_LABEL_WIDTH)

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


class _PathRow(QWidget):
    """A read-only path with Browse… and, optionally, a button to go back to the default."""

    def __init__(self, icon: IconName | None = None, reset_text: str = "") -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.field = FieldBox("", icon)
        self.browse = Button(tr(s.BROWSE))
        layout.addWidget(self.field, 1)
        layout.addWidget(self.browse)
        self.reset: Button | None = None
        if reset_text:
            self.reset = Button(reset_text, ButtonKind.SUBTLE)
            layout.addWidget(self.reset)


class SettingsPage(Page):
    hardware_changed = Signal(bool)
    check_requested = Signal()
    # "ffmpeg" or "ffprobe".
    engine_browse_requested = Signal(str)
    engine_reset_requested = Signal()
    save_mode_changed = Signal(str)
    save_folder_browse_requested = Signal()
    video_format_changed = Signal(str)
    audio_format_changed = Signal(str)
    quality_changed = Signal(Quality)
    temp_browse_requested = Signal()
    temp_reset_requested = Signal()
    theme_changed = Signal(str)
    updates_automatic_changed = Signal(bool)
    update_check_requested = Signal()
    # UPDATE_DOWNLOAD, UPDATE_RESTART or UPDATE_OPEN_PAGE.
    update_action_requested = Signal(str)
    update_notes_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view: SettingsView | None = None

        # Conversion engine
        self.engine_badge = Badge(tr(s.SETTINGS_WORKING), BadgeTone.SUCCESS, "CircleCheck")
        self.engine_text = elided("")
        status = QWidget()
        status_layout = QHBoxLayout(status)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(8)
        status_layout.addWidget(self.engine_badge)
        status_layout.addWidget(self.engine_text, 1)
        self.ffmpeg_row = _PathRow()
        self.ffmpeg_row.browse.clicked.connect(lambda: self.engine_browse_requested.emit("ffmpeg"))
        self.ffprobe_row = _PathRow()
        self.ffprobe_row.browse.clicked.connect(
            lambda: self.engine_browse_requested.emit("ffprobe")
        )
        self.engine_note = Note("", "Info", "accent")
        self.check_button = Button(tr(s.CHECK_AGAIN), icon="RefreshCw")
        self.check_button.clicked.connect(self.check_requested)
        self.automatic_button = Button(tr(s.SETTINGS_FIND_AUTOMATICALLY), ButtonKind.SUBTLE)
        self.automatic_button.clicked.connect(self.engine_reset_requested)
        engine_buttons = QWidget()
        engine_buttons_layout = QHBoxLayout(engine_buttons)
        engine_buttons_layout.setContentsMargins(0, 0, 0, 0)
        engine_buttons_layout.setSpacing(8)
        engine_buttons_layout.addWidget(self.check_button)
        engine_buttons_layout.addWidget(self.automatic_button)
        engine_buttons_layout.addStretch()

        # Defaults
        self.save_same = RadioButton(tr(s.SETTINGS_SAME_FOLDER))
        self.save_folder = RadioButton(tr(s.SETTINGS_THIS_FOLDER))
        self.save_same.toggled.connect(lambda on: self._on_save_mode(SAVE_SAME, on))
        self.save_folder.toggled.connect(lambda on: self._on_save_mode(SAVE_FOLDER, on))
        self.folder_row = _PathRow("Folder")
        self.folder_row.setContentsMargins(28, 0, 0, 0)
        self.folder_row.browse.clicked.connect(self.save_folder_browse_requested)
        folder_choice = QWidget()
        folder_layout = QVBoxLayout(folder_choice)
        folder_layout.setContentsMargins(0, 0, 0, 0)
        folder_layout.setSpacing(8)
        folder_layout.addWidget(self.save_same)
        folder_layout.addWidget(self.save_folder)
        folder_layout.addWidget(self.folder_row)
        self.video_format = ChoiceCombo(tr(s.SETTINGS_VIDEO_FORMAT))
        self.video_format.format_changed.connect(self.video_format_changed)
        self.audio_format = ChoiceCombo(tr(s.SETTINGS_AUDIO_FORMAT))
        self.audio_format.format_changed.connect(self.audio_format_changed)
        self.quality = SegmentedControl(vm.quality_options(), accessible_name=tr(s.FIELD_QUALITY))
        self.quality.changed.connect(
            lambda value: self.quality_changed.emit(vm.quality_from_value(value))
        )

        # Performance
        hardware = QWidget()
        hardware_layout = QHBoxLayout(hardware)
        hardware_layout.setContentsMargins(0, 0, 0, 0)
        hardware_layout.setSpacing(12)
        self.hardware_switch = Switch()
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

        # Temporary files
        self.temp_row = _PathRow(reset_text=tr(s.SETTINGS_USE_DEFAULT))
        self.temp_row.browse.clicked.connect(self.temp_browse_requested)
        if self.temp_row.reset is not None:
            self.temp_row.reset.clicked.connect(self.temp_reset_requested)

        # Appearance
        self.theme = SegmentedControl(
            [
                SegmentOption("system", tr(s.SETTINGS_THEME_SYSTEM)),
                SegmentOption("light", tr(s.SETTINGS_THEME_LIGHT)),
                SegmentOption("dark", tr(s.SETTINGS_THEME_DARK)),
            ],
            accessible_name=tr(s.SETTINGS_THEME),
        )
        self.theme.changed.connect(self.theme_changed)

        # Updates
        self.update_badge = Badge("", BadgeTone.NEUTRAL)
        self.update_text = elided("")
        update_status = QWidget()
        update_status_layout = QHBoxLayout(update_status)
        update_status_layout.setContentsMargins(0, 0, 0, 0)
        update_status_layout.setSpacing(8)
        update_status_layout.addWidget(self.update_badge)
        update_status_layout.addWidget(self.update_text, 1)
        automatic = QWidget()
        automatic_layout = QHBoxLayout(automatic)
        automatic_layout.setContentsMargins(0, 0, 0, 0)
        automatic_layout.setSpacing(12)
        self.automatic_switch = Switch()
        self.automatic_switch.setAccessibleName(tr(s.UPDATES_AUTOMATIC))
        self.automatic_switch.toggled.connect(self.updates_automatic_changed)
        automatic_layout.addWidget(self.automatic_switch, 0, Qt.AlignmentFlag.AlignTop)
        automatic_text = QVBoxLayout()
        automatic_text.setSpacing(0)
        automatic_text.addWidget(label(tr(s.UPDATES_AUTOMATIC), TextStyle.BODY_STRONG, wrap=True))
        self.automatic_help = label(
            tr(s.UPDATES_AUTOMATIC_HELP), TextStyle.CAPTION, "secondary", wrap=True
        )
        automatic_text.addWidget(self.automatic_help)
        automatic_layout.addLayout(automatic_text, 1)
        self.update_check = Button(tr(s.UPDATES_CHECK_NOW), icon="RefreshCw")
        self.update_check.clicked.connect(self.update_check_requested)
        self.update_action = Button(
            tr(s.UPDATES_DOWNLOAD), ButtonKind.PRIMARY, icon="ArrowDownToLine"
        )
        self.update_action.clicked.connect(self._on_update_action)
        self.update_notes = Button(tr(s.UPDATES_WHATS_NEW), ButtonKind.SUBTLE)
        self.update_notes.clicked.connect(self.update_notes_requested)
        update_buttons = QWidget()
        update_buttons_layout = QHBoxLayout(update_buttons)
        update_buttons_layout.setContentsMargins(0, 0, 0, 0)
        update_buttons_layout.setSpacing(8)
        update_buttons_layout.addWidget(self.update_action)
        update_buttons_layout.addWidget(self.update_check)
        update_buttons_layout.addWidget(self.update_notes)
        update_buttons_layout.addStretch()
        self._update_action = ""

        self.sections = [
            _Section(
                tr(s.SETTINGS_ENGINE),
                tr(s.SETTINGS_ENGINE_TEXT),
                [
                    status,
                    _setting("ffmpeg.exe", self.ffmpeg_row),
                    _setting("ffprobe.exe", self.ffprobe_row),
                    self.engine_note,
                    engine_buttons,
                ],
            ),
            _Section(
                tr(s.SETTINGS_DEFAULTS),
                tr(s.SETTINGS_DEFAULTS_TEXT),
                [
                    _setting(tr(s.SETTINGS_SAVE_TO), folder_choice),
                    _setting(tr(s.SETTINGS_VIDEO_FORMAT), self.video_format),
                    _setting(tr(s.SETTINGS_AUDIO_FORMAT), self.audio_format),
                    _setting(tr(s.FIELD_QUALITY), self.quality),
                ],
            ),
            _Section(tr(s.SETTINGS_PERFORMANCE), tr(s.SETTINGS_PERFORMANCE_TEXT), [hardware]),
            _Section(
                tr(s.SETTINGS_TEMP),
                tr(s.SETTINGS_TEMP_TEXT),
                [_setting(tr(s.SETTINGS_LOCATION), self.temp_row, tr(s.SETTINGS_LOCATION_HELP))],
            ),
            _Section(
                tr(s.SETTINGS_APPEARANCE),
                tr(s.SETTINGS_APPEARANCE_TEXT),
                [_setting(tr(s.SETTINGS_THEME), self.theme)],
            ),
            _Section(tr(s.UPDATES), tr(s.UPDATES_TEXT), [update_status, automatic, update_buttons]),
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
        self.scroll_area = page_scroll(content)
        layout.addWidget(self.scroll_area, 1)

    def show_view(self, view: SettingsView) -> None:
        self.view = view
        controls = (
            self.save_same,
            self.save_folder,
            self.video_format,
            self.audio_format,
            self.quality,
            self.hardware_switch,
            self.theme,
        )
        for control in controls:
            control.blockSignals(True)
        try:
            if view.engine_working:
                self.engine_badge.set_badge(
                    tr(s.SETTINGS_WORKING), BadgeTone.SUCCESS, "CircleCheck"
                )
            else:
                self.engine_badge.set_badge(tr(s.SETTINGS_NOT_FOUND), BadgeTone.DANGER, "CircleX")
            self.engine_text.setText(view.engine_text)
            self.ffmpeg_row.field.set_text(view.ffmpeg)
            self.ffprobe_row.field.set_text(view.ffprobe)
            self.engine_note.set_text(view.engine_note)
            self.engine_note.set_tone(
                "warning" if view.engine_note_warning else "accent",
                "TriangleAlert" if view.engine_note_warning else "Info",
            )
            self.engine_note.setVisible(bool(view.engine_note))
            self.automatic_button.setVisible(view.engine_chosen)

            self.save_same.setChecked(view.save_mode == SAVE_SAME)
            self.save_folder.setChecked(view.save_mode != SAVE_SAME)
            self.folder_row.field.set_text(view.save_folder)
            self.folder_row.setEnabled(view.save_mode != SAVE_SAME)
            self.video_format.set_choices(view.video_formats, view.video_format)
            self.audio_format.set_choices(view.audio_formats, view.audio_format)
            self.quality.set_value(vm.quality_value(view.quality))

            self.hardware_switch.setChecked(view.hardware_enabled)
            self.set_hardware_text(view.hardware_text)

            self.temp_row.field.set_text(view.temp_location)
            if self.temp_row.reset is not None:
                self.temp_row.reset.setVisible(not view.temp_is_default)
            self.theme.set_value(view.theme)
        finally:
            for control in controls:
                control.blockSignals(False)
        self.show_update(view.update)

    def show_update(self, view: UpdateView) -> None:
        """Only the update rows, so download progress doesn't redo the whole page."""
        self.update_badge.set_badge(view.badge, view.tone)
        self.update_text.setText(view.text)
        self.automatic_switch.blockSignals(True)
        self.automatic_switch.setChecked(view.automatic)
        self.automatic_switch.blockSignals(False)
        self.automatic_help.setText(
            tr(s.UPDATES_AUTOMATIC_HELP if view.installable else s.UPDATES_NOT_INSTALLED_HELP)
        )
        self.update_check.setEnabled(not view.checking)
        self._update_action = view.action
        if view.action in UPDATE_BUTTONS:
            text, icon = UPDATE_BUTTONS[view.action]
            self.update_action.setText(tr(text))
            self.update_action.set_icon_name(icon)
        self.update_action.setVisible(bool(view.action))
        self.update_notes.setVisible(view.notes)

    def _on_update_action(self) -> None:
        if self._update_action:
            self.update_action_requested.emit(self._update_action)

    def _on_save_mode(self, mode: str, on: bool) -> None:
        if on:
            self.save_mode_changed.emit(mode)

    def set_hardware_text(self, text: str) -> None:
        self.hardware_help.setText(text)
        self.hardware_switch.setAccessibleDescription(text)

    def set_compact(self, compact: bool) -> None:
        for section in self.sections:
            section.set_compact(compact)
