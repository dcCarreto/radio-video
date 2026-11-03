"""Output formats and quality presets used by Simple Mode."""

from __future__ import annotations

from collections.abc import Callable, Collection
from dataclasses import dataclass
from enum import Enum
from typing import TypeVar

from radio_video.models.conversion import AudioOptions, ConversionSettings, VideoOptions
from radio_video.models.media import MediaInfo
from radio_video.models.tracks import SUBTITLE_COPY, StreamMap, TrackPolicy, plan_streams

T = TypeVar("T")


class Quality(Enum):
    HIGH = "High"
    BALANCED = "Balanced"
    SMALL = "Small file"


# Video containers keep every audio track. MP4 and WebM convert text subtitles to their own
# text formats (image subtitles are left out); MKV copies all of them. WebM can't store cover
# art. Audio-only formats keep the main audio track; lossy ones mix surround down to stereo.
VIDEO_MP4 = TrackPolicy(all_audio=True, subtitle_codec="mov_text", cover_art=True)
VIDEO_MKV = TrackPolicy(all_audio=True, subtitle_codec=SUBTITLE_COPY, cover_art=True)
VIDEO_WEBM = TrackPolicy(all_audio=True, subtitle_codec="webvtt")
AUDIO_LOSSY_WITH_COVER = TrackPolicy(cover_art=True, downmix_to_stereo=True)
AUDIO_LOSSY = TrackPolicy(downmix_to_stereo=True)
AUDIO_LOSSLESS_WITH_COVER = TrackPolicy(cover_art=True)
AUDIO_LOSSLESS = TrackPolicy()


@dataclass(frozen=True)
class OutputFormat:
    key: str
    label: str
    extension: str
    is_video: bool
    encoders: tuple[str, ...]
    build: Callable[[Quality], ConversionSettings]
    muxer: str
    policy: TrackPolicy
    lossless: bool = False

    def settings(self, quality: Quality) -> ConversionSettings:
        return self.build(Quality.HIGH if self.lossless else quality)

    def is_available(self, encoders: Collection[str]) -> bool:
        return all(encoder in encoders for encoder in self.encoders)

    def plan(self, media: MediaInfo) -> StreamMap:
        return plan_streams(media, self.policy, include_video=self.is_video)


def _by_quality(high: T, balanced: T, small: T) -> Callable[[Quality], T]:
    values = {Quality.HIGH: high, Quality.BALANCED: balanced, Quality.SMALL: small}
    return values.__getitem__


_X264_CRF = _by_quality(18, 23, 28)
_X265_CRF = _by_quality(22, 26, 30)
_VP9_CRF = _by_quality(24, 32, 40)
_AAC_VIDEO_BITRATE = _by_quality(256_000, 192_000, 128_000)
_OPUS_VIDEO_BITRATE = _by_quality(160_000, 128_000, 96_000)
_MP3_BITRATE = _by_quality(320_000, 192_000, 128_000)
_M4A_BITRATE = _by_quality(256_000, 160_000, 96_000)
_OPUS_BITRATE = _by_quality(160_000, 96_000, 64_000)
# libvorbis -q:a scale; 6 is about 192 kb/s for stereo, 4 about 128 kb/s.
_VORBIS_QUALITY = _by_quality(8.0, 6.0, 4.0)


def _h264_aac(quality: Quality) -> ConversionSettings:
    return ConversionSettings(
        video=VideoOptions(
            codec="libx264", crf=_X264_CRF(quality), preset="medium", pixel_format="yuv420p"
        ),
        audio=AudioOptions(codec="aac", bitrate=_AAC_VIDEO_BITRATE(quality)),
    )


def _h265_aac(quality: Quality) -> ConversionSettings:
    return ConversionSettings(
        video=VideoOptions(
            codec="libx265", crf=_X265_CRF(quality), preset="medium", pixel_format="yuv420p"
        ),
        audio=AudioOptions(codec="aac", bitrate=_AAC_VIDEO_BITRATE(quality)),
    )


def _vp9_opus(quality: Quality) -> ConversionSettings:
    return ConversionSettings(
        video=VideoOptions(
            codec="libvpx-vp9", crf=_VP9_CRF(quality), bitrate=0, pixel_format="yuv420p"
        ),
        audio=AudioOptions(codec="libopus", bitrate=_OPUS_VIDEO_BITRATE(quality)),
    )


def _audio(
    codec: str,
    bitrate: Callable[[Quality], int] | None = None,
    vbr_quality: Callable[[Quality], float] | None = None,
) -> Callable[[Quality], ConversionSettings]:
    def build(quality: Quality) -> ConversionSettings:
        return ConversionSettings(
            video=None,
            audio=AudioOptions(
                codec=codec,
                bitrate=bitrate(quality) if bitrate else None,
                quality=vbr_quality(quality) if vbr_quality else None,
            ),
        )

    return build


OUTPUT_FORMATS: tuple[OutputFormat, ...] = (
    OutputFormat(
        "mp4-h264", "MP4 (H.264 + AAC)", ".mp4", True, ("libx264", "aac"), _h264_aac,
        "mp4", VIDEO_MP4,
    ),
    OutputFormat(
        "mp4-h265", "MP4 (H.265 + AAC)", ".mp4", True, ("libx265", "aac"), _h265_aac,
        "mp4", VIDEO_MP4,
    ),
    OutputFormat(
        "mkv-h264", "MKV (H.264 + AAC)", ".mkv", True, ("libx264", "aac"), _h264_aac,
        "matroska", VIDEO_MKV,
    ),
    OutputFormat(
        "webm-vp9", "WebM (VP9 + Opus)", ".webm", True, ("libvpx-vp9", "libopus"), _vp9_opus,
        "webm", VIDEO_WEBM,
    ),
    OutputFormat(
        "mp3", "MP3", ".mp3", False, ("libmp3lame",), _audio("libmp3lame", _MP3_BITRATE),
        "mp3", AUDIO_LOSSY_WITH_COVER,
    ),
    OutputFormat(
        "m4a-aac", "AAC (M4A)", ".m4a", False, ("aac",), _audio("aac", _M4A_BITRATE),
        "ipod", AUDIO_LOSSY_WITH_COVER,
    ),
    OutputFormat(
        "opus", "Opus", ".opus", False, ("libopus",), _audio("libopus", _OPUS_BITRATE),
        "opus", AUDIO_LOSSY,
    ),
    OutputFormat(
        "ogg-vorbis", "Ogg Vorbis", ".ogg", False, ("libvorbis",),
        _audio("libvorbis", vbr_quality=_VORBIS_QUALITY), "ogg", AUDIO_LOSSY,
    ),
    OutputFormat(
        "flac", "FLAC (lossless)", ".flac", False, ("flac",), _audio("flac"),
        "flac", AUDIO_LOSSLESS_WITH_COVER, lossless=True,
    ),
    OutputFormat(
        "wav", "WAV (lossless)", ".wav", False, ("pcm_s16le",), _audio("pcm_s16le"),
        "wav", AUDIO_LOSSLESS, lossless=True,
    ),
)  # fmt: skip


def format_by_key(key: str) -> OutputFormat:
    for fmt in OUTPUT_FORMATS:
        if fmt.key == key:
            return fmt
    raise KeyError(key)


def available_formats(
    encoders: Collection[str], source_has_video: bool
) -> tuple[OutputFormat, ...]:
    """Formats the installed FFmpeg can produce and that make sense for the source.

    Video formats are offered only for sources with a video stream; audio formats are always
    offered, which covers extracting audio from video.
    """
    return tuple(
        fmt
        for fmt in OUTPUT_FORMATS
        if fmt.is_available(encoders) and (source_has_video or not fmt.is_video)
    )
