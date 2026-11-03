from __future__ import annotations

import logging
import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication

from radio_video import APP_NAME, __version__
from radio_video.ffmpeg.capabilities import CapabilityError, ffmpeg_version, list_encoders
from radio_video.ffmpeg.hardware import detect_hardware
from radio_video.ffmpeg.locator import FFmpegNotFoundError, FFmpegTools, locate_tools
from radio_video.services.preview import purge_stale_previews
from radio_video.ui import theme
from radio_video.ui.native.shell import set_app_user_model_id
from radio_video.ui.widgets.focus_ring import FocusRing
from radio_video.ui.windows.main_window import Engine, MainWindow

logger = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv if argv is None else argv)
    logging.basicConfig(
        level=logging.DEBUG if "--debug" in args else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    set_app_user_model_id()
    app = QApplication(args)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("Radio-Video")

    if "--ui-gallery" in args:
        from radio_video.ui import gallery

        return gallery.run(app, args)

    theme.install(app)
    FocusRing.install(app)

    tools: FFmpegTools | None = None
    encoders: frozenset[str] = frozenset()
    version: str | None = None
    try:
        tools = locate_tools()
        logger.info("Using ffmpeg %s and ffprobe %s", tools.ffmpeg, tools.ffprobe)
        encoders = list_encoders(tools.ffmpeg)
        version = ffmpeg_version(tools.ffmpeg)
    except FFmpegNotFoundError as exc:
        logger.error(str(exc))
    except CapabilityError as exc:
        logger.error(str(exc))

    if removed := purge_stale_previews():
        logger.info("Removed %d stale preview folders", removed)

    window = MainWindow(Engine(tools, encoders, version), detect_hardware=detect_hardware)
    window.show()
    return app.exec()
