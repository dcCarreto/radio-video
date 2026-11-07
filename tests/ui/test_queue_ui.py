"""The Queue tab with the main window: adding, running and the rules between the two."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from pytestqt.qtbot import QtBot

from radio_video.ffmpeg import FFmpegTools, probe
from radio_video.ffmpeg.capabilities import list_encoders
from radio_video.models.advanced import AdvancedChoices
from radio_video.models.presets import OUTPUT_FORMATS, Quality
from radio_video.services.queue import QueueStatus
from radio_video.ui.demo import DEMO_MEDIA
from radio_video.ui.state import Page, Screen
from radio_video.ui.windows.main_window import Engine, MainWindow

TIMEOUT_MS = 60000
ALL_ENCODERS = frozenset(e for fmt in OUTPUT_FORMATS for e in fmt.encoders)


def _settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> Iterator[MainWindow]:
    engine = Engine(FFmpegTools(tmp_path / "ffmpeg.exe", tmp_path / "ffprobe.exe"), ALL_ENCODERS)
    main = MainWindow(engine, settings=_settings(tmp_path))
    qtbot.addWidget(main)
    source = tmp_path / DEMO_MEDIA.path.name
    source.write_bytes(b"")
    main.load_media(replace(DEMO_MEDIA, path=source), folder=tmp_path)
    yield main
    main.machine._state = main.machine.state.__class__()


def test_add_to_queue_keeps_the_current_settings(window: MainWindow) -> None:
    window.machine.set_quality(Quality.HIGH)
    window.machine.set_advanced(AdvancedChoices(height=720))
    window.convert_page.file.panel.add_to_queue.click()
    assert window.queue is not None
    (entry,) = window.queue.entries
    assert (entry.format_key, entry.quality) == ("mp4-h264", Quality.HIGH)
    assert entry.choices.height == 720
    assert entry.status is QueueStatus.WAITING
    assert window.tabs.buttons()[1].text() == "Queue · 1"
    page = window.queue_page
    assert page.run_button.text() == "Start Queue" and page.run_button.isEnabled()
    assert page.view is not None
    assert page.view.rows[0].target == "MP4 (H.264 + AAC), High · Custom"


def test_queue_and_convert_tab_take_turns(window: MainWindow) -> None:
    assert window.queue is not None
    window.queue.runner.start = lambda job: None  # type: ignore[method-assign]
    window.add_current_to_queue()
    window.start_queue()
    assert window.queue.running
    panel = window.convert_page.file.panel
    assert not panel.convert.isEnabled()
    assert panel.convert.toolTip().startswith("The queue is converting")
    assert window.queue_page.run_button.text() == "Stop Queue"
    window.stop_queue()
    assert not window.queue.running
    assert panel.convert.isEnabled()

    # While the Convert tab converts, the queue waits.
    window.queue.retry(window.queue.entries[0].id)
    window.machine.conversion_requested()
    window.machine.conversion_started()
    window._render_queue()
    assert not window.queue_page.run_button.isEnabled()
    assert "conversion on the Convert tab" in window.queue_page.run_button.toolTip()


def test_unreadable_files_show_as_failed_rows(window: MainWindow, tmp_path: Path) -> None:
    window._on_queue_file_read(tmp_path / "broken.mkv", "Invalid data found")
    assert window.queue is not None
    (entry,) = window.queue.entries
    assert entry.status is QueueStatus.FAILED and not entry.readable
    row = window.queue_page.view.rows[0] if window.queue_page.view else None
    assert row is not None and row.progress_text == "Can’t read this file"
    assert not row.can_retry


def test_audio_files_get_an_audio_format(window: MainWindow, tmp_path: Path) -> None:
    audio = replace(DEMO_MEDIA, path=tmp_path / "song.flac", streams=DEMO_MEDIA.audio_streams)
    window._on_queue_file_read(audio.path, audio)
    assert window.queue is not None
    assert window.queue.entries[0].format_key not in ("mp4-h264", "mp4-h265", "mkv-h264")


def test_page_selection_and_keyboard(window: MainWindow, qtbot: QtBot) -> None:
    for _ in range(3):
        window.add_current_to_queue()
    page = window.queue_page
    assert page.view is not None
    ids = [row.entry_id for row in page.view.rows]
    page.select(ids[2])
    assert page.up_button.isEnabled() and not page.down_button.isEnabled()
    page.up_button.click()
    assert window.queue is not None
    assert [e.id for e in window.queue.entries] == [ids[0], ids[2], ids[1]]
    page.remove_button.click()
    assert len(window.queue.entries) == 2


@pytest.mark.ffmpeg
def test_queue_converts_files_one_after_another(
    qtbot: QtBot,
    ffmpeg_tools: FFmpegTools,
    sample_video: Path,
    sample_audio: Path,
    tmp_path: Path,
) -> None:
    engine = Engine(ffmpeg_tools, list_encoders(ffmpeg_tools.ffmpeg), "test")
    window = MainWindow(engine, settings=_settings(tmp_path))
    qtbot.addWidget(window)
    window.session.folder = tmp_path
    window.machine.set_format("mp3", lossless=False)
    assert window.queue is not None
    queue = window.queue
    window.add_files_to_queue([sample_video, sample_audio])
    qtbot.waitUntil(lambda: len(queue.entries) == 2, timeout=TIMEOUT_MS)
    assert [e.path for e in queue.entries] == [sample_video, sample_audio]
    assert window.machine.state.screen is Screen.QUEUE
    with qtbot.waitSignal(queue.run_finished, timeout=TIMEOUT_MS):
        window.queue_page.run_button.click()
    assert [e.status for e in queue.entries] == [QueueStatus.DONE, QueueStatus.DONE]
    for entry in queue.entries:
        assert entry.output is not None and entry.output.parent == tmp_path
        assert probe(entry.output, ffmpeg_tools.ffprobe).audio_streams[0].codec_name == "mp3"
    assert window.queue_page.counts.text() == "2 done"
    window.machine.go(Page.CONVERT)
