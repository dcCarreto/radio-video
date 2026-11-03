"""Turns media information and settings into the text the screens show.

Everything here is plain data in, strings out, so the copy can be tested without widgets.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QLocale

from radio_video.models.estimate import codec_display_name, estimate_output_size
from radio_video.models.media import MediaInfo, StreamInfo, StreamType
from radio_video.models.presets import OutputFormat, Quality
from radio_video.models.tracks import SUBTITLE_COPY, StreamMap, is_text_subtitle
from radio_video.ui import strings as s
from radio_video.ui.icons import IconName
from radio_video.ui.state import Progress
from radio_video.ui.strings import tr
from radio_video.ui.widgets.format_combo import FormatGroup, FormatOption
from radio_video.ui.widgets.segmented import SegmentOption
from radio_video.ui.widgets.streams_table import StreamRow
from radio_video.utils.formatting import (
    format_bitrate,
    format_duration,
    format_frame_rate,
    format_size,
)
from radio_video.utils.paths import unique_output_path

RECOMMENDED_FORMAT = "mp4-h264"
STEREO_CHANNELS = 2
WHOLE_UNITS_FROM = 10
NO_VALUE = "—"

QUALITY_TEXT = {
    Quality.HIGH: (s.QUALITY_HIGH, s.QUALITY_HIGH_SUB, s.QUALITY_HIGH_HELP),
    Quality.BALANCED: (s.QUALITY_BALANCED, s.QUALITY_BALANCED_SUB, s.QUALITY_BALANCED_HELP),
    Quality.SMALL: (s.QUALITY_SMALL, s.QUALITY_SMALL_SUB, s.QUALITY_SMALL_HELP),
}
QUALITY_VALUES = {Quality.HIGH: "high", Quality.BALANCED: "balanced", Quality.SMALL: "small"}

# Names of source codecs as people know them, for summaries and screen readers.
DECODER_NAMES = {
    "h264": "H.264",
    "hevc": "H.265",
    "vp9": "VP9",
    "av1": "AV1",
    "aac": "AAC",
    "mp3": "MP3",
    "opus": "Opus",
    "vorbis": "Vorbis",
    "flac": "FLAC",
    "subrip": "SRT",
    "mov_text": "MP4 text",
    "webvtt": "WebVTT",
    "mjpeg": "JPEG",
    "png": "PNG",
}
SUBTITLE_TARGETS = {"mov_text": s.SUBTITLE_MP4_TEXT, "webvtt": s.SUBTITLE_WEBVTT}
LAYOUT_NAMES = {1: s.DETAIL_MONO, 2: s.DETAIL_STEREO, 6: "5.1", 8: "7.1"}


# Quality and format pickers


def quality_value(quality: Quality) -> str:
    return QUALITY_VALUES[quality]


def quality_from_value(value: str) -> Quality:
    return next(q for q, v in QUALITY_VALUES.items() if v == value)


def quality_label(quality: Quality) -> str:
    return tr(QUALITY_TEXT[quality][0])


def quality_help(quality: Quality) -> str:
    return tr(QUALITY_TEXT[quality][2])


def quality_options() -> list[SegmentOption]:
    return [
        SegmentOption(quality_value(q), tr(label), tr(sub), tr(help_text))
        for q, (label, sub, help_text) in QUALITY_TEXT.items()
    ]


def format_description(fmt: OutputFormat) -> str:
    return tr(s.FORMAT_DESCRIPTIONS[fmt.key])


def format_help(fmt: OutputFormat, source_has_video: bool) -> str:
    description = format_description(fmt)
    if source_has_video and not fmt.is_video:
        return tr(s.EXTRACTS_AUDIO).format(description=description)
    return description


def format_groups(formats: Sequence[OutputFormat], source_has_video: bool) -> list[FormatGroup]:
    def options(video: bool) -> tuple[FormatOption, ...]:
        return tuple(
            FormatOption(fmt.key, fmt.label, format_description(fmt), fmt.key == RECOMMENDED_FORMAT)
            for fmt in formats
            if fmt.is_video is video
        )

    groups = []
    if video := options(True):
        groups.append(FormatGroup(tr(s.FORMAT_GROUP_VIDEO), video))
    if audio := options(False):
        title = s.FORMAT_GROUP_AUDIO_FROM_VIDEO if source_has_video else s.FORMAT_GROUP_AUDIO
        groups.append(FormatGroup(tr(title), audio))
    return groups


def format_and_quality(fmt: OutputFormat, quality: Quality) -> str:
    """ "MP4 (H.264 + AAC), Balanced"; lossless formats have no quality."""
    if fmt.lossless:
        return fmt.label
    return tr(s.CONVERTING_WHAT).format(format=fmt.label, quality=quality_label(quality))


def container_name(fmt: OutputFormat) -> str:
    """ "WebM (VP9 + Opus)" → "WebM"."""
    return fmt.label.split(" (")[0]


# Streams


def language_name(code: str | None) -> str:
    if not code or code.lower() in {"und", "zxx", "mis", "mul"}:
        return NO_VALUE
    language = QLocale.codeToLanguage(code, QLocale.LanguageCodeType.AnyLanguageCode)
    if language is QLocale.Language.AnyLanguage:
        return code
    return QLocale.languageToString(language)


def layout_name(stream: StreamInfo) -> str:
    channels = stream.channels or 0
    if channels in LAYOUT_NAMES:
        name = LAYOUT_NAMES[channels]
        return tr(name) if name in (s.DETAIL_MONO, s.DETAIL_STEREO) else str(name)
    layout = (stream.channel_layout or "").split("(")[0]
    return layout or f"{channels} ch"


STREAM_KINDS: dict[StreamType, tuple[object, IconName]] = {
    StreamType.VIDEO: (s.TYPE_VIDEO, "Film"),
    StreamType.AUDIO: (s.TYPE_AUDIO, "Music"),
    StreamType.SUBTITLE: (s.TYPE_SUBTITLE, "Captions"),
    StreamType.ATTACHMENT: (s.TYPE_ATTACHMENT, "FileText"),
}


def stream_kind(stream: StreamInfo) -> tuple[str, IconName]:
    if stream.is_attached_picture:
        return tr(s.TYPE_COVER), "Image"
    text, icon = STREAM_KINDS.get(stream.type, (s.TYPE_DATA, "FileText"))
    return tr(text), icon


def codec_label(stream: StreamInfo) -> str:
    codec = stream.codec_name or "unknown"
    return f"{codec} ({stream.profile})" if stream.profile else codec


def stream_details(stream: StreamInfo) -> str:
    parts: list[str] = []
    if stream.is_attached_picture:
        if stream.width and stream.height:
            parts.append(f"{stream.width}×{stream.height}")
        name = DECODER_NAMES.get(stream.codec_name or "", (stream.codec_name or "").upper())
        parts.append(tr(s.DETAIL_IMAGE).format(format=name))
    elif stream.type is StreamType.VIDEO:
        if stream.width and stream.height:
            parts.append(f"{stream.width}×{stream.height}")
        if stream.frame_rate:
            parts.append(format_frame_rate(stream.frame_rate))
        if stream.bit_rate:
            parts.append(format_bitrate(stream.bit_rate))
    elif stream.type is StreamType.AUDIO:
        if stream.sample_rate:
            parts.append(f"{stream.sample_rate / 1000:g} kHz")
        if stream.channels or stream.channel_layout:
            parts.append(layout_name(stream))
        if stream.bit_rate:
            parts.append(format_bitrate(stream.bit_rate))
    elif stream.type is StreamType.SUBTITLE:
        parts.append(tr(s.DETAIL_TEXT if is_text_subtitle(stream) else s.DETAIL_IMAGE_SUBTITLE))
    return " · ".join(parts)


def stream_rows(media: MediaInfo) -> list[StreamRow]:
    rows = []
    per_kind: dict[str, int] = {}
    for number, stream in enumerate(media.streams, start=1):
        kind, icon = stream_kind(stream)
        per_kind[kind] = per_kind.get(kind, 0) + 1
        language = language_name(stream.language)
        details = stream_details(stream)
        codec = stream.codec_name or ""
        spoken = [
            f"{kind} {per_kind[kind]}",
            DECODER_NAMES.get(codec, codec),
            details.replace(" · ", " "),
            language if language != NO_VALUE else "",
            stream.title or "",
        ]
        rows.append(
            StreamRow(
                number=number,
                kind=kind,
                icon=icon,
                codec=codec_label(stream),
                details=details,
                language=language,
                title=stream.title or "",
                is_default=stream.is_default and not stream.is_attached_picture,
                codec_tooltip=tr(s.CODEC_TOOLTIPS[codec]) if codec in s.CODEC_TOOLTIPS else "",
                tooltip=f"{kind} {number}: {stream.title}" if stream.title else "",
                accessible=", ".join(part for part in spoken if part),
            )
        )
    return rows


def _join(items: list[str]) -> str:
    if len(items) == 1:
        return tr(s.SUMMARY_SINGLE).format(only=items[0])
    head = tr(s.LIST_SEPARATOR).join(items[:-1])
    return tr(s.SUMMARY_LIST).format(head=head, last=items[-1])


def _languages(streams: Sequence[StreamInfo]) -> list[str]:
    names: list[str] = []
    for stream in streams:
        name = language_name(stream.language)
        if name != NO_VALUE and name not in names:
            names.append(name)
    return names


def source_summary(media: MediaInfo) -> str:
    """ "1 video track, 3 audio tracks (Portuguese, English), 7 subtitle tracks and 1 cover
    image." For audio-only files: "Audio-only file: 1 audio track (stereo, 44.1 kHz).\""""
    audio = media.audio_streams
    cover = [st for st in media.streams if st.is_attached_picture]
    if not media.has_video and len(audio) == 1:
        track = audio[0]
        details = [layout_name(track).lower()]
        if track.sample_rate:
            details.append(f"{track.sample_rate / 1000:g} kHz")
        return tr(s.SUMMARY_AUDIO_ONLY).format(
            tracks=tr(s.SUMMARY_AUDIO, 1), details=", ".join(details)
        )
    items = []
    if media.video_streams:
        items.append(tr(s.SUMMARY_VIDEO, len(media.video_streams)))
    if audio:
        tracks = tr(s.SUMMARY_AUDIO, len(audio))
        languages = _languages(audio)
        if languages and len(audio) > 1:
            tracks = tr(s.SUMMARY_AUDIO_LANGUAGES).format(
                tracks=tracks, languages=tr(s.LIST_SEPARATOR).join(languages)
            )
        items.append(tracks)
    if media.subtitle_streams:
        items.append(tr(s.SUMMARY_SUBTITLES, len(media.subtitle_streams)))
    if cover:
        items.append(tr(s.SUMMARY_COVER, len(cover)))
    return _join(items) if items else ""


def track_chips(media: MediaInfo) -> list[tuple[IconName, str]]:
    chips: list[tuple[IconName, str]] = []
    cover = sum(1 for st in media.streams if st.is_attached_picture)
    counts: tuple[tuple[IconName, object, int], ...] = (
        ("Film", s.CHIP_VIDEO, len(media.video_streams)),
        ("Music", s.CHIP_AUDIO, len(media.audio_streams)),
        ("Captions", s.CHIP_SUBTITLES, len(media.subtitle_streams)),
        ("Image", s.CHIP_COVER, cover),
    )
    for icon, text, count in counts:
        if count:
            chips.append((icon, tr(text, count)))
    return chips


def inside_header(media: MediaInfo) -> str:
    return tr(s.INSIDE_HEADER).format(count=tr(s.TRACK_COUNT, len(media.streams)))


def facts(media: MediaInfo) -> tuple[list[str], str]:
    title = next((v for k, v in media.tags.items() if k.lower() == "title" and v), NO_VALUE)
    return (
        [
            media.format_long_name or media.format_name or NO_VALUE,
            format_duration(media.duration),
            format_size(media.size),
            format_bitrate(media.bit_rate),
        ],
        title,
    )


# What the output will contain


def output_contents(fmt: OutputFormat, media: MediaInfo, plan: StreamMap) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    left_out: list[str] = []
    settings = fmt.settings(Quality.BALANCED)
    streams = {stream.index: stream for stream in media.streams}
    has_cover = any(st.is_attached_picture for st in media.streams)

    if fmt.is_video:
        if plan.video is not None and settings.video is not None:
            video = streams[plan.video]
            parts = [codec_display_name(settings.video.codec)]
            if video.width and video.height:
                parts.append(f"{video.width}×{video.height}")
            if video.frame_rate:
                parts.append(format_frame_rate(video.frame_rate))
            rows.append((tr(s.ROW_VIDEO), ", ".join(parts)))
        if plan.audio and settings.audio is not None:
            codec = codec_display_name(settings.audio.codec)
            rows.append(
                (tr(s.ROW_AUDIO), tr(s.CONTENT_AUDIO_TRACKS, len(plan.audio)).format(codec=codec))
            )
        if plan.subtitles:
            count = len(plan.subtitles)
            if plan.subtitle_codec == SUBTITLE_COPY:
                text = tr(s.CONTENT_SUBTITLES_COPIED, count)
            else:
                target = tr(SUBTITLE_TARGETS.get(plan.subtitle_codec or "", s.SUBTITLE_MP4_TEXT))
                text = tr(s.CONTENT_SUBTITLES_CONVERTED, count).format(codec=target)
            rows.append((tr(s.ROW_SUBTITLES), text))
        if len(plan.subtitles) < len(media.subtitle_streams):
            left_out.append(tr(s.LEFT_OUT_IMAGE_SUBTITLES))
    else:
        if plan.audio:
            index = plan.audio[0]
            track = streams[index]
            number = [a.index for a in media.audio_streams].index(index) + 1
            language = language_name(track.language)
            name = (
                tr(s.CONTENT_TRACK_LANGUAGE).format(number=number, language=language)
                if language != NO_VALUE
                else tr(s.CONTENT_TRACK).format(number=number)
            )
            layout = layout_name(track)
            if plan.downmix_to_stereo:
                text = tr(s.CONTENT_DOWNMIX).format(track=name, layout=layout)
            elif fmt.lossless and (track.channels or 0) > STEREO_CHANNELS:
                text = tr(s.CONTENT_LAYOUT_KEPT).format(track=name, layout=layout)
            else:
                text = tr(s.CONTENT_LAYOUT).format(track=name, layout=layout.lower())
            rows.append((tr(s.ROW_AUDIO), text))
        if media.has_video:
            left_out.append(tr(s.LEFT_OUT_VIDEO))
        others = len(media.audio_streams) - len(plan.audio)
        if others > 0:
            left_out.append(tr(s.LEFT_OUT_AUDIO, others))
        if media.subtitle_streams:
            left_out.append(tr(s.LEFT_OUT_SUBTITLES))

    cover_row: tuple[str, str] | None = None
    if has_cover:
        if plan.cover_art is not None:
            cover_row = (tr(s.ROW_COVER), tr(s.CONTENT_KEPT))
        elif fmt.is_video:
            reason = tr(s.CONTENT_COVER_LEFT_OUT).format(format=container_name(fmt))
            cover_row = (tr(s.ROW_COVER), reason)
        else:
            left_out.append(tr(s.LEFT_OUT_COVER))
    left_out_row = (tr(s.ROW_LEFT_OUT), _sentence(left_out)) if left_out else None
    # Video formats list what is inside first; audio formats say what was left out right
    # after the one track they keep.
    tail = [cover_row, left_out_row] if fmt.is_video else [left_out_row, cover_row]
    return rows + [row for row in tail if row is not None]


def output_track_text(fmt: OutputFormat, media: MediaInfo, plan: StreamMap) -> str:
    """The audio track as it sounds in the output: "Track 1 (Portuguese), stereo"."""
    if not plan.audio:
        return ""
    track = next(st for st in media.streams if st.index == plan.audio[0])
    number = [a.index for a in media.audio_streams].index(track.index) + 1
    language = language_name(track.language)
    name = (
        tr(s.CONTENT_TRACK_LANGUAGE).format(number=number, language=language)
        if language != NO_VALUE
        else tr(s.CONTENT_TRACK).format(number=number)
    )
    layout = tr(s.DETAIL_STEREO) if plan.downmix_to_stereo else layout_name(track)
    return tr(s.CONTENT_LAYOUT).format(track=name, layout=layout.lower())


def _sentence(items: list[str]) -> str:
    text = tr(s.LIST_SEPARATOR).join(items)
    return text[:1].upper() + text[1:]


@dataclass(frozen=True)
class Estimate:
    value: str
    how: str
    known: bool


def format_estimate_size(size: int) -> str:
    """ "≈ 22 MB" above 10 units, "≈ 3.2 MB" below."""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            break
        value /= 1024
    number = f"{round(value)}" if value >= WHOLE_UNITS_FROM or unit == "B" else f"{value:.1f}"
    return f"{number} {unit}"


def estimate(
    fmt: OutputFormat, quality: Quality, media: MediaInfo, measured: int | None
) -> Estimate:
    """Honest size estimate: calculated when the bitrate fixes it, measured after a preview
    with the same settings, otherwise unknown."""
    calculated = estimate_output_size(fmt.settings(quality), media)
    if calculated is not None:
        value = tr(s.ESTIMATE_VALUE).format(size=format_estimate_size(calculated))
        return Estimate(value, tr(s.ESTIMATE_CALCULATED), True)
    if measured is not None:
        value = tr(s.ESTIMATE_VALUE).format(size=format_estimate_size(measured))
        return Estimate(value, tr(s.ESTIMATE_MEASURED), True)
    return Estimate(tr(s.ESTIMATE_UNKNOWN), tr(s.ESTIMATE_UNKNOWN_HELP), False)


@dataclass(frozen=True)
class OutputName:
    path: Path
    bumped: int | None


def output_name(folder: Path, media: MediaInfo, fmt: OutputFormat) -> OutputName:
    """The output path, never an existing file; ``bumped`` is the " (n)" number added."""
    stem = media.path.stem
    path = unique_output_path(folder, stem, fmt.extension)
    if path.stem == stem:
        return OutputName(path, None)
    number = path.stem[len(stem) + 2 : -1]
    return OutputName(path, int(number) if number.isdigit() else None)


def name_bumped_text(name: OutputName) -> str:
    return tr(s.NAME_BUMPED).format(number=name.bumped) if name.bumped else ""


# Progress


def percent(fraction: float) -> int:
    return min(100, max(0, round(fraction * 100)))


def progress_detail(progress: Progress) -> str:
    """ "42% · 3.1× · 0:25 remaining"."""
    parts = [tr(s.PROGRESS_PERCENT).format(percent=percent(progress.fraction))]
    if progress.speed:
        parts.append(tr(s.PROGRESS_SPEED).format(speed=f"{progress.speed:.1f}"))
    if progress.remaining is not None:
        parts.append(tr(s.PROGRESS_REMAINING).format(time=format_duration(progress.remaining)))
    return tr(s.PROGRESS_SEPARATOR).join(parts)


def speed_tooltip(speed: float | None) -> str:
    if not speed:
        return ""
    return tr(s.SPEED_TOOLTIP).format(speed=f"{speed:.1f}", seconds=round(60 / speed))
