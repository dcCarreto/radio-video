from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from radio_video.ffmpeg import FFmpegNotFoundError, FFmpegTools, probe
from radio_video.ffmpeg.capabilities import list_encoders
from radio_video.models.conversion import ConversionJob
from radio_video.models.hardware import NVENC, HardwareSupport
from radio_video.models.presets import OUTPUT_FORMATS, Quality
from radio_video.ui.demo import DEMO_MEDIA
from radio_video.ui.dialogs.failed_dialog import FailedDialog
from radio_video.ui.dialogs.quit_dialog import QuitDialog
from radio_video.ui.errors_map import NextStep
from radio_video.ui.state import Dialog, Drop, Job, PreviewKind, Progress, Screen
from radio_video.ui.windows.main_window import Engine, MainWindow

TIMEOUT_MS = 60000
ALL_ENCODERS = frozenset(e for fmt in OUTPUT_FORMATS for e in fmt.encoders)


@pytest.fixture
def settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


def _window(qtbot: QtBot, engine: Engine, settings: QSettings, **kwargs: object) -> MainWindow:
    window = MainWindow(engine, settings=settings, **kwargs)  # type: ignore[arg-type]
    qtbot.addWidget(window)
    return window


@pytest.fixture
def demo_window(qtbot: QtBot, settings: QSettings, tmp_path: Path) -> Iterator[MainWindow]:
    """A window showing the demo file without FFmpeg; services are never started."""
    engine = Engine(FFmpegTools(tmp_path / "ffmpeg.exe", tmp_path / "ffprobe.exe"), ALL_ENCODERS)
    window = _window(qtbot, engine, settings)
    source = tmp_path / DEMO_MEDIA.path.name
    source.write_bytes(b"")
    window.load_media(replace(DEMO_MEDIA, path=source), folder=tmp_path)
    yield window
    window.machine._state = window.machine.state.__class__()


def test_missing_engine_shows_setup_page(qtbot: QtBot, settings: QSettings) -> None:
    def missing() -> FFmpegTools:
        raise FFmpegNotFoundError("ffmpeg", "RADIO_VIDEO_FFMPEG")

    window = _window(qtbot, Engine(None), settings, locate=missing)
    page = window.convert_page
    assert window.machine.state.screen is Screen.MISSING
    assert page.views.currentWidget() is page.missing
    assert not page.steps.isVisibleTo(window)
    assert not window.open_action.isEnabled()
    assert window.status_item.text.text() == "Conversion engine not found"

    window.check_engine_again()
    assert page.missing.still_missing.isVisibleTo(window)


def test_engine_found_after_check_again(qtbot: QtBot, settings: QSettings, tmp_path: Path) -> None:
    tools = FFmpegTools(tmp_path / "ffmpeg.exe", tmp_path / "ffprobe.exe")
    window = _window(qtbot, Engine(None), settings, locate=lambda: tools)
    window.check_engine_again()
    assert window.machine.state.screen is Screen.START
    assert window.analyzer is not None


def test_copy_command(qtbot: QtBot, settings: QSettings, qapp: QApplication) -> None:
    window = _window(qtbot, Engine(None), settings)
    window.convert_page.missing.copy_button.click()
    clipboard = qapp.clipboard()
    assert clipboard is not None and clipboard.text() == "winget install --id Gyan.FFmpeg -e"
    assert window.convert_page.missing.copy_button.text() == "Copied"


def test_loaded_file_renders_source_and_panel(demo_window: MainWindow) -> None:
    window = demo_window
    page = window.convert_page
    assert page.views.currentWidget() is page.file
    assert window.windowTitle().endswith(".mkv · Radio/Video")
    source = page.file.source
    assert source.name.text() == DEMO_MEDIA.path.name
    assert source.summary.text().startswith("1 video track, 3 audio tracks")
    assert source.table.model().rowCount() == 12
    panel = page.file.panel
    assert panel.format.current_key() == "mp4-h264"
    assert panel.output.estimate_value.text() == "Depends on the content"
    assert panel.convert.isEnabled()
    assert page.steps.current() == 2
    assert window.mode_label.text() == "Simple Mode"


def test_lossless_format_replaces_quality_with_note(demo_window: MainWindow) -> None:
    panel = demo_window.convert_page.file.panel
    panel.format.set_current_key("flac")
    assert demo_window.machine.state.lossless
    assert panel.lossless_note.isVisibleTo(panel)
    assert not panel.quality.isVisibleTo(panel)
    panel.format.set_current_key("mp3")
    assert not panel.lossless_note.isVisibleTo(panel)
    assert panel.output.estimate_value.text().startswith("≈")
    assert "Extracts the audio" in panel.format_help.text()


def test_existing_output_name_gets_a_number(demo_window: MainWindow, tmp_path: Path) -> None:
    (tmp_path / f"{DEMO_MEDIA.path.stem}.mp4").write_bytes(b"")
    demo_window.machine.set_quality(Quality.HIGH)
    output = demo_window.convert_page.file.panel.output
    assert output.name.text().endswith(" (1).mp4")
    assert "so “(1)” was added" in output.bumped.text()


def test_converting_locks_settings_and_shows_progress(demo_window: MainWindow) -> None:
    machine = demo_window.machine
    machine.conversion_requested()
    machine.conversion_started()
    machine.conversion_progress(Progress(0.42, 3.1, 25))
    panel = demo_window.convert_page.file.panel
    source = demo_window.convert_page.file.source
    assert panel.footer_pages.currentWidget() is panel.progress
    assert panel.progress_text.text() == "42% · 3.1× · 0:25 remaining"
    assert not panel.format.isEnabled()
    assert not panel.quality.isEnabled()
    assert not source.open_button.isEnabled()
    assert source.paused.isVisibleTo(source)
    assert not demo_window.open_action.isEnabled()
    assert demo_window.status_item.text.text() == "Converting… 42%"

    machine.drag_over(accepted=True)
    assert machine.state.drop is Drop.BLOCKED
    file_view = demo_window.convert_page.file
    assert file_view.overlay_box.isVisibleTo(file_view)
    assert "paused while a conversion runs" in demo_window.overlay.blocked_text.text()


def test_success_and_canceled_footers(demo_window: MainWindow, tmp_path: Path) -> None:
    machine = demo_window.machine
    panel = demo_window.convert_page.file.panel
    machine.conversion_requested()
    machine.conversion_started()
    machine.conversion_succeeded(tmp_path / "clip.mp3", 124_000, 43)
    assert panel.footer_pages.currentWidget() is panel.result
    assert panel.result.title.text() == "Saved clip.mp3 (121.1 KB)"
    assert panel.result_primary.text() == "Show in Folder"
    assert demo_window.convert_page.steps.current() == 5
    machine.dismiss_result()

    machine.conversion_requested()
    machine.conversion_started()
    machine.conversion_progress(Progress(0.42))
    machine.conversion_canceled()
    assert panel.result.title.text() == "Conversion canceled"
    assert panel.result_help.text().startswith("Stopped at 42%.")
    assert panel.result_primary.text() == "Convert Again"


def test_failure_opens_dialog_with_next_step(demo_window: MainWindow, qtbot: QtBot) -> None:
    machine = demo_window.machine
    machine.conversion_requested()
    machine.conversion_started()
    machine.conversion_failed("No space left on device\nFFmpeg exited with code -28")
    dialog = demo_window._dialog
    assert isinstance(dialog, FailedDialog)
    assert dialog.report.action_text == "Choose Another Folder…"
    assert dialog.windowTitle() == "Radio/Video"
    dialog.reject()
    qtbot.waitUntil(lambda: machine.state.dialog is None)


def test_quit_while_converting_asks_and_keeps_converting(demo_window: MainWindow) -> None:
    machine = demo_window.machine
    machine.conversion_requested()
    machine.conversion_started()
    machine.conversion_progress(Progress(0.42))
    assert not demo_window.close()
    dialog = demo_window._dialog
    assert isinstance(dialog, QuitDialog)
    assert "is 42% done" in dialog.text.text()
    assert dialog.keep_button.hasFocus() or dialog.focusWidget() is dialog.keep_button
    dialog.reject()
    assert machine.state.job is Job.CONVERTING
    assert machine.state.dialog is None


def test_about_dialog(demo_window: MainWindow) -> None:
    demo_window.about_action.trigger()
    assert demo_window.machine.state.dialog is Dialog.ABOUT
    demo_window._dialog.reject()  # type: ignore[union-attr]
    assert demo_window.machine.state.dialog is None


def test_compact_layout_below_1200(demo_window: MainWindow, qtbot: QtBot) -> None:
    demo_window.resize(960, 720)
    demo_window.show()
    qtbot.waitExposed(demo_window)
    source = demo_window.convert_page.file.source
    assert source.open_button.text() == "Open…"
    assert source.table.compact
    demo_window.resize(1440, 900)
    qtbot.waitUntil(lambda: source.open_button.text() == "Open Another File…")


def test_keyboard_tab_shortcuts(demo_window: MainWindow, qtbot: QtBot) -> None:
    demo_window.show()
    with qtbot.waitActive(demo_window):
        demo_window.activateWindow()
    screens = []
    for key in (Qt.Key.Key_3, Qt.Key.Key_1):
        qtbot.keyClick(demo_window, key, Qt.KeyboardModifier.ControlModifier)
        screens.append(demo_window.machine.state.screen)
    assert screens == [Screen.HISTORY, Screen.MAIN]


@pytest.mark.ffmpeg
def test_opens_and_converts_a_file(
    qtbot: QtBot, ffmpeg_tools: FFmpegTools, sample_video: Path, settings: QSettings, tmp_path: Path
) -> None:
    engine = Engine(ffmpeg_tools, list_encoders(ffmpeg_tools.ffmpeg), "test")
    window = _window(qtbot, engine, settings)
    assert window.analyzer is not None and window.runner is not None
    with qtbot.waitSignal(window.analyzer.analyzed, timeout=TIMEOUT_MS):
        window.open_file(sample_video)
    assert window.machine.state.screen is Screen.MAIN
    assert window.convert_page.file.source.table.model().rowCount() == 3

    window.session.folder = tmp_path
    window.convert_page.file.panel.format.set_current_key("mp3")
    with qtbot.waitSignal(window.runner.succeeded, timeout=TIMEOUT_MS) as blocker:
        window.start_conversion()
    output = blocker.args[0]
    assert output == (tmp_path / "sample.mp3").resolve()
    assert window.machine.state.job is Job.SUCCESS
    assert probe(output, ffmpeg_tools.ffprobe).audio_streams[0].codec_name == "mp3"
    assert window.convert_page.file.panel.output.name.text() == "sample.mp3"
    window.machine.dismiss_result()
    assert window.convert_page.file.panel.output.name.text() == "sample (1).mp3"


@pytest.mark.ffmpeg
def test_preview_measures_size(
    qtbot: QtBot, ffmpeg_tools: FFmpegTools, sample_video: Path, settings: QSettings
) -> None:
    engine = Engine(ffmpeg_tools, list_encoders(ffmpeg_tools.ffmpeg), "test")
    window = _window(qtbot, engine, settings)
    assert window.analyzer is not None
    with qtbot.waitSignal(window.analyzer.analyzed, timeout=TIMEOUT_MS):
        window.open_file(sample_video)
    output = window.convert_page.file.panel.output
    assert output.estimate_value.text() == "Depends on the content"

    # CI runners have no audio device; Qt Multimedia can hang stopping audio playback there.
    window.preview_autoplay = False
    window.open_preview(PreviewKind.SAMPLE)
    preview = window.preview_window
    assert preview is not None
    with qtbot.waitSignal(preview.ready, timeout=TIMEOUT_MS):
        pass
    assert output.estimate_how.text() == "Measured from a preview."
    assert preview.convert_button.isVisibleTo(preview)
    window.machine.set_quality(Quality.HIGH)
    assert preview.outdated.isVisibleTo(preview)
    assert output.estimate_value.text() == "Depends on the content"
    preview.close()
    assert window.preview_window is None
    assert window.machine.state.preview is None


def test_advanced_mode_shows_planned_panel_with_summary(demo_window: MainWindow) -> None:
    demo_window.toggle_mode()
    state = demo_window.machine.state
    assert state.mode.value == "advanced"
    panel = demo_window.convert_page.file.panel
    assert panel.bodies.currentWidget() is panel.advanced
    assert panel.summary.isVisibleTo(panel)
    summary = panel.summary_text.text()
    assert summary.startswith("MP4 · H.264 x264 CRF 23 medium · 1920×1080")
    assert "3 × AAC 192 kb/s" in summary
    assert demo_window.mode_label.text() == "Advanced Mode"
    assert panel.convert.isEnabled()
    demo_window.toggle_mode()
    assert panel.bodies.currentIndex() == 0
    assert not panel.summary.isVisibleTo(panel)


def test_mode_is_locked_while_converting(demo_window: MainWindow) -> None:
    machine = demo_window.machine
    machine.conversion_requested()
    machine.conversion_started()
    demo_window.toggle_mode()
    assert machine.state.mode.value == "simple"


NVIDIA = HardwareSupport(NVENC, NVENC.encoders, "NVIDIA GeForce RTX 4070 SUPER")


def _started_jobs(window: MainWindow) -> list[ConversionJob]:
    jobs: list[ConversionJob] = []
    assert window.runner is not None
    window.runner.start = jobs.append  # type: ignore[method-assign,assignment]
    return jobs


def test_hardware_encoding_is_on_by_default_and_can_be_turned_off(
    demo_window: MainWindow, settings: QSettings
) -> None:
    demo_window.engine.hardware = NVIDIA
    jobs = _started_jobs(demo_window)
    demo_window.start_conversion()
    assert jobs[-1].settings.video is not None
    assert jobs[-1].settings.video.codec == "h264_nvenc"

    demo_window.machine._state = demo_window.machine.state.__class__(screen=Screen.MAIN)
    demo_window.settings_page.hardware_switch.setChecked(False)
    assert settings.value("performance/hardwareAcceleration", type=bool) is False
    demo_window.start_conversion()
    assert jobs[-1].settings.video is not None
    assert jobs[-1].settings.video.codec == "libx264"


def test_convert_with_software_after_a_hardware_failure(demo_window: MainWindow) -> None:
    demo_window.engine.hardware = NVIDIA
    jobs = _started_jobs(demo_window)
    demo_window.follow_next_step(NextStep.CONVERT_WITH_SOFTWARE)
    assert jobs[-1].settings.video is not None
    assert jobs[-1].settings.video.codec == "libx264"

    demo_window.machine._state = demo_window.machine.state.__class__(screen=Screen.MAIN)
    demo_window.start_conversion()
    assert jobs[-1].settings.video is not None
    assert jobs[-1].settings.video.codec == "h264_nvenc"


def test_hardware_detection_runs_in_the_background(
    qtbot: QtBot, settings: QSettings, tmp_path: Path
) -> None:
    tools = FFmpegTools(tmp_path / "ffmpeg.exe", tmp_path / "ffprobe.exe")
    window = _window(
        qtbot, Engine(tools, ALL_ENCODERS), settings, detect_hardware=lambda *_: NVIDIA
    )
    help_label = window.settings_page.hardware_help
    qtbot.waitUntil(lambda: window.engine.hardware_checked, timeout=TIMEOUT_MS)
    assert window.engine.hardware is NVIDIA
    assert help_label.text().startswith("Detected: NVIDIA GeForce RTX 4070 SUPER (NVENC).")

    window = _window(qtbot, Engine(tools, ALL_ENCODERS), settings, detect_hardware=lambda *_: None)
    qtbot.waitUntil(lambda: window.engine.hardware_checked, timeout=TIMEOUT_MS)
    assert window.settings_page.hardware_help.text().startswith("No supported graphics card")


def test_play_opens_the_original_and_stays_available_while_converting(
    demo_window: MainWindow,
) -> None:
    # CI runners have no audio device; Qt Multimedia can hang stopping audio playback there.
    demo_window.preview_autoplay = False
    machine = demo_window.machine
    machine.conversion_requested()
    machine.conversion_started()
    demo_window.convert_page.file.source.play_button.click()
    preview = demo_window.preview_window
    assert preview is not None and preview.original
    assert machine.state.dialog is Dialog.PREVIEW
    assert not preview.switch_button.isEnabled()
    # A converted preview waits for the conversion and leaves the player open.
    demo_window.open_preview(PreviewKind.SAMPLE)
    assert demo_window.preview_window is preview
    machine.conversion_canceled()
    assert preview.switch_button.isEnabled()
    preview.close()
    assert demo_window.preview_window is None
    assert machine.state.preview is None
