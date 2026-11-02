from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from radio_video.ffmpeg import FFmpegTools, probe
from radio_video.ffmpeg.capabilities import list_encoders
from radio_video.models.media import MediaInfo
from radio_video.models.presets import Quality
from radio_video.services.conversion import ConversionRunner
from radio_video.ui.main_window import MainWindow
from radio_video.ui.simple_mode import SimpleModePanel

pytestmark = pytest.mark.ffmpeg

TIMEOUT_MS = 60000


@pytest.fixture(scope="module")
def encoders(ffmpeg_tools: FFmpegTools) -> frozenset[str]:
    return list_encoders(ffmpeg_tools.ffmpeg)


@pytest.fixture
def source(sample_video: Path, tmp_path: Path) -> Path:
    copy = tmp_path / "clip.mkv"
    shutil.copy(sample_video, copy)
    return copy


def _panel(
    qtbot: QtBot, tools: FFmpegTools, encoders: frozenset[str], media: Path
) -> SimpleModePanel:
    runner = ConversionRunner(tools.ffmpeg)
    panel = SimpleModePanel(runner, encoders)
    qtbot.addWidget(panel)
    panel.set_media(probe(media, tools.ffprobe))
    return panel


def _select_format(panel: SimpleModePanel, key: str) -> None:
    for index in range(panel.format_combo.count()):
        if panel.format_combo.itemData(index).key == key:
            panel.format_combo.setCurrentIndex(index)
            return
    raise AssertionError(f"format {key} not offered")


def _offered(panel: SimpleModePanel) -> list[str]:
    return [panel.format_combo.itemData(i).key for i in range(panel.format_combo.count())]


def test_video_source_offers_video_and_audio_formats(
    qtbot: QtBot, ffmpeg_tools: FFmpegTools, encoders: frozenset[str], source: Path
) -> None:
    panel = _panel(qtbot, ffmpeg_tools, encoders, source)
    offered = _offered(panel)
    assert "mp4-h264" in offered
    assert "mp3" in offered
    assert panel.folder_edit.text() == str(source.parent)
    assert panel.output_label.text() == "clip.mp4"
    assert "H.264 video" in panel.details_label.text()
    assert panel.convert_button.isEnabled()


def test_audio_source_offers_only_audio_formats(
    qtbot: QtBot, ffmpeg_tools: FFmpegTools, encoders: frozenset[str], sample_audio: Path
) -> None:
    panel = _panel(qtbot, ffmpeg_tools, encoders, sample_audio)
    offered = _offered(panel)
    assert offered
    assert not any(key.startswith(("mp4", "mkv", "webm")) for key in offered)


def test_lossless_disables_quality_and_estimates_wav_size(
    qtbot: QtBot, ffmpeg_tools: FFmpegTools, encoders: frozenset[str], source: Path
) -> None:
    panel = _panel(qtbot, ffmpeg_tools, encoders, source)
    _select_format(panel, "wav")
    assert not panel.quality_combo.isEnabled()
    assert panel.size_label.text().startswith("≈")
    _select_format(panel, "mp4-h264")
    assert panel.quality_combo.isEnabled()
    assert "Depends on the content" in panel.size_label.text()


def test_existing_output_is_not_overwritten(
    qtbot: QtBot, ffmpeg_tools: FFmpegTools, encoders: frozenset[str], source: Path
) -> None:
    (source.parent / "clip.mp3").write_bytes(b"existing")
    panel = _panel(qtbot, ffmpeg_tools, encoders, source)
    _select_format(panel, "mp3")
    assert panel.output_label.text() == "clip (1).mp3"


def test_converts_with_selected_preset(
    qtbot: QtBot, ffmpeg_tools: FFmpegTools, encoders: frozenset[str], source: Path
) -> None:
    panel = _panel(qtbot, ffmpeg_tools, encoders, source)
    _select_format(panel, "mp3")
    panel.quality_combo.setCurrentIndex(list(Quality).index(Quality.SMALL))
    busy: list[bool] = []
    panel.busy_changed.connect(busy.append)

    with qtbot.waitSignal(panel._runner.succeeded, timeout=TIMEOUT_MS) as blocker:
        panel.convert_button.click()

    output = blocker.args[0]
    assert output == (source.parent / "clip.mp3").resolve()
    assert busy == [True, False]
    assert panel.show_button.isVisible() or not panel.isVisible()
    assert panel.status_label.text().startswith("Saved clip.mp3")
    assert panel.progress_bar.value() == panel.progress_bar.maximum()
    info = probe(output, ffmpeg_tools.ffprobe)
    (audio,) = info.audio_streams
    assert audio.codec_name == "mp3"
    assert not info.has_video
    assert panel.output_label.text() == "clip (1).mp3"


def test_window_blocks_opening_files_while_converting(
    qtbot: QtBot, ffmpeg_tools: FFmpegTools, encoders: frozenset[str], source: Path
) -> None:
    window = MainWindow(ffmpeg_tools, encoders=encoders)
    qtbot.addWidget(window)
    assert window.analyzer is not None and window.simple_panel is not None
    with qtbot.waitSignal(window.analyzer.analyzed, timeout=TIMEOUT_MS):
        window.open_file(source)
    assert window.pages.currentWidget() is window.media_page
    assert isinstance(window.media, MediaInfo)

    panel = window.simple_panel
    _select_format(panel, "mp4-h264")
    with qtbot.waitSignal(panel.busy_changed, timeout=TIMEOUT_MS):
        panel.convert_button.click()
    assert not window.open_action.isEnabled()
    assert not panel.format_combo.isEnabled()
    assert panel.cancel_button.isVisibleTo(panel)

    with qtbot.waitSignal(panel.busy_changed, timeout=TIMEOUT_MS):
        pass
    assert window.open_action.isEnabled()
    assert panel.format_combo.isEnabled()
