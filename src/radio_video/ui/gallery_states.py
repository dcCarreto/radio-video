"""Screen states from the design, built in a real main window with demo data.

Used by ``--ui-gallery``: each state opens a window in that state, and ``--capture`` saves
the window (with any dialog or popup composited on top) next to the design canvas.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QPoint, QSettings, QSize
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from radio_video.ffmpeg.locator import FFmpegTools
from radio_video.models.advanced import AdvancedChoices
from radio_video.models.estimate import estimate_output_size
from radio_video.models.hardware import NVENC, HardwareSupport
from radio_video.models.media import MediaInfo
from radio_video.models.presets import OUTPUT_FORMATS, OutputFormat, Quality
from radio_video.services.history import HistoryRecord, HistoryResult
from radio_video.services.preview import PreviewKind as ServiceKind
from radio_video.services.preview import PreviewSample
from radio_video.services.queue import QueueStatus
from radio_video.ui import viewmodel as vm
from radio_video.ui.demo import DEMO_FOLDER, DEMO_MEDIA
from radio_video.ui.dialogs.failed_dialog import FailedDialog
from radio_video.ui.errors_map import Failure
from radio_video.ui.state import Mode, Page, PreviewKind, Progress, UiState
from radio_video.ui.widgets.drop_zone import DropState
from radio_video.ui.windows.main_window import COMPACT_BELOW, Engine, MainWindow
from radio_video.ui.windows.preview_window import Phase, PreviewRequest, PreviewWindow

# Client sizes: the design's 1440×900 and 960×720 frames include a 32 px title bar.
SIZES = {"l": QSize(1440, 868), "s": QSize(960, 688)}
ALL_ENCODERS = frozenset(e for fmt in OUTPUT_FORMATS for e in fmt.encoders)
MB = 1024 * 1024

FAILED_LOG = (
    'ffmpeg -hide_banner -i "Interview – Lisbon Studio Session (Final Cut, 2026-03-14).mkv" '
    "-map 0 -c:v libx264 -crf 23 -preset medium -c:a aac -b:a 160k -c:s mov_text "
    '"Interview – Lisbon Studio Session (Final Cut, 2026-03-14) (1).mp4.part"\n'
    "frame= 2104 fps= 74 q=28.0 size=  13568kB time=00:01:27.71 bitrate=1267.2kbits/s "
    "speed=3.08x\n"
    "[mp4 @ 000001d2c3a4e0c0] Error writing packet: No space left on device\n"
    "av_interleaved_write_frame(): No space left on device\n"
    'Error writing trailer of "…(1).mp4.part": No space left on device\n'
    "Conversion failed! (exit code -28)"
)


def _demo_names(folder: Path, media: MediaInfo, fmt: OutputFormat) -> vm.OutputName:
    """As in the design: an MP4 with the same name already exists in the folder."""
    stem = media.path.stem
    if fmt.extension == ".mp4":
        return vm.OutputName(folder / f"{stem} (1){fmt.extension}", 1)
    return vm.OutputName(folder / f"{stem}{fmt.extension}", None)


def demo_window(size: str = "l") -> MainWindow:
    settings = QSettings(
        str(Path(tempfile.gettempdir()) / "rv-gallery.ini"), QSettings.Format.IniFormat
    )
    links = Path("C:/Users/Ana/AppData/Local/Microsoft/WinGet/Links")
    engine = Engine(
        FFmpegTools(links / "ffmpeg.exe", links / "ffprobe.exe"),
        ALL_ENCODERS,
        "7.1",
        hardware=HardwareSupport(NVENC, NVENC.encoders, "NVIDIA GeForce RTX 3060"),
        hardware_checked=True,
    )
    history = Path(tempfile.gettempdir()) / "rv-gallery-history.json"
    history.unlink(missing_ok=True)
    window = MainWindow(engine, settings=settings, history_path=history)
    window.output_namer = _demo_names
    window.folder_writable = lambda _folder: True
    window.resize(SIZES[size])
    return window


def _loaded(window: MainWindow) -> None:
    window.load_media(DEMO_MEDIA, folder=DEMO_FOLDER)


def _converting(window: MainWindow, fraction: float = 0.42) -> None:
    _loaded(window)
    machine = window.machine
    window.session.destination = DEMO_FOLDER / f"{DEMO_MEDIA.path.stem} (1).mp4"
    machine.conversion_requested()
    machine.conversion_started()
    machine.conversion_progress(Progress(fraction, 3.1, 25))


def _measured(window: MainWindow) -> None:
    _loaded(window)
    machine = window.machine
    machine.preview_requested(PreviewKind.SAMPLE)
    machine.preview_ready(22 * MB)
    machine.preview_closed()


def _success(window: MainWindow) -> None:
    _measured(window)
    machine = window.machine
    machine.conversion_requested()
    machine.conversion_started()
    output = DEMO_FOLDER / f"{DEMO_MEDIA.path.stem} (1).mp4"
    machine.conversion_succeeded(output, round(22.4 * MB), 43)


def _canceled(window: MainWindow) -> None:
    _converting(window)
    window.machine.conversion_canceled()


def _failed(window: MainWindow) -> None:
    _converting(window, 0.66)
    source = Path(tempfile.gettempdir()) / "rv-gallery-source.mkv"
    source.touch()

    def failure(state: UiState, media: MediaInfo) -> Failure:
        return Failure(
            FAILED_LOG, source, Path("C:/Users/Ana/Videos/Exports/out.mp4"), 0.66, 22 * MB
        )

    window.failure_for = failure  # type: ignore[method-assign]
    window.machine.conversion_failed(FAILED_LOG)
    dialog = window.open_dialog
    if isinstance(dialog, FailedDialog):
        dialog.expander.setChecked(True)


def _format(key: str) -> Callable[[MainWindow], None]:
    def apply(window: MainWindow) -> None:
        _loaded(window)
        window.convert_page.file.panel.format.set_current_key(key)

    return apply


def _blocked(window: MainWindow) -> None:
    _converting(window)
    window.machine.drag_over(accepted=True)


def _advanced(tab: str) -> Callable[[MainWindow], None]:
    def apply(window: MainWindow) -> None:
        _loaded(window)
        window.machine.set_mode(Mode.ADVANCED)
        window.convert_page.file.panel.advanced.tabs.set_current(tab)

    return apply


def _custom(window: MainWindow) -> None:
    _loaded(window)
    window.machine.set_advanced(AdvancedChoices(crf=20, preset="slow", height=720))


# File, format, quality, status, fraction, size, took, error
DEMO_QUEUE: tuple[
    tuple[str, str, Quality, QueueStatus, float, int | None, float | None, str], ...
] = (
    (
        "Interview – Lisbon Studio Session (Final Cut, 2026-03-14).mkv",
        "mp4-h264",
        Quality.BALANCED,
        QueueStatus.DONE,
        1.0,
        22 * MB + 400 * 1024,
        43.0,
        "",
    ),
    (
        "Rehearsal day 2 – wide camera.mov",
        "mp4-h265",
        Quality.SMALL,
        QueueStatus.CONVERTING,
        0.42,
        None,
        None,
        "",
    ),
    ("Podcast ep. 41 – raw.wav", "mp3", Quality.BALANCED, QueueStatus.WAITING, 0, None, None, ""),
    (
        "B-roll_harbour_0412.mp4",
        "webm-vp9",
        Quality.BALANCED,
        QueueStatus.FAILED,
        0.3,
        None,
        None,
        "No space left on device",
    ),
    (
        "Voice memo 2026-02-11 08.14.m4a",
        "opus",
        Quality.BALANCED,
        QueueStatus.WAITING,
        0,
        None,
        None,
        "",
    ),
    (
        "Old family tape (VHS transfer).avi",
        "mkv-h264",
        Quality.HIGH,
        QueueStatus.CANCELED,
        0.18,
        None,
        None,
        "",
    ),
)


def _queue_demo(window: MainWindow) -> None:
    """The design's example queue: one file of every status, the second one converting."""
    _loaded(window)
    queue = window.queue
    if queue is None:
        return
    for name, key, quality, status, fraction, size, took, error in DEMO_QUEUE:
        path = DEMO_FOLDER / name
        if status is QueueStatus.FAILED:
            # The source must exist, otherwise the failure reads as "the original was moved".
            path = Path(tempfile.gettempdir()) / name
            path.touch()
        media = replace(DEMO_MEDIA, path=path)
        entry = queue.add(media.path, key, quality, AdvancedChoices(), DEMO_FOLDER, media)
        queue._replace(
            replace(
                entry,
                status=status,
                fraction=fraction,
                size=size,
                took=took,
                error=error,
                speed=3.1 if status is QueueStatus.CONVERTING else None,
                remaining=25.0 if status is QueueStatus.CONVERTING else None,
            )
        )
        if status is QueueStatus.CONVERTING:
            queue._current = entry.id
    queue._running = True
    window.machine.go(Page.QUEUE)
    window._render_queue()
    page = window.queue_page
    if page.view is not None:
        page.select(page.view.rows[3].entry_id)


def _history_demo(window: MainWindow) -> None:
    """The design's example history, newest first; saved files exist, one was moved."""
    folder = Path(tempfile.gettempdir()) / "rv-gallery-outputs"
    folder.mkdir(exist_ok=True)
    now = datetime.now().replace(second=0, microsecond=0)
    yesterday = now - timedelta(days=1)
    rows = (
        (
            now.replace(hour=14, minute=32),
            "Interview – Lisbon Studio Session (Final Cut, 2026-03-14).mkv",
            "Interview – Lisbon Studio Session (Final Cut, 2026-03-14) (1).mp4",
            "mp4-h264",
            "Balanced",
            HistoryResult.SAVED,
            22 * MB + 400 * 1024,
            43.0,
            "",
        ),
        (
            now.replace(hour=11, minute=5),
            "Podcast ep. 40 – raw.wav",
            "Podcast ep. 40 – raw.mp3",
            "mp3",
            "Balanced",
            HistoryResult.SAVED,
            38 * MB + 700 * 1024,
            12.0,
            "",
        ),
        (
            yesterday.replace(hour=18, minute=20),
            "B-roll_harbour_0412.mp4",
            "",
            "webm-vp9",
            "Balanced",
            HistoryResult.FAILED,
            None,
            62.0,
            "No space left on device",
        ),
        (
            yesterday.replace(hour=9, minute=47),
            "clip.mov",
            "clip.mp3",
            "mp3",
            "Balanced",
            HistoryResult.SAVED,
            121_754,
            1.0,
            "",
        ),
        (
            datetime(2026, 10, 3, 16, 10),
            "Old family tape (VHS transfer).avi",
            "",
            "mkv-h264",
            "High",
            HistoryResult.CANCELED,
            None,
            54.0,
            "",
        ),
        (
            datetime(2026, 10, 1, 10, 2),
            "Rehearsal day 1.mov",
            "Rehearsal day 1.mp4",
            "mp4-h265",
            "Small file",
            HistoryResult.SAVED,
            1288 * MB,
            378.0,
            "",
        ),
    )
    for when, source, output, key, quality, result, size, took, error in reversed(rows):
        output_path = folder / output if output else None
        # Every saved file exists except the oldest, which shows as moved.
        if output_path is not None and source != "Rehearsal day 1.mov":
            output_path.touch()
        window.history.add(
            HistoryRecord(
                when=when,
                source=DEMO_FOLDER / source,
                output=output_path,
                format_key=key,
                quality=quality,
                custom=False,
                result=result,
                size=size,
                took=took,
                fraction=0.18 if result is HistoryResult.CANCELED else 1.0,
                error=error,
            )
        )
    _loaded(window)
    window.machine.go(Page.HISTORY)


def _page(page: Page) -> Callable[[MainWindow], None]:
    def apply(window: MainWindow) -> None:
        _loaded(window)
        window.machine.go(page)

    return apply


def _quit(window: MainWindow) -> None:
    _converting(window)
    window.close()


def _about(window: MainWindow) -> None:
    _loaded(window)
    window.machine.show_about()


PREVIEW_LOG = (
    "[h264 @ 0000020a] Invalid NAL unit size (1835 > 1214).\n"
    "[h264 @ 0000020a] Error splitting the input into NAL units.\n"
    "Error while decoding stream #0:0: Invalid data found when processing input"
)


def _demo_frame() -> QImage:
    """A neutral gradient standing in for a converted video frame."""
    image = QImage(1920, 1080, QImage.Format.Format_RGB32)
    painter = QPainter(image)
    gradient = QLinearGradient(0, 0, 1920, 1080)
    gradient.setColorAt(0, QColor("#2b3a42"))
    gradient.setColorAt(1, QColor("#7a5c3e"))
    painter.fillRect(image.rect(), gradient)
    painter.end()
    return image


def _preview(phase: Phase, key: str = "mp4-h264") -> Callable[[MainWindow], None]:
    def apply(window: MainWindow) -> None:
        _loaded(window)
        if key != "mp4-h264":
            window.convert_page.file.panel.format.set_current_key(key)
        machine = window.machine
        machine.preview_requested(PreviewKind.SAMPLE)
        state = machine.state
        fmt = window.current_format(state)
        request = PreviewRequest(
            DEMO_MEDIA,
            fmt,
            state.quality,
            PreviewKind.SAMPLE,
            vm.output_contents(fmt, DEMO_MEDIA, fmt.plan(DEMO_MEDIA)),
            estimate_output_size(fmt.settings(state.quality), DEMO_MEDIA),
        )
        compact = window.width() < COMPACT_BELOW
        preview = PreviewWindow(
            Path("ffmpeg.exe"), request, compact=compact, autoplay=False, parent=window
        )
        if phase is Phase.READY:
            measured = 22 * MB
            preview._sample = PreviewSample(
                Path("preview.mp4"), ServiceKind.SHORT, 20.0, 15.0, round(measured * 15 / 133)
            )
            preview.canvas.show_image(_demo_frame())
            preview.player_bar.set_duration(15_000)
            preview.player_bar.set_position(4_000)
            machine.preview_ready(measured)
            preview._set_phase(phase)
        elif phase is Phase.FAILED:
            preview._last_time = 4.0
            source = Path(tempfile.gettempdir()) / "rv-gallery-source.mkv"
            source.touch()
            preview.request = replace(request, media=replace(DEMO_MEDIA, path=source))
            preview._show_failure(PREVIEW_LOG)
            preview.request = request
            machine.preview_failed()
        elif phase is Phase.CANCELED:
            preview._set_phase(phase)
            machine.preview_canceled()
        else:
            preview.card_bar.set_fraction(0.64)
            preview.card_progress.setText(vm.progress_detail(Progress(0.64, None, 2)))
            machine.preview_progress(Progress(0.64))
        window.preview_window = preview
        preview.show()

    return apply


def _original(window: MainWindow) -> None:
    """The opened file played as it is, nothing converted."""
    _loaded(window)
    window.machine.preview_requested(PreviewKind.ORIGINAL)
    state = window.machine.state
    request = PreviewRequest(
        DEMO_MEDIA,
        window.current_format(state),
        state.quality,
        PreviewKind.ORIGINAL,
        vm.original_contents(DEMO_MEDIA),
    )
    compact = window.width() < COMPACT_BELOW
    preview = PreviewWindow(
        Path("ffmpeg.exe"), request, compact=compact, autoplay=False, parent=window
    )
    preview.canvas.show_image(_demo_frame())
    preview.player_bar.set_duration(133_000)
    preview.player_bar.set_position(41_000)
    window.preview_window = preview
    preview.show()


@dataclass(frozen=True)
class GalleryState:
    key: str
    title: str
    apply: Callable[[MainWindow], object]
    popup: bool = False


STATES = (
    GalleryState("start", "Start: empty", lambda w: None),
    GalleryState(
        "start-over", "Start: file dragged over", lambda w: w.drop_zone.set_state(DropState.OVER)
    ),
    GalleryState("missing", "FFmpeg missing", lambda w: w.machine.engine_missing()),
    GalleryState("loaded", "File loaded: MP4, Balanced", _loaded),
    GalleryState("picker", "Format picker open", _loaded, popup=True),
    GalleryState("mp3", "Extract audio: MP3 (size calculable)", _format("mp3")),
    GalleryState("flac", "Lossless: FLAC (quality not applicable)", _format("flac")),
    GalleryState("measured", "After a preview: size measured", _measured),
    GalleryState("converting", "Converting", _converting),
    GalleryState("blocked", "Converting: file dropped (blocked)", _blocked),
    GalleryState("success", "Finished", _success),
    GalleryState("canceled", "Canceled", _canceled),
    GalleryState("failed", "Failed: dialog with details", _failed),
    GalleryState("pv-creating", "Preview: creating", _preview(Phase.CREATING)),
    GalleryState("pv-ready", "Preview: ready (video)", _preview(Phase.READY)),
    GalleryState("pv-audio", "Preview: audio only", _preview(Phase.READY, "mp3")),
    GalleryState("pv-failed", "Preview: failed", _preview(Phase.FAILED)),
    GalleryState("pv-canceled", "Preview: canceled", _preview(Phase.CANCELED)),
    GalleryState("pv-original", "Original: played as it is", _original),
    GalleryState("quit", "Quit during conversion", _quit),
    GalleryState("about", "About", _about),
    GalleryState("adv-video", "Advanced Mode: Video", _advanced("video")),
    GalleryState("adv-audio", "Advanced Mode: Audio", _advanced("audio")),
    GalleryState("adv-tracks", "Advanced Mode: Tracks", _advanced("tracks")),
    GalleryState("adv-output", "Advanced Mode: Output and filters", _advanced("output")),
    GalleryState("custom", "Simple Mode after Advanced changes", _custom),
    GalleryState("queue", "Queue: running, every status", _queue_demo),
    GalleryState("queue-empty", "Queue: empty", _page(Page.QUEUE)),
    GalleryState("history", "History: saved, failed, canceled and moved", _history_demo),
    GalleryState("history-empty", "History: empty", _page(Page.HISTORY)),
    GalleryState("settings", "Settings", _page(Page.SETTINGS)),
)


def build(state: GalleryState, size: str = "l") -> MainWindow:
    window = demo_window(size)
    window.show()
    QApplication.processEvents()
    state.apply(window)
    QApplication.processEvents()
    if state.popup:
        window.convert_page.file.panel.format.showPopup()
        QApplication.processEvents()
    return window


def capture(window: MainWindow) -> QPixmap:
    """The window's client area with an open dialog or popup painted where it appears."""
    QApplication.processEvents()
    image = window.grab()
    painter = QPainter(image)
    overlays: list[QWidget] = []
    dialog = window.open_dialog
    if isinstance(dialog, QDialog) and dialog.isVisible():
        overlays.append(dialog)
    preview = window.preview_window
    if preview is not None and preview.isVisible():
        overlays.append(preview)
    combo = window.convert_page.file.panel.format
    popup = combo.view().window()
    if popup.isVisible():
        overlays.append(popup)
    for widget in overlays:
        top_left = window.mapFromGlobal(widget.mapToGlobal(QPoint(0, 0)))
        if widget is dialog or widget is preview:
            top_left = QPoint(
                (image.width() - widget.width()) // 2, (image.height() - widget.height()) // 2
            )
        painter.drawPixmap(top_left, widget.grab())
    painter.end()
    return image
