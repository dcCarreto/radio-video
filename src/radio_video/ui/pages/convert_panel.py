"""Right pane in Simple Mode: format, quality, destination, what you'll get, and the footer
that turns into progress, success or canceled states."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QPaintEvent, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from radio_video.models.presets import Quality
from radio_video.ui import strings as s
from radio_video.ui import theme
from radio_video.ui import viewmodel as vm
from radio_video.ui.pages.advanced_panel import AdvancedPanel
from radio_video.ui.state import Job, Mode, PreviewKind
from radio_video.ui.strings import tr
from radio_video.ui.theme import fonts
from radio_video.ui.theme.fonts import TextStyle
from radio_video.ui.viewmodel import Estimate
from radio_video.ui.widgets.button import Button, ButtonKind, ButtonSize
from radio_video.ui.widgets.format_combo import FormatCombo, FormatGroup
from radio_video.ui.widgets.frames import Card, FieldBox, Note, NumberBox, Rule
from radio_video.ui.widgets.labels import ElidedLabel, kicker, label
from radio_video.ui.widgets.painting import antialiased, follow_theme
from radio_video.ui.widgets.progress import ProgressBlock, ProgressState, StatusIcon
from radio_video.ui.widgets.segmented import SegmentedControl, SegmentOption
from radio_video.ui.widgets.stack import fit_stack_height

PANEL_WIDTH = 440
PANEL_WIDTH_COMPACT = 380
PANEL_WIDTH_ADVANCED = 620
PANEL_WIDTH_ADVANCED_COMPACT = 460
PANEL_MIN_WIDTH = 360
PANEL_MAX_WIDTH = 720
POPUP_MAX_HEIGHT = 520
POPUP_MAX_HEIGHT_COMPACT = 400


@dataclass(frozen=True)
class PanelView:
    groups: list[FormatGroup]
    format_key: str
    format_help: str
    lossless: bool
    quality: Quality
    folder: str
    folder_error: str
    output_name: str
    output_is_video: bool
    bumped_text: str
    contents: list[tuple[str, str]]
    estimate: Estimate
    job: Job = Job.IDLE
    mode: Mode = Mode.SIMPLE
    what: str = ""
    progress_text: str = ""
    fraction: float = 0.0
    speed_tip: str = ""
    result_title: str = ""
    result_text: str = ""
    summary: str = ""

    @property
    def locked(self) -> bool:
        return self.job in (Job.STARTING, Job.CONVERTING)


def _field(number: int, title: str) -> tuple[QVBoxLayout, QLabel]:
    box = QVBoxLayout()
    box.setSpacing(6)
    heading = QHBoxLayout()
    heading.setSpacing(8)
    heading.addWidget(NumberBox(number))
    text = label(title, TextStyle.BODY_STRONG)
    heading.addWidget(text)
    heading.addStretch()
    box.addLayout(heading)
    return box, text


class OutputCard(Card):
    """ "You'll get": output name, what goes in it, and the estimated size."""

    def __init__(self) -> None:
        super().__init__()
        self.icon = StatusIcon(16)
        self.name = ElidedLabel("", TextStyle.BODY_STRONG, mode=Qt.TextElideMode.ElideMiddle)
        self.bumped = label("", TextStyle.CAPTION, "secondary", wrap=True)
        self.contents = QGridLayout()
        self.contents.setHorizontalSpacing(12)
        self.contents.setVerticalSpacing(4)
        self.contents.setColumnStretch(1, 1)
        self.estimate_value = label("", TextStyle.BODY_STRONG)
        self.estimate_how = label("", TextStyle.CAPTION, "secondary", wrap=True)

        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        name_row.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignTop)
        name_row.addWidget(self.name, 1)

        estimate_row = QHBoxLayout()
        estimate_row.addWidget(label(tr(s.ESTIMATED_SIZE), tone="secondary"), 1)
        estimate_row.addWidget(self.estimate_value)
        estimate = QVBoxLayout()
        estimate.setContentsMargins(0, 10, 0, 0)
        estimate.setSpacing(2)
        estimate.addLayout(estimate_row)
        estimate.addWidget(self.estimate_how)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        layout.addWidget(kicker(tr(s.YOU_GET)))
        layout.addLayout(name_row)
        layout.addWidget(self.bumped)
        layout.addLayout(self.contents)
        layout.addWidget(Rule(hairline=True))
        layout.addLayout(estimate)

    def apply_view(self, view: PanelView) -> None:
        self.icon.set_icon("Film" if view.output_is_video else "Music")
        self.name.setText(view.output_name)
        self.bumped.setText(view.bumped_text)
        self.bumped.setVisible(bool(view.bumped_text))
        while self.contents.count():
            item = self.contents.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        small = fonts.make_font(13)
        for row, (title, value) in enumerate(view.contents):
            title_label = label(title, tone="secondary")
            value_label = label(value, wrap=True)
            for widget in (title_label, value_label):
                widget.setFont(small)
            self.contents.addWidget(title_label, row, 0, Qt.AlignmentFlag.AlignTop)
            self.contents.addWidget(value_label, row, 1)
        self.estimate_value.setText(view.estimate.value)
        self.estimate_how.setText(view.estimate.how)


class _Footer(QFrame):
    def __init__(self) -> None:
        super().__init__()
        follow_theme(self)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        p = theme.palette()
        painter.fillRect(self.rect(), p.surface)
        painter.fillRect(QRectF(0, 0, self.width(), 2), p.rule)


def _pair(left: Button, right: Button) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(8)
    for button in (left, right):
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row.addWidget(button, 1)
    return row


class ConvertPanel(QFrame):
    mode_changed = Signal(Mode)
    format_changed = Signal(str)
    quality_changed = Signal(Quality)
    browse_requested = Signal()
    preview_requested = Signal(PreviewKind)
    convert_requested = Signal()
    cancel_requested = Signal()
    show_in_folder_requested = Signal()
    done_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ConvertPanel")
        self.setMinimumWidth(PANEL_MIN_WIDTH)
        self.setMaximumWidth(PANEL_MAX_WIDTH)
        self._groups: list[FormatGroup] | None = None
        self._compact = False
        self._advanced = False

        # Mode
        self.mode = SegmentedControl(
            [
                SegmentOption("simple", tr(s.MODE_SIMPLE), tooltip=tr(s.MODE_SIMPLE_TIP)),
                SegmentOption(
                    "advanced",
                    tr(s.MODE_ADVANCED),
                    tooltip=tr(s.MODE_ADVANCED_TIP),
                    planned=True,
                    planned_text=tr(s.BADGE_PLANNED),
                ),
            ],
            accessible_name=tr(s.MODE_LABEL),
        )
        self.mode.set_value("simple")
        self.mode.changed.connect(lambda value: self.mode_changed.emit(Mode(value)))
        self.mode_help = label(tr(s.MODE_SIMPLE_HELP), TextStyle.CAPTION, "secondary", wrap=True)
        self.top = QWidget()
        self.top_layout = QVBoxLayout(self.top)
        self.top_layout.setSpacing(6)
        self.top_layout.addWidget(self.mode)
        self.top_layout.addWidget(self.mode_help)

        # Fields
        format_box, _ = _field(1, tr(s.FIELD_FORMAT))
        self.format = FormatCombo()
        self.format.setAccessibleName(tr(s.FIELD_FORMAT))
        self.format.delegate.recommended_text = tr(s.BADGE_RECOMMENDED)
        self.format.format_changed.connect(self.format_changed)
        self.format_help = label("", TextStyle.CAPTION, "secondary", wrap=True)
        format_box.addWidget(self.format)
        format_box.addWidget(self.format_help)

        quality_box, _ = _field(2, tr(s.FIELD_QUALITY))
        self.quality = SegmentedControl(vm.quality_options(), accessible_name=tr(s.FIELD_QUALITY))
        self.quality.changed.connect(
            lambda value: self.quality_changed.emit(vm.quality_from_value(value))
        )
        self.quality_help = label("", TextStyle.CAPTION, "secondary", wrap=True)
        self.lossless_note = Note(tr(s.QUALITY_LOSSLESS))
        quality_box.addWidget(self.quality)
        quality_box.addWidget(self.quality_help)
        quality_box.addWidget(self.lossless_note)

        folder_box, _ = _field(3, tr(s.FIELD_SAVE_TO))
        self.folder = FieldBox()
        self.browse = Button(tr(s.BROWSE))
        self.browse.setToolTip(tr(s.BROWSE_TOOLTIP))
        self.browse.clicked.connect(self.browse_requested)
        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)
        folder_row.addWidget(self.folder, 1)
        folder_row.addWidget(self.browse)
        self.folder_error = label(tr(s.FOLDER_NOT_WRITABLE), TextStyle.CAPTION, "danger", wrap=True)
        folder_box.addLayout(folder_row)
        folder_box.addWidget(self.folder_error)

        self.output = OutputCard()

        content = QWidget()
        content.setProperty("transparent", True)
        self.fields = QVBoxLayout(content)
        self.fields.setSpacing(20)
        self.fields.addLayout(format_box)
        self.fields.addLayout(quality_box)
        self.fields.addLayout(folder_box)
        self.fields.addWidget(self.output)
        self.fields.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(content)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Footer pages
        self.preview_short = Button(
            tr(s.PREVIEW_SHORT), icon="Eye", shortcut_hint=tr(s.SHORTCUT_PREVIEW)
        )
        self.preview_short.setToolTip(tr(s.PREVIEW_SHORT_TOOLTIP))
        self.preview_short.clicked.connect(lambda: self.preview_requested.emit(PreviewKind.SAMPLE))
        self.preview_full = Button(tr(s.PREVIEW_FULL), icon="MonitorPlay")
        self.preview_full.setToolTip(tr(s.PREVIEW_FULL_TOOLTIP))
        self.preview_full.clicked.connect(lambda: self.preview_requested.emit(PreviewKind.FULL))
        self.preview_help = label(tr(s.PREVIEW_HELPER), TextStyle.CAPTION, "secondary", wrap=True)
        self.convert = Button(
            tr(s.CONVERT),
            ButtonKind.PRIMARY,
            icon="ArrowRightLeft",
            shortcut_hint=tr(s.SHORTCUT_CONVERT),
            size=ButtonSize.LARGE,
            block=True,
        )
        self.convert.clicked.connect(self.convert_requested)
        idle = QWidget()
        idle_layout = QVBoxLayout(idle)
        idle_layout.setContentsMargins(0, 0, 0, 0)
        idle_layout.setSpacing(10)
        self.summary = QWidget()
        summary_layout = QVBoxLayout(self.summary)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(4)
        summary_layout.addWidget(kicker(tr(s.ADV_SUMMARY)))
        self.summary_text = label("", TextStyle.MONO_SMALL, wrap=True)
        summary_layout.addWidget(self.summary_text)
        idle_layout.addWidget(self.summary)
        idle_layout.addLayout(_pair(self.preview_short, self.preview_full))
        idle_layout.addWidget(self.preview_help)
        idle_layout.addWidget(self.convert)

        self.progress = ProgressBlock()
        self.progress_text = label("", TextStyle.BODY_STRONG)
        self.progress_help = label(tr(s.CONVERTING_HELP), TextStyle.CAPTION, "secondary", wrap=True)
        self.cancel = Button(
            tr(s.CANCEL_CONVERSION),
            ButtonKind.DANGER,
            icon="X",
            shortcut_hint=tr(s.SHORTCUT_CANCEL),
            block=True,
        )
        self.cancel.clicked.connect(self.cancel_requested)
        for widget in (self.progress_text, self.progress_help, self.cancel):
            self.progress.add_widget(widget)

        self.result = ProgressBlock()
        self.result_text = ElidedLabel(
            "", TextStyle.CAPTION, mode=Qt.TextElideMode.ElideLeft, tone="secondary"
        )
        self.result_help = label("", TextStyle.CAPTION, "secondary", wrap=True)
        self.result_primary = Button(tr(s.SHOW_IN_FOLDER), ButtonKind.PRIMARY, icon="FolderOpen")
        self.result_secondary = Button(tr(s.DONE))
        self.result_primary.clicked.connect(self._on_result_primary)
        self.result_secondary.clicked.connect(self.done_requested)
        self.result.add_widget(self.result_text)
        self.result.add_widget(self.result_help)
        buttons = QWidget()
        pair = _pair(self.result_primary, self.result_secondary)
        pair.setContentsMargins(0, 0, 0, 0)
        buttons.setLayout(pair)
        self.result.add_widget(buttons)

        self.footer_pages = QStackedWidget()
        for page in (idle, self.progress, self.result):
            self.footer_pages.addWidget(page)
        self.footer_pages.currentChanged.connect(self._fit_footer)
        self.footer = _Footer()
        self.footer_layout = QVBoxLayout(self.footer)
        self.footer_layout.addWidget(self.footer_pages)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.top)
        layout.addWidget(Rule(hairline=True))
        self.advanced = AdvancedPanel()
        self.bodies = QStackedWidget()
        self.bodies.addWidget(scroll)
        self.bodies.addWidget(self.advanced)
        layout.addWidget(self.bodies, 1)
        layout.addWidget(self.footer)
        self._job = Job.IDLE
        self._fit_footer()
        self.set_compact(False)
        follow_theme(self)

    # Rendering
    def apply_view(self, view: PanelView) -> None:
        self._job = view.job
        locked = view.locked
        self.mode.set_value(view.mode.value)
        advanced = view.mode is Mode.ADVANCED
        self._advanced = advanced
        self.bodies.setCurrentIndex(1 if advanced else 0)
        self.summary.setVisible(advanced)
        self.summary_text.setText(view.summary)
        self._fit_footer()
        self.preview_help.setVisible(not advanced and not self._compact)
        self.mode_help.setText(
            tr(s.MODE_SIMPLE_HELP if view.mode is Mode.SIMPLE else s.MODE_ADVANCED_HELP)
        )
        if view.groups != self._groups:
            self._groups = view.groups
            self.format.set_groups(view.groups, view.format_key)
        elif self.format.current_key() != view.format_key:
            self.format.blockSignals(True)
            self.format.set_current_key(view.format_key)
            self.format.blockSignals(False)
        self.format_help.setText(view.format_help)
        self.quality.blockSignals(True)
        self.quality.set_value(vm.quality_value(view.quality))
        self.quality.blockSignals(False)
        self.quality.setVisible(not view.lossless)
        self.quality_help.setVisible(not view.lossless)
        self.quality_help.setText(vm.quality_help(view.quality))
        self.lossless_note.setVisible(view.lossless)
        self.folder.set_text(view.folder)
        self.folder_error.setVisible(bool(view.folder_error))
        self.output.apply_view(view)
        for widget in (self.mode, self.format, self.quality, self.browse):
            widget.setEnabled(not locked)
        self.convert.setEnabled(not view.folder_error)
        self._render_footer(view)

    def _render_footer(self, view: PanelView) -> None:
        if view.job in (Job.STARTING, Job.CONVERTING):
            self.footer_pages.setCurrentWidget(self.progress)
            starting = view.job is Job.STARTING
            self.progress.set_busy(True)
            self.progress.set_header(
                tr(s.STARTING_TITLE if starting else s.CONVERTING_TITLE),
                tr(s.STARTING_TEXT) if starting else view.what,
            )
            self.progress.bar.set_state(ProgressState.ACTIVE)
            if starting:
                self.progress.bar.set_indeterminate(True)
            else:
                self.progress.bar.set_fraction(view.fraction)
            self.progress_text.setText(view.progress_text)
            self.progress_text.setVisible(not starting)
            self.progress_text.setToolTip(view.speed_tip)
        elif view.job is Job.SUCCESS:
            self.footer_pages.setCurrentWidget(self.result)
            self.result.set_status_icon("CircleCheck", "success")
            self.result.set_header(view.result_title)
            self.result.bar.set_state(ProgressState.SUCCESS)
            self.result.bar.set_fraction(1.0)
            self.result_text.setText(view.result_text)
            self.result_text.show()
            self.result_help.hide()
            self.result_primary.setText(tr(s.SHOW_IN_FOLDER))
            self.result_primary.set_icon_name("FolderOpen")
            self.result_secondary.setText(tr(s.DONE))
        elif view.job is Job.CANCELED:
            self.footer_pages.setCurrentWidget(self.result)
            self.result.set_status_icon("Ban")
            self.result.set_header(tr(s.CANCELED_TITLE))
            self.result.bar.set_state(ProgressState.CANCELED)
            self.result.bar.set_fraction(view.fraction)
            self.result_text.hide()
            self.result_help.setText(view.result_text)
            self.result_help.show()
            self.result_primary.setText(tr(s.CONVERT_AGAIN))
            self.result_primary.set_icon_name("RotateCcw")
            self.result_secondary.setText(tr(s.DISMISS))
        else:
            self.footer_pages.setCurrentIndex(0)

    def _fit_footer(self, _index: int = 0) -> None:
        """Size the footer to the current page, not the tallest one."""
        fit_stack_height(self.footer_pages)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit_footer()

    def _on_result_primary(self) -> None:
        if self._job is Job.SUCCESS:
            self.show_in_folder_requested.emit()
        else:
            self.convert_requested.emit()

    def focus_after_render(self) -> QWidget | None:
        """The control that should take focus for the current footer state."""
        if self._job in (Job.STARTING, Job.CONVERTING):
            return self.cancel
        if self._job in (Job.SUCCESS, Job.CANCELED):
            return self.result_primary
        return None

    def set_compact(self, compact: bool) -> None:
        self._compact = compact
        side = 20 if compact else 24
        self.top_layout.setContentsMargins(side, 16, side, 14)
        self.fields.setContentsMargins(side, 20, side, 20)
        self.fields.setSpacing(16 if compact else 20)
        self.footer_layout.setContentsMargins(side, 16, side, 20)
        self.preview_help.setVisible(not compact and not self._advanced)
        self.advanced.set_compact(compact)
        self.preview_short.set_shortcut_hint(None if compact else tr(s.SHORTCUT_PREVIEW))
        self.format.max_popup_height = POPUP_MAX_HEIGHT_COMPACT if compact else POPUP_MAX_HEIGHT

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        painter.fillRect(self.rect(), theme.palette().surface)
