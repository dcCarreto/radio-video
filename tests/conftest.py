from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from radio_video.ffmpeg import FFmpegNotFoundError, FFmpegTools, locate_tools

# CI sets this so a missing FFmpeg fails the run instead of silently skipping tests.
REQUIRE_FFMPEG = os.environ.get("RADIO_VIDEO_REQUIRE_FFMPEG") == "1"


@pytest.fixture(scope="session")
def ffmpeg_tools() -> FFmpegTools:
    try:
        return locate_tools()
    except FFmpegNotFoundError as exc:
        if REQUIRE_FFMPEG:
            pytest.fail(str(exc))
        pytest.skip(str(exc))


def _generate(tools: FFmpegTools, output: Path, *args: str) -> Path:
    subprocess.run(
        [str(tools.ffmpeg), "-hide_banner", "-loglevel", "error", "-y", *args, str(output)],
        check=True,
        timeout=60,
    )
    return output


@pytest.fixture(scope="session")
def media_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("media")


@pytest.fixture(scope="session")
def sample_video(ffmpeg_tools: FFmpegTools, media_dir: Path) -> Path:
    """Three-second 320x240 25 fps H.264 video with a stereo AAC track and a subtitle."""
    srt = media_dir / "sample.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    return _generate(
        ffmpeg_tools,
        media_dir / "sample.mkv",
        "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=25:duration=3",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=3",
        "-i", str(srt),
        "-map", "0:v", "-map", "1:a", "-map", "2:s",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ac", "2",
        "-c:s", "srt",
        "-metadata", "title=Sample Clip",
        "-metadata:s:a:0", "language=eng",
    )  # fmt: skip


@pytest.fixture(scope="session")
def sample_audio(ffmpeg_tools: FFmpegTools, media_dir: Path) -> Path:
    """Two-second mono 44.1 kHz FLAC file."""
    return _generate(
        ffmpeg_tools,
        media_dir / "sample.flac",
        "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=44100:duration=2",
        "-c:a", "flac",
    )  # fmt: skip
