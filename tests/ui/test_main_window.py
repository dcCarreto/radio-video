from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from radio_video.ffmpeg import FFmpegTools
from radio_video.models import MediaInfo, StreamInfo, StreamType
from radio_video.services.analysis import MediaAnalyzer
from radio_video.ui.main_window import MainWindow
from radio_video.ui.media_info_view import MediaInfoView, stream_details


def _media() -> MediaInfo:
    return MediaInfo(
        path=Path("C:/videos/movie.mkv"),
        format_name="matroska,webm",
        format_long_name="Matroska / WebM",
        duration=125.0,
        size=10 * 1024 * 1024,
        bit_rate=640_000,
        tags={"title": "Movie"},
        streams=(
            StreamInfo(
                index=0,
                type=StreamType.VIDEO,
                codec_name="h264",
                profile="High",
                width=1280,
                height=720,
                frame_rate=25.0,
                pixel_format="yuv420p",
            ),
            StreamInfo(
                index=1,
                type=StreamType.AUDIO,
                codec_name="opus",
                sample_rate=48000,
                channel_layout="stereo",
                language="eng",
            ),
        ),
    )


def test_stream_details() -> None:
    video, audio = _media().streams
    assert stream_details(video) == "1280×720 · 25 fps · yuv420p"
    assert stream_details(audio) == "48 kHz · stereo"


def test_media_info_view_shows_summary_and_streams(qtbot: QtBot) -> None:
    view = MediaInfoView()
    qtbot.addWidget(view)
    view.set_media(_media())

    assert view.file_label.text() == "movie.mkv"
    assert view.container_label.text() == "Matroska / WebM"
    assert view.duration_label.text() == "2:05"
    assert view.size_label.text() == "10.0 MB"
    assert view.title_label.text() == "Movie"
    assert view.streams.topLevelItemCount() == 2
    audio = view.streams.topLevelItem(1)
    assert audio is not None
    assert audio.text(1) == "Audio"
    assert audio.text(2) == "opus"
    assert audio.text(4) == "eng"


def test_window_without_ffmpeg_explains_and_disables_opening(qtbot: QtBot) -> None:
    window = MainWindow(None, "ffmpeg was not found.")
    qtbot.addWidget(window)
    assert window.analyzer is None
    assert not window.open_action.isEnabled()
    assert not window.drop_area.open_button.isEnabled()
    assert window.pages.currentWidget() is window.drop_area


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


@pytest.mark.ffmpeg
def test_window_opens_file(qtbot: QtBot, ffmpeg_tools: FFmpegTools, sample_video: Path) -> None:
    window = MainWindow(ffmpeg_tools)
    qtbot.addWidget(window)
    assert window.analyzer is not None
    with qtbot.waitSignal(window.analyzer.analyzed, timeout=15000):
        window.open_file(sample_video)
    assert window.pages.currentWidget() is window.info_view
    assert window.media is not None
    assert window.media.path == sample_video
    assert window.info_view.streams.topLevelItemCount() == 3
    assert "sample.mkv" in window.windowTitle()
