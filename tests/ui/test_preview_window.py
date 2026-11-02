from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from radio_video.models.presets import Quality, format_by_key
from radio_video.ui import viewmodel as vm
from radio_video.ui.demo import DEMO_MEDIA
from radio_video.ui.state import PreviewKind
from radio_video.ui.windows.preview_window import Phase, PreviewRequest, PreviewWindow


def _request(key: str = "mp4-h264", kind: PreviewKind = PreviewKind.SAMPLE) -> PreviewRequest:
    fmt = format_by_key(key)
    return PreviewRequest(
        DEMO_MEDIA,
        fmt,
        Quality.BALANCED,
        kind,
        vm.output_contents(fmt, DEMO_MEDIA, fmt.plan(DEMO_MEDIA)),
    )


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> Iterator[PreviewWindow]:
    preview = PreviewWindow(tmp_path / "ffmpeg.exe", _request(), autoplay=False)
    qtbot.addWidget(preview)
    yield preview


def test_creating_state_explains_what_is_converted(window: PreviewWindow) -> None:
    assert window.phase is Phase.CREATING
    assert window.windowTitle() == f"Converted preview: {DEMO_MEDIA.path.stem}"
    assert window.card_title.text() == "Creating the preview…"
    assert window.card_text.text() == "Converting a 15-second sample with your exact settings."
    assert window.card_action.text() == "Cancel"
    assert not window.convert_button.isVisibleTo(window)
    assert not window.player_bar.isVisibleTo(window)
    assert window.side_estimate.text() == "Measured when the preview is ready"


def test_whole_file_part_text(qtbot: QtBot, tmp_path: Path) -> None:
    preview = PreviewWindow(tmp_path / "f.exe", _request(kind=PreviewKind.FULL), autoplay=False)
    qtbot.addWidget(preview)
    assert preview.part.text() == "The whole file, 2:13"


def test_failure_names_the_time_when_the_source_is_damaged(qtbot: QtBot, tmp_path: Path) -> None:
    # The source must exist, otherwise the failure reads as "the original was moved".
    source = tmp_path / "clip.mkv"
    source.write_bytes(b"")
    request = replace(_request(), media=replace(DEMO_MEDIA, path=source))
    preview = PreviewWindow(tmp_path / "f.exe", request, autoplay=False)
    qtbot.addWidget(preview)
    preview._last_time = 24.0
    preview._show_failure("Invalid data found when processing input")
    assert preview.phase is Phase.FAILED
    assert preview.card_title.text() == "The preview couldn’t be created"
    assert preview.card_text.text().startswith("FFmpeg stopped while reading the file around 0:24.")
    assert preview.card_action.text() == "Try Again"


def test_canceled_state_offers_to_create_again(window: PreviewWindow, qtbot: QtBot) -> None:
    window._on_canceled()
    assert window.phase is Phase.CANCELED
    assert window.card_text.text() == "Nothing was saved. Your settings haven’t changed."
    with qtbot.waitSignal(window.retry_requested) as blocker:
        window.card_action.click()
    assert blocker.args == [PreviewKind.SAMPLE]


def test_escape_cancels_creation(
    window: PreviewWindow, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    canceled: list[bool] = []
    monkeypatch.setattr(window.generator, "cancel", lambda: canceled.append(True))
    qtbot.keyClick(window, Qt.Key.Key_Escape)
    assert canceled == [True]


def test_audio_preview_describes_the_track(qtbot: QtBot, tmp_path: Path) -> None:
    preview = PreviewWindow(tmp_path / "f.exe", _request("mp3"), autoplay=False)
    qtbot.addWidget(preview)
    assert preview.audio_text.text() == "MP3, Balanced · Track 1 (Portuguese), stereo"
