"""Main window: connects the services to the state machine and renders the state."""

from __future__ import annotations

import contextlib
import logging
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime
from functools import partial
from pathlib import Path

from PySide6.QtCore import (
    QProcess,
    QRectF,
    QRunnable,
    QSettings,
    QStandardPaths,
    Qt,
    QThreadPool,
    QUrl,
    Signal,
    SignalInstance,
    Slot,
)
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDesktopServices,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QKeySequence,
    QPaintEvent,
    QResizeEvent,
    QShortcut,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from radio_video.ffmpeg.capabilities import CapabilityError, ffmpeg_version, list_encoders
from radio_video.ffmpeg.locator import FFmpegNotFoundError, FFmpegTools, locate_tools
from radio_video.ffmpeg.progress import ProgressUpdate
from radio_video.models.advanced import AdvancedChoices, EncoderChoice, Recipe, resolve
from radio_video.models.conversion import ConversionJob, ConversionSettings
from radio_video.models.estimate import estimate_output_size
from radio_video.models.hardware import HardwareSupport, accelerate
from radio_video.models.media import MediaInfo
from radio_video.models.presets import OutputFormat, available_formats, format_by_key
from radio_video.services.analysis import MediaAnalyzer
from radio_video.services.conversion import ConversionError, ConversionRunner
from radio_video.services.history import HistoryRecord, HistoryResult, HistoryStore
from radio_video.services.queue import ConversionQueue, FileReader, QueueEntry, QueueStatus
from radio_video.ui import icons, theme
from radio_video.ui import strings as s
from radio_video.ui import viewmodel as vm
from radio_video.ui.dialogs.about_dialog import AboutDialog
from radio_video.ui.dialogs.failed_dialog import FailedDialog
from radio_video.ui.dialogs.quit_dialog import QuitDialog
from radio_video.ui.errors_map import Failure, NextStep, describe
from radio_video.ui.file_types import open_file_filter
from radio_video.ui.native.dwm import style_title_bar
from radio_video.ui.native.notify import Notifier
from radio_video.ui.native.taskbar import TaskbarProgress, TaskbarState
from radio_video.ui.pages.advanced_panel import AdvancedView, output_summary
from radio_video.ui.pages.convert_page import ConvertPage
from radio_video.ui.pages.convert_panel import PanelView
from radio_video.ui.pages.history_page import HistoryPage
from radio_video.ui.pages.history_page import row_view as history_row
from radio_video.ui.pages.planned_pages import SettingsPage
from radio_video.ui.pages.queue_page import QueuePage, QueueView, counts_text, row_view
from radio_video.ui.pages.start_view import make_drop_zone
from radio_video.ui.state import (
    Dialog,
    Drop,
    EscapeAction,
    Job,
    Mode,
    Page,
    PreviewKind,
    Progress,
    Screen,
    StateMachine,
    UiState,
)
from radio_video.ui.strings import tr
from radio_video.ui.theme.fonts import TextStyle
from radio_video.ui.theme.tokens import Palette
from radio_video.ui.widgets.button import ButtonKind
from radio_video.ui.widgets.drop_zone import DropState, check_drop, dropped_paths
from radio_video.ui.widgets.labels import label
from radio_video.ui.widgets.painting import antialiased, fill_rounded, follow_theme
from radio_video.ui.widgets.progress import Spinner
from radio_video.ui.widgets.tab_strip import TabSpec, TabStrip
from radio_video.ui.windows.preview_window import PreviewRequest, PreviewWindow
from radio_video.utils.formatting import format_duration, format_size

logger = logging.getLogger(__name__)

COMPACT_BELOW = 1200
# Client sizes; with the 32 px title bar the window is 960×720 and 1440×900.
MIN_SIZE = (960, 688)
DEFAULT_SIZE = (1440, 868)
STATUS_HEIGHT = 26
STATUS_MESSAGE_MS = 5000
LAST_FOLDER_KEY = "convert/lastFolder"
HARDWARE_KEY = "performance/hardwareAcceleration"
PAGE_INDEX = {Page.CONVERT: 0, Page.QUEUE: 1, Page.HISTORY: 2, Page.SETTINGS: 3}


@dataclass
class Engine:
    """The FFmpeg installation the window works with."""

    tools: FFmpegTools | None
    encoders: frozenset[str] = frozenset()
    version: str | None = None
    hardware: HardwareSupport | None = None
    hardware_checked: bool = False

    @property
    def available(self) -> bool:
        return self.tools is not None


HardwareDetector = Callable[[Path, frozenset[str]], HardwareSupport | None]


class _HardwareTask(QRunnable):
    """Runs the hardware test encodes off the UI thread."""

    def __init__(
        self,
        found: SignalInstance,
        request: int,
        detect: HardwareDetector,
        ffmpeg: Path,
        encoders: frozenset[str],
    ) -> None:
        super().__init__()
        self._found = found
        self._request = request
        self._detect = detect
        self._ffmpeg = ffmpeg
        self._encoders = encoders

    def run(self) -> None:
        try:
            support = self._detect(self._ffmpeg, self._encoders)
        except Exception:
            logger.exception("Hardware encoder detection failed")
            support = None
        # RuntimeError: the window closed while the test encodes ran.
        with contextlib.suppress(RuntimeError):
            self._found.emit(self._request, support)


@dataclass
class _Session:
    media: MediaInfo | None = None
    folder: Path | None = None
    started_at: float = 0.0
    destination: Path | None = None
    # What the running conversion was started with, for the history.
    format_key: str = ""
    quality: str | None = None
    custom: bool = False
    existing: set[Path] = field(default_factory=set)


class _Dot(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.tone = "success"
        self.setFixedSize(8, 8)
        follow_theme(self)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        fill_rounded(painter, QRectF(self.rect()), 4, theme.palette().color(self.tone))


class _StatusItem(QWidget):
    """Left side of the status bar: a dot or spinner and a short status."""

    def __init__(self) -> None:
        super().__init__()
        self.dot = _Dot()
        self.spinner = Spinner(12, "text_2")
        self.text = label("", TextStyle.CAPTION, "secondary")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.dot)
        layout.addWidget(self.spinner)
        layout.addWidget(self.text)

    def show_status(self, text: str, *, busy: bool, ok: bool = True) -> None:
        self.text.setText(text)
        self.spinner.setVisible(busy)
        self.dot.setVisible(not busy)
        self.dot.tone = "success" if ok else "warning"
        self.dot.update()
        self.setAccessibleName(text)


class MainWindow(QMainWindow):
    _hardware_found = Signal(int, object)

    def __init__(
        self,
        engine: Engine,
        *,
        settings: QSettings | None = None,
        locate: Callable[[], FFmpegTools] = locate_tools,
        detect_hardware: HardwareDetector | None = None,
        history_path: Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.engine = engine
        self.settings = settings or QSettings()
        self._locate = locate
        self._detect_hardware = detect_hardware
        self._hardware_request = 0
        # Set by "Convert with Software" after the graphics card encoder failed.
        self._software_next = False
        self.session = _Session()
        self.machine = StateMachine()
        self.history = HistoryStore(history_path or default_history_path())
        self._dialog: QDialog | None = None
        self._dialog_kind: Dialog | None = None
        self.preview_window: PreviewWindow | None = None
        self._compact: bool | None = None
        self._quitting = False
        self._last_job: Job | None = None
        # Replaceable so the UI gallery can show the design's demo states without files.
        self.output_namer: Callable[[Path, MediaInfo, OutputFormat], vm.OutputName] = vm.output_name
        self.folder_writable: Callable[[Path], bool] = _writable
        # Previews start playing when ready; tests on machines without audio turn this off.
        self.preview_autoplay = True

        self.setWindowTitle(tr(s.APP_NAME))
        self.setWindowIcon(icons.app_icon())
        self.setMinimumSize(*MIN_SIZE)
        self.resize(*DEFAULT_SIZE)
        self.setAcceptDrops(True)

        self.analyzer: MediaAnalyzer | None = None
        self.runner: ConversionRunner | None = None
        self.queue: ConversionQueue | None = None
        self.reader: FileReader | None = None
        # Files dragged over the window, to word the drop overlay.
        self._drag_count = 1
        self._create_services()
        self._create_ui()
        self._create_actions()
        self._create_shortcuts()
        self.taskbar = TaskbarProgress(self)
        self.notifier = Notifier(self)
        self.notifier.activated.connect(self._bring_to_front)
        self._hardware_found.connect(self._on_hardware_found)
        self._start_hardware_detection()

        self.machine.subscribe(self._render)
        if not engine.available:
            self.machine.engine_missing()
        else:
            self._render(self.machine.state)
        theme.current().changed.connect(self._on_theme_changed)

    # Setup
    def _create_services(self) -> None:
        tools = self.engine.tools
        if tools is None:
            return
        self.analyzer = MediaAnalyzer(tools.ffprobe, parent=self)
        self.analyzer.started.connect(self.machine.analysis_started)
        self.analyzer.analyzed.connect(self._on_analyzed)
        self.analyzer.failed.connect(self._on_analysis_failed)
        self.runner = ConversionRunner(tools.ffmpeg, parent=self)
        self.runner.started.connect(self._on_conversion_started)
        self.runner.progress.connect(self._on_conversion_progress)
        self.runner.succeeded.connect(self._on_conversion_succeeded)
        self.runner.failed.connect(self._on_conversion_failed)
        self.runner.canceled.connect(self._on_conversion_canceled)
        # The queue has its own runner; only one of the two converts at a time.
        self.queue = ConversionQueue(
            ConversionRunner(tools.ffmpeg, parent=self), self._queue_job, parent=self
        )
        self.queue.changed.connect(self._render_queue)
        self.queue.progressed.connect(self._on_queue_progress)
        self.queue.run_finished.connect(self._on_queue_finished)
        self.queue.entry_finished.connect(self._record_queue_entry)
        self.reader = FileReader(tools.ffprobe, parent=self)
        self.reader.read.connect(self._on_queue_file_read)

    def _create_ui(self) -> None:
        self.tabs = TabStrip(
            [
                TabSpec("main", tr(s.TAB_CONVERT), "ArrowRightLeft"),
                TabSpec("queue", tr(s.TAB_QUEUE), "ListOrdered"),
                TabSpec("history", tr(s.TAB_HISTORY), "History"),
                TabSpec(
                    "settings", tr(s.TAB_SETTINGS), "Settings", True, tr(s.BADGE_PLANNED), True
                ),
            ]
        )
        self.tabs.current_changed.connect(lambda key: self.machine.go(Page(key)))

        self.drop_zone = make_drop_zone(lambda: not self.machine.can_open())
        self.drop_zone.open_requested.connect(self.open_file_dialog)
        self.drop_zone.file_dropped.connect(self.open_file)
        self.drop_zone.files_dropped.connect(self.add_files_to_queue)
        self.overlay = make_drop_zone(show_open_button=False)
        self.convert_page = ConvertPage(self.drop_zone, self.overlay)
        page = self.convert_page
        page.missing.check_again.connect(self.check_engine_again)
        page.file.source.open_requested.connect(self.open_file_dialog)
        page.file.source.play_requested.connect(lambda: self.open_preview(PreviewKind.ORIGINAL))
        panel = page.file.panel
        panel.mode_changed.connect(self._on_mode_changed)
        panel.format_changed.connect(self._on_format_changed)
        panel.quality_changed.connect(self.machine.set_quality)
        panel.browse_requested.connect(self.choose_folder)
        panel.preview_requested.connect(self.open_preview)
        panel.convert_requested.connect(self.start_conversion)
        panel.cancel_requested.connect(self.cancel_conversion)
        panel.show_in_folder_requested.connect(self.show_output_in_folder)
        panel.done_requested.connect(self.machine.dismiss_result)
        panel.reset_requested.connect(self.machine.reset_advanced)
        panel.queue_requested.connect(self.add_current_to_queue)
        panel.advanced.choices_changed.connect(self.machine.set_advanced)
        panel.advanced.format_changed.connect(self._on_format_changed)

        self.pages = QStackedWidget()
        self.pages.addWidget(self.convert_page)
        self.queue_page = QueuePage()
        self.queue_page.add_requested.connect(self.add_files_dialog)
        self.queue_page.start_requested.connect(self.start_queue)
        self.queue_page.stop_requested.connect(self.stop_queue)
        self.queue_page.pause_toggled.connect(self._on_queue_pause)
        self.queue_page.move_requested.connect(self._on_queue_move)
        self.queue_page.retry_requested.connect(self._on_queue_retry)
        self.queue_page.remove_requested.connect(self._on_queue_remove)
        self.queue_page.clear_requested.connect(self._on_queue_clear)
        self.history_page = HistoryPage()
        self.history_page.open_requested.connect(self._open_history_output)
        self.history_page.show_requested.connect(self._show_history_output)
        self.history_page.details_requested.connect(self._show_history_details)
        self.history_page.clear_requested.connect(self.clear_history)
        self.settings_page = SettingsPage(
            self.engine.tools, self.engine.version, hardware_enabled=self.hardware_enabled
        )
        self.settings_page.hardware_changed.connect(self._on_hardware_changed)
        for page_widget in (self.queue_page, self.history_page, self.settings_page):
            self.pages.addWidget(page_widget)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.tabs)
        layout.addWidget(self.pages, 1)
        self.setCentralWidget(central)

        status = self.statusBar()
        status.setSizeGripEnabled(False)
        status.setFixedHeight(STATUS_HEIGHT)
        self.status_item = _StatusItem()
        self.mode_label = label("", TextStyle.CAPTION, "secondary")
        self.mode_label.setContentsMargins(0, 0, 12, 0)
        status.addWidget(self.status_item, 1)
        status.addPermanentWidget(self.mode_label)

    def _create_actions(self) -> None:
        self.open_action = QAction(tr(s.ACTION_OPEN), self)
        self.open_action.setShortcut(QKeySequence("Ctrl+O"))
        self.open_action.setIcon(icons.icon("FolderOpen", theme.palette().text))
        self.open_action.triggered.connect(self.open_file_dialog)
        self.exit_action = QAction(tr(s.ACTION_EXIT), self)
        self.exit_action.setShortcut(QKeySequence("Alt+F4"))
        self.exit_action.triggered.connect(self.close)
        self.about_action = QAction(tr(s.ACTION_ABOUT), self)
        self.about_action.setShortcut(QKeySequence("F1"))
        self.about_action.triggered.connect(self.machine.show_about)
        self.about_qt_action = QAction(tr(s.ACTION_ABOUT_QT), self)
        self.about_qt_action.triggered.connect(QApplication.aboutQt)

        file_menu = self.menuBar().addMenu(tr(s.MENU_FILE))
        file_menu.addAction(self.open_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)
        help_menu = self.menuBar().addMenu(tr(s.MENU_HELP))
        help_menu.addAction(self.about_action)
        help_menu.addAction(self.about_qt_action)

    def _create_shortcuts(self) -> None:
        def shortcut(keys: str, handler: Callable[[], object]) -> None:
            QShortcut(QKeySequence(keys), self, activated=handler)  # type: ignore[call-overload]

        shortcut("Ctrl+Return", self.start_conversion)
        shortcut("Ctrl+Enter", self.start_conversion)
        shortcut("Ctrl+Shift+Return", self.add_current_to_queue)
        shortcut("Ctrl+Shift+Enter", self.add_current_to_queue)
        shortcut("Ctrl+P", lambda: self.open_preview(PreviewKind.SAMPLE))
        shortcut("Ctrl+Shift+P", lambda: self.open_preview(PreviewKind.FULL))
        shortcut("Ctrl+Shift+Space", lambda: self.open_preview(PreviewKind.ORIGINAL))
        shortcut("Esc", self._on_escape)
        shortcut("Ctrl+M", self.toggle_mode)
        for number, page in enumerate(PAGE_INDEX, start=1):
            shortcut(f"Ctrl+{number}", partial(self.tabs.set_current, page.value))

    # Rendering
    def _render(self, state: UiState) -> None:
        media = self.session.media
        self.tabs.blockSignals(True)
        self.tabs.set_current(state.page.value)
        self.tabs.blockSignals(False)
        self.pages.setCurrentIndex(PAGE_INDEX[state.page])
        if state.page is Page.HISTORY:
            self._render_history()

        page = self.convert_page
        if state.screen is Screen.MISSING:
            page.show_view(page.missing)
        elif state.screen is Screen.START or media is None:
            page.show_view(page.start)
            if state.analyzing:
                self.drop_zone.set_state(DropState.READING)
            elif state.drop is Drop.IDLE and self.drop_zone.state is DropState.READING:
                self.drop_zone.set_state(DropState.IDLE)
        else:
            page.show_view(page.file)
            self._render_file(state, media)
        page.steps.set_current(state.step)

        self.open_action.setEnabled(self.machine.can_open())
        self.setWindowTitle(
            tr(s.WINDOW_TITLE_FILE).format(name=media.path.name)
            if media is not None and state.has_file
            else tr(s.APP_NAME)
        )
        if self.preview_window is not None:
            self.preview_window.set_outdated(self.machine.preview_outdated())
            self.preview_window.set_locked(state.locked)
        self._render_status(state)
        self._render_taskbar(state)
        self._render_dialog(state)

    def _render_file(self, state: UiState, media: MediaInfo) -> None:
        file_view = self.convert_page.file
        file_view.source.set_converting(state.converting)
        overlay = state.drop in (Drop.OVER, Drop.BLOCKED)
        if overlay:
            reason = (
                tr(s.DROP_BLOCKED_CONVERTING) if state.converting else tr(s.DROP_BLOCKED_SEVERAL)
            )
            self.overlay.set_state(
                DropState.OVER if state.drop is Drop.OVER else DropState.BLOCKED,
                reason,
                self._drag_count,
            )
        file_view.set_overlay_visible(overlay)
        previous_job = self._last_job
        advanced = state.mode is Mode.ADVANCED
        if advanced:
            file_view.panel.advanced.show_view(self.advanced_view(state, media))
        file_view.set_advanced(advanced)
        file_view.panel.apply_view(self.panel_view(state, media))
        if previous_job is not state.job:
            target = file_view.panel.focus_after_render()
            if target is not None:
                target.setFocus(Qt.FocusReason.OtherFocusReason)
        self._last_job = state.job

    def advanced_view(self, state: UiState, media: MediaInfo) -> AdvancedView:
        fmt = self.current_format(state)
        recipe = self.recipe(state, media)
        formats = available_formats(self.engine.encoders, media.has_video)
        return AdvancedView(
            media=media,
            fmt=fmt,
            quality=state.quality,
            choices=state.advanced,
            recipe=recipe,
            final=self.final_settings(recipe, state),
            groups=vm.format_groups(formats, media.has_video),
            formats=formats,
            encoders=frozenset(self.engine.encoders),
            hardware=self.engine.hardware,
            hardware_on=self.hardware_enabled,
            locked=state.locked,
        )

    def panel_view(self, state: UiState, media: MediaInfo) -> PanelView:
        formats = available_formats(self.engine.encoders, media.has_video)
        fmt = self.current_format(state)
        recipe = self.recipe(state, media)
        folder = self.session.folder or media.path.parent
        if state.job is Job.SUCCESS and state.output is not None:
            name = vm.OutputName(state.output, None)
        else:
            name = self.output_namer(folder, media, fmt)
        estimate = vm.estimate(fmt, state.quality, media, state.measured_size, recipe)
        result_title = result_text = ""
        if state.job is Job.SUCCESS and state.output is not None:
            result_title = tr(s.SUCCESS_TITLE).format(
                name=state.output.name, size=format_size(state.output_size)
            )
            result_text = tr(s.SUCCESS_TEXT).format(
                folder=str(state.output.parent), time=format_duration(state.took)
            )
        elif state.job is Job.CANCELED:
            result_text = tr(s.CANCELED_TEXT).format(percent=vm.percent(state.progress.fraction))
        return PanelView(
            groups=vm.format_groups(formats, media.has_video),
            format_key=fmt.key,
            format_help=vm.format_help(fmt, media.has_video),
            lossless=fmt.lossless,
            quality=state.quality,
            folder=str(folder),
            folder_error="" if self.folder_writable(folder) else tr(s.FOLDER_NOT_WRITABLE),
            output_name=name.path.name,
            output_is_video=fmt.is_video,
            bumped_text=vm.name_bumped_text(name),
            contents=vm.output_contents(fmt, media, recipe.streams, recipe.settings),
            estimate=estimate,
            job=state.job,
            mode=state.mode,
            what=vm.format_and_quality(fmt, state.quality),
            progress_text=vm.progress_detail(state.progress),
            fraction=state.progress.fraction,
            speed_tip=vm.speed_tooltip(state.progress.speed),
            result_title=result_title,
            result_text=result_text,
            summary=output_summary(
                media,
                fmt,
                recipe,
                self.final_settings(recipe, state),
                estimate.value if estimate.known else tr(s.ADV_SIZE_AFTER_PREVIEW),
            )
            if state.mode is Mode.ADVANCED
            else "",
            custom=not state.advanced.is_default,
            queue_busy=self.queue is not None and self.queue.running,
        )

    def _render_status(self, state: UiState) -> None:
        if state.screen is Screen.MISSING:
            self.status_item.show_status(tr(s.STATUS_ENGINE_MISSING), busy=False, ok=False)
        elif state.converting:
            percent = vm.percent(state.progress.fraction)
            self.status_item.show_status(tr(s.STATUS_CONVERTING).format(percent=percent), busy=True)
        elif self.queue is not None and self.queue.running:
            self.status_item.show_status(self._queue_status_text(), busy=True)
        elif state.previewing and state.preview is not None:
            percent = vm.percent(state.preview.progress.fraction)
            self.status_item.show_status(tr(s.STATUS_PREVIEWING).format(percent=percent), busy=True)
        else:
            text = tr(s.STATUS_ENGINE_READY).format(version=self.engine.version or "")
            self.status_item.show_status(text.rstrip(), busy=False)
        on_main = state.screen is Screen.MAIN
        self.mode_label.setVisible(on_main)
        self.mode_label.setText(
            tr(s.STATUS_SIMPLE_MODE if state.mode is Mode.SIMPLE else s.STATUS_ADVANCED_MODE)
        )

    def _render_taskbar(self, state: UiState) -> None:
        if self.queue is not None and self.queue.running and not state.converting:
            self.taskbar.set_state(TaskbarState.NORMAL)
            self.taskbar.set_fraction(self.queue.overall_fraction())
        elif state.job is Job.STARTING:
            self.taskbar.set_state(TaskbarState.INDETERMINATE)
        elif state.job is Job.CONVERTING:
            self.taskbar.set_state(TaskbarState.NORMAL)
            self.taskbar.set_fraction(state.progress.fraction)
        elif state.dialog is Dialog.FAILED:
            self.taskbar.set_state(TaskbarState.ERROR)
            self.taskbar.set_fraction(1.0)
        else:
            self.taskbar.set_state(TaskbarState.NONE)

    def _render_dialog(self, state: UiState) -> None:
        wanted = state.dialog if state.dialog is not Dialog.PREVIEW else None
        if wanted is self._dialog_kind:
            return
        if self._dialog is not None:
            current, self._dialog, self._dialog_kind = self._dialog, None, None
            current.done(QDialog.DialogCode.Rejected)
        if wanted is None:
            return
        dialog = self._make_dialog(wanted, state)
        if dialog is None:
            return
        self._dialog, self._dialog_kind = dialog, wanted
        dialog.finished.connect(
            lambda result, d=dialog, k=wanted: self._on_dialog_finished(d, k, result)
        )
        dialog.open()

    def _make_dialog(self, kind: Dialog, state: UiState) -> QDialog | None:
        media = self.session.media
        if kind is Dialog.ABOUT:
            return AboutDialog(self)
        if kind is Dialog.QUIT:
            name = self.session.destination.name if self.session.destination else ""
            return QuitDialog.for_conversion(name, vm.percent(state.progress.fraction), self)
        if kind is Dialog.FAILED and media is not None:
            return FailedDialog(describe(self.failure_for(state, media)), parent=self)
        return None

    @property
    def open_dialog(self) -> QDialog | None:
        return self._dialog

    def failure_for(self, state: UiState, media: MediaInfo) -> Failure:
        recipe = self.recipe(state, media)
        calculated = estimate_output_size(recipe.settings, media, recipe.streams)
        return Failure(
            details=state.error or "",
            source=media.path,
            destination=self.session.destination,
            fraction=state.progress.fraction,
            needed_bytes=calculated or state.measured_size,
        )

    def _on_dialog_finished(self, dialog: QDialog, kind: Dialog, result: int) -> None:
        if dialog is not self._dialog:
            return
        self._dialog, self._dialog_kind = None, None
        accepted = result == QDialog.DialogCode.Accepted
        if kind is Dialog.FAILED and isinstance(dialog, FailedDialog):
            self.machine.close_dialog()
            if accepted:
                self.follow_next_step(dialog.report.next_step)
        elif kind is Dialog.QUIT:
            self.machine.close_dialog()
            if accepted:
                self._quitting = True
                self.cancel_conversion()
                if self.runner is not None:
                    self.runner.wait()
                self.close()
        else:
            self.machine.close_dialog()
        dialog.deleteLater()

    def follow_next_step(self, step: NextStep) -> None:
        if step is NextStep.CHOOSE_FOLDER:
            self.choose_folder()
        elif step in (NextStep.OPEN_FILE, NextStep.OPEN_ANOTHER):
            self.open_file_dialog()
        elif step is NextStep.CHOOSE_FORMAT:
            combo = self.convert_page.file.panel.format
            combo.setFocus(Qt.FocusReason.OtherFocusReason)
            combo.showPopup()
        elif step is NextStep.CONVERT_WITH_SOFTWARE:
            self._software_next = True
            self.start_conversion()
        elif step is NextStep.TRY_AGAIN:
            self.start_conversion()

    # Settings
    def current_format(self, state: UiState | None = None) -> OutputFormat:
        state = state or self.machine.state
        media = self.session.media
        formats = available_formats(self.engine.encoders, media.has_video if media else True)
        keys = [fmt.key for fmt in formats]
        if state.format_key in keys:
            return format_by_key(state.format_key)
        return formats[0] if formats else format_by_key(state.format_key)

    def _on_format_changed(self, key: str) -> None:
        self.machine.set_format(key, lossless=format_by_key(key).lossless)

    def _on_mode_changed(self, mode: Mode) -> None:
        if not self.machine.set_mode(mode):
            self.convert_page.file.panel.mode.set_value(self.machine.state.mode.value)

    def toggle_mode(self) -> None:
        if self.machine.state.screen is Screen.MAIN:
            mode = Mode.SIMPLE if self.machine.state.mode is Mode.ADVANCED else Mode.ADVANCED
            self.machine.set_mode(mode)

    def default_folder(self, media: MediaInfo) -> Path:
        saved = str(self.settings.value(LAST_FOLDER_KEY, "") or "")
        if saved and Path(saved).is_dir():
            return Path(saved)
        location = (
            QStandardPaths.StandardLocation.MoviesLocation
            if media.has_video
            else QStandardPaths.StandardLocation.MusicLocation
        )
        folder = QStandardPaths.writableLocation(location)
        return Path(folder) if folder else media.path.parent

    @Slot()
    def choose_folder(self) -> None:
        if self.machine.state.locked:
            return
        start = str(self.session.folder or "")
        folder = QFileDialog.getExistingDirectory(self, tr(s.BROWSE_TOOLTIP), start)
        if folder:
            self.session.folder = Path(folder)
            self.settings.setValue(LAST_FOLDER_KEY, folder)
            self._render(self.machine.state)

    # Opening files
    @Slot()
    def open_file_dialog(self) -> None:
        if not self.machine.can_open():
            self.statusBar().showMessage(tr(s.DROP_BLOCKED_CONVERTING), STATUS_MESSAGE_MS)
            return
        start = str(self.session.media.path.parent) if self.session.media else ""
        filename, _ = QFileDialog.getOpenFileName(
            self, tr(s.ACTION_OPEN).rstrip("…"), start, open_file_filter()
        )
        if filename:
            self.open_file(Path(filename))

    @Slot(Path)
    def open_file(self, path: Path) -> None:
        if self.analyzer is None or not self.machine.can_open():
            return
        self.analyzer.analyze(path)

    def load_media(self, media: MediaInfo, folder: Path | None = None) -> None:
        """Show an analyzed file. Also used by the UI gallery with demo media."""
        self.session.media = media
        self.session.folder = folder or self.default_folder(media)
        formats = available_formats(self.engine.encoders, media.has_video)
        keys = [fmt.key for fmt in formats]
        key = self.machine.state.format_key
        if keys and key not in keys:
            key = keys[0]
        self.machine.file_opened(media.path, format_key=key, lossless=format_by_key(key).lossless)
        self.convert_page.file.source.set_media(media)
        self.convert_page.file.panel.format.setFocus(Qt.FocusReason.OtherFocusReason)

    @Slot(MediaInfo)
    def _on_analyzed(self, media: MediaInfo) -> None:
        self.load_media(media)

    @Slot(Path, str)
    def _on_analysis_failed(self, path: Path, message: str) -> None:
        self.machine.analysis_failed()
        self.drop_zone.set_state(DropState.IDLE)
        report = describe(Failure(details=message, source=path))
        dialog = FailedDialog(report, report.what_happened, reassure=False, parent=self)
        dialog.finished.connect(
            lambda result: result == QDialog.DialogCode.Accepted and self.open_file_dialog()
        )
        dialog.finished.connect(dialog.deleteLater)
        dialog.open()

    # Drag and drop over the window
    def _drag_allowed(self) -> bool:
        return self.machine.state.screen in (Screen.MAIN, Screen.QUEUE)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if not self._drag_allowed() or not event.mimeData().hasUrls():
            return
        event.accept()
        paths = dropped_paths(event)
        self._drag_count = len(paths)
        refusal = check_drop(paths, not self.machine.can_open())
        if self.machine.state.screen is Screen.QUEUE and paths:
            # On the Queue tab every file goes to the queue.
            refusal = check_drop([*paths, *paths], busy=False)
        self.machine.drag_over(accepted=refusal is None)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802
        if self.machine.state.drop is Drop.OVER:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:  # noqa: N802
        self.machine.drag_left()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        paths = dropped_paths(event)
        to_queue = len(paths) > 1 or self.machine.state.screen is Screen.QUEUE
        allowed = check_drop(paths, busy=not to_queue and not self.machine.can_open()) is None
        self.machine.drag_left()
        if allowed:
            event.acceptProposedAction()
            if to_queue:
                self.add_files_to_queue(paths)
            else:
                self.open_file(paths[0])

    # Conversion
    @Slot()
    def start_conversion(self) -> None:
        software, self._software_next = self._software_next, False
        media = self.session.media
        if media is None or self.runner is None:
            return
        state = self.machine.state
        if state.screen is not Screen.MAIN or state.converting or self._dialog is not None:
            return
        if self.queue is not None and self.queue.running:
            self.statusBar().showMessage(tr(s.CONVERT_BLOCKED_QUEUE), STATUS_MESSAGE_MS)
            return
        fmt = self.current_format(state)
        folder = self.session.folder or media.path.parent
        if not self.folder_writable(folder):
            return
        name = self.output_namer(folder, media, fmt)
        if not self.machine.conversion_requested():
            return
        self.session.destination = name.path
        self.session.started_at = time.monotonic()
        self.session.format_key = fmt.key
        self.session.quality = None if fmt.lossless else state.quality.value
        self.session.custom = not state.advanced.is_default
        try:
            recipe = self.recipe(state, media)
            job = ConversionJob(
                source=media.path,
                destination=name.path,
                settings=self.final_settings(recipe, state, software=software),
                duration=media.duration,
                streams=recipe.streams,
            )
            self.runner.start(job)
        except (ConversionError, ValueError, OSError) as exc:
            self.machine.conversion_started()
            self.machine.conversion_failed(str(exc))
            return
        self.notifier.conversion_started()

    @Slot()
    def cancel_conversion(self) -> None:
        if self.runner is not None and self.runner.is_running:
            self.runner.cancel()

    @Slot(ConversionJob)
    def _on_conversion_started(self, _job: ConversionJob) -> None:
        self.machine.conversion_started()

    @Slot(ProgressUpdate)
    def _on_conversion_progress(self, update: ProgressUpdate) -> None:
        job = self.runner.job if self.runner is not None else None
        duration = job.expected_duration if job is not None else None
        fraction = update.fraction(duration)
        if fraction is None:
            return
        self.machine.conversion_progress(
            Progress(fraction, update.speed, update.remaining_seconds(duration))
        )

    @Slot(Path)
    def _on_conversion_succeeded(self, output: Path) -> None:
        size = output.stat().st_size if output.exists() else None
        took = time.monotonic() - self.session.started_at
        self.machine.conversion_succeeded(output, size, took)
        self._record(HistoryResult.SAVED, output=output, size=size, took=took)
        self.notifier.conversion_finished(output.name)
        if self._quitting:
            self.close()

    @Slot(str)
    def _on_conversion_failed(self, message: str) -> None:
        self._record(HistoryResult.FAILED, error=message)
        self.machine.conversion_failed(message)
        self.notifier.conversion_failed()

    @Slot()
    def _on_conversion_canceled(self) -> None:
        self._record(HistoryResult.CANCELED, fraction=self.machine.state.progress.fraction)
        self.machine.conversion_canceled()
        self.notifier.conversion_stopped()

    @Slot()
    def show_output_in_folder(self) -> None:
        output = self.machine.state.output
        if output is None:
            return
        show_in_folder(output)

    # Previews
    def open_preview(self, kind: PreviewKind) -> None:
        media = self.session.media
        if media is None or self.engine.tools is None:
            return
        original = kind is PreviewKind.ORIGINAL
        if self.machine.state.locked and not original:
            # Keep the open window: a converted preview has to wait for the conversion.
            return
        if self.preview_window is not None:
            self.preview_window.close()
        if not self.machine.preview_requested(kind):
            return
        state = self.machine.state
        fmt = self.current_format(state)
        if original:
            request = PreviewRequest(
                media=media,
                fmt=fmt,
                quality=state.quality,
                kind=kind,
                contents=vm.original_contents(media),
            )
        else:
            recipe = self.recipe(state, media)
            request = PreviewRequest(
                media=media,
                fmt=fmt,
                quality=state.quality,
                kind=kind,
                contents=vm.output_contents(fmt, media, recipe.streams, recipe.settings),
                calculated_size=estimate_output_size(recipe.settings, media, recipe.streams),
                settings=self.final_settings(recipe, state),
                streams=recipe.streams,
            )
        window = PreviewWindow(
            self.engine.tools.ffmpeg,
            request,
            compact=bool(self._compact),
            autoplay=self.preview_autoplay,
            parent=self,
        )
        window.progress.connect(self.machine.preview_progress)
        window.ready.connect(self.machine.preview_ready)
        window.failed.connect(self.machine.preview_failed)
        window.canceled.connect(self.machine.preview_canceled)
        window.closed.connect(lambda w=window: self._on_preview_closed(w))
        window.retry_requested.connect(self.open_preview)
        window.switch_requested.connect(self.open_preview)
        window.convert_requested.connect(self._convert_from_preview)
        window.set_locked(state.locked)
        self.preview_window = window
        window.show()
        window.start()

    def _on_preview_closed(self, window: PreviewWindow) -> None:
        if window is self.preview_window:
            self.preview_window = None
            self.machine.preview_closed()

    def _convert_from_preview(self) -> None:
        if self.preview_window is not None:
            self.preview_window.close()
        self.start_conversion()

    # Queue
    def add_current_to_queue(self) -> None:
        """Queue the open file with the current format, quality and Advanced choices."""
        media = self.session.media
        state = self.machine.state
        if self.queue is None or media is None or state.screen is not Screen.MAIN:
            return
        folder = self.session.folder or media.path.parent
        if not self.folder_writable(folder):
            return
        fmt = self.current_format(state)
        self.queue.add(media.path, fmt.key, state.quality, state.advanced, folder, media)
        self.statusBar().showMessage(
            tr(s.QUEUE_ADDED).format(name=media.path.name), STATUS_MESSAGE_MS
        )

    def add_files_dialog(self) -> None:
        start = str(self.session.media.path.parent) if self.session.media else ""
        filenames, _ = QFileDialog.getOpenFileNames(
            self, tr(s.QUEUE_ADD_DIALOG), start, open_file_filter()
        )
        if filenames:
            self.add_files_to_queue([Path(name) for name in filenames])

    def add_files_to_queue(self, paths: list[Path]) -> None:
        """Read the files in the background; each one joins the queue when read."""
        if self.reader is None:
            return
        self.reader.read_files(paths)
        self.machine.go(Page.QUEUE)

    @Slot(Path, object)
    def _on_queue_file_read(self, path: Path, result: MediaInfo | str) -> None:
        if self.queue is None:
            return
        state = self.machine.state
        # Track choices belong to the open file; the rest carries over.
        choices = replace(state.advanced, tracks=None)
        if isinstance(result, MediaInfo):
            formats = available_formats(self.engine.encoders, result.has_video)
            keys = [fmt.key for fmt in formats]
            key = state.format_key if state.format_key in keys else (keys[0] if keys else "")
            folder = self.session.folder or self.default_folder(result)
            if key:
                self.queue.add(path, key, state.quality, choices, folder, result)
                return
            result = tr(s.QUEUE_CANT_READ)
        self.queue.add(path, state.format_key, state.quality, choices, path.parent, None, result)

    def _queue_job(self, entry: QueueEntry) -> ConversionJob:
        media = entry.media
        if media is None:
            raise ValueError(entry.error or tr(s.QUEUE_CANT_READ))
        if not self.folder_writable(entry.folder):
            raise ValueError(tr(s.FOLDER_NOT_WRITABLE))
        fmt = format_by_key(entry.format_key)
        recipe = resolve(fmt, entry.quality, media, entry.choices)
        return ConversionJob(
            source=entry.path,
            destination=self.output_namer(entry.folder, media, fmt).path,
            settings=self.final_settings_for(recipe, entry.choices),
            duration=media.duration,
            streams=recipe.streams,
        )

    def start_queue(self) -> None:
        if self.queue is None or self.machine.state.converting:
            return
        if self.queue.start():
            self.notifier.conversion_started()

    def stop_queue(self) -> None:
        if self.queue is not None:
            self.queue.stop()

    def _on_queue_pause(self, pause: bool) -> None:
        if self.queue is not None:
            self.queue.pause_after_current = pause

    def _on_queue_move(self, entry_id: int, delta: int) -> None:
        if self.queue is not None:
            self.queue.move(entry_id, delta)

    def _on_queue_retry(self, entry_id: int) -> None:
        if self.queue is not None:
            self.queue.retry(entry_id)

    def _on_queue_remove(self, entry_id: int) -> None:
        if self.queue is not None:
            self.queue.remove(entry_id)

    def _on_queue_clear(self) -> None:
        if self.queue is not None:
            self.queue.clear_finished()

    def queue_view(self) -> QueueView:
        queue = self.queue
        if queue is None:
            return QueueView((), False, False, tr(s.STATUS_ENGINE_MISSING), False, None, 0, 0, "")
        entries = queue.entries
        current = queue.current
        position = (
            next(i for i, e in enumerate(entries, start=1) if e.id == current.id)
            if current is not None
            else None
        )
        blocked = ""
        if self.machine.state.converting:
            blocked = tr(s.QUEUE_START_BLOCKED)
        elif not queue.can_start():
            blocked = tr(s.QUEUE_NOTHING_WAITING)
        return QueueView(
            rows=tuple(row_view(entry) for entry in entries),
            running=queue.running,
            can_start=queue.can_start() and not self.machine.state.converting,
            start_blocked=blocked,
            pause_after=queue.pause_after_current,
            current=position,
            total=len(entries),
            fraction=queue.overall_fraction(),
            counts=counts_text(queue.counts()),
        )

    def _render_queue(self) -> None:
        self.queue_page.show_view(self.queue_view())
        queue = self.queue
        active = 0
        if queue is not None:
            counts = queue.counts()
            active = counts.waiting + counts.converting
        label = tr(s.QUEUE_TAB_COUNT).format(count=active) if active else tr(s.TAB_QUEUE)
        self.tabs.set_label("queue", label)
        state = self.machine.state
        if state.screen is Screen.MAIN and self.session.media is not None:
            self.convert_page.file.panel.apply_view(self.panel_view(state, self.session.media))
        self._render_status(state)
        self._render_taskbar(state)

    @Slot(int)
    def _on_queue_progress(self, entry_id: int) -> None:
        queue = self.queue
        entry = queue.entry(entry_id) if queue is not None else None
        if queue is None or entry is None:
            return
        self.queue_page.update_row(row_view(entry), queue.overall_fraction())
        self._render_status(self.machine.state)
        self._render_taskbar(self.machine.state)

    def _queue_status_text(self) -> str:
        queue = self.queue
        if queue is None or queue.current is None:
            return tr(s.QUEUE_TITLE)
        position = next(i for i, e in enumerate(queue.entries, start=1) if e.id == queue.current.id)
        return tr(s.QUEUE_RUNNING_STATUS).format(
            current=position,
            total=len(queue.entries),
            percent=vm.percent(queue.overall_fraction()),
        )

    @Slot()
    def _on_queue_finished(self) -> None:
        if self.queue is None:
            return
        counts = self.queue.counts()
        if counts.waiting == 0 and counts.converting == 0:
            self.notifier.queue_finished(counts_text(counts), counts.failed > 0)
        else:
            self.notifier.conversion_stopped()

    # History
    def _record(
        self,
        result: HistoryResult,
        *,
        output: Path | None = None,
        size: int | None = None,
        took: float | None = None,
        fraction: float = 0.0,
        error: str = "",
    ) -> None:
        media = self.session.media
        if media is None or not self.session.format_key:
            return
        self.history.add(
            HistoryRecord(
                when=datetime.now().replace(microsecond=0),
                source=media.path,
                output=output,
                format_key=self.session.format_key,
                quality=self.session.quality,
                custom=self.session.custom,
                result=result,
                size=size,
                took=took if took is not None else time.monotonic() - self.session.started_at,
                fraction=fraction,
                error=error,
            )
        )
        self._render_history()

    @Slot(object)
    def _record_queue_entry(self, entry: QueueEntry) -> None:
        if entry.media is None:
            return
        results = {
            QueueStatus.DONE: HistoryResult.SAVED,
            QueueStatus.FAILED: HistoryResult.FAILED,
            QueueStatus.CANCELED: HistoryResult.CANCELED,
        }
        result = results.get(entry.status)
        if result is None:
            return
        fmt = format_by_key(entry.format_key)
        self.history.add(
            HistoryRecord(
                when=datetime.now().replace(microsecond=0),
                source=entry.path,
                output=entry.output if result is HistoryResult.SAVED else None,
                format_key=entry.format_key,
                quality=None if fmt.lossless else entry.quality.value,
                custom=not entry.choices.is_default,
                result=result,
                size=entry.size,
                took=entry.took,
                fraction=entry.fraction,
                error=entry.error,
            )
        )
        self._render_history()

    def _render_history(self) -> None:
        if self.machine.state.page is not Page.HISTORY:
            return
        rows = tuple(
            history_row(index, record) for index, record in enumerate(self.history.records)
        )
        self.history_page.show_rows(rows)

    def _history_record(self, index: int) -> HistoryRecord | None:
        records = self.history.records
        return records[index] if 0 <= index < len(records) else None

    def _open_history_output(self, index: int) -> None:
        record = self._history_record(index)
        if record is not None and record.output is not None and record.output.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(record.output)))

    def _show_history_output(self, index: int) -> None:
        record = self._history_record(index)
        if record is not None and record.output is not None:
            show_in_folder(record.output)

    def _show_history_details(self, index: int) -> None:
        record = self._history_record(index)
        if record is None:
            return
        report = describe(Failure(details=record.error, source=record.source))
        title = tr(s.HISTORY_DETAILS_TITLE).format(name=record.source.name)
        dialog = FailedDialog(report, title, reassure=False, parent=self)
        # Only for reading: there is nothing to retry from here.
        dialog.action_button.hide()
        dialog.close_button.set_kind(ButtonKind.PRIMARY)
        dialog.close_button.setFocus(Qt.FocusReason.OtherFocusReason)
        dialog.finished.connect(dialog.deleteLater)
        dialog.open()

    def clear_history(self) -> None:
        if not self.history.records:
            return
        dialog = QuitDialog.for_clearing_history(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.history.clear()
            self._render_history()

    # Engine
    @Slot()
    def check_engine_again(self) -> None:
        try:
            tools = self._locate()
        except FFmpegNotFoundError:
            self.convert_page.missing.show_still_missing()
            return
        try:
            encoders = list_encoders(tools.ffmpeg)
        except CapabilityError:
            encoders = frozenset()
        self.engine = Engine(tools, encoders, ffmpeg_version(tools.ffmpeg))
        self._create_services()
        self._start_hardware_detection()
        self.machine.engine_found()

    # Hardware encoding
    @property
    def hardware_enabled(self) -> bool:
        return bool(self.settings.value(HARDWARE_KEY, True, type=bool))

    def recipe(self, state: UiState | None = None, media: MediaInfo | None = None) -> Recipe:
        """Settings and tracks for the current format, quality and Advanced choices."""
        state = state or self.machine.state
        media = media or self.session.media
        if media is None:
            raise ValueError("No file is open")
        return resolve(self.current_format(state), state.quality, media, state.advanced)

    def final_settings(
        self, recipe: Recipe, state: UiState | None = None, *, software: bool = False
    ) -> ConversionSettings:
        """The recipe's settings, with the video on the graphics card when that is chosen.

        Advanced Mode can ask for software or the graphics card; otherwise the Settings
        switch decides.
        """
        state = state or self.machine.state
        return self.final_settings_for(recipe, state.advanced, software=software)

    def final_settings_for(
        self, recipe: Recipe, choices: AdvancedChoices, *, software: bool = False
    ) -> ConversionSettings:
        encoder = choices.encoder
        use_card = encoder is EncoderChoice.HARDWARE or (
            encoder is EncoderChoice.AUTO and self.hardware_enabled
        )
        if software or not use_card:
            return recipe.settings
        return accelerate(recipe.settings, self.engine.hardware)

    def hardware_text(self) -> str:
        support = self.engine.hardware
        if support is not None:
            adapter = support.adapter or support.family.vendors[0]
            return tr(s.SETTINGS_HARDWARE_DETECTED).format(
                adapter=adapter, technology=support.technology
            )
        if not self.engine.hardware_checked:
            return tr(s.SETTINGS_HARDWARE_CHECKING)
        return tr(s.SETTINGS_HARDWARE_NONE)

    def _start_hardware_detection(self) -> None:
        self._hardware_request += 1
        tools = self.engine.tools
        detect = self._detect_hardware
        if tools is None or detect is None or self.engine.hardware_checked:
            self.engine.hardware_checked = True
            self.settings_page.set_hardware_text(self.hardware_text())
            return
        self.settings_page.set_hardware_text(self.hardware_text())
        QThreadPool.globalInstance().start(
            _HardwareTask(
                self._hardware_found,
                self._hardware_request,
                detect,
                tools.ffmpeg,
                self.engine.encoders,
            )
        )

    @Slot(int, object)
    def _on_hardware_found(self, request: int, support: HardwareSupport | None) -> None:
        if request != self._hardware_request:
            return
        self.engine.hardware = support
        self.engine.hardware_checked = True
        self.settings_page.set_hardware_text(self.hardware_text())

    @Slot(bool)
    def _on_hardware_changed(self, enabled: bool) -> None:
        self.settings.setValue(HARDWARE_KEY, enabled)

    # Keyboard
    def _on_escape(self) -> None:
        if self.machine.escape_action() is EscapeAction.CANCEL_CONVERSION:
            self.cancel_conversion()

    # Window
    def discard_for_gallery(self) -> None:
        """Close at once without asking; the UI gallery uses this after a screenshot."""
        if self._dialog is not None:
            dialog, self._dialog, self._dialog_kind = self._dialog, None, None
            dialog.done(QDialog.DialogCode.Rejected)
        self.convert_page.file.panel.format.hidePopup()
        self._quitting = True
        self.close()
        self.deleteLater()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if not self._quitting and not self.machine.close_requested():
            event.ignore()
            return
        if not self._quitting and self.machine.state.previewing:
            dialog = QuitDialog.for_preview(self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                event.ignore()
                return
        queue = self.queue
        if not self._quitting and queue is not None and queue.running:
            current = queue.current
            name = current.path.name if current is not None else ""
            percent = vm.percent(current.fraction if current is not None else 0.0)
            if QuitDialog.for_queue(name, percent, self).exec() != QDialog.DialogCode.Accepted:
                event.ignore()
                return
        if queue is not None and queue.running:
            queue.stop()
            queue.runner.wait()
        if self.preview_window is not None:
            self.preview_window.close()
        if self.runner is not None and self.runner.is_running:
            self.runner.cancel()
            self.runner.wait()
        self.taskbar.close()
        super().closeEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        compact = event.size().width() < COMPACT_BELOW
        if compact != self._compact:
            self._compact = compact
            self.convert_page.set_compact(compact)
            for planned in (self.queue_page, self.history_page, self.settings_page):
                planned.set_compact(compact)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self._on_theme_changed(theme.palette())
        if self.machine.state.screen is Screen.START:
            self.drop_zone.open_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_theme_changed(self, palette: Palette) -> None:
        if self.isVisible():
            style_title_bar(self, dark=palette.is_dark, caption=palette.bg, text=palette.text)
        self.open_action.setIcon(icons.icon("FolderOpen", palette.text))

    def _bring_to_front(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()


def default_history_path() -> Path:
    folder = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(folder) / "history.json"


def show_in_folder(path: Path) -> None:
    """Open Explorer with the file selected, or the folder when the file is gone."""
    if sys.platform == "win32" and path.exists():
        QProcess.startDetached("explorer", [f"/select,{path}"])
    else:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))


def _writable(folder: Path) -> bool:
    return folder.is_dir() and os.access(folder, os.W_OK)
