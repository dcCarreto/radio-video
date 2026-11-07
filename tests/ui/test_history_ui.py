"""History with the main window: recording, actions and clearing."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QDialog
from pytestqt.qtbot import QtBot

from radio_video.ffmpeg import FFmpegTools
from radio_video.models.advanced import AdvancedChoices
from radio_video.models.presets import OUTPUT_FORMATS, Quality
from radio_video.services.history import HistoryRecord, HistoryResult, HistoryStore
from radio_video.services.queue import QueueStatus
from radio_video.ui.demo import DEMO_MEDIA
from radio_video.ui.dialogs.failed_dialog import FailedDialog
from radio_video.ui.dialogs.quit_dialog import QuitDialog
from radio_video.ui.pages.history_page import when_text
from radio_video.ui.state import Page
from radio_video.ui.windows.main_window import Engine, MainWindow

ALL_ENCODERS = frozenset(e for fmt in OUTPUT_FORMATS for e in fmt.encoders)


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> Iterator[MainWindow]:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    engine = Engine(FFmpegTools(tmp_path / "ffmpeg.exe", tmp_path / "ffprobe.exe"), ALL_ENCODERS)
    main = MainWindow(engine, settings=settings, history_path=tmp_path / "history.json")
    qtbot.addWidget(main)
    source = tmp_path / DEMO_MEDIA.path.name
    source.write_bytes(b"")
    main.load_media(replace(DEMO_MEDIA, path=source), folder=tmp_path)
    yield main
    main.machine._state = main.machine.state.__class__()


def _convert(window: MainWindow) -> None:
    assert window.runner is not None
    window.runner.start = lambda job: None  # type: ignore[method-assign]
    window.start_conversion()
    window.machine.conversion_started()


def test_convert_tab_conversions_are_recorded(window: MainWindow, tmp_path: Path) -> None:
    window.machine.set_quality(Quality.HIGH)
    _convert(window)
    output = tmp_path / "out.mp4"
    output.write_bytes(b"x" * 2048)
    window._on_conversion_succeeded(output)
    (record,) = window.history.records
    assert record.result is HistoryResult.SAVED
    assert (record.format_key, record.quality, record.custom) == ("mp4-h264", "High", False)
    assert record.output == output and record.size == 2048
    # Kept on disk for the next session.
    assert HistoryStore(tmp_path / "history.json").records == window.history.records

    window.machine.dismiss_result()
    _convert(window)
    window._on_conversion_failed("No space left on device")
    assert window.history.records[0].result is HistoryResult.FAILED
    assert window.history.records[0].error == "No space left on device"


def test_queue_files_are_recorded(window: MainWindow, tmp_path: Path) -> None:
    assert window.queue is not None
    entry = window.queue.add(
        DEMO_MEDIA.path, "mp3", Quality.BALANCED, AdvancedChoices(height=720), tmp_path, DEMO_MEDIA
    )
    window._record_queue_entry(replace(entry, status=QueueStatus.CANCELED, fraction=0.18))
    (record,) = window.history.records
    assert record.result is HistoryResult.CANCELED and record.custom
    assert record.fraction == 0.18


def test_page_lists_records_and_offers_actions(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    saved = tmp_path / "saved.mp4"
    saved.write_bytes(b"x")
    for output, result, error in (
        (tmp_path / "gone.mp4", HistoryResult.SAVED, ""),
        (None, HistoryResult.FAILED, "Invalid data found when processing input"),
        (saved, HistoryResult.SAVED, ""),
    ):
        window.history.add(
            HistoryRecord(
                datetime.now(),
                DEMO_MEDIA.path,
                output,
                "mp4-h264",
                "Balanced",
                False,
                result,
                size=1,
                took=2.0,
                error=error,
            )
        )
    window.machine.go(Page.HISTORY)
    page = window.history_page
    assert [row.moved for row in page.rows] == [False, False, True]
    assert page.clear_button.isEnabled()
    opened: list[str] = []
    monkeypatch.setattr(
        "radio_video.ui.windows.main_window.QDesktopServices.openUrl",
        lambda url: opened.append(url.toLocalFile()),
    )
    page.open_requested.emit(0)
    assert [Path(p) for p in opened] == [saved]

    window._show_history_details(1)
    dialogs = [d for d in window.findChildren(FailedDialog) if d.isVisible()]
    assert dialogs and not dialogs[-1].action_button.isVisible()
    dialogs[-1].reject()

    monkeypatch.setattr(QuitDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    window.clear_history()
    assert window.history.records == ()
    assert page.empty.isVisibleTo(page) and not page.clear_button.isEnabled()


def test_when_text() -> None:
    today = date(2026, 11, 7)
    assert when_text(datetime(2026, 11, 7, 14, 32), today) == "Today, 14:32"
    assert when_text(datetime(2026, 11, 6, 9, 47), today) == "Yesterday, 09:47"
    assert when_text(datetime(2026, 10, 3, 16, 10), today) == "3 Oct 2026, 16:10"
