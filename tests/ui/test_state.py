from __future__ import annotations

from pathlib import Path

from radio_video.models.presets import Quality
from radio_video.ui.state import (
    STEP_CHOOSE,
    STEP_CONVERT,
    STEP_OPEN,
    STEPS_DONE,
    Dialog,
    Drop,
    EscapeAction,
    Job,
    Mode,
    Page,
    PreviewKind,
    PreviewPhase,
    Progress,
    Screen,
    StateMachine,
    UiState,
)

SOURCE = Path("C:/videos/clip.mkv")


# Reading state through functions keeps mypy from narrowing properties across transitions.
def _screen(machine: StateMachine) -> Screen:
    return machine.state.screen


def _phase(machine: StateMachine) -> PreviewPhase | None:
    preview = machine.state.preview
    return preview.phase if preview is not None else None


def _loaded() -> StateMachine:
    machine = StateMachine()
    machine.analysis_started(SOURCE)
    machine.file_opened(SOURCE)
    return machine


def _converting() -> StateMachine:
    machine = _loaded()
    machine.conversion_requested()
    machine.conversion_started()
    machine.conversion_progress(Progress(0.42, 3.1, 25))
    return machine


def test_initial_state_is_start_screen() -> None:
    state = StateMachine().state
    assert state.screen is Screen.START
    assert state.step == STEP_OPEN
    assert state.page is Page.CONVERT


def test_listeners_see_every_change() -> None:
    seen: list[UiState] = []
    machine = StateMachine(on_change=seen.append)
    machine.drag_over(accepted=True)
    machine.drag_left()
    assert [s.drop for s in seen] == [Drop.OVER, Drop.IDLE]


def test_opening_a_file_shows_the_main_screen() -> None:
    machine = StateMachine()
    machine.analysis_started(SOURCE)
    assert machine.state.analyzing
    machine.file_opened(SOURCE)
    state = machine.state
    assert state.screen is Screen.MAIN
    assert state.has_file and not state.analyzing
    assert state.step == STEP_CHOOSE


def test_refused_drop_shows_blocked_state() -> None:
    machine = StateMachine()
    machine.drag_over(accepted=False)
    assert machine.state.drop is Drop.BLOCKED


def test_engine_missing_and_found() -> None:
    machine = StateMachine()
    machine.engine_missing()
    assert _screen(machine) is Screen.MISSING
    assert not machine.can_open()
    assert machine.go(Page.CONVERT)
    assert _screen(machine) is Screen.MISSING
    machine.engine_found()
    assert _screen(machine) is Screen.START


def test_conversion_locks_settings_and_opening() -> None:
    machine = _converting()
    state = machine.state
    assert state.job is Job.CONVERTING
    assert state.step == STEP_CONVERT
    assert state.progress.fraction == 0.42
    assert not machine.can_open()
    assert not machine.set_format("mp3", lossless=False)
    assert not machine.set_quality(Quality.HIGH)
    assert not machine.set_mode(Mode.ADVANCED)
    assert not machine.preview_requested(PreviewKind.SAMPLE)
    assert not machine.file_opened(Path("C:/videos/other.mkv"))
    machine.drag_over(accepted=True)
    assert machine.state.drop is Drop.BLOCKED
    assert machine.state.format_key == "mp4-h264"


def test_conversion_success_and_dismiss() -> None:
    machine = _converting()
    machine.conversion_succeeded(Path("C:/videos/clip.mp4"), 1000, 43.0)
    state = machine.state
    assert state.job is Job.SUCCESS
    assert state.step == STEPS_DONE
    assert state.output == Path("C:/videos/clip.mp4")
    assert machine.dismiss_result()
    assert machine.state.job is Job.IDLE


def test_conversion_failure_opens_dialog_and_unlocks() -> None:
    machine = _converting()
    machine.conversion_failed("No space left on device")
    state = machine.state
    assert state.dialog is Dialog.FAILED
    assert state.job is Job.IDLE
    assert state.error == "No space left on device"
    assert machine.can_open()
    machine.close_dialog()
    assert machine.state.dialog is None
    assert machine.state.error is None


def test_cancel_keeps_progress_for_the_message() -> None:
    machine = _converting()
    machine.conversion_canceled()
    assert machine.state.job is Job.CANCELED
    assert machine.state.progress.fraction == 0.42


def test_changing_settings_clears_a_finished_result() -> None:
    machine = _converting()
    machine.conversion_canceled()
    machine.set_quality(Quality.HIGH)
    assert machine.state.job is Job.IDLE


def test_quit_while_converting_asks_first() -> None:
    machine = _converting()
    assert not machine.close_requested()
    assert machine.state.dialog is Dialog.QUIT
    machine.close_dialog()
    assert machine.state.dialog is None
    assert machine.state.job is Job.CONVERTING
    assert _loaded().close_requested()


def test_preview_measures_size_for_the_same_settings_only() -> None:
    machine = _loaded()
    machine.preview_requested(PreviewKind.SAMPLE)
    assert machine.state.dialog is Dialog.PREVIEW
    assert machine.state.previewing
    machine.preview_progress(Progress(0.64))
    machine.preview_ready(22_000_000)
    state = machine.state
    assert state.preview is not None and state.preview.phase is PreviewPhase.READY
    assert state.measured_size == 22_000_000
    assert state.step == STEP_CONVERT

    machine.preview_closed()
    machine.set_quality(Quality.SMALL)
    assert machine.state.measured_size is None
    machine.set_quality(Quality.BALANCED)
    assert machine.state.measured_size == 22_000_000
    machine.set_format("mp3", lossless=False)
    assert machine.state.measured_size is None


def test_lossless_measurement_ignores_quality() -> None:
    machine = _loaded()
    machine.set_format("flac", lossless=True)
    machine.preview_requested(PreviewKind.SAMPLE)
    machine.preview_ready(31_000_000)
    machine.preview_closed()
    machine.set_quality(Quality.HIGH)
    assert machine.state.measured_size == 31_000_000


def test_opening_another_file_forgets_measurements() -> None:
    machine = _loaded()
    machine.preview_requested(PreviewKind.SAMPLE)
    machine.preview_ready(1)
    machine.preview_closed()
    machine.file_opened(Path("C:/videos/other.mkv"))
    assert machine.state.measured == {}


def test_settings_change_marks_open_preview_outdated() -> None:
    machine = _loaded()
    machine.preview_requested(PreviewKind.FULL)
    machine.preview_ready(None)
    assert not machine.preview_outdated()
    machine.set_quality(Quality.HIGH)
    assert machine.preview_outdated()


def test_preview_failure_and_cancel() -> None:
    machine = _loaded()
    machine.preview_requested(PreviewKind.SAMPLE)
    machine.preview_failed()
    assert _phase(machine) is PreviewPhase.FAILED
    assert not machine.preview_canceled()
    machine.preview_requested(PreviewKind.SAMPLE)
    machine.preview_canceled()
    assert _phase(machine) is PreviewPhase.CANCELED
    assert machine.state.measured_size is None


def test_escape_priorities() -> None:
    machine = _loaded()
    assert machine.escape_action() is EscapeAction.NONE
    machine.preview_requested(PreviewKind.SAMPLE)
    assert machine.escape_action() is EscapeAction.CANCEL_PREVIEW
    machine.preview_canceled()
    assert machine.escape_action() is EscapeAction.CLOSE_DIALOG
    machine.preview_closed()
    machine.conversion_requested()
    assert machine.escape_action() is EscapeAction.CANCEL_CONVERSION
    machine.close_requested()
    assert machine.escape_action() is EscapeAction.CLOSE_DIALOG


def test_tabs_navigate_between_pages() -> None:
    machine = _loaded()
    machine.go(Page.HISTORY)
    assert _screen(machine) is Screen.HISTORY
    assert machine.state.page is Page.HISTORY
    machine.go(Page.CONVERT)
    assert _screen(machine) is Screen.MAIN
