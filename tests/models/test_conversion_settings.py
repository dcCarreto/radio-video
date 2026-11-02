from pathlib import Path
from typing import Any

import pytest

from radio_video.models.conversion import (
    AudioOptions,
    ConversionJob,
    ConversionSettings,
    VideoOptions,
)

AUDIO = ConversionSettings(video=None, audio=AudioOptions(codec="libmp3lame"))


@pytest.mark.parametrize("codec", ["lib x264", "-y", "libx264;rm", ""])
def test_rejects_unsafe_codec_names(codec: str) -> None:
    with pytest.raises(ValueError, match="Invalid video codec"):
        VideoOptions(codec=codec)


def test_accepts_real_encoder_names() -> None:
    for codec in ("libx264", "h264_nvenc", "libvpx-vp9", "prores_ks", "copy"):
        VideoOptions(codec=codec)


@pytest.mark.parametrize(
    "kwargs",
    [{"crf": 64}, {"crf": -1}, {"bitrate": -1}, {"width": -2}, {"frame_rate": 0}],
)
def test_rejects_out_of_range_video_values(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        VideoOptions(codec="libx264", **kwargs)


def test_zero_video_bitrate_means_uncapped() -> None:
    assert VideoOptions(codec="libvpx-vp9", crf=32, bitrate=0).bitrate == 0


def test_stream_copy_rejects_encoding_options() -> None:
    with pytest.raises(ValueError, match="stream copy"):
        VideoOptions(codec="copy", crf=20)
    with pytest.raises(ValueError, match="stream copy"):
        AudioOptions(codec="copy", bitrate=128_000)


def test_settings_require_an_output_stream() -> None:
    with pytest.raises(ValueError, match="video, audio or both"):
        ConversionSettings(video=None, audio=None)


def test_job_rejects_same_source_and_destination(tmp_path: Path) -> None:
    path = tmp_path / "a.mp3"
    with pytest.raises(ValueError, match="different from the source"):
        ConversionJob(source=path, destination=path, settings=AUDIO)


def test_job_requires_extension(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="extension"):
        ConversionJob(source=tmp_path / "a.wav", destination=tmp_path / "out", settings=AUDIO)


@pytest.mark.parametrize(
    ("duration", "start", "length", "expected"),
    [
        (100.0, None, None, 100.0),
        (100.0, 30.0, None, 70.0),
        (100.0, 30.0, 15.0, 15.0),
        (100.0, 95.0, 15.0, 5.0),
        (None, None, 15.0, 15.0),
        (None, None, None, None),
        (10.0, 20.0, None, None),
    ],
)
def test_expected_duration(
    duration: float | None, start: float | None, length: float | None, expected: float | None
) -> None:
    job = ConversionJob(
        source=Path("in.wav"),
        destination=Path("out.mp3"),
        settings=AUDIO,
        duration=duration,
        start=start,
        length=length,
    )
    assert job.expected_duration == expected
