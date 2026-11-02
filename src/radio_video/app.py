from __future__ import annotations

import logging
import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication

from radio_video import APP_NAME, __version__
from radio_video.ffmpeg.capabilities import CapabilityError, list_encoders
from radio_video.ffmpeg.locator import FFmpegNotFoundError, FFmpegTools, locate_tools
from radio_video.services.preview import purge_stale_previews
from radio_video.ui.main_window import MainWindow

logger = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv if argv is None else argv)
    logging.basicConfig(
        level=logging.DEBUG if "--debug" in args else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = QApplication(args)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("Radio-Video")

    if "--ui-gallery" in args:
        from radio_video.ui import gallery

        return gallery.run(app, args)

    tools: FFmpegTools | None = None
    tools_error: str | None = None
    encoders: frozenset[str] = frozenset()
    try:
        tools = locate_tools()
        logger.info("Using ffmpeg %s and ffprobe %s", tools.ffmpeg, tools.ffprobe)
        encoders = list_encoders(tools.ffmpeg)
    except FFmpegNotFoundError as exc:
        tools_error = str(exc)
        logger.error(tools_error)
    except CapabilityError as exc:
        logger.error(str(exc))

    if removed := purge_stale_previews():
        logger.info("Removed %d stale preview folders", removed)

    window = MainWindow(tools, tools_error, encoders)
    window.show()
    return app.exec()
