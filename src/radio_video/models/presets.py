"""Output formats and quality presets used by Simple Mode."""

from __future__ import annotations

from collections.abc import Callable, Collection
from dataclasses import dataclass
from enum import Enum

from radio_video.models.conversion import AudioOptions, ConversionSettings, VideoOptions


class Quality(Enum):
    HIGH = "High"
    BALANCED = "Balanced"
    SMALL = "Small file"


@dataclass(frozen=True)
class OutputFormat:
    key: str
    label: str
    extension: str
    is_video: bool
    encoders: tuple[str, ...]
    build: Callable[[Quality], ConversionSettings]
    lossless: bool = False

    def settings(self, quality: Quality) -> ConversionSettings:
        return self.build(Quality.HIGH if self.lossless else quality)

    def is_available(self, encoders: Collection[str]) -> bool:
        return all(encoder in encoders for encoder in self.encoders)


def _by_quality(high: int, balanced: int, small: int) -> Callable[[Quality], int]:
    values = {Quality.HIGH: high, Quality.BALANCED: balanced, Quality.SMALL: small}
    return values.__getitem__


_X264_CRF = _by_quality(18, 23, 28)
_X265_CRF = _by_quality(22, 26, 30)
_VP9_CRF = _by_quality(24, 32, 40)
_AAC_BITRATE = _by_quality(256_000, 192_000, 128_000)
_OPUS_BITRATE = _by_quality(160_000, 128_000, 96_000)
_MP3_BITRATE = _by_quality(320_000, 192_000, 128_000)
_VORBIS_BITRATE = _by_quality(256_000, 192_000, 128_000)


def _h264_aac(quality: Quality) -> ConversionSettings:
    return ConversionSettings(
        video=VideoOptions(
            codec="libx264", crf=_X264_CRF(quality), preset="medium", pixel_format="yuv420p"
        ),
        audio=AudioOptions(codec="aac", bitrate=_AAC_BITRATE(quality)),
    )


def _h265_aac(quality: Quality) -> ConversionSettings:
    return ConversionSettings(
        video=VideoOptions(
            codec="libx265", crf=_X265_CRF(quality), preset="medium", pixel_format="yuv420p"
        ),
        audio=AudioOptions(codec="aac", bitrate=_AAC_BITRATE(quality)),
    )


def _vp9_opus(quality: Quality) -> ConversionSettings:
    return ConversionSettings(
        video=VideoOptions(
            codec="libvpx-vp9", crf=_VP9_CRF(quality), bitrate=0, pixel_format="yuv420p"
        ),
        audio=AudioOptions(codec="libopus", bitrate=_OPUS_BITRATE(quality)),
    )


def _audio(
    codec: str, bitrate: Callable[[Quality], int] | None = None
) -> Callable[[Quality], ConversionSettings]:
    def build(quality: Quality) -> ConversionSettings:
        return ConversionSettings(
            video=None,
            audio=AudioOptions(codec=codec, bitrate=bitrate(quality) if bitrate else None),
        )

    return build


OUTPUT_FORMATS: tuple[OutputFormat, ...] = (
    OutputFormat("mp4-h264", "MP4 (H.264 + AAC)", ".mp4", True, ("libx264", "aac"), _h264_aac),
    OutputFormat("mp4-h265", "MP4 (H.265 + AAC)", ".mp4", True, ("libx265", "aac"), _h265_aac),
    OutputFormat("mkv-h264", "MKV (H.264 + AAC)", ".mkv", True, ("libx264", "aac"), _h264_aac),
    OutputFormat(
        "webm-vp9", "WebM (VP9 + Opus)", ".webm", True, ("libvpx-vp9", "libopus"), _vp9_opus
    ),
    OutputFormat("mp3", "MP3", ".mp3", False, ("libmp3lame",), _audio("libmp3lame", _MP3_BITRATE)),
    OutputFormat("m4a-aac", "AAC (M4A)", ".m4a", False, ("aac",), _audio("aac", _AAC_BITRATE)),
    OutputFormat("opus", "Opus", ".opus", False, ("libopus",), _audio("libopus", _OPUS_BITRATE)),
    OutputFormat(
        "ogg-vorbis",
        "Ogg Vorbis",
        ".ogg",
        False,
        ("libvorbis",),
        _audio("libvorbis", _VORBIS_BITRATE),
    ),
    OutputFormat(
        "flac", "FLAC (lossless)", ".flac", False, ("flac",), _audio("flac"), lossless=True
    ),
    OutputFormat(
        "wav", "WAV (lossless)", ".wav", False, ("pcm_s16le",), _audio("pcm_s16le"), lossless=True
    ),
)


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
