from pathlib import Path

import pytest

from radio_video.ffmpeg import FFmpegTools
from radio_video.ffmpeg.capabilities import (
    CapabilityError,
    list_encoders,
    parse_encoders,
    parse_version,
)

SAMPLE = """Encoders:
 V..... = Video
 A..... = Audio
 S..... = Subtitle
 .F.... = Frame-level multithreading
 ------
 V....D libx264              libx264 H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10 (codec h264)
 V....D libvpx-vp9           libvpx VP9 (codec vp9)
 VF.... h264_nvenc           NVIDIA NVENC H.264 encoder (codec h264)
 A....D aac                  AAC (Advanced Audio Coding)
 A..X.D opus                 Opus
 S..... srt                  SubRip subtitle
"""


def test_parse_encoders() -> None:
    assert parse_encoders(SAMPLE) == {
        "libx264",
        "libvpx-vp9",
        "h264_nvenc",
        "aac",
        "opus",
        "srt",
    }


def test_parse_ignores_legend_and_noise() -> None:
    assert parse_encoders("Encoders:\n V..... = Video\n ------\n\n") == frozenset()


def test_missing_executable(tmp_path: Path) -> None:
    with pytest.raises(CapabilityError):
        list_encoders(tmp_path / "missing.exe")


@pytest.mark.ffmpeg
def test_list_encoders_from_ffmpeg(ffmpeg_tools: FFmpegTools) -> None:
    encoders = list_encoders(ffmpeg_tools.ffmpeg)
    assert {"libx264", "aac", "flac", "pcm_s16le"} <= encoders


@pytest.mark.parametrize(
    ("line", "version"),
    [
        ("ffmpeg version 7.1-full_build-www.gyan.dev Copyright (c) 2000-2024", "7.1"),
        ("ffmpeg version n6.1.1 Copyright", "6.1.1"),
        ("ffmpeg version 9.0.2-essentials_build", "9.0.2"),
        ("ffmpeg version N-112233-gabcdef", None),
        ("not ffmpeg", None),
    ],
)
def test_parse_version(line: str, version: str | None) -> None:
    assert parse_version(line) == version
