"""Windows shell identity: groups the taskbar button and notifications under one app."""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)

# Must match the AppUserModelID of the installer's shortcuts (packaging/radio-video.iss).
APP_USER_MODEL_ID = "dcCarreto.RadioVideo"


def set_app_user_model_id(app_id: str = APP_USER_MODEL_ID) -> bool:
    if sys.platform != "win32":
        return False
    import ctypes

    try:
        result = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except (AttributeError, OSError):
        logger.debug("Could not set the AppUserModelID", exc_info=True)
        return False
    return bool(result == 0)
