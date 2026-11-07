from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtMultimedia import QMediaPlayer
from pytestqt.qtbot import QtBot

from radio_video.models.media import MediaInfo
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


def _original(tmp_path: Path, media: MediaInfo = DEMO_MEDIA) -> PreviewWindow:
    request = replace(_request(kind=PreviewKind.ORIGINAL), contents=vm.original_contents(media))
    return PreviewWindow(tmp_path / "f.exe", replace(request, media=media), autoplay=False)


def test_original_player_plays_the_file_without_converting(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "clip.mkv"
    source.write_bytes(b"")
    preview = _original(tmp_path, replace(DEMO_MEDIA, path=source))
    qtbot.addWidget(preview)
    sources: list[str] = []
    monkeypatch.setattr(preview.player, "setSource", lambda url: sources.append(url.toLocalFile()))
    monkeypatch.setattr(
        preview.generator, "generate", lambda *args: pytest.fail("the original is not converted")
    )
    assert preview.phase is Phase.READY
    assert preview.start()
    assert [Path(p) for p in sources] == [source]
    assert preview.windowTitle() == "Original: clip.mkv"
    assert preview.part.text() == "The whole file, 2:13"
    assert preview.ready_note.text.text() == (
        "This is the file you opened, played as it is. Nothing was converted."
    )
    assert preview.side_size.text() == "186.4 MB"
    assert preview.area.currentWidget() is preview.canvas
    assert preview.player_bar.isVisibleTo(preview)
    assert preview.switch_button.text() == "Preview Converted"
    assert preview.convert_button.text() == "Convert"
    with qtbot.waitSignal(preview.switch_requested) as blocker:
        preview.switch_button.click()
    assert blocker.args == [PreviewKind.SAMPLE]


def test_original_contents_list_every_track() -> None:
    rows = dict(vm.original_contents(DEMO_MEDIA))
    assert rows["Container"] == "Matroska / WebM"
    assert rows["Video 1"].startswith("H.264")
    assert "Audio 1" in rows


def test_original_player_offers_a_converted_preview_when_it_cannot_play(
    qtbot: QtBot, tmp_path: Path
) -> None:
    preview = _original(tmp_path)
    qtbot.addWidget(preview)
    preview._on_player_error(QMediaPlayer.Error.FormatError, "Unsupported codec")
    assert preview.phase is Phase.FAILED
    assert preview.card_title.text() == "This file can’t be played here"
    assert preview.card_log.toPlainText() == "Unsupported codec"
    with qtbot.waitSignal(preview.switch_requested) as blocker:
        preview.card_action.click()
    assert blocker.args == [PreviewKind.SAMPLE]


def test_original_player_reports_a_moved_file(qtbot: QtBot, tmp_path: Path) -> None:
    preview = _original(tmp_path, replace(DEMO_MEDIA, path=tmp_path / "gone.mkv"))
    qtbot.addWidget(preview)
    assert not preview.start()
    assert preview.phase is Phase.FAILED


def test_original_player_while_converting_only_plays(qtbot: QtBot, tmp_path: Path) -> None:
    preview = _original(tmp_path)
    qtbot.addWidget(preview)
    preview.set_locked(True)
    assert not preview.switch_button.isEnabled()
    assert not preview.convert_button.isEnabled()
    preview.set_locked(False)
    assert preview.switch_button.isEnabled()


def test_original_audio_file_shows_the_audio_card(qtbot: QtBot, tmp_path: Path) -> None:
    audio_only = replace(DEMO_MEDIA, streams=DEMO_MEDIA.audio_streams[:1])
    preview = _original(tmp_path, audio_only)
    qtbot.addWidget(preview)
    assert preview.area.currentWidget() is preview.audio_card
    assert preview.audio_text.text() == vm.source_summary(audio_only)


def test_converted_preview_offers_the_original(window: PreviewWindow, qtbot: QtBot) -> None:
    window._on_canceled()
    assert window.switch_button.text() == "Play Original"
    with qtbot.waitSignal(window.switch_requested) as blocker:
        window.switch_button.click()
    assert blocker.args == [PreviewKind.ORIGINAL]
