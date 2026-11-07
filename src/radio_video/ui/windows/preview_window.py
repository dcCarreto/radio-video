"""Preview window: plays a converted preview or the opened file itself.

A converted preview is made with the exact settings (a sample or the whole file); the window
always says that it shows the converted output, measures the real size, and offers to convert
the full file with the same settings. The original player converts nothing: it plays the
opened file as it is, so the two can be compared.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QCloseEvent, QKeyEvent, QPaintEvent, QResizeEvent, QShowEvent
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPlainTextEdit,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from radio_video.ffmpeg.progress import ProgressUpdate
from radio_video.models.conversion import ConversionSettings
from radio_video.models.media import MediaInfo
from radio_video.models.presets import OutputFormat, Quality
from radio_video.models.tracks import StreamMap
from radio_video.services.conversion import ConversionError
from radio_video.services.preview import PreviewGenerator, PreviewSample, short_preview_range
from radio_video.services.preview import PreviewKind as ServiceKind
from radio_video.ui import icons, theme
from radio_video.ui import strings as s
from radio_video.ui import viewmodel as vm
from radio_video.ui.errors_map import ErrorKind, Failure, describe
from radio_video.ui.icons import IconName
from radio_video.ui.native.dwm import style_title_bar
from radio_video.ui.state import PreviewKind, Progress
from radio_video.ui.strings import tr
from radio_video.ui.theme import fonts
from radio_video.ui.theme.fonts import TextStyle
from radio_video.ui.theme.tokens import Palette
from radio_video.ui.widgets.badge import Badge, BadgeTone
from radio_video.ui.widgets.button import Button, ButtonKind, ButtonSize, Expander
from radio_video.ui.widgets.frames import Card, Note, Rule
from radio_video.ui.widgets.labels import ElidedLabel, kicker, label
from radio_video.ui.widgets.painting import antialiased, fill_rounded, follow_theme
from radio_video.ui.widgets.player import Player
from radio_video.ui.widgets.progress import ProgressBar, Spinner, StatusIcon
from radio_video.ui.widgets.video_canvas import VideoCanvas
from radio_video.utils.formatting import format_duration, format_size

logger = logging.getLogger(__name__)

SIZE = QSize(1040, 668)
SIZE_COMPACT = QSize(860, 568)
SIDE_WIDTH = 260
SIDE_WIDTH_COMPACT = 220
CARD_MAX_WIDTH = 400
SEEK_MS = 5000
LOG_MAX_HEIGHT = 140
RULE_WIDTH = 2


class Phase(Enum):
    CREATING = "creating"
    READY = "ready"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass(frozen=True)
class PreviewRequest:
    media: MediaInfo
    fmt: OutputFormat
    quality: Quality
    kind: PreviewKind
    contents: list[tuple[str, str]]
    calculated_size: int | None = None
    # The settings to convert with; the format's own settings when not given.
    settings: ConversionSettings | None = None
    # The tracks to map; the format's own choice when not given.
    streams: StreamMap | None = None

    def plan(self) -> StreamMap:
        return self.streams if self.streams is not None else self.fmt.plan(self.media)


class _Area(QFrame):
    """Rounded area behind the state card or the audio card."""

    def __init__(self, color: str = "sunken") -> None:
        super().__init__()
        self._color = color
        self.card: QWidget | None = None
        follow_theme(self)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        # As in the design: min(400 px, the area minus 24 px on each side).
        if self.card is not None:
            self.card.setFixedWidth(max(min(CARD_MAX_WIDTH, self.width() - 48), 160))

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        fill_rounded(painter, QRectF(self.rect()), 4, theme.palette().color(self._color))


class _Band(QFrame):
    """Header or footer band: background colour and a rule on one edge."""

    def __init__(self, *, rule_below: bool, rule_width: int) -> None:
        super().__init__()
        self._below, self._width = rule_below, rule_width
        follow_theme(self)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        p = theme.palette()
        painter.fillRect(self.rect(), p.bg)
        color = p.rule if self._width == RULE_WIDTH else p.border
        y = self.height() - self._width if self._below else 0
        painter.fillRect(QRectF(0, y, self.width(), self._width), color)


def _value(title: str, value: QWidget) -> QVBoxLayout:
    box = QVBoxLayout()
    box.setSpacing(2)
    box.addWidget(label(title, TextStyle.CAPTION, "secondary"))
    box.addWidget(value)
    return box


class PreviewWindow(QWidget):
    convert_requested = Signal()
    retry_requested = Signal(PreviewKind)
    # The other kind of preview: the original from a converted one, and the reverse.
    switch_requested = Signal(PreviewKind)
    progress = Signal(Progress)
    ready = Signal(object)
    failed = Signal()
    canceled = Signal()
    closed = Signal()

    def __init__(
        self,
        ffmpeg: Path,
        request: PreviewRequest,
        *,
        compact: bool = False,
        autoplay: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.request = request
        self.original = request.kind is PreviewKind.ORIGINAL
        self.phase = Phase.CREATING
        self._autoplay = autoplay
        self._locked = False
        self._sample: PreviewSample | None = None
        self._last_time: float | None = None
        media = request.media
        if self.original:
            self.setWindowTitle(tr(s.ORIGINAL_WINDOW_TITLE).format(name=media.path.name))
        else:
            self.setWindowTitle(tr(s.PREVIEW_WINDOW_TITLE).format(name=media.path.stem))
        self.setWindowIcon(icons.app_icon())
        self.resize(SIZE_COMPACT if compact else SIZE)

        self.generator = PreviewGenerator(ffmpeg, self)
        self.generator.progress.connect(self._on_progress)
        self.generator.ready.connect(self._on_ready)
        self.generator.failed.connect(self._on_failed)
        self.generator.canceled.connect(self._on_canceled)
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(0.8)
        self.player.setAudioOutput(self.audio_output)
        self.player.errorOccurred.connect(self._on_player_error)

        what = vm.format_and_quality(request.fmt, request.quality)
        badge_text = tr(s.ORIGINAL_BADGE if self.original else s.PREVIEW_BADGE)
        badge_icon: IconName = "Play" if self.original else "Eye"
        self.part = label("", tone="secondary")
        header = _Band(rule_below=True, rule_width=2)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(24, 14, 24, 16)
        header_layout.setSpacing(4)
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(Badge(badge_text, BadgeTone.ACCENT, badge_icon))
        top.addWidget(self.part, 1)
        header_layout.addLayout(top)
        title = media.path.name if self.original else what
        header_layout.addWidget(
            ElidedLabel(title, TextStyle.TITLE, mode=Qt.TextElideMode.ElideMiddle)
        )

        # Area: state card, video canvas or audio card
        self.canvas = VideoCanvas(badge_text, badge_icon)
        self.player.setVideoOutput(self.canvas.sink)
        self.audio_card = self._make_audio_card(what, badge_text, badge_icon)
        self.state_area = _Area()
        self.card = Card()
        self.state_area.card = self.card
        self._build_card()
        state_layout = QVBoxLayout(self.state_area)
        state_layout.setContentsMargins(24, 24, 24, 24)
        # Centred with stretches: an alignment flag would drop height-for-width and clip text.
        card_row = QHBoxLayout()
        card_row.addStretch()
        card_row.addWidget(self.card)
        card_row.addStretch()
        state_layout.addStretch()
        state_layout.addLayout(card_row)
        state_layout.addStretch()
        self.area = QStackedWidget()
        for page in (self.state_area, self.canvas, self.audio_card):
            self.area.addWidget(page)

        self.ready_note = Note(
            tr(s.ORIGINAL_NOTE if self.original else s.PREVIEW_READY_NOTE), "Info", "accent"
        )
        self.player_bar = Player(
            play_tip=tr(s.PLAYER_PLAY),
            pause_tip=tr(s.PLAYER_PAUSE),
            seek_tip=tr(s.PLAYER_SEEK),
            mute_tip=tr(s.PLAYER_MUTE),
            unmute_tip=tr(s.PLAYER_UNMUTE),
            volume_tip=tr(s.PLAYER_VOLUME),
        )
        self.player_bar.play_toggled.connect(self.toggle_playback)
        self.player_bar.seek_requested.connect(self.player.setPosition)
        self.player_bar.mute_toggled.connect(self.toggle_mute)
        self.player_bar.volume_changed.connect(lambda v: self.audio_output.setVolume(v / 100))
        self.player.durationChanged.connect(self.player_bar.set_duration)
        self.player.positionChanged.connect(self.player_bar.set_position)
        self.player.playbackStateChanged.connect(self._on_playback_state)

        self.outdated = Note(tr(s.PREVIEW_OUTDATED), "TriangleAlert", "warning")
        self.update_button = Button(tr(s.PREVIEW_UPDATE), size=ButtonSize.SMALL)
        self.outdated.add_widget(self.update_button)
        self.update_button.clicked.connect(lambda: self.retry_requested.emit(self.request.kind))
        self.outdated.hide()

        main = QVBoxLayout()
        main.setContentsMargins(24, 16, 20, 16)
        main.setSpacing(10)
        main.addWidget(self.area, 1)
        main.addWidget(self.outdated)
        main.addWidget(self.ready_note)
        main.addWidget(self.player_bar)

        self.side = self._make_side(compact)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addLayout(main, 1)
        body.addWidget(self.side)

        footer = _Band(rule_below=False, rule_width=1)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 12, 24, 12)
        footer_layout.setSpacing(8)
        footer_layout.addStretch()
        self.close_button = Button(tr(s.CLOSE), shortcut_hint=tr(s.SHORTCUT_CANCEL))
        self.close_button.clicked.connect(self.close)
        if self.original:
            self.switch_button = Button(tr(s.ORIGINAL_PREVIEW_CONVERTED), icon="Eye")
            self.switch_button.setToolTip(tr(s.ORIGINAL_PREVIEW_CONVERTED_TOOLTIP))
            self._switch_kind = PreviewKind.SAMPLE
        else:
            self.switch_button = Button(tr(s.PREVIEW_PLAY_ORIGINAL), icon="Play")
            self.switch_button.setToolTip(tr(s.PREVIEW_PLAY_ORIGINAL_TOOLTIP))
            self._switch_kind = PreviewKind.ORIGINAL
        self.switch_button.clicked.connect(self._switch)
        self.convert_button = Button(
            tr(s.CONVERT if self.original else s.PREVIEW_CONVERT_FULL),
            ButtonKind.PRIMARY,
            icon="ArrowRightLeft",
            shortcut_hint=tr(s.SHORTCUT_CONVERT),
        )
        self.convert_button.clicked.connect(self._convert)
        footer_layout.addWidget(self.close_button)
        footer_layout.addWidget(self.switch_button)
        footer_layout.addWidget(self.convert_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addLayout(body, 1)
        layout.addWidget(footer)
        theme.current().changed.connect(self._on_theme_changed)
        # The original has nothing to create: it is ready as soon as the window opens.
        self._set_phase(Phase.READY if self.original else Phase.CREATING)

    # Building blocks
    def _make_audio_card(self, what: str, badge_text: str, badge_icon: IconName) -> QWidget:
        area = _Area()
        layout = QVBoxLayout(area)
        layout.setContentsMargins(24, 12, 24, 24)
        layout.setSpacing(0)
        layout.addWidget(
            Badge(badge_text, BadgeTone.ACCENT, badge_icon), 0, Qt.AlignmentFlag.AlignLeft
        )
        layout.addStretch()
        music = StatusIcon(40)
        music.set_icon("Music")
        layout.addWidget(music)
        layout.addSpacing(12)
        title = s.ORIGINAL_AUDIO_TITLE if self.original else s.PREVIEW_AUDIO_TITLE
        layout.addWidget(label(tr(title), TextStyle.TITLE))
        fmt, media = self.request.fmt, self.request.media
        if self.original:
            text = vm.source_summary(media)
        else:
            track = vm.output_track_text(fmt, media, self.request.plan())
            text = tr(s.PREVIEW_AUDIO_TEXT).format(settings=what, track=track)
        self.audio_text = label(text, tone="secondary", wrap=True)
        layout.addWidget(self.audio_text)
        return area

    def _build_card(self) -> None:
        card = QVBoxLayout(self.card)
        card.setContentsMargins(20, 20, 20, 20)
        card.setSpacing(12)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.card_spinner = Spinner(20)
        self.card_icon = StatusIcon(20)
        self.card_title = label("", TextStyle.SUBTITLE, wrap=True)
        row.addWidget(self.card_spinner)
        row.addWidget(self.card_icon)
        row.addWidget(self.card_title, 1)
        card.addLayout(row)
        self.card_text = label("", tone="secondary", wrap=True)
        self.card_help = label("", tone="secondary", wrap=True)
        self.card_bar = ProgressBar()
        self.card_progress = label("", TextStyle.BODY_STRONG)
        self.card_expander = Expander(tr(s.TECHNICAL_DETAILS))
        self.card_log = QPlainTextEdit()
        self.card_log.setObjectName("Log")
        self.card_log.setReadOnly(True)
        self.card_log.setFont(fonts.font(TextStyle.MONO_SMALL))
        self.card_log.setMaximumHeight(LOG_MAX_HEIGHT)
        self.card_log.hide()
        self.card_expander.toggled.connect(self.card_log.setVisible)
        self.card_action = Button("", ButtonKind.PRIMARY)
        self.card_action.clicked.connect(self._on_card_action)
        for widget in (
            self.card_text,
            self.card_help,
            self.card_bar,
            self.card_progress,
            self.card_expander,
            self.card_log,
        ):
            card.addWidget(widget)
        card.addWidget(self.card_action, 0, Qt.AlignmentFlag.AlignLeft)

    def _make_side(self, compact: bool) -> QWidget:
        content = QWidget()
        content.setProperty("transparent", True)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)
        original = self.original
        layout.addWidget(kicker(tr(s.ORIGINAL_SIDE_TITLE if original else s.PREVIEW_SIDE_TITLE)))
        self.side_part = label("", wrap=True)
        layout.addLayout(_value(tr(s.PREVIEW_PART), self.side_part))
        self.side_size = label("", TextStyle.BODY_STRONG, wrap=True)
        layout.addLayout(
            _value(tr(s.ORIGINAL_SIZE if original else s.PREVIEW_SIZE), self.side_size)
        )
        self.side_estimate = label("", TextStyle.BODY_STRONG, wrap=True)
        self.side_estimate_how = label("", TextStyle.CAPTION, "secondary", wrap=True)
        if not original:
            # The original is not converted, so there is no output size to estimate.
            estimate = _value(tr(s.PREVIEW_FULL_SIZE), self.side_estimate)
            estimate.addWidget(self.side_estimate_how)
            layout.addLayout(estimate)
        layout.addSpacing(8)
        layout.addWidget(Rule())
        layout.addWidget(kicker(tr(s.ORIGINAL_CONTENTS if original else s.PREVIEW_SETTINGS_USED)))
        for title, value in self.request.contents:
            layout.addLayout(_value(title, label(value, wrap=True)))
        layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        side = QFrame()
        side_layout = QHBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(0)
        side_layout.addWidget(Rule(hairline=True, vertical=True))
        side_layout.addWidget(scroll, 1)
        side.setFixedWidth(SIDE_WIDTH_COMPACT if compact else SIDE_WIDTH)
        return side

    # Generation
    def start(self) -> bool:
        if self.original:
            return self._play_original()
        request = self.request
        kind = ServiceKind.SHORT if request.kind is PreviewKind.SAMPLE else ServiceKind.FULL
        self._sample = None
        self._last_time = None
        self.player.setSource(QUrl())
        self.canvas.clear()
        try:
            self.generator.generate(
                request.media,
                request.settings or request.fmt.settings(request.quality),
                request.fmt.extension,
                kind,
                request.plan(),
            )
        except (ConversionError, ValueError, OSError) as exc:
            self._show_failure(str(exc))
            return False
        self._set_phase(Phase.CREATING)
        return True

    def _play_original(self) -> bool:
        """Play the opened file directly: nothing is converted or written."""
        path = self.request.media.path
        if not path.is_file():
            self._show_failure(f"{path}: No such file or directory")
            return False
        self.canvas.clear()
        self._set_phase(Phase.READY)
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        if self._autoplay:
            self.player.play()
        return True

    @Slot(QMediaPlayer.Error, str)
    def _on_player_error(self, error: QMediaPlayer.Error, message: str) -> None:
        if error is QMediaPlayer.Error.NoError or not self.original:
            return
        logger.info("The original can't be played here: %s", message)
        self.card_text.setText(tr(s.ORIGINAL_FAILED_TEXT))
        self.card_help.setText(tr(s.ORIGINAL_FAILED_DO))
        self.card_log.setPlainText(message)
        self._set_phase(Phase.FAILED)

    def part_text(self) -> str:
        duration = self.request.media.duration
        total = format_duration(duration)
        if self.original:
            return tr(s.PREVIEW_PART_FULL).format(total=total)
        if self.request.kind is PreviewKind.SAMPLE:
            start, length = short_preview_range(duration)
            if length is not None:
                return tr(s.PREVIEW_PART_SAMPLE).format(
                    length=format_duration(length), start=format_duration(start), total=total
                )
        return tr(s.PREVIEW_PART_FULL).format(total=total)

    @Slot(ProgressUpdate)
    def _on_progress(self, update: ProgressUpdate) -> None:
        job = self.generator.runner.job
        duration = job.expected_duration if job is not None else None
        fraction = update.fraction(duration)
        if update.out_time is not None:
            self._last_time = update.out_time
        if fraction is None:
            return
        progress = Progress(fraction, update.speed, update.remaining_seconds(duration))
        self.card_bar.set_fraction(fraction)
        self.card_progress.setText(vm.progress_detail(Progress(fraction, None, progress.remaining)))
        self.progress.emit(progress)

    @Slot(PreviewSample)
    def _on_ready(self, sample: PreviewSample) -> None:
        self._sample = sample
        self._set_phase(Phase.READY)
        self.ready.emit(sample.estimated_full_size(self.request.media.duration))
        self.player.setSource(QUrl.fromLocalFile(str(sample.path)))
        if self._autoplay:
            self.player.play()

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self._show_failure(message)
        self.failed.emit()

    def _show_failure(self, message: str) -> None:
        report = describe(Failure(details=message, source=self.request.media.path))
        if self.original:
            self.card_text.setText(report.what_happened)
            self.card_help.setText(report.what_to_do)
        elif report.kind is ErrorKind.UNREADABLE and self._last_time is not None:
            start = self.generator.runner.job.start if self.generator.runner.job else 0
            at = format_duration((start or 0) + self._last_time)
            self.card_text.setText(tr(s.PREVIEW_FAILED_AT).format(time=at))
            self.card_help.setText(tr(s.PREVIEW_FAILED_AT_DO))
        else:
            self.card_text.setText(report.what_happened)
            self.card_help.setText(report.what_to_do)
        self.card_log.setPlainText(message)
        self._set_phase(Phase.FAILED)

    @Slot()
    def _on_canceled(self) -> None:
        self._set_phase(Phase.CANCELED)
        self.canceled.emit()

    def cancel(self) -> None:
        if self.phase is Phase.CREATING:
            self.generator.cancel()

    def _on_card_action(self) -> None:
        if self.phase is Phase.CREATING:
            self.cancel()
        elif self.original:
            # The player can't open the file; a converted preview still can.
            self._switch()
        else:
            self.retry_requested.emit(self.request.kind)

    def _switch(self) -> None:
        if self.phase is not Phase.CREATING and self.switch_button.isEnabled():
            self.switch_requested.emit(self._switch_kind)

    def _convert(self) -> None:
        if self.phase is Phase.READY and not self._locked:
            self.convert_requested.emit()

    def set_locked(self, locked: bool) -> None:
        """While converting the window only plays: no new preview, no second conversion."""
        if locked != self._locked:
            self._locked = locked
            self._set_phase(self.phase)

    def _render_buttons(self) -> None:
        self.convert_button.setVisible(self.phase is Phase.READY)
        self.convert_button.setEnabled(not self._locked)
        # From the original, a converted preview needs the converter, which may be busy.
        self.switch_button.setVisible(self.phase is not Phase.CREATING)
        self.switch_button.setEnabled(not (self.original and self._locked))

    # Rendering
    def _set_phase(self, phase: Phase) -> None:
        self.phase = phase
        ready = phase is Phase.READY
        audio = not self.request.fmt.is_video
        self.part.setText(self.part_text())
        self.side_part.setText(self.part_text())
        if self.original:
            audio = not self.request.media.has_video
        self.ready_note.setVisible(ready)
        self.player_bar.setVisible(ready)
        self._render_buttons()
        if ready:
            self.area.setCurrentWidget(self.audio_card if audio else self.canvas)
        else:
            self.area.setCurrentWidget(self.state_area)
            self._render_card(phase)
        self._render_side()

    def _render_card(self, phase: Phase) -> None:
        creating = phase is Phase.CREATING
        failed = phase is Phase.FAILED
        self.card_spinner.setVisible(creating)
        self.card_icon.setVisible(not creating)
        self.card_bar.setVisible(creating)
        self.card_progress.setVisible(creating)
        self.card_help.setVisible(failed)
        self.card_expander.setVisible(failed)
        self.card_log.setVisible(failed and self.card_expander.isChecked())
        if creating:
            self.card_title.setText(tr(s.PREVIEW_CREATING_TITLE))
            sample = self.request.kind is PreviewKind.SAMPLE
            self.card_text.setText(
                tr(s.PREVIEW_CREATING_SAMPLE if sample else s.PREVIEW_CREATING_FULL)
            )
            self.card_bar.set_fraction(0)
            self.card_progress.setText(vm.progress_detail(Progress(0.0)))
            self.card_action.setText(tr(s.CANCEL))
            self.card_action.set_kind(ButtonKind.DANGER)
            self.card_action.set_icon_name("X")
            self.card_action.set_shortcut_hint(tr(s.SHORTCUT_CANCEL))
        elif failed and self.original:
            self.card_icon.set_icon("CircleX", "danger")
            self.card_title.setText(tr(s.ORIGINAL_FAILED_TITLE))
            self.card_action.setText(tr(s.ORIGINAL_PREVIEW_CONVERTED))
            self.card_action.set_kind(ButtonKind.PRIMARY)
            self.card_action.set_icon_name("Eye")
            self.card_action.set_shortcut_hint(None)
        elif failed:
            self.card_icon.set_icon("CircleX", "danger")
            self.card_title.setText(tr(s.PREVIEW_FAILED_TITLE))
            self.card_action.setText(tr(s.ACTION_TRY_AGAIN))
            self.card_action.set_kind(ButtonKind.PRIMARY)
            self.card_action.set_icon_name("RotateCcw")
            self.card_action.set_shortcut_hint(None)
        else:
            self.card_icon.set_icon("Ban")
            self.card_title.setText(tr(s.PREVIEW_CANCELED_TITLE))
            self.card_text.setText(tr(s.PREVIEW_CANCELED_TEXT))
            self.card_action.setText(tr(s.PREVIEW_AGAIN))
            self.card_action.set_kind(ButtonKind.PRIMARY)
            self.card_action.set_icon_name("Eye")
            self.card_action.set_shortcut_hint(None)
        self.card_action.setEnabled(not (failed and self.original and self._locked))
        self.card_action.updateGeometry()

    def _render_side(self) -> None:
        if self.original:
            self.side_size.setText(format_size(self.request.media.size))
            return
        sample = self._sample if self.phase is Phase.READY else None
        if sample is not None:
            length = sample.length or self.request.media.duration
            self.side_size.setText(
                tr(s.PREVIEW_SIZE_VALUE).format(
                    size=format_size(sample.size), length=format_duration(length)
                )
            )
        else:
            self.side_size.setText(vm.NO_VALUE)
        calculated = self.request.calculated_size
        measured = (
            sample.estimated_full_size(self.request.media.duration) if sample is not None else None
        )
        if calculated is not None and sample is not None:
            self.side_estimate.setText(
                tr(s.ESTIMATE_VALUE).format(size=vm.format_estimate_size(calculated))
            )
            self.side_estimate_how.setText(tr(s.PREVIEW_CALCULATED))
        elif measured is not None:
            self.side_estimate.setText(
                tr(s.ESTIMATE_VALUE).format(size=vm.format_estimate_size(measured))
            )
            self.side_estimate_how.setText(tr(s.PREVIEW_MEASURED_HERE))
        else:
            self.side_estimate.setText(tr(s.PREVIEW_FULL_SIZE_PENDING))
            self.side_estimate_how.setText("")
        self.side_estimate_how.setVisible(bool(self.side_estimate_how.text()))

    def set_outdated(self, outdated: bool) -> None:
        self.outdated.setVisible(outdated and self.phase is Phase.READY)

    # Playback
    @Slot()
    def toggle_playback(self) -> None:
        if self.phase is not Phase.READY:
            return
        if self.player.playbackState() is QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    @Slot()
    def toggle_mute(self) -> None:
        muted = not self.audio_output.isMuted()
        self.audio_output.setMuted(muted)
        self.player_bar.set_muted(muted)

    def seek(self, delta_ms: int) -> None:
        if self.phase is Phase.READY:
            target = min(max(self.player.position() + delta_ms, 0), self.player.duration())
            self.player.setPosition(target)

    def _on_playback_state(self, state: QMediaPlayer.PlaybackState) -> None:
        self.player_bar.set_playing(state is QMediaPlayer.PlaybackState.PlayingState)

    # Window
    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        if key == Qt.Key.Key_Escape:
            if self.phase is Phase.CREATING:
                self.cancel()
            else:
                self.close()
        elif ctrl and key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._convert()
        elif key in (Qt.Key.Key_Space, Qt.Key.Key_K):
            self.toggle_playback()
        elif key == Qt.Key.Key_Left:
            self.seek(-SEEK_MS)
        elif key == Qt.Key.Key_Right:
            self.seek(SEEK_MS)
        elif key == Qt.Key.Key_M:
            self.toggle_mute()
        else:
            super().keyPressEvent(event)
            return
        event.accept()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self._on_theme_changed(theme.palette())

    def _on_theme_changed(self, palette: Palette) -> None:
        if self.isVisible():
            style_title_bar(self, dark=palette.is_dark, caption=palette.bg, text=palette.text)

    def release(self) -> None:
        """Stop playback, cancel generation and delete the temporary files."""
        self.player.pause()
        self.player.setSource(QUrl())
        self.generator.discard()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.release()
        self.closed.emit()
        super().closeEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        painter.fillRect(self.rect(), theme.palette().surface)
