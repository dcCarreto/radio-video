from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from radio_video.ffmpeg import FFmpegTools
from radio_video.models import MediaInfo
from radio_video.services.analysis import MediaAnalyzer


@pytest.mark.ffmpeg
def test_analyzer_reports_media(
    qtbot: QtBot, ffmpeg_tools: FFmpegTools, sample_video: Path
) -> None:
    analyzer = MediaAnalyzer(ffmpeg_tools.ffprobe)
    with qtbot.waitSignal(analyzer.analyzed, timeout=15000) as blocker:
        analyzer.analyze(sample_video)
    info = blocker.args[0]
    assert isinstance(info, MediaInfo)
    assert info.path == sample_video
    assert not analyzer.busy


@pytest.mark.ffmpeg
def test_analyzer_reports_only_latest_request(
    qtbot: QtBot, ffmpeg_tools: FFmpegTools, sample_video: Path, sample_audio: Path
) -> None:
    analyzer = MediaAnalyzer(ffmpeg_tools.ffprobe)
    received: list[MediaInfo] = []
    analyzer.analyzed.connect(received.append)
    with qtbot.waitSignal(analyzer.analyzed, timeout=15000):
        analyzer.analyze(sample_video)
        analyzer.analyze(sample_audio)
    qtbot.wait(300)
    assert [info.path for info in received] == [sample_audio]


@pytest.mark.ffmpeg
def test_analyzer_reports_failure(qtbot: QtBot, ffmpeg_tools: FFmpegTools, tmp_path: Path) -> None:
    bad = tmp_path / "broken.mp4"
    bad.write_bytes(b"not media")
    analyzer = MediaAnalyzer(ffmpeg_tools.ffprobe)
    with qtbot.waitSignal(analyzer.failed, timeout=15000) as blocker:
        analyzer.analyze(bad)
    path, message = blocker.args
    assert path == bad
    assert "broken.mp4" in message
