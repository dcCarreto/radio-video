"""Title bar colours through the Desktop Window Manager (Windows 11).

The native title bar is kept for snap layouts and system behaviour; only its colours follow
the theme. Does nothing on other platforms or older Windows builds.
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36


def _colorref(color: QColor) -> int:
    return color.red() | (color.green() << 8) | (color.blue() << 16)


def style_title_bar(window: QWidget, *, dark: bool, caption: QColor, text: QColor) -> bool:
    """Apply dark mode and caption colours to a top-level window. Returns True on success."""
    if sys.platform != "win32" or not window.isWindow():
        return False
    import ctypes
    from ctypes import wintypes

    try:
        dwmapi = ctypes.WinDLL("dwmapi")
    except OSError:
        return False
    set_attribute = dwmapi.DwmSetWindowAttribute
    set_attribute.argtypes = [wintypes.HWND, wintypes.DWORD, wintypes.LPCVOID, wintypes.DWORD]
    set_attribute.restype = ctypes.c_long

    hwnd = wintypes.HWND(int(window.winId()))
    ok = True
    for attribute, value in (
        (DWMWA_USE_IMMERSIVE_DARK_MODE, int(dark)),
        (DWMWA_CAPTION_COLOR, _colorref(caption)),
        (DWMWA_TEXT_COLOR, _colorref(text)),
    ):
        data = wintypes.DWORD(value)
        result = set_attribute(hwnd, attribute, ctypes.byref(data), ctypes.sizeof(data))
        if result != 0:
            logger.debug("DwmSetWindowAttribute(%d) failed: 0x%08x", attribute, result & 0xFFFFFFFF)
            ok = False
    return ok
