"""Screen states from the design, built in a real main window with demo data.

Used by ``--ui-gallery``: each state opens a window in that state, and ``--capture`` saves
the window (with any dialog or popup composited on top) next to the design canvas.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPoint, QSettings, QSize
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from radio_video.ffmpeg.locator import FFmpegTools
from radio_video.models.media import MediaInfo
from radio_video.models.presets import OUTPUT_FORMATS, OutputFormat
from radio_video.ui import viewmodel as vm
from radio_video.ui.demo import DEMO_FOLDER, DEMO_MEDIA
from radio_video.ui.dialogs.failed_dialog import FailedDialog
from radio_video.ui.errors_map import Failure
from radio_video.ui.state import PreviewKind, Progress, UiState
from radio_video.ui.widgets.drop_zone import DropState
from radio_video.ui.windows.main_window import Engine, MainWindow

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
    engine = Engine(FFmpegTools(Path("ffmpeg.exe"), Path("ffprobe.exe")), ALL_ENCODERS, "7.1")
    window = MainWindow(engine, settings=settings)
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


def _quit(window: MainWindow) -> None:
    _converting(window)
    window.close()


def _about(window: MainWindow) -> None:
    _loaded(window)
    window.machine.show_about()


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
    GalleryState("quit", "Quit during conversion", _quit),
    GalleryState("about", "About", _about),
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
    combo = window.convert_page.file.panel.format
    popup = combo.view().window()
    if popup.isVisible():
        overlays.append(popup)
    for widget in overlays:
        top_left = window.mapFromGlobal(widget.mapToGlobal(QPoint(0, 0)))
        if widget is dialog:
            top_left = QPoint(
                (image.width() - widget.width()) // 2, (image.height() - widget.height()) // 2
            )
        painter.drawPixmap(top_left, widget.grab())
    painter.end()
    return image
