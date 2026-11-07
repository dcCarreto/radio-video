"""The Settings tab with the main window: every setting acts and is kept."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from pytestqt.qtbot import QtBot

from radio_video.ffmpeg import FFmpegTools
from radio_video.ffmpeg.capabilities import list_encoders, program_version
from radio_video.models.presets import OUTPUT_FORMATS, Quality
from radio_video.ui import theme
from radio_video.ui.demo import DEMO_MEDIA
from radio_video.ui.state import Page, PreviewKind
from radio_video.ui.theme.tokens import Scheme
from radio_video.ui.windows.main_window import (
    FFMPEG_KEY,
    FFPROBE_KEY,
    Engine,
    MainWindow,
    chosen_tools,
)

ALL_ENCODERS = frozenset(e for fmt in OUTPUT_FORMATS for e in fmt.encoders)


def _settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> Iterator[MainWindow]:
    engine = Engine(FFmpegTools(tmp_path / "ffmpeg.exe", tmp_path / "ffprobe.exe"), ALL_ENCODERS)
    main = MainWindow(engine, settings=_settings(tmp_path), history_path=tmp_path / "h.json")
    qtbot.addWidget(main)
    yield main
    main.machine._state = main.machine.state.__class__()
    theme.current().set_override(None)


def _open(window: MainWindow, tmp_path: Path, audio_only: bool = False) -> None:
    source = tmp_path / ("song.flac" if audio_only else DEMO_MEDIA.path.name)
    source.write_bytes(b"")
    media = replace(DEMO_MEDIA, path=source)
    if audio_only:
        media = replace(media, streams=DEMO_MEDIA.audio_streams)
    window.load_media(media)


def test_new_files_start_with_the_defaults(window: MainWindow, tmp_path: Path) -> None:
    page = window.settings_page
    page.video_format.set_current_key("mkv-h264")
    page.audio_format.set_current_key("opus")
    page.quality.set_value("high")
    _open(window, tmp_path)
    state = window.machine.state
    assert (state.format_key, state.quality) == ("mkv-h264", Quality.HIGH)
    _open(window, tmp_path, audio_only=True)
    assert window.machine.state.format_key == "opus"


def test_save_in_the_same_folder_as_the_original(window: MainWindow, tmp_path: Path) -> None:
    window.settings_page.save_same.setChecked(True)
    _open(window, tmp_path)
    assert window.session.folder == tmp_path
    assert window.settings.value("defaults/saveMode") == "same"


def test_chosen_ffmpeg_is_checked_and_kept(
    window: MainWindow, tmp_path: Path, ffmpeg_tools: FFmpegTools
) -> None:
    impostor = tmp_path / "notepad.exe"
    impostor.write_bytes(b"")
    assert not window.set_engine_program("ffmpeg", impostor)
    view = window.settings_view()
    assert view.engine_note_warning and "didn’t answer as ffmpeg" in view.engine_note

    assert window.set_engine_program("ffmpeg", ffmpeg_tools.ffmpeg)
    # ffprobe from the same folder is taken along.
    assert chosen_tools(window.settings) == ffmpeg_tools
    view = window.settings_view()
    assert view.engine_note == "Restart Radio/Video to switch to the FFmpeg chosen here."
    assert view.engine_chosen
    window.settings_page.automatic_button.click()
    assert window.settings.value(FFMPEG_KEY) is None and window.settings.value(FFPROBE_KEY) is None


def test_choosing_ffmpeg_when_missing_starts_the_engine(
    qtbot: QtBot, tmp_path: Path, ffmpeg_tools: FFmpegTools
) -> None:
    main = MainWindow(Engine(None), settings=_settings(tmp_path), history_path=tmp_path / "h.json")
    qtbot.addWidget(main)
    main.machine.go(Page.SETTINGS)
    assert not main.settings_page.view or not main.settings_page.view.engine_working
    assert main.set_engine_program("ffmpeg", ffmpeg_tools.ffmpeg)
    assert main.engine.available
    assert main.engine.encoders == list_encoders(ffmpeg_tools.ffmpeg)
    assert main.settings_page.view is not None and main.settings_page.view.engine_working


def test_previews_use_the_chosen_temporary_folder(window: MainWindow, tmp_path: Path) -> None:
    temp = tmp_path / "previews"
    temp.mkdir()
    window._save_setting("files/temporaryFolder", str(temp))
    assert window.preview_temp_root() == temp
    _open(window, tmp_path)
    window.preview_autoplay = False
    window.open_preview(PreviewKind.SAMPLE)
    assert window.preview_window is not None
    assert window.preview_window.generator.temp_root == temp
    window.preview_window.close()
    window.settings_page.temp_row.reset.click()  # type: ignore[union-attr]
    assert window.preview_temp_root() is None


def test_theme_applies_at_once_and_is_kept(window: MainWindow) -> None:
    window.settings_page.theme.set_value("dark")
    assert theme.current().override is Scheme.DARK
    assert window.settings.value("appearance/theme") == "dark"
    window.settings_page.theme.set_value("system")
    assert theme.current().override is None


def test_program_version_tells_ffmpeg_from_ffprobe(ffmpeg_tools: FFmpegTools) -> None:
    assert program_version(ffmpeg_tools.ffmpeg, "ffmpeg")
    assert program_version(ffmpeg_tools.ffprobe, "ffprobe")
    assert program_version(ffmpeg_tools.ffmpeg, "ffprobe") is None
