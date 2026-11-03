from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from radio_video.ffmpeg import FFmpegTools, probe
from radio_video.models.conversion import ConversionJob
from radio_video.models.media import MediaInfo
from radio_video.models.presets import Quality, format_by_key
from radio_video.services.conversion import ConversionRunner, partial_path

pytestmark = pytest.mark.ffmpeg

TIMEOUT_MS = 120000


def _convert(
    qtbot: QtBot, tools: FFmpegTools, source: Path, key: str, destination: Path
) -> MediaInfo:
    media = probe(source, tools.ffprobe)
    fmt = format_by_key(key)
    job = ConversionJob(
        source,
        destination,
        fmt.settings(Quality.SMALL),
        duration=media.duration,
        streams=fmt.plan(media),
    )
    runner = ConversionRunner(tools.ffmpeg)
    with qtbot.waitSignal(runner.succeeded, timeout=TIMEOUT_MS):
        runner.start(job)
    assert not partial_path(destination).exists()
    return probe(destination, tools.ffprobe)


def test_mp4_keeps_every_track_and_the_cover(
    qtbot: QtBot, ffmpeg_tools: FFmpegTools, multitrack_video: Path, tmp_path: Path
) -> None:
    info = _convert(qtbot, ffmpeg_tools, multitrack_video, "mp4-h264", tmp_path / "out.mp4")
    assert [s.codec_name for s in info.video_streams] == ["h264"]
    assert [s.channels for s in info.audio_streams] == [6, 2]
    assert [s.language for s in info.audio_streams] == ["por", "eng"]
    assert [s.codec_name for s in info.subtitle_streams] == ["mov_text"]
    assert any(s.is_attached_picture for s in info.streams)


def test_webm_converts_subtitles_to_webvtt_without_cover(
    qtbot: QtBot, ffmpeg_tools: FFmpegTools, multitrack_video: Path, tmp_path: Path
) -> None:
    info = _convert(qtbot, ffmpeg_tools, multitrack_video, "webm-vp9", tmp_path / "out.webm")
    assert len(info.audio_streams) == 2
    assert [s.codec_name for s in info.subtitle_streams] == ["webvtt"]
    assert not any(s.is_attached_picture for s in info.streams)


def test_mp3_extracts_main_track_in_stereo_with_cover(
    qtbot: QtBot, ffmpeg_tools: FFmpegTools, multitrack_video: Path, tmp_path: Path
) -> None:
    info = _convert(qtbot, ffmpeg_tools, multitrack_video, "mp3", tmp_path / "out.mp3")
    (audio,) = info.audio_streams
    assert audio.codec_name == "mp3"
    assert audio.channels == 2
    assert not info.has_video
    assert any(s.is_attached_picture for s in info.streams)


def test_flac_keeps_surround(
    qtbot: QtBot, ffmpeg_tools: FFmpegTools, multitrack_video: Path, tmp_path: Path
) -> None:
    info = _convert(qtbot, ffmpeg_tools, multitrack_video, "flac", tmp_path / "out.flac")
    (audio,) = info.audio_streams
    assert audio.channels == 6


def test_vorbis_uses_variable_bitrate(
    qtbot: QtBot, ffmpeg_tools: FFmpegTools, sample_audio: Path, tmp_path: Path
) -> None:
    info = _convert(qtbot, ffmpeg_tools, sample_audio, "ogg-vorbis", tmp_path / "out.ogg")
    assert info.audio_streams[0].codec_name == "vorbis"
