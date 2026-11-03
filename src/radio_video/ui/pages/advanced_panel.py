"""Advanced Mode, planned: shows every technical setting with a one-line explanation.

The settings are not editable yet; values reflect the current file and the Simple choices,
which carry over. A banner says the screen isn't built yet.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
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

from radio_video.models.estimate import codec_display_name
from radio_video.models.media import MediaInfo, StreamType
from radio_video.models.presets import OutputFormat, Quality
from radio_video.models.tracks import SUBTITLE_COPY
from radio_video.ui import strings as s
from radio_video.ui import viewmodel as vm
from radio_video.ui.icons import IconName
from radio_video.ui.strings import tr
from radio_video.ui.theme.fonts import TextStyle
from radio_video.ui.widgets.checks import CheckBox, LabeledCheck
from radio_video.ui.widgets.frames import ComboFace, Note, PlannedBanner
from radio_video.ui.widgets.grid_table import Column, GridTable
from radio_video.ui.widgets.labels import label
from radio_video.ui.widgets.player import Slider
from radio_video.ui.widgets.progress import StatusIcon
from radio_video.ui.widgets.segmented import SegmentedControl, SegmentOption
from radio_video.ui.widgets.tab_strip import TabSpec, TabStrip
from radio_video.utils.formatting import format_frame_rate

TAB_HEIGHT = 40
CRF_MAX = 51
SPIN_WIDTH = 72


def _recommended(value: str) -> QLabel:
    text = tr(s.RECOMMENDED_VALUE).format(value=f"<b>{value}</b>")
    result = label(text, TextStyle.CAPTION, "secondary", wrap=True)
    result.setTextFormat(Qt.TextFormat.RichText)
    return result


def _field(title: str, control: QWidget, help_text: str = "", rec: str = "") -> QWidget:
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    layout.addWidget(label(title, TextStyle.BODY_STRONG))
    layout.addWidget(control)
    if help_text:
        layout.addWidget(label(help_text, TextStyle.CAPTION, "secondary", wrap=True))
    if rec:
        layout.addWidget(_recommended(rec))
    return box


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
    return tr(s.ADV_KEEP_ORIGINAL_VALUE).format(value=value)


class _FieldGrid(QWidget):
    """Two columns of fields, one column in compact windows; wide fields span both."""

    def __init__(self) -> None:
        super().__init__()
        self._fields: list[tuple[QWidget, bool]] = []
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(24)
        self._grid.setVerticalSpacing(20)
        self._compact = False

    def add(self, widget: QWidget, *, wide: bool = False) -> None:
        self._fields.append((widget, wide))
        self._relayout()

    def set_compact(self, compact: bool) -> None:
        self._compact = compact
        self._relayout()

    def _relayout(self) -> None:
        for widget, _wide in self._fields:
            self._grid.removeWidget(widget)
        columns = 1 if self._compact else 2
        row = column = 0
        for widget, wide in self._fields:
            if wide or columns == 1:
                if column:
                    row, column = row + 1, 0
                self._grid.addWidget(widget, row, 0, 1, columns)
                row += 1
                continue
            self._grid.addWidget(widget, row, column)
            column += 1
            if column == columns:
                row, column = row + 1, 0
        for index in range(2):
            self._grid.setColumnStretch(index, 1 if index < columns else 0)


class AdvancedPanel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
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
        self._grids: list[_FieldGrid] = []
        self._contents: list[QVBoxLayout] = []
        for _ in range(4):
            self.pages.addWidget(self._page())
        self.tabs.current_changed.connect(
            lambda key: self.pages.setCurrentIndex(
                ["video", "audio", "tracks", "output"].index(key)
            )
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.tabs)
        layout.addWidget(self.pages, 1)
        self._key: tuple[object, ...] | None = None
        self._shown: tuple[MediaInfo, OutputFormat, Quality] | None = None
        self._compact = False

    def _page(self) -> QScrollArea:
        content = QWidget()
        content.setProperty("transparent", True)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(PlannedBanner(tr(s.PLANNED_ADVANCED), tr(s.BADGE_PLANNED)))
        body = QVBoxLayout()
        body.setContentsMargins(24, 20, 24, 20)
        body.setSpacing(12)
        layout.addLayout(body)
        layout.addStretch(1)
        self._contents.append(body)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        return scroll

    def set_compact(self, compact: bool) -> None:
        changed = compact != self._compact
        self._compact = compact
        if changed and self._shown is not None:
            self._key = None
            self.show_settings(*self._shown)
            return
        side = 20 if compact else 24
        for body in self._contents:
            body.setContentsMargins(side, 20, side, 20)
        for grid in self._grids:
            grid.set_compact(compact)

    def show_settings(self, media: MediaInfo, fmt: OutputFormat, quality: Quality) -> None:
        key = (media.path, fmt.key, quality)
        if key == self._key:
            return
        self._key = key
        self._shown = (media, fmt, quality)
        for body in self._contents:
            while body.count():
                item = body.takeAt(0)
                widget = item.widget() if item is not None else None
                if widget is not None:
                    widget.deleteLater()
        self._grids = []
        self._video(media, fmt, quality)
        self._audio(media, fmt, quality)
        self._tracks(media, fmt, quality)
        self._output(fmt)
        self.set_compact(self._compact)

    def _grid(self, page: int) -> _FieldGrid:
        grid = _FieldGrid()
        self._grids.append(grid)
        self._contents[page].addWidget(grid)
        return grid

    def _video(self, media: MediaInfo, fmt: OutputFormat, quality: Quality) -> None:
        grid = self._grid(0)
        settings = fmt.settings(quality)
        video = settings.video
        source = media.video_streams[0] if media.video_streams else None
        grid.add(_field(tr(s.FIELD_FORMAT), ComboFace(fmt.label)), wide=True)
        grid.add(
            LabeledCheck(CheckBox(tr(s.ADV_STREAM_COPY)), tr(s.ADV_STREAM_COPY_HELP)), wide=True
        )
        if video is None:
            return
        codec = codec_display_name(video.codec)
        encoder = f"{codec} · Software ({video.codec.removeprefix('lib')})"
        grid.add(
            _field(
                tr(s.ADV_ENCODER),
                ComboFace(encoder),
                tr(s.ADV_ENCODER_HELP),
                f"Software ({video.codec.removeprefix('lib')})",
            )
        )
        method = SegmentedControl(
            [
                SegmentOption("crf", tr(s.ADV_CONSTANT_QUALITY)),
                SegmentOption("bitrate", tr(s.ADV_TARGET_BITRATE)),
            ]
        )
        method.set_value("crf")
        grid.add(
            _field(
                tr(s.ADV_QUALITY_METHOD),
                method,
                tr(s.ADV_QUALITY_METHOD_HELP),
                tr(s.ADV_CONSTANT_QUALITY),
            )
        )
        crf = video.crf or 0
        crf_row = QWidget()
        row = QGridLayout(crf_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.setHorizontalSpacing(12)
        slider = Slider()
        slider.setRange(0, CRF_MAX)
        slider.setValue(crf)
        slider.setEnabled(True)
        spin = ComboFace(str(crf))
        spin.setFixedWidth(SPIN_WIDTH)
        row.addWidget(slider, 0, 0)
        row.addWidget(spin, 0, 1)
        balanced = fmt.settings(Quality.BALANCED).video
        rec_crf = f"{balanced.crf} ({vm.quality_label(Quality.BALANCED)})" if balanced else ""
        grid.add(_field(tr(s.ADV_CRF), crf_row, tr(s.ADV_CRF_HELP), rec_crf))
        if video.preset:
            grid.add(
                _field(tr(s.ADV_PRESET), ComboFace(video.preset), tr(s.ADV_PRESET_HELP), "medium")
            )
        keep = tr(s.ADV_KEEP_ORIGINAL)
        if source is not None:
            size = f"{source.width}×{source.height}" if source.width else keep
            grid.add(
                _field(
                    tr(s.ADV_RESOLUTION), ComboFace(_keep(size)), tr(s.ADV_RESOLUTION_HELP), keep
                )
            )
            aspect = source.display_aspect_ratio or "16:9"
            grid.add(
                _field(tr(s.ADV_ASPECT), ComboFace(_keep(aspect)), tr(s.ADV_ASPECT_HELP), keep)
            )
            rate = format_frame_rate(source.frame_rate)
            grid.add(
                _field(
                    tr(s.ADV_FRAME_RATE), ComboFace(_keep(rate)), tr(s.ADV_FRAME_RATE_HELP), keep
                )
            )
        if video.pixel_format:
            grid.add(
                _field(
                    tr(s.ADV_PIXEL_FORMAT),
                    ComboFace(video.pixel_format),
                    tr(s.ADV_PIXEL_FORMAT_HELP),
                    video.pixel_format,
                )
            )

    def _audio(self, media: MediaInfo, fmt: OutputFormat, quality: Quality) -> None:
        grid = self._grid(1)
        audio = fmt.settings(quality).audio
        if audio is None:
            return
        codec = codec_display_name(audio.codec)
        grid.add(_field(tr(s.ADV_CODEC), ComboFace(codec), tr(s.ADV_CODEC_HELP), codec))
        if audio.bitrate:
            rate = f"{audio.bitrate // 1000} kb/s"
            balanced = fmt.settings(Quality.BALANCED).audio
            rec = f"{balanced.bitrate // 1000} kb/s" if balanced and balanced.bitrate else rate
            grid.add(_field(tr(s.ADV_BITRATE), ComboFace(rate), tr(s.ADV_BITRATE_HELP), rec))
        keep = tr(s.ADV_KEEP_ORIGINAL)
        tracks = media.audio_streams
        rates = sorted({f"{t.sample_rate / 1000:g} kHz" for t in tracks if t.sample_rate})
        layouts = sorted({vm.layout_name(t) for t in tracks}, reverse=True)
        grid.add(
            _field(
                tr(s.ADV_SAMPLE_RATE),
                ComboFace(_keep(" / ".join(rates) or keep)),
                tr(s.ADV_SAMPLE_RATE_HELP),
                keep,
            )
        )
        grid.add(
            _field(
                tr(s.ADV_CHANNELS),
                ComboFace(_keep(" / ".join(layouts).lower() or keep)),
                tr(s.ADV_CHANNELS_HELP),
                keep,
            )
        )
        grid.add(Note(tr(s.ADV_AUDIO_NOTE)), wide=True)

    def _tracks(self, media: MediaInfo, fmt: OutputFormat, quality: Quality) -> None:
        body = self._contents[2]
        plan = fmt.plan(media)
        kept = {plan.video, plan.cover_art, *plan.audio, *plan.subtitles} - {None}
        body.addWidget(
            label(
                tr(s.ADV_TRACKS_HELP).format(kept=len(kept), total=len(media.streams)),
                TextStyle.CAPTION,
                "secondary",
                wrap=True,
            )
        )
        table = GridTable(
            [
                Column(tr(s.ADV_TRACKS_KEEP), 52),
                Column(tr(s.ADV_TRACKS_TYPE), 110),
                Column(tr(s.ADV_TRACKS_NAME)),
                Column(tr(s.ADV_TRACKS_OUTPUT), 150 if self._compact else 190),
            ],
            on_surface=True,
        )
        settings = fmt.settings(quality)
        for stream in media.streams:
            keep = stream.index in kept
            check = CheckBox()
            check.setChecked(keep)
            kind, icon = vm.stream_kind(stream)
            language = vm.language_name(stream.language)
            name = " · ".join(part for part in (language, stream.title or "") if part)
            if not keep:
                output = tr(s.ADV_TRACK_LEFT_OUT)
            elif stream.is_attached_picture:
                output = tr(s.ADV_TRACK_COPY)
            elif stream.type is StreamType.VIDEO and settings.video is not None:
                output = tr(s.ADV_TRACK_CONVERT).format(
                    codec=codec_display_name(settings.video.codec)
                )
            elif stream.type is StreamType.AUDIO and settings.audio is not None:
                rate = f" {settings.audio.bitrate // 1000} kb/s" if settings.audio.bitrate else ""
                output = tr(s.ADV_TRACK_CONVERT).format(
                    codec=codec_display_name(settings.audio.codec) + rate
                )
            elif plan.subtitle_codec == SUBTITLE_COPY:
                output = tr(s.ADV_TRACK_COPY)
            else:
                target = (
                    s.SUBTITLE_MP4_TEXT if plan.subtitle_codec == "mov_text" else s.SUBTITLE_WEBVTT
                )
                output = tr(s.ADV_TRACK_CONVERT).format(codec=tr(target))
            table.add_row(
                [
                    check,
                    _kind_cell(kind, icon),
                    label(name),
                    label(output, tone=None if keep else "secondary"),
                ]
            )
        body.addWidget(table)

    def _output(self, fmt: OutputFormat) -> None:
        grid = self._grid(3)
        container = vm.container_name(fmt)
        grid.add(
            _field(tr(s.ADV_CONTAINER), ComboFace(container), tr(s.ADV_CONTAINER_HELP), container)
        )
        grid.add(
            _field(
                tr(s.ADV_DEINTERLACE),
                ComboFace(tr(s.ADV_DEINTERLACE_AUTO)),
                tr(s.ADV_DEINTERLACE_HELP),
                "Auto",
            )
        )
        checks = QWidget()
        layout = QVBoxLayout(checks)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        for text, help_text, on in (
            (s.ADV_FAST_START, s.ADV_FAST_START_HELP, True),
            (s.ADV_METADATA, s.ADV_METADATA_HELP, True),
            (s.ADV_LOUDNESS, s.ADV_LOUDNESS_HELP, False),
        ):
            box = CheckBox(tr(text))
            box.setChecked(on)
            layout.addWidget(LabeledCheck(box, tr(help_text)))
        grid.add(checks, wide=True)


def output_summary(media: MediaInfo, fmt: OutputFormat, quality: Quality) -> str:
    """One line with every technical choice, as in the Advanced footer."""
    settings = fmt.settings(quality)
    plan = fmt.plan(media)
    parts = [vm.container_name(fmt)]
    video = settings.video
    source = media.video_streams[0] if media.video_streams else None
    if video is not None and plan.video is not None:
        encoder = f"{codec_display_name(video.codec)} {video.codec.removeprefix('lib')}"
        quality_part = f"CRF {video.crf}" if video.crf is not None else ""
        parts.append(" ".join(p for p in (encoder, quality_part, video.preset or "") if p))
        if source is not None and source.width:
            parts.append(f"{source.width}×{source.height}")
            parts.append(format_frame_rate(source.frame_rate))
        if video.pixel_format:
            parts.append(video.pixel_format)
    audio = settings.audio
    if audio is not None and plan.audio:
        rate = f" {audio.bitrate // 1000} kb/s" if audio.bitrate else ""
        parts.append(f"{len(plan.audio)} × {codec_display_name(audio.codec)}{rate}")
    if plan.subtitles:
        parts.append(tr(s.CHIP_SUBTITLES, len(plan.subtitles)))
    estimate = vm.estimate(fmt, quality, media, None)
    parts.append(estimate.value if estimate.known else tr(s.ADV_SIZE_AFTER_PREVIEW))
    return " · ".join(parts)
