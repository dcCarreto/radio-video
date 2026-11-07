"""Advanced Mode: technical choices layered over a format and a quality.

Simple Mode is the same recipe with no choices made, so both modes share one path from the
user's choices to FFmpeg: :func:`resolve` turns a format, a quality and the choices into the
conversion settings and the tracks to map. Choices that don't fit the format or the file are
ignored rather than producing a command FFmpeg would refuse.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass, replace
from enum import Enum

from radio_video.models.conversion import COPY, AudioOptions, ConversionSettings, VideoOptions
from radio_video.models.media import MediaInfo, StreamInfo, StreamType
from radio_video.models.presets import OutputFormat, Quality
from radio_video.models.tracks import (
    STEREO,
    SUBTITLE_COPY,
    StreamMap,
    is_text_subtitle,
)


class RateControl(Enum):
    QUALITY = "quality"
    BITRATE = "bitrate"


class EncoderChoice(Enum):
    # Follows the "Use hardware acceleration" setting.
    AUTO = "auto"
    SOFTWARE = "software"
    HARDWARE = "hardware"


class Deinterlace(Enum):
    AUTO = "auto"
    OFF = "off"
    ALWAYS = "always"


@dataclass(frozen=True)
class AdvancedChoices:
    """What the user changed in Advanced Mode; ``None`` keeps the format's own value."""

    copy_video: bool = False
    encoder: EncoderChoice = EncoderChoice.AUTO
    rate_control: RateControl = RateControl.QUALITY
    crf: int | None = None
    video_bitrate: int | None = None
    preset: str | None = None
    height: int | None = None
    aspect: str | None = None
    frame_rate: float | None = None
    pixel_format: str | None = None
    audio_codec: str | None = None
    audio_bitrate: int | None = None
    sample_rate: int | None = None
    channels: int | None = None
    # Source stream indices to keep; None keeps what the format keeps.
    tracks: frozenset[int] | None = None
    deinterlace: Deinterlace = Deinterlace.AUTO
    fast_start: bool = True
    keep_metadata: bool = True
    normalize_loudness: bool = False

    @property
    def is_default(self) -> bool:
        return self == AdvancedChoices()

    def for_quality(self) -> AdvancedChoices:
        """After picking a quality in Simple Mode: the quality sets the levels again."""
        return replace(
            self,
            rate_control=RateControl.QUALITY,
            crf=None,
            video_bitrate=None,
            audio_bitrate=None,
        )

    def for_format(self) -> AdvancedChoices:
        """After switching formats: codec-specific choices and tracks start over."""
        return replace(
            self.for_quality(),
            copy_video=False,
            preset=None,
            pixel_format=None,
            audio_codec=None,
            sample_rate=None,
            tracks=None,
        )


# Option lists, in the order they are offered.
X26X_PRESETS = (
    "ultrafast",
    "superfast",
    "veryfast",
    "faster",
    "fast",
    "medium",
    "slow",
    "slower",
    "veryslow",
)
PRESETS = {"libx264": X26X_PRESETS, "libx265": X26X_PRESETS}
CRF_RANGE = {"libx264": (0, 51), "libx265": (0, 51), "libvpx-vp9": (0, 63)}
HEIGHTS = (2160, 1440, 1080, 720, 576, 480, 360)
FRAME_RATES = (60.0, 50.0, 30.0, 29.97, 25.0, 24.0, 23.976)
ASPECTS = ("16:9", "4:3", "21:9", "1:1", "9:16")
PIXEL_FORMATS = {
    "libx264": ("yuv420p", "yuv422p", "yuv444p"),
    "libx265": ("yuv420p", "yuv420p10le"),
    "libvpx-vp9": ("yuv420p", "yuv420p10le"),
}
VIDEO_BITRATES = (
    1_000_000,
    2_500_000,
    5_000_000,
    8_000_000,
    12_000_000,
    16_000_000,
    25_000_000,
    40_000_000,
)
DEFAULT_VIDEO_BITRATE = 5_000_000
AUDIO_BITRATES = (64_000, 96_000, 128_000, 160_000, 192_000, 256_000, 320_000)
DEFAULT_AUDIO_BITRATE = 160_000
SAMPLE_RATES = (48_000, 44_100, 32_000, 22_050)
# libopus only encodes these rates; 48 kHz is the one worth offering.
OPUS_SAMPLE_RATES = (48_000,)
CHANNEL_COUNTS = (2, 1)
LOSSLESS_AUDIO = frozenset({"flac", "pcm_s16le"})

# Video codecs each container can hold as they are, for stream copy. Matroska holds anything.
VIDEO_COPY_CODECS = {
    "mp4": frozenset({"h264", "hevc", "av1", "vp9", "mpeg4"}),
    "webm": frozenset({"vp8", "vp9", "av1"}),
}
# Audio codecs each container can hold as they are.
AUDIO_COPY_CODECS = {
    "mp4": frozenset({"aac", "mp3", "ac3", "eac3", "alac", "opus", "flac"}),
    "webm": frozenset({"opus", "vorbis"}),
    "mp3": frozenset({"mp3"}),
    "ipod": frozenset({"aac", "alac"}),
    "opus": frozenset({"opus"}),
    "ogg": frozenset({"vorbis", "opus", "flac"}),
    "flac": frozenset({"flac"}),
    "wav": frozenset({"pcm_s16le"}),
}
# Encoders offered for audio inside video containers, besides copying.
VIDEO_CONTAINER_AUDIO = {
    "mp4": ("aac",),
    "matroska": ("aac", "libopus", "flac"),
    "webm": ("libopus", "libvorbis"),
}


class TrackRule(Enum):
    KEEP = "keep"
    # One of a kind: checking it unchecks the others of its type.
    ONE_OF = "one_of"
    NOT_SUPPORTED = "not_supported"


def track_rule(fmt: OutputFormat, stream: StreamInfo) -> TrackRule:
    """Whether the format can hold this track, and how many of its kind."""
    policy = fmt.policy
    if stream.is_attached_picture:
        return TrackRule.KEEP if policy.cover_art else TrackRule.NOT_SUPPORTED
    if stream.type is StreamType.VIDEO:
        return TrackRule.ONE_OF if fmt.is_video else TrackRule.NOT_SUPPORTED
    if stream.type is StreamType.AUDIO:
        return TrackRule.KEEP if fmt.is_video else TrackRule.ONE_OF
    text_or_copied = policy.subtitle_codec == SUBTITLE_COPY or is_text_subtitle(stream)
    if stream.type is StreamType.SUBTITLE and fmt.is_video and text_or_copied:
        return TrackRule.KEEP
    return TrackRule.NOT_SUPPORTED


def default_tracks(fmt: OutputFormat, media: MediaInfo) -> frozenset[int]:
    plan = fmt.plan(media)
    kept = {plan.video, plan.cover_art, *plan.audio, *plan.subtitles}
    return frozenset(index for index in kept if index is not None)


def kept_tracks(fmt: OutputFormat, media: MediaInfo, choices: AdvancedChoices) -> frozenset[int]:
    """The tracks that will be kept: the choice, limited to what the format can hold."""
    if choices.tracks is None:
        return default_tracks(fmt, media)
    kept: set[int] = set()
    seen_one_of: set[StreamType] = set()
    for stream in media.streams:
        if stream.index not in choices.tracks:
            continue
        rule = track_rule(fmt, stream)
        if rule is TrackRule.NOT_SUPPORTED:
            continue
        if rule is TrackRule.ONE_OF:
            if stream.type in seen_one_of:
                continue
            seen_one_of.add(stream.type)
        kept.add(stream.index)
    return frozenset(kept)


def toggle_track(
    fmt: OutputFormat, media: MediaInfo, choices: AdvancedChoices, index: int, keep: bool
) -> AdvancedChoices:
    """Choices with one track kept or left out; one-of-a-kind tracks replace each other."""
    kept = set(kept_tracks(fmt, media, choices))
    stream = next(s for s in media.streams if s.index == index)
    rule = track_rule(fmt, stream)
    if rule is TrackRule.NOT_SUPPORTED:
        return choices
    if keep:
        if rule is TrackRule.ONE_OF:
            kept -= {
                s.index
                for s in media.streams
                if s.type is stream.type and not s.is_attached_picture
            }
        kept.add(index)
    else:
        kept.discard(index)
    tracks = None if kept == default_tracks(fmt, media) else frozenset(kept)
    return replace(choices, tracks=tracks)


def _stream(media: MediaInfo, index: int | None) -> StreamInfo | None:
    return next((s for s in media.streams if s.index == index), None)


def can_copy_video(fmt: OutputFormat, media: MediaInfo, index: int | None = None) -> bool:
    if not fmt.is_video:
        return False
    stream = _stream(media, index) if index is not None else None
    if stream is None and media.video_streams:
        stream = media.video_streams[0]
    if stream is None:
        return False
    allowed = VIDEO_COPY_CODECS.get(fmt.muxer)
    return allowed is None or (stream.codec_name or "") in allowed


def can_copy_audio(fmt: OutputFormat, audio: list[StreamInfo]) -> bool:
    if not audio:
        return False
    allowed = AUDIO_COPY_CODECS.get(fmt.muxer)
    return allowed is None or all((s.codec_name or "") in allowed for s in audio)


def audio_codecs(fmt: OutputFormat, encoders: Collection[str]) -> tuple[str, ...]:
    """Audio encoders the format can use with this FFmpeg, the format's own first."""
    base = fmt.settings(Quality.BALANCED).audio
    own = base.codec if base is not None else None
    if fmt.is_video:
        offered = VIDEO_CONTAINER_AUDIO.get(fmt.muxer, (own,) if own else ())
    else:
        offered = (own,) if own else ()
    codecs = [own] if own else []
    codecs += [c for c in offered if c and c != own and c in encoders]
    return tuple(c for c in codecs if c is not None)


def sample_rates(codec: str) -> tuple[int, ...]:
    return OPUS_SAMPLE_RATES if codec == "libopus" else SAMPLE_RATES


def smaller_heights(media: MediaInfo, index: int | None = None) -> tuple[int, ...]:
    """Resolutions below the source's: never upscale."""
    stream = _stream(media, index) if index is not None else None
    if stream is None and media.video_streams:
        stream = media.video_streams[0]
    if stream is None or not stream.height:
        return ()
    return tuple(height for height in HEIGHTS if height < stream.height)


@dataclass(frozen=True)
class Recipe:
    """What a conversion does: software settings and the tracks to map."""

    settings: ConversionSettings
    streams: StreamMap


def _video(
    fmt: OutputFormat,
    quality: Quality,
    media: MediaInfo,
    choices: AdvancedChoices,
    index: int | None,
) -> VideoOptions | None:
    base = fmt.settings(quality).video
    if base is None or not fmt.is_video:
        return None
    if choices.copy_video and can_copy_video(fmt, media, index):
        return VideoOptions(codec=COPY)
    video = base
    if choices.rate_control is RateControl.BITRATE:
        video = replace(video, crf=None, bitrate=choices.video_bitrate or DEFAULT_VIDEO_BITRATE)
    elif choices.crf is not None:
        low, high = CRF_RANGE.get(video.codec, (0, 51))
        video = replace(video, crf=min(max(choices.crf, low), high))
    if choices.preset is not None and choices.preset in PRESETS.get(video.codec, ()):
        video = replace(video, preset=choices.preset)
    if choices.height is not None and choices.height in smaller_heights(media, index):
        video = replace(video, height=choices.height)
    if choices.pixel_format in PIXEL_FORMATS.get(video.codec, ()):
        video = replace(video, pixel_format=choices.pixel_format)
    deinterlace = None if choices.deinterlace is Deinterlace.OFF else choices.deinterlace.value
    return replace(
        video,
        frame_rate=choices.frame_rate,
        aspect=choices.aspect,
        deinterlace=deinterlace,
    )


def _audio(
    fmt: OutputFormat,
    quality: Quality,
    media: MediaInfo,
    choices: AdvancedChoices,
    kept_audio: list[StreamInfo],
) -> AudioOptions | None:
    base = fmt.settings(quality).audio
    if base is None:
        return None
    codec = choices.audio_codec or base.codec
    if codec == COPY:
        if can_copy_audio(fmt, kept_audio):
            return AudioOptions(codec=COPY)
        codec = base.codec
    lossless = codec in LOSSLESS_AUDIO
    if lossless:
        audio = AudioOptions(codec=codec)
    elif choices.audio_bitrate is not None:
        audio = AudioOptions(codec=codec, bitrate=choices.audio_bitrate)
    elif codec == base.codec:
        audio = base
    else:
        audio = AudioOptions(codec=codec, bitrate=base.bitrate or DEFAULT_AUDIO_BITRATE)
    sample_rate = choices.sample_rate if choices.sample_rate in sample_rates(codec) else None
    return replace(audio, sample_rate=sample_rate, channels=choices.channels)


def resolve(
    fmt: OutputFormat,
    quality: Quality,
    media: MediaInfo,
    choices: AdvancedChoices | None = None,
) -> Recipe:
    """The settings and tracks for a format, a quality and the Advanced choices."""
    choices = choices or AdvancedChoices()
    kept = kept_tracks(fmt, media, choices)
    in_order = [s for s in media.streams if s.index in kept]
    video_index = next(
        (s.index for s in in_order if s.type is StreamType.VIDEO and not s.is_attached_picture),
        None,
    )
    cover = next((s.index for s in in_order if s.is_attached_picture), None)
    kept_audio = [s for s in in_order if s.type is StreamType.AUDIO]
    subtitles = tuple(s.index for s in in_order if s.type is StreamType.SUBTITLE)

    video = _video(fmt, quality, media, choices, video_index) if video_index is not None else None
    audio = _audio(fmt, quality, media, choices, kept_audio) if kept_audio else None
    if video is None and audio is None:
        if kept != default_tracks(fmt, media):
            # Nothing playable kept: fall back to the format's own tracks.
            return resolve(fmt, quality, media, replace(choices, tracks=None))
        base = fmt.settings(quality)
        video, audio = base.video, base.audio
    normalize = choices.normalize_loudness and audio is not None and not audio.is_copy
    settings = ConversionSettings(
        video=video,
        audio=audio,
        preserve_metadata=choices.keep_metadata,
        fast_start=choices.fast_start,
        normalize_loudness=normalize,
    )
    downmix = (
        fmt.policy.downmix_to_stereo
        and audio is not None
        and not audio.is_copy
        and choices.channels is None
        and any((s.channels or 0) > STEREO for s in kept_audio)
    )
    plan = StreamMap(
        video=video_index if video is not None else None,
        audio=tuple(s.index for s in kept_audio),
        subtitles=subtitles,
        cover_art=cover,
        subtitle_codec=fmt.policy.subtitle_codec if subtitles else None,
        downmix_to_stereo=downmix,
    )
    return Recipe(settings, plan)
