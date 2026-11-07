"""UI state machine for the main window, free of Qt so it can be tested directly.

Mirrors the design prototype: a screen, the drop zone, the conversion job, the preview and
the open dialog. Widgets render a :class:`UiState`; services report events through the
methods of :class:`StateMachine`, which refuse transitions the design does not allow (for
example opening a file while converting) and return whether the event was applied.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path

from radio_video.models.presets import Quality


class Screen(Enum):
    START = "start"
    MISSING = "missing"
    MAIN = "main"
    QUEUE = "queue"
    HISTORY = "history"
    SETTINGS = "settings"


class Page(Enum):
    """Main tabs. ``CONVERT`` shows the start, missing or main screen."""

    CONVERT = "main"
    QUEUE = "queue"
    HISTORY = "history"
    SETTINGS = "settings"


class Drop(Enum):
    IDLE = "idle"
    OVER = "over"
    BLOCKED = "blocked"


class Job(Enum):
    IDLE = "idle"
    STARTING = "starting"
    CONVERTING = "converting"
    SUCCESS = "success"
    CANCELED = "canceled"


class PreviewPhase(Enum):
    CREATING = "creating"
    READY = "ready"
    FAILED = "failed"
    CANCELED = "canceled"


class PreviewKind(Enum):
    SAMPLE = "sample"
    FULL = "full"
    # The opened file played as it is: nothing is converted, so it is ready at once.
    ORIGINAL = "original"


class Dialog(Enum):
    PREVIEW = "preview"
    FAILED = "failed"
    QUIT = "quit"
    ABOUT = "about"


class Mode(Enum):
    SIMPLE = "simple"
    ADVANCED = "advanced"


class EscapeAction(Enum):
    NONE = "none"
    CANCEL_PREVIEW = "cancel_preview"
    CLOSE_DIALOG = "close_dialog"
    CANCEL_CONVERSION = "cancel_conversion"


# Steps in the strip: Open, Check, Choose, Preview, Convert; 5 means all done.
STEP_OPEN, STEP_CHECK, STEP_CHOOSE, STEP_PREVIEW, STEP_CONVERT, STEPS_DONE = range(6)


@dataclass(frozen=True)
class SettingsKey:
    """What a measured size is valid for: the same file, format and quality."""

    source: Path | None
    format_key: str
    quality: Quality | None


@dataclass(frozen=True)
class Progress:
    fraction: float = 0.0
    speed: float | None = None
    remaining: float | None = None


@dataclass(frozen=True)
class PreviewState:
    kind: PreviewKind
    phase: PreviewPhase
    progress: Progress = Progress()
    settings: SettingsKey | None = None


@dataclass(frozen=True)
class UiState:
    screen: Screen = Screen.START
    has_file: bool = False
    source: Path | None = None
    analyzing: bool = False
    drop: Drop = Drop.IDLE
    format_key: str = "mp4-h264"
    quality: Quality = Quality.BALANCED
    lossless: bool = False
    mode: Mode = Mode.SIMPLE
    advanced_tab: str = "video"
    job: Job = Job.IDLE
    progress: Progress = Progress()
    output: Path | None = None
    output_size: int | None = None
    took: float | None = None
    error: str | None = None
    dialog: Dialog | None = None
    preview: PreviewState | None = None
    measured: dict[SettingsKey, int] = field(default_factory=dict)

    @property
    def converting(self) -> bool:
        return self.job in (Job.STARTING, Job.CONVERTING)

    @property
    def page(self) -> Page:
        if self.screen in (Screen.START, Screen.MISSING, Screen.MAIN):
            return Page.CONVERT
        return Page(self.screen.value)

    @property
    def settings_key(self) -> SettingsKey:
        return SettingsKey(self.source, self.format_key, None if self.lossless else self.quality)

    @property
    def measured_size(self) -> int | None:
        """Size measured by a preview with exactly the current file, format and quality."""
        return self.measured.get(self.settings_key)

    @property
    def previewing(self) -> bool:
        return (
            self.dialog is Dialog.PREVIEW
            and self.preview is not None
            and self.preview.phase is PreviewPhase.CREATING
        )

    @property
    def locked(self) -> bool:
        """Settings, opening files and previews are locked while converting."""
        return self.converting

    @property
    def step(self) -> int:
        if self.screen is not Screen.MAIN:
            return STEP_OPEN
        if self.converting:
            return STEP_CONVERT
        if self.job is Job.SUCCESS:
            return STEPS_DONE
        if self.measured_size is not None:
            return STEP_CONVERT
        return STEP_CHOOSE


class StateMachine:
    """Holds the current :class:`UiState` and notifies a listener after every change."""

    def __init__(
        self, state: UiState | None = None, on_change: Callable[[UiState], None] | None = None
    ) -> None:
        self._state = state or UiState()
        self._listeners: list[Callable[[UiState], None]] = []
        if on_change is not None:
            self._listeners.append(on_change)

    @property
    def state(self) -> UiState:
        return self._state

    def subscribe(self, listener: Callable[[UiState], None]) -> None:
        self._listeners.append(listener)

    def _set(self, **changes: object) -> bool:
        self._state = replace(self._state, **changes)  # type: ignore[arg-type]
        for listener in list(self._listeners):
            listener(self._state)
        return True

    # Engine
    def engine_missing(self) -> bool:
        return self._set(screen=Screen.MISSING)

    def engine_found(self) -> bool:
        if self._state.screen is not Screen.MISSING:
            return False
        return self._set(screen=Screen.MAIN if self._state.has_file else Screen.START)

    # Opening files
    def can_open(self) -> bool:
        return not self._state.converting and self._state.screen is not Screen.MISSING

    def drag_over(self, accepted: bool) -> bool:
        if not accepted or not self.can_open():
            return self._set(drop=Drop.BLOCKED)
        return self._set(drop=Drop.OVER)

    def drag_left(self) -> bool:
        return self._set(drop=Drop.IDLE)

    def analysis_started(self, path: Path) -> bool:
        if not self.can_open():
            return self._set(drop=Drop.BLOCKED)
        return self._set(analyzing=True, drop=Drop.IDLE, screen=self._convert_screen())

    def analysis_failed(self) -> bool:
        return self._set(analyzing=False)

    def file_opened(
        self, path: Path, *, format_key: str | None = None, lossless: bool | None = None
    ) -> bool:
        if self._state.converting:
            return False
        return self._set(
            screen=Screen.MAIN,
            has_file=True,
            source=path,
            analyzing=False,
            drop=Drop.IDLE,
            job=Job.IDLE,
            progress=Progress(),
            output=None,
            error=None,
            dialog=None,
            preview=None,
            measured={},
            format_key=format_key or self._state.format_key,
            lossless=self._state.lossless if lossless is None else lossless,
        )

    # Navigation
    def go(self, page: Page) -> bool:
        if page is Page.CONVERT:
            return self._set(screen=self._convert_screen())
        return self._set(screen=Screen(page.value))

    def _convert_screen(self) -> Screen:
        if self._state.screen is Screen.MISSING:
            return Screen.MISSING
        return Screen.MAIN if self._state.has_file else Screen.START

    # Settings (locked while converting)
    def set_mode(self, mode: Mode) -> bool:
        if self._state.locked:
            return False
        return self._set(mode=mode)

    def set_advanced_tab(self, tab: str) -> bool:
        return self._set(advanced_tab=tab)

    def set_format(self, key: str, *, lossless: bool) -> bool:
        if self._state.locked:
            return False
        job = Job.IDLE if self._state.job in (Job.SUCCESS, Job.CANCELED) else self._state.job
        return self._set(format_key=key, lossless=lossless, job=job)

    def set_quality(self, quality: Quality) -> bool:
        if self._state.locked:
            return False
        job = Job.IDLE if self._state.job in (Job.SUCCESS, Job.CANCELED) else self._state.job
        return self._set(quality=quality, job=job)

    # Conversion
    def conversion_requested(self) -> bool:
        if self._state.screen is not Screen.MAIN or self._state.converting:
            return False
        return self._set(job=Job.STARTING, progress=Progress(), dialog=None, error=None)

    def conversion_started(self) -> bool:
        if self._state.job is not Job.STARTING:
            return False
        return self._set(job=Job.CONVERTING)

    def conversion_progress(self, progress: Progress) -> bool:
        if not self._state.converting:
            return False
        return self._set(job=Job.CONVERTING, progress=progress)

    def conversion_succeeded(self, output: Path, size: int | None, took: float) -> bool:
        if not self._state.converting:
            return False
        dialog = None if self._state.dialog is Dialog.QUIT else self._state.dialog
        return self._set(
            job=Job.SUCCESS,
            progress=Progress(1.0),
            output=output,
            output_size=size,
            took=took,
            dialog=dialog,
        )

    def conversion_failed(self, error: str) -> bool:
        if not self._state.converting:
            return False
        return self._set(job=Job.IDLE, error=error, dialog=Dialog.FAILED)

    def conversion_canceled(self) -> bool:
        if not self._state.converting:
            return False
        dialog = None if self._state.dialog is Dialog.QUIT else self._state.dialog
        return self._set(job=Job.CANCELED, dialog=dialog)

    def dismiss_result(self) -> bool:
        if self._state.job not in (Job.SUCCESS, Job.CANCELED):
            return False
        return self._set(job=Job.IDLE, progress=Progress())

    # Previews
    def preview_requested(self, kind: PreviewKind) -> bool:
        if self._state.screen is not Screen.MAIN:
            return False
        if kind is PreviewKind.ORIGINAL:
            # Playing the file only reads it, so it stays available while converting.
            preview = PreviewState(kind, PreviewPhase.READY, Progress(1.0))
            return self._set(dialog=Dialog.PREVIEW, preview=preview)
        if self._state.locked:
            return False
        preview = PreviewState(kind, PreviewPhase.CREATING, settings=self._state.settings_key)
        return self._set(dialog=Dialog.PREVIEW, preview=preview)

    def preview_progress(self, progress: Progress) -> bool:
        preview = self._state.preview
        if preview is None or preview.phase is not PreviewPhase.CREATING:
            return False
        return self._set(preview=replace(preview, progress=progress))

    def preview_ready(self, measured_full_size: int | None) -> bool:
        preview = self._state.preview
        if preview is None or preview.phase is not PreviewPhase.CREATING:
            return False
        measured = dict(self._state.measured)
        if measured_full_size is not None and preview.settings is not None:
            measured[preview.settings] = measured_full_size
        return self._set(
            preview=replace(preview, phase=PreviewPhase.READY, progress=Progress(1.0)),
            measured=measured,
        )

    def preview_failed(self) -> bool:
        preview = self._state.preview
        if preview is None or preview.phase is not PreviewPhase.CREATING:
            return False
        return self._set(preview=replace(preview, phase=PreviewPhase.FAILED))

    def preview_canceled(self) -> bool:
        preview = self._state.preview
        if preview is None or preview.phase is not PreviewPhase.CREATING:
            return False
        return self._set(preview=replace(preview, phase=PreviewPhase.CANCELED))

    def preview_outdated(self) -> bool:
        """True when the settings changed after the preview was made."""
        preview = self._state.preview
        return (
            preview is not None
            and preview.kind is not PreviewKind.ORIGINAL
            and preview.settings != self._state.settings_key
        )

    def preview_closed(self) -> bool:
        if self._state.dialog is not Dialog.PREVIEW:
            return False
        return self._set(dialog=None, preview=None)

    # Dialogs and quitting
    def show_about(self) -> bool:
        return self._set(dialog=Dialog.ABOUT)

    def close_dialog(self) -> bool:
        if self._state.dialog is None:
            return False
        error = None if self._state.dialog is Dialog.FAILED else self._state.error
        return self._set(dialog=None, error=error)

    def close_requested(self) -> bool:
        """Returns True when the window may close now; otherwise asks first."""
        if self._state.converting:
            self._set(dialog=Dialog.QUIT)
            return False
        return True

    def escape_action(self) -> EscapeAction:
        """Esc cancels a preview being created, closes a dialog, or cancels a conversion.

        Canceling is safe and reversible, so Esc never asks first.
        """
        state = self._state
        if state.previewing:
            return EscapeAction.CANCEL_PREVIEW
        if state.dialog is not None:
            return EscapeAction.CLOSE_DIALOG
        if state.converting:
            return EscapeAction.CANCEL_CONVERSION
        return EscapeAction.NONE
