from __future__ import annotations

import logging
import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication

from radio_video import APP_NAME, __version__
from radio_video.ffmpeg.locator import FFmpegNotFoundError, FFmpegTools, locate_tools
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

    tools: FFmpegTools | None = None
    tools_error: str | None = None
    try:
        tools = locate_tools()
        logger.info("Using ffmpeg %s and ffprobe %s", tools.ffmpeg, tools.ffprobe)
    except FFmpegNotFoundError as exc:
        tools_error = str(exc)
        logger.error(tools_error)

    window = MainWindow(tools, tools_error)
    window.show()
    return app.exec()
