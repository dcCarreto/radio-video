from pathlib import Path

import pytest

from radio_video.models.conversion import AudioOptions, ConversionSettings, VideoOptions
from radio_video.models.estimate import describe_settings, estimate_output_size
from radio_video.models.media import MediaInfo, StreamInfo, StreamType

VIDEO = StreamInfo(index=0, type=StreamType.VIDEO, width=1920, height=1080)
AUDIO = StreamInfo(index=1, type=StreamType.AUDIO, sample_rate=48000, channels=2)


def _media(*streams: StreamInfo, duration: float | None = 60.0) -> MediaInfo:
    return MediaInfo(
        path=Path("in.mkv"), format_name="matroska", duration=duration, streams=streams
    )


def test_bitrate_based_audio_is_predictable() -> None:
    settings = ConversionSettings(video=None, audio=AudioOptions("libmp3lame", bitrate=192_000))
    assert estimate_output_size(settings, _media(VIDEO, AUDIO)) == 192_000 * 60 // 8


def test_pcm_uses_source_sample_rate_and_channels() -> None:
    settings = ConversionSettings(video=None, audio=AudioOptions("pcm_s16le"))
    assert estimate_output_size(settings, _media(AUDIO)) == 48000 * 2 * 2 * 60


def test_pcm_respects_resampling_options() -> None:
    settings = ConversionSettings(
        video=None, audio=AudioOptions("pcm_s16le", sample_rate=44100, channels=1)
    )
    assert estimate_output_size(settings, _media(AUDIO)) == 44100 * 1 * 2 * 60


@pytest.mark.parametrize(
    "settings",
    [
        ConversionSettings(video=VideoOptions("libx264", crf=23), audio=AudioOptions("aac", 1)),
        ConversionSettings(video=VideoOptions("libvpx-vp9", crf=32, bitrate=0), audio=None),
        ConversionSettings(video=None, audio=AudioOptions("flac")),
    ],
)
def test_quality_based_encoding_is_not_predictable(settings: ConversionSettings) -> None:
    assert estimate_output_size(settings, _media(VIDEO, AUDIO)) is None


def test_constant_bitrate_video_is_predictable() -> None:
    settings = ConversionSettings(
        video=VideoOptions("libx264", bitrate=2_000_000), audio=AudioOptions("aac", 128_000)
    )
    assert estimate_output_size(settings, _media(VIDEO, AUDIO)) == 2_128_000 * 60 // 8


def test_video_settings_ignored_for_audio_only_source() -> None:
    settings = ConversionSettings(
        video=VideoOptions("libx264", crf=23), audio=AudioOptions("aac", 128_000)
    )
    assert estimate_output_size(settings, _media(AUDIO)) == 128_000 * 60 // 8


def test_unknown_duration() -> None:
    settings = ConversionSettings(video=None, audio=AudioOptions("libmp3lame", bitrate=192_000))
    assert estimate_output_size(settings, _media(AUDIO, duration=None)) is None


def test_describe_settings() -> None:
    settings = ConversionSettings(
        video=VideoOptions("libx264", crf=23), audio=AudioOptions("aac", bitrate=192_000)
    )
    assert describe_settings(settings) == "H.264 video, quality CRF 23 · AAC audio, 192 kb/s"
    assert describe_settings(settings, _media(AUDIO)) == "AAC audio, 192 kb/s"
    lossless = ConversionSettings(video=None, audio=AudioOptions("flac"))
    assert describe_settings(lossless) == "FLAC audio, lossless"
