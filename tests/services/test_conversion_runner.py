from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from radio_video.ffmpeg import FFmpegTools, probe
from radio_video.ffmpeg.progress import ProgressUpdate
from radio_video.models.conversion import (
    AudioOptions,
    ConversionJob,
    ConversionSettings,
    VideoOptions,
)
from radio_video.services.conversion import ConversionError, ConversionRunner, partial_path

pytestmark = pytest.mark.ffmpeg

TIMEOUT_MS = 60000

MP4 = ConversionSettings(
    video=VideoOptions(codec="libx264", preset="ultrafast", crf=30, width=160),
    audio=AudioOptions(codec="aac", bitrate=96_000),
)
MP3 = ConversionSettings(video=None, audio=AudioOptions(codec="libmp3lame", bitrate=128_000))


@pytest.fixture(scope="module")
def long_video(ffmpeg_tools: FFmpegTools, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Two minutes of video, cheap to generate but slow to re-encode at high resolution."""
    output = tmp_path_factory.mktemp("long") / "long.mkv"
    subprocess.run(
        [
            str(ffmpeg_tools.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=25:duration=120",
            "-c:v", "mpeg4", "-q:v", "10", str(output),
        ],
        check=True,
        timeout=120,
    )  # fmt: skip
    return output


def test_converts_video(
    qtbot: QtBot, ffmpeg_tools: FFmpegTools, sample_video: Path, tmp_path: Path
) -> None:
    runner = ConversionRunner(ffmpeg_tools.ffmpeg)
    destination = tmp_path / "out.mp4"
    updates: list[ProgressUpdate] = []
    runner.progress.connect(updates.append)

    job = ConversionJob(sample_video, destination, MP4, duration=3.0)
    with qtbot.waitSignal(runner.succeeded, timeout=TIMEOUT_MS) as blocker:
        runner.start(job)

    assert blocker.args == [destination.resolve()]
    assert not runner.is_running
    assert updates and updates[-1].finished
    assert not partial_path(destination).exists()

    info = probe(destination, ffmpeg_tools.ffprobe)
    (video,) = info.video_streams
    (audio,) = info.audio_streams
    assert video.codec_name == "h264"
    assert (video.width, video.height) == (160, 120)
    assert audio.codec_name == "aac"
    assert not info.subtitle_streams
    assert info.duration == pytest.approx(3.0, abs=0.2)


def test_extracts_audio(
    qtbot: QtBot, ffmpeg_tools: FFmpegTools, sample_video: Path, tmp_path: Path
) -> None:
    runner = ConversionRunner(ffmpeg_tools.ffmpeg)
    destination = tmp_path / "audio.mp3"
    with qtbot.waitSignal(runner.succeeded, timeout=TIMEOUT_MS):
        runner.start(ConversionJob(sample_video, destination, MP3))
    info = probe(destination, ffmpeg_tools.ffprobe)
    assert not info.has_video
    assert info.audio_streams[0].codec_name == "mp3"


def test_converts_time_range(
    qtbot: QtBot, ffmpeg_tools: FFmpegTools, sample_video: Path, tmp_path: Path
) -> None:
    runner = ConversionRunner(ffmpeg_tools.ffmpeg)
    destination = tmp_path / "clip.mp4"
    with qtbot.waitSignal(runner.succeeded, timeout=TIMEOUT_MS):
        runner.start(ConversionJob(sample_video, destination, MP4, start=1.0, length=1.0))
    info = probe(destination, ffmpeg_tools.ffprobe)
    assert info.duration == pytest.approx(1.0, abs=0.2)


def _ffmpeg_processes() -> set[int]:
    tasklist = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32" / "tasklist.exe"
    result = subprocess.run(
        [str(tasklist), "/FI", "IMAGENAME eq ffmpeg.exe", "/NH", "/FO", "CSV"],
        capture_output=True,
        text=True,
        check=False,
    )
    return {int(line.split('","')[1]) for line in result.stdout.splitlines() if '","' in line}


@pytest.mark.skipif(sys.platform != "win32", reason="Windows process shims")
def test_immediate_cancel_through_shim_leaves_no_ffmpeg_running(
    qtbot: QtBot, ffmpeg_tools: FFmpegTools, long_video: Path, tmp_path: Path
) -> None:
    shim = tmp_path / "ffmpeg-shim.cmd"
    shim.write_text(f'@"{ffmpeg_tools.ffmpeg}" %*\n', encoding="utf-8")
    before = _ffmpeg_processes()
    slow = ConversionSettings(
        video=VideoOptions(codec="libx264", preset="veryslow", width=1920, height=1440),
        audio=None,
    )
    runner = ConversionRunner(shim)
    destination = tmp_path / "out" / "shim.mp4"
    destination.parent.mkdir()
    runner.start(ConversionJob(long_video, destination, slow, duration=120.0))

    with qtbot.waitSignal(runner.canceled, timeout=TIMEOUT_MS):
        runner.cancel()

    qtbot.wait(1500)
    assert _ffmpeg_processes() - before == set()
    assert not any(destination.parent.iterdir())


def test_cancel_removes_partial_output(
    qtbot: QtBot, ffmpeg_tools: FFmpegTools, long_video: Path, tmp_path: Path
) -> None:
    slow = ConversionSettings(
        video=VideoOptions(codec="libx264", preset="veryslow", width=1920, height=1440),
        audio=None,
    )
    runner = ConversionRunner(ffmpeg_tools.ffmpeg)
    destination = tmp_path / "canceled.mp4"
    runner.start(ConversionJob(long_video, destination, slow, duration=120.0))
    qtbot.waitSignal(runner.progress, timeout=TIMEOUT_MS).wait()
    assert runner.is_running

    with qtbot.waitSignal(runner.canceled, timeout=TIMEOUT_MS):
        runner.cancel()

    assert not runner.is_running
    assert not destination.exists()
    assert not partial_path(destination).exists()


def test_failure_reports_ffmpeg_error(
    qtbot: QtBot, ffmpeg_tools: FFmpegTools, sample_video: Path, tmp_path: Path
) -> None:
    bad = ConversionSettings(video=VideoOptions(codec="no_such_encoder"), audio=None)
    runner = ConversionRunner(ffmpeg_tools.ffmpeg)
    destination = tmp_path / "bad.mp4"
    with qtbot.waitSignal(runner.failed, timeout=TIMEOUT_MS) as blocker:
        runner.start(ConversionJob(sample_video, destination, bad))
    assert "no_such_encoder" in blocker.args[0]
    assert not destination.exists()
    assert not partial_path(destination).exists()
    assert not runner.is_running


def test_missing_ffmpeg_executable_fails(qtbot: QtBot, sample_video: Path, tmp_path: Path) -> None:
    runner = ConversionRunner(tmp_path / "missing-ffmpeg.exe")
    with qtbot.waitSignal(runner.failed, timeout=TIMEOUT_MS) as blocker:
        runner.start(ConversionJob(sample_video, tmp_path / "out.mp3", MP3))
    assert "Could not start FFmpeg" in blocker.args[0]
    assert not runner.is_running


def test_refuses_to_overwrite_without_permission(
    qtbot: QtBot, ffmpeg_tools: FFmpegTools, sample_video: Path, tmp_path: Path
) -> None:
    destination = tmp_path / "exists.mp3"
    destination.write_bytes(b"keep me")
    runner = ConversionRunner(ffmpeg_tools.ffmpeg)
    with pytest.raises(ConversionError, match="already exists"):
        runner.start(ConversionJob(sample_video, destination, MP3))
    assert destination.read_bytes() == b"keep me"

    with qtbot.waitSignal(runner.succeeded, timeout=TIMEOUT_MS):
        runner.start(ConversionJob(sample_video, destination, MP3, overwrite=True))
    assert destination.read_bytes() != b"keep me"


def test_rejects_second_conversion_while_running(
    qtbot: QtBot, ffmpeg_tools: FFmpegTools, long_video: Path, tmp_path: Path
) -> None:
    runner = ConversionRunner(ffmpeg_tools.ffmpeg)
    runner.start(ConversionJob(long_video, tmp_path / "a.mp3", MP3))
    try:
        with pytest.raises(ConversionError, match="already running"):
            runner.start(ConversionJob(long_video, tmp_path / "b.mp3", MP3))
    finally:
        with qtbot.waitSignal(runner.canceled, timeout=TIMEOUT_MS):
            runner.cancel()


def test_rejects_missing_destination_folder(ffmpeg_tools: FFmpegTools, sample_video: Path) -> None:
    runner = ConversionRunner(ffmpeg_tools.ffmpeg)
    job = ConversionJob(sample_video, Path("Z:/does/not/exist/out.mp3"), MP3)
    with pytest.raises(ConversionError, match="does not exist"):
        runner.start(job)
