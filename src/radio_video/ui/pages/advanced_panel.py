"""Advanced Mode: every technical setting, each with a one-line explanation.

The controls are built once and updated in place from an :class:`AdvancedView`, so a
change never rebuilds the panel under the pointer. Each control turns into a new
:class:`AdvancedChoices` sent through ``choices_changed``; the window resolves it and shows
the result again. Only what fits the format and the file is offered.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from radio_video.ffmpeg.command import FAST_START_MUXERS
from radio_video.models.advanced import ASPECTS as ASPECT_RATIOS
from radio_video.models.advanced import (
    AUDIO_BITRATES,
    CHANNEL_COUNTS,
    CRF_RANGE,
    DEFAULT_AUDIO_BITRATE,
    FRAME_RATES,
    LOSSLESS_AUDIO,
    PIXEL_FORMATS,
    PRESETS,
    VIDEO_BITRATES,
    AdvancedChoices,
    Deinterlace,
    EncoderChoice,
    RateControl,
    Recipe,
    TrackRule,
    audio_codecs,
    can_copy_audio,
    can_copy_video,
    kept_tracks,
    sample_rates,
    smaller_heights,
    toggle_track,
    track_rule,
)
from radio_video.models.conversion import COPY, ConversionSettings
from radio_video.models.estimate import codec_display_name
from radio_video.models.hardware import HardwareSupport
from radio_video.models.media import MediaInfo, StreamInfo, StreamType
from radio_video.models.presets import OutputFormat, Quality
from radio_video.models.tracks import SUBTITLE_COPY, StreamMap
from radio_video.ui import strings as s
from radio_video.ui import viewmodel as vm
from radio_video.ui.icons import IconName
from radio_video.ui.strings import tr
from radio_video.ui.theme.fonts import TextStyle
from radio_video.ui.widgets.badge import Badge, BadgeTone
from radio_video.ui.widgets.checks import CheckBox, LabeledCheck
from radio_video.ui.widgets.format_combo import Choice, ChoiceCombo, FormatCombo, FormatGroup
from radio_video.ui.widgets.frames import Note
from radio_video.ui.widgets.grid_table import Column, GridTable
from radio_video.ui.widgets.labels import label
from radio_video.ui.widgets.player import Slider
from radio_video.ui.widgets.progress import StatusIcon
from radio_video.ui.widgets.segmented import SegmentedControl, SegmentOption
from radio_video.ui.widgets.tab_strip import TabSpec, TabStrip
from radio_video.utils.formatting import format_bitrate, format_frame_rate

TAB_HEIGHT = 40
VALUE_WIDTH = 44
TAB_KEYS = ["video", "audio", "tracks", "output"]
KEEP = ""

PIXEL_DESCRIPTIONS = {
    "yuv420p": s.ADV_PIXEL_8BIT,
    "yuv422p": s.ADV_PIXEL_422,
    "yuv444p": s.ADV_PIXEL_444,
    "yuv420p10le": s.ADV_PIXEL_10BIT,
}
SUBTITLE_TARGET_NAMES = {"mov_text": s.SUBTITLE_MP4_TEXT, "webvtt": s.SUBTITLE_WEBVTT}


@dataclass(frozen=True)
class AdvancedView:
    media: MediaInfo
    fmt: OutputFormat
    quality: Quality
    choices: AdvancedChoices
    recipe: Recipe
    # The settings FFmpeg will get, with the graphics card applied.
    final: ConversionSettings
    groups: list[FormatGroup]
    formats: tuple[OutputFormat, ...]
    encoders: frozenset[str]
    hardware: HardwareSupport | None
    hardware_on: bool
    locked: bool = False


def _recommended_label() -> QLabel:
    result = label("", TextStyle.CAPTION, "secondary", wrap=True)
    result.setTextFormat(Qt.TextFormat.RichText)
    return result


class _Field(QWidget):
    """Title, control, help line and the recommended value."""

    def __init__(self, title: str, control: QWidget, help_text: str = "") -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(label(title, TextStyle.BODY_STRONG))
        layout.addWidget(control)
        # Added before hiding: showing or hiding a parentless widget makes it a window.
        self.help = label(help_text, TextStyle.CAPTION, "secondary", wrap=True)
        self.rec = _recommended_label()
        layout.addWidget(self.help)
        layout.addWidget(self.rec)
        self.help.setVisible(bool(help_text))
        self.rec.hide()

    def set_help(self, text: str) -> None:
        self.help.setText(text)
        self.help.setVisible(bool(text))

    def set_recommended(self, value: str) -> None:
        if value:
            self.rec.setText(tr(s.RECOMMENDED_VALUE).format(value=f"<b>{value}</b>"))
        self.rec.setVisible(bool(value))


class _FieldGrid(QWidget):
    """Two columns of fields, one column in compact windows; wide fields span both.

    Hidden fields leave no gap. Changes are collected and laid out once by ``apply()``;
    only fields that move are placed again, since every placement re-polishes the widget.
    """

    def __init__(self) -> None:
        super().__init__()
        self._fields: list[tuple[QWidget, bool]] = []
        self._hidden: set[int] = set()
        self._places: dict[int, tuple[int, int, int]] = {}
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(24)
        self._grid.setVerticalSpacing(20)
        self._compact = False
        self._dirty = False

    def add(self, widget: QWidget, *, wide: bool = False) -> None:
        self._fields.append((widget, wide))
        self._dirty = True

    def set_compact(self, compact: bool) -> None:
        if compact != self._compact:
            self._compact = compact
            self._dirty = True
            self.apply()

    def set_shown(self, widget: QWidget, shown: bool) -> None:
        key = id(widget)
        if shown != (key not in self._hidden):
            self._hidden.symmetric_difference_update({key})
            self._dirty = True

    def apply(self) -> None:
        if not self._dirty:
            return
        self._dirty = False
        columns = 1 if self._compact else 2
        row = column = 0
        places: dict[int, tuple[int, int, int]] = {}
        for widget, wide in self._fields:
            if id(widget) in self._hidden:
                continue
            if wide or columns == 1:
                if column:
                    row, column = row + 1, 0
                places[id(widget)] = (row, 0, columns)
                row += 1
                continue
            places[id(widget)] = (row, column, 1)
            column += 1
            if column == columns:
                row, column = row + 1, 0
        for widget, _wide in self._fields:
            key = id(widget)
            place = places.get(key)
            if place != self._places.get(key):
                self._grid.removeWidget(widget)
                if place is not None:
                    self._grid.addWidget(widget, place[0], place[1], 1, place[2])
            if widget.isHidden() != (place is None):
                widget.setHidden(place is None)
        self._places = places
        for index in range(2):
            self._grid.setColumnStretch(index, 1 if index < columns else 0)


def _kind_cell(kind: str, icon: IconName) -> QWidget:
    cell = QWidget()
    layout = QHBoxLayout(cell)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    status = StatusIcon(16)
    status.set_icon(icon)
    layout.addWidget(status)
    layout.addWidget(label(kind), 1)
    return cell


def _keep(value: str) -> str:
    return tr(s.ADV_KEEP_ORIGINAL_VALUE).format(value=value) if value else tr(s.ADV_KEEP_ORIGINAL)


def _rate_key(rate: float) -> str:
    return f"{rate:g}"


class AdvancedPanel(QFrame):
    choices_changed = Signal(object)
    format_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view: AdvancedView | None = None
        self._compact = False
        self._tracks_key: tuple[object, ...] | None = None
        self.track_checks: dict[int, CheckBox] = {}
        self.track_outputs: dict[int, QLabel] = {}

        self.tabs = TabStrip(
            [
                TabSpec("video", tr(s.ADV_TAB_VIDEO)),
                TabSpec("audio", tr(s.ADV_TAB_AUDIO)),
                TabSpec("tracks", tr(s.ADV_TAB_TRACKS)),
                TabSpec("output", tr(s.ADV_TAB_OUTPUT)),
            ],
            height=TAB_HEIGHT,
            padding=20,
            background="surface",
        )
        self.tabs.setAccessibleName(tr(s.MODE_ADVANCED))
        self.pages = QStackedWidget()
        self._bodies: list[QVBoxLayout] = []
        for _ in TAB_KEYS:
            self.pages.addWidget(self._page())
        self.tabs.current_changed.connect(
            lambda key: self.pages.setCurrentIndex(TAB_KEYS.index(key))
        )
        self._grids: list[_FieldGrid] = []
        self._built = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.tabs)
        layout.addWidget(self.pages, 1)

    # Building
    def _page(self) -> QScrollArea:
        content = QWidget()
        content.setProperty("transparent", True)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        body = QVBoxLayout()
        body.setContentsMargins(24, 20, 24, 20)
        body.setSpacing(12)
        layout.addLayout(body)
        layout.addStretch(1)
        self._bodies.append(body)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        return scroll

    def _grid(self, page: int) -> _FieldGrid:
        grid = _FieldGrid()
        self._grids.append(grid)
        self._bodies[page].addWidget(grid)
        return grid

    def _combo(
        self, title: str, help_text: str, handler: Callable[[str], None]
    ) -> tuple[_Field, ChoiceCombo]:
        combo = ChoiceCombo(title)
        combo.format_changed.connect(handler)
        return _Field(title, combo, help_text), combo

    def _build_video(self) -> None:
        grid = self.video_grid = self._grid(0)
        self.format = FormatCombo()
        self.format.setAccessibleName(tr(s.FIELD_FORMAT))
        self.format.delegate.recommended_text = tr(s.BADGE_RECOMMENDED)
        self.format.format_changed.connect(self._on_format)
        grid.add(_Field(tr(s.FIELD_FORMAT), self.format), wide=True)
        self.no_video = Note("")
        grid.add(self.no_video, wide=True)

        self.copy_video = CheckBox(tr(s.ADV_STREAM_COPY))
        self.copy_video.toggled.connect(lambda on: self._change(copy_video=on))
        self.copy_field = LabeledCheck(self.copy_video, tr(s.ADV_STREAM_COPY_HELP))
        grid.add(self.copy_field, wide=True)

        encoder_box = QWidget()
        encoder_layout = QVBoxLayout(encoder_box)
        encoder_layout.setContentsMargins(0, 0, 0, 0)
        encoder_layout.setSpacing(6)
        self.encoder = ChoiceCombo(tr(s.ADV_ENCODER))
        self.encoder.format_changed.connect(lambda key: self._change(encoder=EncoderChoice(key)))
        self.encoder_badge = Badge("", BadgeTone.SUCCESS, "Cpu")
        encoder_layout.addWidget(self.encoder)
        encoder_layout.addWidget(self.encoder_badge, 0, Qt.AlignmentFlag.AlignLeft)
        self.encoder_field = _Field(tr(s.ADV_ENCODER), encoder_box, tr(s.ADV_ENCODER_HELP))
        grid.add(self.encoder_field)

        self.method = SegmentedControl(
            [
                SegmentOption(RateControl.QUALITY.value, tr(s.ADV_CONSTANT_QUALITY)),
                SegmentOption(RateControl.BITRATE.value, tr(s.ADV_TARGET_BITRATE)),
            ],
            accessible_name=tr(s.ADV_QUALITY_METHOD),
        )
        self.method.changed.connect(lambda key: self._change(rate_control=RateControl(key)))
        self.method_field = _Field(
            tr(s.ADV_QUALITY_METHOD), self.method, tr(s.ADV_QUALITY_METHOD_HELP)
        )
        self.method_field.set_recommended(tr(s.ADV_CONSTANT_QUALITY))
        grid.add(self.method_field)

        crf_row = QWidget()
        row = QHBoxLayout(crf_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        self.crf = Slider()
        self.crf.setAccessibleName(tr(s.ADV_CRF))
        self.crf.valueChanged.connect(self._on_crf)
        self.crf_value = label("", TextStyle.BODY_STRONG)
        self.crf_value.setFixedWidth(VALUE_WIDTH)
        self.crf_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.crf, 1)
        row.addWidget(self.crf_value)
        self.crf_field = _Field(tr(s.ADV_CRF), crf_row, tr(s.ADV_CRF_HELP))
        grid.add(self.crf_field)

        self.video_bitrate_field, self.video_bitrate = self._combo(
            tr(s.ADV_VIDEO_BITRATE),
            tr(s.ADV_VIDEO_BITRATE_HELP),
            lambda key: self._change(video_bitrate=int(key)),
        )
        grid.add(self.video_bitrate_field)
        self.preset_field, self.preset = self._combo(
            tr(s.ADV_PRESET), tr(s.ADV_PRESET_HELP), lambda key: self._change(preset=key)
        )
        grid.add(self.preset_field)
        self.resolution_field, self.resolution = self._combo(
            tr(s.ADV_RESOLUTION),
            tr(s.ADV_RESOLUTION_HELP),
            lambda key: self._change(height=int(key) if key else None),
        )
        grid.add(self.resolution_field)
        self.aspect_field, self.aspect = self._combo(
            tr(s.ADV_ASPECT), tr(s.ADV_ASPECT_HELP), lambda key: self._change(aspect=key or None)
        )
        grid.add(self.aspect_field)
        self.frame_rate_field, self.frame_rate = self._combo(
            tr(s.ADV_FRAME_RATE),
            tr(s.ADV_FRAME_RATE_HELP),
            lambda key: self._change(frame_rate=float(key) if key else None),
        )
        grid.add(self.frame_rate_field)
        self.pixel_field, self.pixel = self._combo(
            tr(s.ADV_PIXEL_FORMAT),
            tr(s.ADV_PIXEL_FORMAT_HELP),
            lambda key: self._change(pixel_format=key),
        )
        grid.add(self.pixel_field)
        for field in (self.resolution_field, self.aspect_field, self.frame_rate_field):
            field.set_recommended(tr(s.ADV_KEEP_ORIGINAL))

    def _build_audio(self) -> None:
        grid = self.audio_grid = self._grid(1)
        self.audio_codec_field, self.audio_codec = self._combo(
            tr(s.ADV_CODEC), "", lambda key: self._change(audio_codec=key)
        )
        grid.add(self.audio_codec_field)
        self.audio_bitrate_field, self.audio_bitrate = self._combo(
            tr(s.ADV_BITRATE),
            tr(s.ADV_BITRATE_HELP),
            lambda key: self._change(audio_bitrate=int(key) if key else None),
        )
        grid.add(self.audio_bitrate_field)
        self.sample_rate_field, self.sample_rate = self._combo(
            tr(s.ADV_SAMPLE_RATE),
            tr(s.ADV_SAMPLE_RATE_HELP),
            lambda key: self._change(sample_rate=int(key) if key else None),
        )
        grid.add(self.sample_rate_field)
        self.channels_field, self.channels = self._combo(
            tr(s.ADV_CHANNELS),
            tr(s.ADV_CHANNELS_HELP),
            lambda key: self._change(channels=int(key) if key else None),
        )
        grid.add(self.channels_field)
        for field in (self.sample_rate_field, self.channels_field):
            field.set_recommended(tr(s.ADV_KEEP_ORIGINAL))
        self.no_audio = Note(tr(s.ADV_NO_AUDIO_KEPT), "TriangleAlert", "warning")
        grid.add(self.no_audio, wide=True)
        grid.add(Note(tr(s.ADV_AUDIO_NOTE)), wide=True)

    def _build_tracks(self) -> None:
        body = self._bodies[2]
        self.tracks_help = label("", TextStyle.CAPTION, "secondary", wrap=True)
        body.addWidget(self.tracks_help)
        self.tracks_box = QVBoxLayout()
        self.tracks_box.setContentsMargins(0, 0, 0, 0)
        body.addLayout(self.tracks_box)
        self.tracks_table: GridTable | None = None

    def _build_output(self) -> None:
        grid = self.output_grid = self._grid(3)
        self.container_field, self.container = self._combo(
            tr(s.ADV_CONTAINER), tr(s.ADV_CONTAINER_HELP), self._on_format
        )
        grid.add(self.container_field)
        self.deinterlace_field, self.deinterlace = self._combo(
            tr(s.ADV_DEINTERLACE),
            tr(s.ADV_DEINTERLACE_HELP),
            lambda key: self._change(deinterlace=Deinterlace(key)),
        )
        self.deinterlace_field.set_recommended(tr(s.ADV_DEINTERLACE_AUTO))
        grid.add(self.deinterlace_field)
        self.fast_start = CheckBox(tr(s.ADV_FAST_START))
        self.fast_start.toggled.connect(lambda on: self._change(fast_start=on))
        self.fast_start_field = LabeledCheck(self.fast_start, tr(s.ADV_FAST_START_HELP))
        grid.add(self.fast_start_field, wide=True)
        self.metadata = CheckBox(tr(s.ADV_METADATA))
        self.metadata.toggled.connect(lambda on: self._change(keep_metadata=on))
        grid.add(LabeledCheck(self.metadata, tr(s.ADV_METADATA_HELP)), wide=True)
        self.loudness = CheckBox(tr(s.ADV_LOUDNESS))
        self.loudness.toggled.connect(lambda on: self._change(normalize_loudness=on))
        self.loudness_field = LabeledCheck(self.loudness, tr(s.ADV_LOUDNESS_HELP))
        grid.add(self.loudness_field, wide=True)

    # Changes
    def _change(self, **changes: object) -> None:
        if self.view is not None:
            choices = replace(self.view.choices, **changes)  # type: ignore[arg-type]
            if choices != self.view.choices:
                self.choices_changed.emit(choices)

    def _on_crf(self, value: int) -> None:
        self.crf_value.setText(str(value))
        self._change(crf=value)

    def _on_format(self, key: str) -> None:
        if self.view is not None and key != self.view.fmt.key:
            self.format_changed.emit(key)

    def _on_track(self, index: int, keep: bool) -> None:
        view = self.view
        if view is not None:
            choices = toggle_track(view.fmt, view.media, view.choices, index, keep)
            if choices != view.choices:
                self.choices_changed.emit(choices)
            else:
                self._sync_tracks(view)

    # Showing
    def set_compact(self, compact: bool) -> None:
        self._compact = compact
        side = 20 if compact else 24
        for body in self._bodies:
            body.setContentsMargins(side, 20, side, 20)
        for grid in self._grids:
            grid.set_compact(compact)
        if self.view is not None:
            self._tracks_key = None
            self._sync_tracks(self.view)

    def _build(self) -> None:
        """Create the controls the first time Advanced Mode is shown."""
        if self._built:
            return
        self._built = True
        self._build_video()
        self._build_audio()
        self._build_tracks()
        self._build_output()
        for grid in self._grids:
            grid.set_compact(self._compact)
            grid.apply()

    def show_view(self, view: AdvancedView) -> None:
        self._build()
        self.view = view
        widgets: list[QWidget] = [
            self.format,
            self.copy_video,
            self.encoder,
            self.method,
            self.crf,
            self.video_bitrate,
            self.preset,
            self.resolution,
            self.aspect,
            self.frame_rate,
            self.pixel,
            self.audio_codec,
            self.audio_bitrate,
            self.sample_rate,
            self.channels,
            self.container,
            self.deinterlace,
            self.fast_start,
            self.metadata,
            self.loudness,
        ]
        for widget in widgets:
            widget.blockSignals(True)
        try:
            self._sync_video(view)
            self._sync_audio(view)
            self._sync_output(view)
        finally:
            for widget in widgets:
                widget.blockSignals(False)
        for grid in self._grids:
            grid.apply()
        self._sync_tracks(view)
        if view.locked:
            for widget in widgets:
                widget.setEnabled(False)

    def _sync_video(self, view: AdvancedView) -> None:
        fmt, media, choices = view.fmt, view.media, view.choices
        grid = self.video_grid
        self.format.set_groups(view.groups, fmt.key)
        base = fmt.settings(view.quality).video
        has_video = base is not None and view.recipe.streams.video is not None
        self.no_video.set_text(tr(s.ADV_NO_VIDEO).format(format=fmt.label))
        grid.set_shown(self.no_video, base is None)
        video_fields: list[QWidget] = [
            self.copy_field,
            self.encoder_field,
            self.method_field,
            self.crf_field,
            self.video_bitrate_field,
            self.preset_field,
            self.resolution_field,
            self.aspect_field,
            self.frame_rate_field,
            self.pixel_field,
        ]
        for field in video_fields:
            grid.set_shown(field, has_video)
        if base is None or not has_video:
            return
        source = next(
            (st for st in media.streams if st.index == view.recipe.streams.video),
            media.video_streams[0] if media.video_streams else None,
        )
        video = view.recipe.settings.video
        copy = video is not None and video.is_copy
        copyable = can_copy_video(fmt, media, view.recipe.streams.video)
        self.copy_video.setChecked(copy)
        self.copy_video.setEnabled(copyable)
        source_codec = (source.codec_name or "") if source else ""
        copy_help = self.copy_field.help
        if isinstance(copy_help, QLabel):
            copy_help.setText(
                tr(s.ADV_STREAM_COPY_HELP)
                if copyable
                else tr(s.ADV_STREAM_COPY_UNAVAILABLE).format(
                    container=vm.container_name(fmt),
                    codec=vm.DECODER_NAMES.get(source_codec, source_codec.upper()),
                )
            )

        codec = base.codec
        name = codec_display_name(codec)
        hardware = view.hardware.encoder_for(codec) if view.hardware else None
        choices_list = [
            Choice(
                EncoderChoice.SOFTWARE.value,
                tr(s.ADV_ENCODER_SOFTWARE).format(codec=name, encoder=codec.removeprefix("lib")),
            )
        ]
        if hardware is not None and view.hardware is not None:
            choices_list.append(
                Choice(
                    EncoderChoice.HARDWARE.value,
                    tr(s.ADV_ENCODER_HARDWARE).format(
                        codec=name, technology=view.hardware.technology
                    ),
                )
            )
        on_card = view.final.video is not None and view.final.video.codec != (
            video.codec if video else codec
        )
        self.encoder.set_choices(
            choices_list,
            EncoderChoice.HARDWARE.value if on_card else EncoderChoice.SOFTWARE.value,
        )
        self.encoder.setEnabled(len(choices_list) > 1 and not copy)
        if hardware is not None and view.hardware is not None:
            self.encoder_badge.set_badge(
                tr(s.ADV_ENCODER_DETECTED).format(technology=view.hardware.technology),
                BadgeTone.SUCCESS,
                "Cpu",
            )
            self.encoder_badge.show()
            self.encoder_field.set_help(tr(s.ADV_ENCODER_HELP))
        else:
            self.encoder_badge.hide()
            self.encoder_field.set_help(tr(s.ADV_ENCODER_SOFTWARE_ONLY).format(codec=name))
        self.encoder_field.set_recommended(choices_list[0].name)

        bitrate_mode = choices.rate_control is RateControl.BITRATE
        self.method.set_value(choices.rate_control.value)
        low, high = CRF_RANGE.get(codec, (0, 51))
        self.crf.setRange(low, high)
        crf = video.crf if video is not None and video.crf is not None else base.crf or 0
        self.crf.setValue(crf)
        self.crf_value.setText(str(crf))
        balanced = view.fmt.settings(Quality.BALANCED).video
        if balanced is not None and balanced.crf is not None:
            self.crf_field.set_recommended(f"{balanced.crf} ({vm.quality_label(Quality.BALANCED)})")
        grid.set_shown(self.crf_field, not bitrate_mode)
        grid.set_shown(self.video_bitrate_field, bitrate_mode)
        current_bitrate = video.bitrate if video is not None and video.bitrate else None
        self.video_bitrate.set_choices(
            [Choice(str(rate), format_bitrate(rate)) for rate in VIDEO_BITRATES],
            str(current_bitrate or ""),
        )

        presets = PRESETS.get(codec, ())
        grid.set_shown(self.preset_field, bool(presets))
        self.preset.set_choices(
            [Choice(p, p) for p in presets], (video.preset if video else None) or "medium"
        )
        self.preset_field.set_recommended("medium" if presets else "")
        self.preset_field.set_help(tr(s.ADV_PRESET_HARDWARE) if on_card else tr(s.ADV_PRESET_HELP))

        width = source.width if source else None
        height = source.height if source else None
        keep_size = f"{width}×{height}" if width and height else ""
        sizes = [Choice(KEEP, _keep(keep_size))]
        for option in smaller_heights(media, view.recipe.streams.video):
            if width and height:
                scaled = round(width * option / height / 2) * 2
                sizes.append(Choice(str(option), f"{scaled}×{option}"))
            else:
                sizes.append(Choice(str(option), f"{option}p"))
        chosen_height = video.height if video is not None and not copy else None
        self.resolution.set_choices(sizes, str(chosen_height or ""))

        aspect = (source.display_aspect_ratio if source else None) or ""
        self.aspect.set_choices(
            [Choice(KEEP, _keep(aspect))] + [Choice(a, a) for a in ASPECT_RATIOS if a != aspect],
            choices.aspect or KEEP,
        )
        rate = source.frame_rate if source else None
        rates = [Choice(KEEP, _keep(format_frame_rate(rate) if rate else ""))]
        rates += [
            Choice(_rate_key(r), format_frame_rate(r))
            for r in FRAME_RATES
            if rate is None or abs(r - rate) > 0.01
        ]
        self.frame_rate.set_choices(
            rates, _rate_key(choices.frame_rate) if choices.frame_rate else KEEP
        )
        pixels = PIXEL_FORMATS.get(codec, ())
        grid.set_shown(self.pixel_field, bool(pixels))
        self.pixel.set_choices(
            [Choice(p, p, tr(PIXEL_DESCRIPTIONS.get(p, ""))) for p in pixels],
            (video.pixel_format if video else None) or "yuv420p",
        )
        self.pixel_field.set_recommended("yuv420p" if pixels else "")
        for widget in (
            self.method,
            self.crf,
            self.video_bitrate,
            self.preset,
            self.resolution,
            self.aspect,
            self.frame_rate,
            self.pixel,
        ):
            widget.setEnabled(not copy)
        self.preset.setEnabled(not copy and not on_card)

    def _sync_audio(self, view: AdvancedView) -> None:
        fmt, media = view.fmt, view.media
        grid = self.audio_grid
        audio = view.recipe.settings.audio
        kept = [st for st in media.streams if st.index in view.recipe.streams.audio]
        has_audio = audio is not None and bool(kept)
        grid.set_shown(self.no_audio, not has_audio)
        for field in (
            self.audio_codec_field,
            self.audio_bitrate_field,
            self.sample_rate_field,
            self.channels_field,
        ):
            grid.set_shown(field, has_audio)
        if audio is None or not has_audio:
            return
        base = fmt.settings(view.quality).audio
        codecs = [Choice(c, codec_display_name(c)) for c in audio_codecs(fmt, view.encoders)]
        if can_copy_audio(fmt, kept):
            codecs.append(Choice(COPY, tr(s.ADV_AUDIO_COPY), tr(s.ADV_AUDIO_COPY_HELP)))
        copy = audio.is_copy
        self.audio_codec.set_choices(codecs, COPY if copy else audio.codec)
        self.audio_codec.setEnabled(len(codecs) > 1)
        self.audio_codec_field.set_help(
            tr(s.ADV_CODEC_HELP_VIDEO).format(container=vm.container_name(fmt))
            if fmt.is_video
            else tr(s.ADV_CODEC_HELP_AUDIO)
        )
        if base is not None:
            self.audio_codec_field.set_recommended(codec_display_name(base.codec))

        lossless = audio.codec in LOSSLESS_AUDIO
        grid.set_shown(self.audio_bitrate_field, not lossless)
        if base is not None and audio.codec == base.codec and base.quality is not None:
            automatic = tr(s.ADV_VARIABLE_QUALITY).format(value=f"{base.quality:g}")
        elif base is not None and audio.codec == base.codec and base.bitrate:
            automatic = format_bitrate(base.bitrate)
        else:
            automatic = format_bitrate((base.bitrate if base else None) or DEFAULT_AUDIO_BITRATE)
        bitrates = [Choice(KEEP, tr(s.ADV_SET_BY_QUALITY).format(value=automatic))]
        bitrates += [Choice(str(rate), format_bitrate(rate)) for rate in AUDIO_BITRATES]
        chosen = view.choices.audio_bitrate
        self.audio_bitrate.set_choices(bitrates, str(chosen) if chosen else KEEP)
        if base is not None and base.bitrate:
            balanced = fmt.settings(Quality.BALANCED).audio
            rec = balanced.bitrate if balanced is not None and balanced.bitrate else base.bitrate
            self.audio_bitrate_field.set_recommended(format_bitrate(rec))

        rates = sorted({f"{t.sample_rate / 1000:g} kHz" for t in kept if t.sample_rate})
        options = [Choice(KEEP, _keep(" / ".join(rates)))]
        codec = audio.codec if not copy else (base.codec if base else "")
        options += [Choice(str(r), f"{r / 1000:g} kHz") for r in sample_rates(codec)]
        self.sample_rate.set_choices(options, str(audio.sample_rate or KEEP))
        layouts = sorted({vm.layout_name(t) for t in kept}, reverse=True)
        names = {2: tr(s.DETAIL_STEREO), 1: tr(s.DETAIL_MONO)}
        channel_options = [Choice(KEEP, _keep(" / ".join(layouts).lower()))]
        channel_options += [Choice(str(n), names[n]) for n in CHANNEL_COUNTS]
        self.channels.set_choices(channel_options, str(audio.channels or KEEP))
        for widget in (self.audio_bitrate, self.sample_rate, self.channels):
            widget.setEnabled(not copy)

    def _sync_output(self, view: AdvancedView) -> None:
        fmt, choices = view.fmt, view.choices
        grid = self.output_grid
        siblings = [f for f in view.formats if f.encoders == fmt.encoders]
        self.container.set_choices([Choice(f.key, vm.container_name(f)) for f in siblings], fmt.key)
        self.container.setEnabled(len(siblings) > 1)
        self.container_field.set_recommended(vm.container_name(siblings[0]) if siblings else "")
        video = view.recipe.settings.video
        grid.set_shown(self.deinterlace_field, video is not None)
        self.deinterlace.set_choices(
            [
                Choice(Deinterlace.AUTO.value, tr(s.ADV_DEINTERLACE_AUTO)),
                Choice(Deinterlace.OFF.value, tr(s.ADV_DEINTERLACE_OFF)),
                Choice(Deinterlace.ALWAYS.value, tr(s.ADV_DEINTERLACE_ALWAYS)),
            ],
            choices.deinterlace.value,
        )
        self.deinterlace.setEnabled(video is not None and not video.is_copy)
        grid.set_shown(self.fast_start_field, fmt.muxer in FAST_START_MUXERS)
        self.fast_start.setChecked(choices.fast_start)
        self.metadata.setChecked(choices.keep_metadata)
        audio = view.recipe.settings.audio
        copy = audio is not None and audio.is_copy
        self.loudness.setChecked(view.recipe.settings.normalize_loudness)
        self.loudness.setEnabled(audio is not None and not copy)
        help_label = self.loudness_field.help
        if isinstance(help_label, QLabel):
            help_label.setText(tr(s.ADV_LOUDNESS_COPY if copy else s.ADV_LOUDNESS_HELP))

    def _sync_tracks(self, view: AdvancedView) -> None:
        fmt, media = view.fmt, view.media
        key = (media.path, fmt.key, self._compact)
        if key != self._tracks_key:
            self._tracks_key = key
            self._rebuild_tracks(view)
        kept = kept_tracks(fmt, media, view.choices)
        self.tracks_help.setText(
            tr(s.ADV_TRACKS_HELP).format(kept=len(kept), total=len(media.streams))
        )
        for stream in media.streams:
            check = self.track_checks[stream.index]
            check.blockSignals(True)
            check.setChecked(stream.index in kept)
            check.blockSignals(False)
            rule = track_rule(fmt, stream)
            check.setEnabled(rule is not TrackRule.NOT_SUPPORTED and not view.locked)
            output = self.track_outputs[stream.index]
            output.setText(track_output(view, stream, stream.index in kept))
            output.setProperty("tone", None if stream.index in kept else "secondary")
            output.style().unpolish(output)
            output.style().polish(output)

    def _rebuild_tracks(self, view: AdvancedView) -> None:
        if self.tracks_table is not None:
            # Hidden at once: deleteLater only runs when control returns to the event loop.
            self.tracks_table.hide()
            self.tracks_box.removeWidget(self.tracks_table)
            self.tracks_table.deleteLater()
        self.track_checks, self.track_outputs = {}, {}
        table = GridTable(
            [
                Column(tr(s.ADV_TRACKS_KEEP), 52),
                Column(tr(s.ADV_TRACKS_TYPE), 110),
                Column(tr(s.ADV_TRACKS_NAME)),
                Column(tr(s.ADV_TRACKS_OUTPUT), 150 if self._compact else 190),
            ],
            on_surface=True,
        )
        for stream in view.media.streams:
            kind, icon = vm.stream_kind(stream)
            check = CheckBox()
            check.setAccessibleName(f"{tr(s.ADV_TRACKS_KEEP)} {kind}")
            rule = track_rule(view.fmt, stream)
            if rule is TrackRule.NOT_SUPPORTED:
                check.setToolTip(
                    tr(s.ADV_TRACK_NOT_SUPPORTED).format(format=vm.container_name(view.fmt))
                )
            elif rule is TrackRule.ONE_OF:
                check.setToolTip(tr(s.ADV_TRACK_ONE_OF).format(kind=kind.lower()))
            check.toggled.connect(lambda on, index=stream.index: self._on_track(index, on))
            language = vm.language_name(stream.language)
            name = " · ".join(
                part
                for part in (language if language != vm.NO_VALUE else "", stream.title or "")
                if part
            )
            output = label("", wrap=True)
            self.track_checks[stream.index] = check
            self.track_outputs[stream.index] = output
            table.add_row([check, _kind_cell(kind, icon), label(name or vm.NO_VALUE), output])
        self.tracks_table = table
        self.tracks_box.addWidget(table)


def track_output(view: AdvancedView, stream: StreamInfo, kept: bool) -> str:
    """What happens to a track: "Convert to AAC 160 kb/s", "Copy as it is", "Left out"."""
    fmt = view.fmt
    if track_rule(fmt, stream) is TrackRule.NOT_SUPPORTED:
        return tr(s.ADV_TRACK_NOT_SUPPORTED).format(format=vm.container_name(fmt))
    if not kept:
        return tr(s.ADV_TRACK_LEFT_OUT)
    settings = view.final
    if stream.is_attached_picture:
        return tr(s.ADV_TRACK_COPY)
    if stream.type is StreamType.VIDEO and settings.video is not None:
        if settings.video.is_copy:
            return tr(s.ADV_TRACK_COPY)
        return tr(s.ADV_TRACK_CONVERT).format(codec=codec_display_name(_software(settings)))
    if stream.type is StreamType.AUDIO and settings.audio is not None:
        if settings.audio.is_copy:
            return tr(s.ADV_TRACK_COPY)
        rate = f" {format_bitrate(settings.audio.bitrate)}" if settings.audio.bitrate else ""
        return tr(s.ADV_TRACK_CONVERT).format(codec=codec_display_name(settings.audio.codec) + rate)
    plan: StreamMap = view.recipe.streams
    if plan.subtitle_codec == SUBTITLE_COPY or plan.subtitle_codec is None:
        return tr(s.ADV_TRACK_COPY)
    target = SUBTITLE_TARGET_NAMES.get(plan.subtitle_codec, s.SUBTITLE_MP4_TEXT)
    return tr(s.ADV_TRACK_CONVERT).format(codec=tr(target))


HARDWARE_CODEC_NAMES = {
    "h264_nvenc": "libx264",
    "h264_amf": "libx264",
    "h264_qsv": "libx264",
    "hevc_nvenc": "libx265",
    "hevc_amf": "libx265",
    "hevc_qsv": "libx265",
}


HARDWARE_TECHNOLOGIES = {"nvenc": "NVENC", "amf": "AMF", "qsv": "Quick Sync"}


def encoder_label(codec: str) -> str:
    """ "libx264" → "x264", "h264_nvenc" → "NVENC"."""
    family = codec.rsplit("_", 1)[-1]
    if codec in HARDWARE_CODEC_NAMES and family in HARDWARE_TECHNOLOGIES:
        return HARDWARE_TECHNOLOGIES[family]
    return codec.removeprefix("lib")


def _software(settings: ConversionSettings) -> str:
    """The codec name to show: graphics card encoders read as their format."""
    codec = settings.video.codec if settings.video is not None else ""
    return HARDWARE_CODEC_NAMES.get(codec, codec)


def output_summary(
    media: MediaInfo, fmt: OutputFormat, recipe: Recipe, final: ConversionSettings, estimate: str
) -> str:
    """One line with every technical choice, as in the Advanced footer."""
    plan = recipe.streams
    parts = [vm.container_name(fmt)]
    video = final.video
    source = next((st for st in media.streams if st.index == plan.video), None)
    if video is not None and plan.video is not None:
        if video.is_copy:
            codec = (source.codec_name or "") if source else ""
            parts.append(
                tr(s.CONTENT_COPIED).format(codec=vm.DECODER_NAMES.get(codec, codec.upper()))
            )
        else:
            encoder = f"{codec_display_name(_software(final))} {encoder_label(video.codec)}"
            level = f"CRF {video.crf}" if video.crf is not None else ""
            if video.crf is None and video.bitrate:
                level = format_bitrate(video.bitrate)
            parts.append(" ".join(p for p in (encoder, level, video.preset or "") if p))
            if source is not None and source.width and source.height:
                height = video.height or source.height
                width = round(source.width * height / source.height / 2) * 2
                parts.append(f"{width}×{height}")
            rate = video.frame_rate or (source.frame_rate if source else None)
            if rate:
                parts.append(format_frame_rate(rate))
            if video.pixel_format:
                parts.append(video.pixel_format)
    audio = final.audio
    if audio is not None and plan.audio:
        if audio.is_copy:
            parts.append(f"{len(plan.audio)} × {tr(s.ADV_TRACK_COPY).lower()}")
        else:
            audio_rate = f" {format_bitrate(audio.bitrate)}" if audio.bitrate else ""
            parts.append(f"{len(plan.audio)} × {codec_display_name(audio.codec)}{audio_rate}")
    if plan.subtitles:
        parts.append(tr(s.CHIP_SUBTITLES, len(plan.subtitles)))
    parts.append(estimate)
    return " · ".join(parts)
