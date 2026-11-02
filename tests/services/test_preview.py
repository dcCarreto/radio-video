from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from radio_video.ffmpeg import FFmpegTools, probe
from radio_video.models.conversion import AudioOptions, ConversionSettings, VideoOptions
from radio_video.services.preview import (
    SHORT_PREVIEW_SECONDS,
    TEMP_PREFIX,
    PreviewGenerator,
    PreviewKind,
    PreviewSample,
    purge_stale_previews,
    short_preview_range,
)

TIMEOUT_MS = 60000
MP4 = ConversionSettings(
    video=VideoOptions(codec="libx264", preset="ultrafast", crf=30),
    audio=AudioOptions(codec="aac", bitrate=96_000),
)


@pytest.mark.parametrize(
    ("duration", "expected"),
    [
        (None, (0.0, SHORT_PREVIEW_SECONDS)),
        (10.0, (0.0, None)),
        (15.0, (0.0, None)),
        (60.0, (20.0, 15.0)),
        (20.0, (5.0, 15.0)),
        (5400.0, (1800.0, 15.0)),
    ],
)
def test_short_preview_range(duration: float | None, expected: tuple[float, float | None]) -> None:
    assert short_preview_range(duration) == expected


def test_estimated_full_size() -> None:
    short = PreviewSample(Path("p.mp4"), PreviewKind.SHORT, start=20, length=15, size=1_500_000)
    assert short.estimated_full_size(60.0) == 6_000_000
    assert short.estimated_full_size(None) is None
    whole = PreviewSample(Path("p.mp4"), PreviewKind.SHORT, start=0, length=None, size=900)
    assert whole.estimated_full_size(10.0) == 900
    full = PreviewSample(Path("p.mp4"), PreviewKind.FULL, start=0, length=None, size=4321)
    assert full.estimated_full_size(60.0) == 4321


def test_purge_stale_previews(tmp_path: Path) -> None:
    old = tmp_path / f"{TEMP_PREFIX}old"
    recent = tmp_path / f"{TEMP_PREFIX}recent"
    unrelated = tmp_path / "other-folder"
    for folder in (old, recent, unrelated):
        folder.mkdir()
        (folder / "preview.mp4").write_bytes(b"x")
    past = time.time() - 2 * 24 * 3600
    os.utime(old, (past, past))
    os.utime(unrelated, (past, past))

    assert purge_stale_previews(temp_root=tmp_path) == 1
    assert not old.exists()
    assert recent.exists()
    assert unrelated.exists()


@pytest.fixture(scope="module")
def minute_video(ffmpeg_tools: FFmpegTools, tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("preview") / "minute.mkv"
    subprocess.run(
        [
            str(ffmpeg_tools.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=160x120:rate=10:duration=60",
            "-f", "lavfi", "-i", "sine=duration=60",
            "-c:v", "mpeg4", "-q:v", "10", "-c:a", "aac", str(output),
        ],
        check=True,
        timeout=120,
    )  # fmt: skip
    return output


@pytest.mark.ffmpeg
def test_short_preview_converts_sample_from_middle(
    qtbot: QtBot, ffmpeg_tools: FFmpegTools, minute_video: Path
) -> None:
    media = probe(minute_video, ffmpeg_tools.ffprobe)
    generator = PreviewGenerator(ffmpeg_tools.ffmpeg)
    with qtbot.waitSignal(generator.ready, timeout=TIMEOUT_MS) as blocker:
        generator.generate(media, MP4, ".mp4", PreviewKind.SHORT)
    sample = blocker.args[0]
    assert isinstance(sample, PreviewSample)
    assert media.duration is not None
    assert sample.start == pytest.approx(media.duration / 3, abs=0.01)
    assert sample.length == SHORT_PREVIEW_SECONDS
    assert sample.path.name == "preview.mp4"
    assert sample.path.parent.name.startswith(TEMP_PREFIX)

    preview = probe(sample.path, ffmpeg_tools.ffprobe)
    assert preview.duration == pytest.approx(SHORT_PREVIEW_SECONDS, abs=0.5)
    assert preview.video_streams[0].codec_name == "h264"
    assert preview.audio_streams[0].codec_name == "aac"
    assert sample.estimated_full_size(media.duration) == round(
        sample.size * media.duration / SHORT_PREVIEW_SECONDS
    )

    generator.discard()
    assert not sample.path.parent.exists()


@pytest.mark.ffmpeg
def test_full_preview_converts_whole_file(
    qtbot: QtBot, ffmpeg_tools: FFmpegTools, sample_video: Path
) -> None:
    media = probe(sample_video, ffmpeg_tools.ffprobe)
    generator = PreviewGenerator(ffmpeg_tools.ffmpeg)
    with qtbot.waitSignal(generator.ready, timeout=TIMEOUT_MS) as blocker:
        generator.generate(media, MP4, ".mp4", PreviewKind.FULL)
    sample = blocker.args[0]
    assert sample.kind is PreviewKind.FULL
    assert probe(sample.path, ffmpeg_tools.ffprobe).duration == pytest.approx(3.0, abs=0.2)
    generator.discard()


@pytest.mark.ffmpeg
def test_new_preview_replaces_previous_one(
    qtbot: QtBot, ffmpeg_tools: FFmpegTools, sample_video: Path
) -> None:
    media = probe(sample_video, ffmpeg_tools.ffprobe)
    generator = PreviewGenerator(ffmpeg_tools.ffmpeg)
    with qtbot.waitSignal(generator.ready, timeout=TIMEOUT_MS) as first:
        generator.generate(media, MP4, ".mp4", PreviewKind.SHORT)
    with qtbot.waitSignal(generator.ready, timeout=TIMEOUT_MS) as second:
        generator.generate(media, MP4, ".mp4", PreviewKind.SHORT)
    assert not first.args[0].path.exists()
    assert second.args[0].path.exists()
    generator.discard()


@pytest.mark.ffmpeg
def test_cancel_preview_removes_files(
    qtbot: QtBot, ffmpeg_tools: FFmpegTools, minute_video: Path
) -> None:
    slow = ConversionSettings(
        video=VideoOptions(codec="libx264", preset="veryslow", width=1920, height=1440),
        audio=None,
    )
    media = probe(minute_video, ffmpeg_tools.ffprobe)
    generator = PreviewGenerator(ffmpeg_tools.ffmpeg)
    generator.generate(media, slow, ".mp4", PreviewKind.FULL)
    job = generator.runner.job
    assert job is not None
    temp_dir = job.destination.parent
    with qtbot.waitSignal(generator.canceled, timeout=TIMEOUT_MS):
        generator.cancel()
    assert not any(temp_dir.iterdir())
    generator.discard()
    assert not temp_dir.exists()
