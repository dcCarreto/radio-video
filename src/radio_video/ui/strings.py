"""Every user-visible string, in English, exactly as in the copy deck.

Strings are marked with ``QT_TRANSLATE_NOOP`` so ``lupdate`` can extract them, and translated
at the point of use with :func:`tr`, after a translator may have been installed. Templates use
``str.format`` placeholders: ``tr(SAVED).format(name=..., size=...)``.
"""

from __future__ import annotations

from PySide6.QtCore import QT_TRANSLATE_NOOP, QCoreApplication

CONTEXT = "RadioVideo"


def tr(text: object, n: int = -1) -> str:
    # QT_TRANSLATE_NOOP is typed as returning object; it returns the source string unchanged.
    return QCoreApplication.translate(CONTEXT, str(text), None, n)


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

# Steps
STEPS = (
    QT_TRANSLATE_NOOP("RadioVideo", "Open a file"),
    QT_TRANSLATE_NOOP("RadioVideo", "Check what’s inside"),
    QT_TRANSLATE_NOOP("RadioVideo", "Choose a format"),
    QT_TRANSLATE_NOOP("RadioVideo", "Preview (optional)"),
    QT_TRANSLATE_NOOP("RadioVideo", "Convert"),
)
STEPS_SHORT = (
    QT_TRANSLATE_NOOP("RadioVideo", "Open"),
    QT_TRANSLATE_NOOP("RadioVideo", "Check"),
    QT_TRANSLATE_NOOP("RadioVideo", "Choose"),
    QT_TRANSLATE_NOOP("RadioVideo", "Preview"),
    QT_TRANSLATE_NOOP("RadioVideo", "Convert"),
)

# Drop zone
DROP_IDLE_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "Drop an audio or video file here")
DROP_IDLE_HINT = QT_TRANSLATE_NOOP("RadioVideo", "or drag one here from File Explorer")
DROP_IDLE_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Works with MP4, MKV, MOV, AVI, WebM, MP3, WAV, FLAC and most other audio and video formats.",
)
DROP_OVER_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "Release to open the file")
DROP_OVER_TEXT = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Radio/Video will read the file and show what’s inside. The file itself isn’t changed.",
)
DROP_BLOCKED_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "Can’t open a file right now")
DROP_BLOCKED_SEVERAL = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Drop one file at a time. Converting many files at once will come with the queue.",
)
DROP_BLOCKED_CONVERTING = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Opening files is paused while a conversion runs. Wait for it to finish, or cancel it first.",
)
SHORTCUT_OPEN = QT_TRANSLATE_NOOP("RadioVideo", "Ctrl+O")
SHORTCUT_CONVERT = QT_TRANSLATE_NOOP("RadioVideo", "Ctrl+Enter")
SHORTCUT_PREVIEW = QT_TRANSLATE_NOOP("RadioVideo", "Ctrl+P")
SHORTCUT_CANCEL = QT_TRANSLATE_NOOP("RadioVideo", "Esc")

# Streams
STREAM_COLUMNS = (
    QT_TRANSLATE_NOOP("RadioVideo", "#"),
    QT_TRANSLATE_NOOP("RadioVideo", "Type"),
    QT_TRANSLATE_NOOP("RadioVideo", "Codec"),
    QT_TRANSLATE_NOOP("RadioVideo", "Details"),
    QT_TRANSLATE_NOOP("RadioVideo", "Language"),
    QT_TRANSLATE_NOOP("RadioVideo", "Title"),
)
BADGE_DEFAULT = QT_TRANSLATE_NOOP("RadioVideo", "Default")
BADGE_RECOMMENDED = QT_TRANSLATE_NOOP("RadioVideo", "Recommended")

# Convert panel
QUALITY_HIGH = QT_TRANSLATE_NOOP("RadioVideo", "High")
QUALITY_HIGH_SUB = QT_TRANSLATE_NOOP("RadioVideo", "Near-original")
QUALITY_HIGH_HELP = QT_TRANSLATE_NOOP("RadioVideo", "Near-original quality, larger file.")
QUALITY_BALANCED = QT_TRANSLATE_NOOP("RadioVideo", "Balanced")
QUALITY_BALANCED_SUB = QT_TRANSLATE_NOOP("RadioVideo", "Recommended")
QUALITY_BALANCED_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo", "Good quality at a reasonable size. Recommended for most files."
)
QUALITY_SMALL = QT_TRANSLATE_NOOP("RadioVideo", "Small file")
QUALITY_SMALL_SUB = QT_TRANSLATE_NOOP("RadioVideo", "Some quality loss")
QUALITY_SMALL_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo", "Noticeably smaller file, with some visible or audible quality loss."
)
QUALITY_LOSSLESS = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Quality doesn’t apply to lossless formats; they keep the full quality of the source.",
)
FORMAT_GROUP_VIDEO = QT_TRANSLATE_NOOP("RadioVideo", "Video")
FORMAT_GROUP_AUDIO_FROM_VIDEO = QT_TRANSLATE_NOOP("RadioVideo", "Audio only: extracts the audio")
FORMAT_GROUP_AUDIO = QT_TRANSLATE_NOOP("RadioVideo", "Audio")
FORMAT_DESCRIPTIONS = {
    "mp4-h264": QT_TRANSLATE_NOOP("RadioVideo", "Plays on almost every device and website."),
    "mp4-h265": QT_TRANSLATE_NOOP(
        "RadioVideo",
        "About half the size at the same quality. Some older devices can’t play it.",
    ),
    "mkv-h264": QT_TRANSLATE_NOOP(
        "RadioVideo",
        "Keeps every audio and subtitle track. Good for media players and archives.",
    ),
    "webm-vp9": QT_TRANSLATE_NOOP("RadioVideo", "Efficient, made for the web."),
    "mp3": QT_TRANSLATE_NOOP("RadioVideo", "Plays everywhere."),
    "m4a-aac": QT_TRANSLATE_NOOP(
        "RadioVideo", "Better than MP3 at the same size. Standard on Apple devices."
    ),
    "opus": QT_TRANSLATE_NOOP(
        "RadioVideo", "Best quality at small sizes. Great for speech and podcasts."
    ),
    "ogg-vorbis": QT_TRANSLATE_NOOP("RadioVideo", "Open format used by many games and Linux apps."),
    "flac": QT_TRANSLATE_NOOP(
        "RadioVideo", "Lossless audio: identical to the source, larger files."
    ),
    "wav": QT_TRANSLATE_NOOP(
        "RadioVideo", "Uncompressed, very large files. Made for editing software."
    ),
}
BROWSE = QT_TRANSLATE_NOOP("RadioVideo", "Browse…")
BROWSE_TOOLTIP = QT_TRANSLATE_NOOP("RadioVideo", "Choose the folder for the converted file")

# Player
PLAYER_PLAY = QT_TRANSLATE_NOOP("RadioVideo", "Play (Space)")
PLAYER_PAUSE = QT_TRANSLATE_NOOP("RadioVideo", "Pause (Space)")
PLAYER_SEEK = QT_TRANSLATE_NOOP("RadioVideo", "Seek (Left/Right arrow)")
PLAYER_MUTE = QT_TRANSLATE_NOOP("RadioVideo", "Mute (M)")
PLAYER_UNMUTE = QT_TRANSLATE_NOOP("RadioVideo", "Unmute (M)")
PLAYER_VOLUME = QT_TRANSLATE_NOOP("RadioVideo", "Volume")
