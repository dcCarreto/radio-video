"""Every user-visible string, in English, exactly as in the copy deck.

Strings are marked with ``QT_TRANSLATE_NOOP`` so ``lupdate`` can extract them, and translated
at the point of use with :func:`tr`, after a translator may have been installed. Templates use
``str.format`` placeholders: ``tr(SAVED).format(name=..., size=...)``.
"""

from __future__ import annotations

from PySide6.QtCore import QT_TRANSLATE_NOOP, QCoreApplication

CONTEXT = "RadioVideo"


def tr(text: str, n: int = -1) -> str:
    return QCoreApplication.translate(CONTEXT, text, None, n)


# Window, menus, tabs, status bar
APP_NAME = QT_TRANSLATE_NOOP("RadioVideo", "Radio/Video")
WINDOW_TITLE_FILE = QT_TRANSLATE_NOOP("RadioVideo", "{name} · Radio/Video")
MENU_FILE = QT_TRANSLATE_NOOP("RadioVideo", "&File")
MENU_HELP = QT_TRANSLATE_NOOP("RadioVideo", "&Help")
ACTION_OPEN = QT_TRANSLATE_NOOP("RadioVideo", "Open File…")
ACTION_EXIT = QT_TRANSLATE_NOOP("RadioVideo", "Exit")
ACTION_ABOUT = QT_TRANSLATE_NOOP("RadioVideo", "About Radio/Video")
ACTION_ABOUT_QT = QT_TRANSLATE_NOOP("RadioVideo", "About Qt")
TAB_CONVERT = QT_TRANSLATE_NOOP("RadioVideo", "Convert")
TAB_QUEUE = QT_TRANSLATE_NOOP("RadioVideo", "Queue")
TAB_HISTORY = QT_TRANSLATE_NOOP("RadioVideo", "History")
TAB_SETTINGS = QT_TRANSLATE_NOOP("RadioVideo", "Settings")
BADGE_PLANNED = QT_TRANSLATE_NOOP("RadioVideo", "Planned")
STATUS_ENGINE_READY = QT_TRANSLATE_NOOP("RadioVideo", "Conversion engine ready · FFmpeg {version}")
STATUS_ENGINE_MISSING = QT_TRANSLATE_NOOP("RadioVideo", "Conversion engine not found")
STATUS_CONVERTING = QT_TRANSLATE_NOOP("RadioVideo", "Converting… {percent}%")
STATUS_PREVIEWING = QT_TRANSLATE_NOOP("RadioVideo", "Creating preview… {percent}%")
STATUS_SIMPLE_MODE = QT_TRANSLATE_NOOP("RadioVideo", "Simple Mode")
STATUS_ADVANCED_MODE = QT_TRANSLATE_NOOP("RadioVideo", "Advanced Mode")
SPLITTER_TOOLTIP = QT_TRANSLATE_NOOP("RadioVideo", "Drag to resize the panels")
