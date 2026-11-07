"""Every user-visible string, in English, exactly as in the copy deck.

Strings are marked with ``QT_TRANSLATE_NOOP`` so ``lupdate`` can extract them, and translated
at the point of use with :func:`tr`, after a translator may have been installed. Templates use
``str.format`` placeholders: ``tr(SAVED).format(name=..., size=...)``.
"""

from __future__ import annotations

from PySide6.QtCore import QT_TRANSLATE_NOOP, QCoreApplication

CONTEXT = "RadioVideo"


def tr(text: object, n: int = -1) -> str:
    """Translate ``text``; with ``n``, replace ``%n`` and pick the plural form.

    Without an installed translation, the English source applies its own plural rule:
    ``"%n track(s)"`` becomes "1 track" or "3 tracks".
    """
    # QT_TRANSLATE_NOOP is typed as returning object; it returns the source string unchanged.
    source = str(text)
    result = QCoreApplication.translate(CONTEXT, source, None, n)
    if n >= 0 and "(s)" in result:
        result = result.replace("(s)", "" if n == 1 else "s")
    return result


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
    "Drop files, not folders. Several files go to the queue.",
)
DROP_OVER_QUEUE_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "Release to add %n file(s) to the queue")
DROP_OVER_QUEUE_TEXT = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Each file is read and added with the format and quality chosen on the Convert tab.",
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
PLAYER_AUDIO_TRACK = QT_TRANSLATE_NOOP("RadioVideo", "Audio track")
PLAYER_SUBTITLES = QT_TRANSLATE_NOOP("RadioVideo", "Subtitles")
PLAYER_SUBTITLES_OFF = QT_TRANSLATE_NOOP("RadioVideo", "Off")
PLAYER_TRACK = QT_TRANSLATE_NOOP("RadioVideo", "Track {number}")

# Start screen
START_HEADLINE = QT_TRANSLATE_NOOP(
    "RadioVideo", "Convert audio and video files to the format you need."
)
START_INTRO = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Open a file, check what’s inside, choose a format, preview the real result, then convert. "
    "Your original file is never changed.",
)
CELL_ORIGINAL_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "Your original stays untouched")
CELL_ORIGINAL_TEXT = QT_TRANSLATE_NOOP("RadioVideo", "Radio/Video only reads it.")
CELL_OVERWRITE_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "Nothing gets overwritten")
CELL_OVERWRITE_TEXT = QT_TRANSLATE_NOOP(
    "RadioVideo", "If the name is taken, a number is added, like clip (1).mp4."
)
CELL_LEFTOVERS_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "No leftovers")
CELL_LEFTOVERS_TEXT = QT_TRANSLATE_NOOP(
    "RadioVideo", "Canceled or failed conversions are cleaned up."
)
ANALYZING_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "Reading the file…")
ANALYZING_TEXT = QT_TRANSLATE_NOOP("RadioVideo", "This usually takes a second.")

# FFmpeg missing
MISSING_KICKER = QT_TRANSLATE_NOOP("RadioVideo", "One-time setup")
MISSING_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "The conversion engine isn’t installed")
MISSING_BODY = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Radio/Video uses FFmpeg, a free media engine, to read and convert files. It wasn’t found on "
    "this computer. Installing it takes about a minute.",
)
MISSING_OPTION1_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "Install with Windows Package Manager")
MISSING_OPTION1_TEXT = QT_TRANSLATE_NOOP(
    "RadioVideo", "Open Terminal or PowerShell and run this command:"
)
MISSING_COMMAND = "winget install --id Gyan.FFmpeg -e"
MISSING_OPTION1_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "When it finishes, come back here and select Check Again. You don’t need to restart your "
    "computer.",
)
COPY = QT_TRANSLATE_NOOP("RadioVideo", "Copy")
COPY_COMMAND_TOOLTIP = QT_TRANSLATE_NOOP("RadioVideo", "Copy the command to the clipboard")
COPIED = QT_TRANSLATE_NOOP("RadioVideo", "Copied")
MISSING_OPTION2_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "Already have FFmpeg somewhere else?")
MISSING_OPTION2_TEXT = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Set these environment variables to the full paths of ffmpeg.exe and ffprobe.exe, then "
    "restart Radio/Video:",
)
CHECK_AGAIN = QT_TRANSLATE_NOOP("RadioVideo", "Check Again")
CHECK_AGAIN_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo", "Looks for FFmpeg on the PATH and in the variables above."
)
STILL_NOT_FOUND = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Still not found. If you just installed it, close and reopen Radio/Video so Windows can "
    "update the PATH.",
)

# File loaded
SOURCE_KICKER = QT_TRANSLATE_NOOP("RadioVideo", "Source file")
FACT_CONTAINER = QT_TRANSLATE_NOOP("RadioVideo", "Container")
FACT_DURATION = QT_TRANSLATE_NOOP("RadioVideo", "Duration")
FACT_SIZE = QT_TRANSLATE_NOOP("RadioVideo", "Size")
FACT_BITRATE = QT_TRANSLATE_NOOP("RadioVideo", "Bitrate")
FACT_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "Title")
INSIDE_HEADER = QT_TRANSLATE_NOOP("RadioVideo", "What’s inside · {count}")
TRACK_COUNT = QT_TRANSLATE_NOOP("RadioVideo", "%n track(s)")
CHIP_VIDEO = QT_TRANSLATE_NOOP("RadioVideo", "%n video")
CHIP_AUDIO = QT_TRANSLATE_NOOP("RadioVideo", "%n audio")
CHIP_SUBTITLES = QT_TRANSLATE_NOOP("RadioVideo", "%n subtitle(s)")
CHIP_COVER = QT_TRANSLATE_NOOP("RadioVideo", "%n cover image(s)")
SUMMARY_VIDEO = QT_TRANSLATE_NOOP("RadioVideo", "%n video track(s)")
SUMMARY_AUDIO = QT_TRANSLATE_NOOP("RadioVideo", "%n audio track(s)")
SUMMARY_AUDIO_LANGUAGES = QT_TRANSLATE_NOOP("RadioVideo", "{tracks} ({languages})")
SUMMARY_SUBTITLES = QT_TRANSLATE_NOOP("RadioVideo", "%n subtitle track(s)")
SUMMARY_COVER = QT_TRANSLATE_NOOP("RadioVideo", "%n cover image(s)")
SUMMARY_LIST = QT_TRANSLATE_NOOP("RadioVideo", "{head} and {last}.")
SUMMARY_SINGLE = QT_TRANSLATE_NOOP("RadioVideo", "{only}.")
SUMMARY_AUDIO_ONLY = QT_TRANSLATE_NOOP("RadioVideo", "Audio-only file: {tracks} ({details}).")
TYPE_VIDEO = QT_TRANSLATE_NOOP("RadioVideo", "Video")
TYPE_AUDIO = QT_TRANSLATE_NOOP("RadioVideo", "Audio")
TYPE_SUBTITLE = QT_TRANSLATE_NOOP("RadioVideo", "Subtitle")
TYPE_COVER = QT_TRANSLATE_NOOP("RadioVideo", "Cover art")
TYPE_ATTACHMENT = QT_TRANSLATE_NOOP("RadioVideo", "Attachment")
TYPE_DATA = QT_TRANSLATE_NOOP("RadioVideo", "Data")
DETAIL_TEXT = QT_TRANSLATE_NOOP("RadioVideo", "Text")
DETAIL_IMAGE_SUBTITLE = QT_TRANSLATE_NOOP("RadioVideo", "Image")
DETAIL_STEREO = QT_TRANSLATE_NOOP("RadioVideo", "Stereo")
DETAIL_MONO = QT_TRANSLATE_NOOP("RadioVideo", "Mono")
DETAIL_IMAGE = QT_TRANSLATE_NOOP("RadioVideo", "{format} image")
CODEC_TOOLTIPS = {
    "h264": QT_TRANSLATE_NOOP("RadioVideo", "H.264, the most widely supported video format."),
    "hevc": QT_TRANSLATE_NOOP("RadioVideo", "H.265, smaller files, newer devices."),
    "aac": QT_TRANSLATE_NOOP("RadioVideo", "AAC, the standard audio for MP4."),
    "subrip": QT_TRANSLATE_NOOP("RadioVideo", "SRT text subtitles."),
    "mjpeg": QT_TRANSLATE_NOOP("RadioVideo", "An embedded picture, like album art."),
}
OPEN_ANOTHER = QT_TRANSLATE_NOOP("RadioVideo", "Open Another File…")
OPEN_SHORT = QT_TRANSLATE_NOOP("RadioVideo", "Open…")
OPEN_ANOTHER_TOOLTIP = QT_TRANSLATE_NOOP("RadioVideo", "Open another audio or video file")
OPEN_DISABLED_TOOLTIP = QT_TRANSLATE_NOOP(
    "RadioVideo", "You can open another file when the conversion finishes."
)
OPEN_PAUSED = QT_TRANSLATE_NOOP("RadioVideo", "Paused until the conversion finishes")

# Convert panel
MODE_LABEL = QT_TRANSLATE_NOOP("RadioVideo", "Mode")
MODE_SIMPLE = QT_TRANSLATE_NOOP("RadioVideo", "Simple")
MODE_ADVANCED = QT_TRANSLATE_NOOP("RadioVideo", "Advanced")
MODE_SIMPLE_TIP = QT_TRANSLATE_NOOP(
    "RadioVideo", "Pick a format and a quality. Good technical settings are chosen for you."
)
MODE_ADVANCED_TIP = QT_TRANSLATE_NOOP(
    "RadioVideo", "Every technical setting, each with a short explanation."
)
MODE_SIMPLE_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo", "Advanced shows every technical setting. Your choices carry over."
)
MODE_ADVANCED_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo", "Your Simple choices were carried over. Switch back at any time."
)
FIELD_FORMAT = QT_TRANSLATE_NOOP("RadioVideo", "Format")
FIELD_QUALITY = QT_TRANSLATE_NOOP("RadioVideo", "Quality")
FIELD_SAVE_TO = QT_TRANSLATE_NOOP("RadioVideo", "Save to")
EXTRACTS_AUDIO = QT_TRANSLATE_NOOP(
    "RadioVideo", "{description} Extracts the audio; the video is left out."
)
FOLDER_NOT_WRITABLE = QT_TRANSLATE_NOOP(
    "RadioVideo", "You can’t save to this folder. Choose another one."
)
YOU_GET = QT_TRANSLATE_NOOP("RadioVideo", "You’ll get")
NAME_BUMPED = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "A file with this name already exists in the folder, so “({number})” was added. Existing "
    "files are never overwritten.",
)
ROW_VIDEO = QT_TRANSLATE_NOOP("RadioVideo", "Video")
ROW_AUDIO = QT_TRANSLATE_NOOP("RadioVideo", "Audio")
ROW_SUBTITLES = QT_TRANSLATE_NOOP("RadioVideo", "Subtitles")
ROW_COVER = QT_TRANSLATE_NOOP("RadioVideo", "Cover art")
ROW_LEFT_OUT = QT_TRANSLATE_NOOP("RadioVideo", "Left out")
CONTENT_AUDIO_TRACKS = QT_TRANSLATE_NOOP("RadioVideo", "%n track(s), converted to {codec}")
CONTENT_SUBTITLES_CONVERTED = QT_TRANSLATE_NOOP("RadioVideo", "%n track(s), converted to {codec}")
CONTENT_SUBTITLES_COPIED = QT_TRANSLATE_NOOP("RadioVideo", "%n track(s), copied as they are")
CONTENT_KEPT = QT_TRANSLATE_NOOP("RadioVideo", "Kept")
CONTENT_COVER_LEFT_OUT = QT_TRANSLATE_NOOP("RadioVideo", "Left out: {format} can’t store it")
CONTENT_TRACK = QT_TRANSLATE_NOOP("RadioVideo", "Track {number}")
CONTENT_TRACK_LANGUAGE = QT_TRANSLATE_NOOP("RadioVideo", "Track {number} ({language})")
CONTENT_DOWNMIX = QT_TRANSLATE_NOOP("RadioVideo", "{track}, {layout} mixed down to stereo")
CONTENT_LAYOUT_KEPT = QT_TRANSLATE_NOOP("RadioVideo", "{track}, {layout} kept")
CONTENT_LAYOUT = QT_TRANSLATE_NOOP("RadioVideo", "{track}, {layout}")
CONTENT_DOWNMIX_TO = QT_TRANSLATE_NOOP("RadioVideo", "{track}, {layout} mixed to {target}")
CONTENT_COPIED = QT_TRANSLATE_NOOP("RadioVideo", "{codec}, copied as it is")
LEFT_OUT_VIDEO = QT_TRANSLATE_NOOP("RadioVideo", "Video")
LEFT_OUT_AUDIO = QT_TRANSLATE_NOOP("RadioVideo", "%n other audio track(s)")
LEFT_OUT_SUBTITLES = QT_TRANSLATE_NOOP("RadioVideo", "subtitles")
LEFT_OUT_IMAGE_SUBTITLES = QT_TRANSLATE_NOOP("RadioVideo", "image subtitles")
LEFT_OUT_SUBTITLE_TRACKS = QT_TRANSLATE_NOOP("RadioVideo", "%n subtitle track(s)")
LEFT_OUT_COVER = QT_TRANSLATE_NOOP("RadioVideo", "cover art")
LIST_SEPARATOR = QT_TRANSLATE_NOOP("RadioVideo", ", ")
SUBTITLE_MP4_TEXT = QT_TRANSLATE_NOOP("RadioVideo", "MP4 text")
SUBTITLE_WEBVTT = QT_TRANSLATE_NOOP("RadioVideo", "WebVTT")
ESTIMATED_SIZE = QT_TRANSLATE_NOOP("RadioVideo", "Estimated size")
ESTIMATE_VALUE = QT_TRANSLATE_NOOP("RadioVideo", "≈ {size}")
ESTIMATE_CALCULATED = QT_TRANSLATE_NOOP("RadioVideo", "Calculated from the bitrate and length.")
ESTIMATE_MEASURED = QT_TRANSLATE_NOOP("RadioVideo", "Measured from a preview.")
ESTIMATE_UNKNOWN = QT_TRANSLATE_NOOP("RadioVideo", "Depends on the content")
ESTIMATE_UNKNOWN_HELP = QT_TRANSLATE_NOOP("RadioVideo", "Create a preview to measure it.")
PREVIEW_SHORT = QT_TRANSLATE_NOOP("RadioVideo", "Preview 15 s")
PREVIEW_SHORT_TOOLTIP = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Converts a 15-second sample so you can check the quality before converting the whole file.",
)
PREVIEW_FULL = QT_TRANSLATE_NOOP("RadioVideo", "Full Preview")
PREVIEW_FULL_TOOLTIP = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Converts the whole file without saving it, so you can watch the full result first.",
)
PREVIEW_HELPER = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Previews show the converted result with these exact settings, so you see the real quality "
    "before saving.",
)
CONVERT = QT_TRANSLATE_NOOP("RadioVideo", "Convert")

# Conversion states
STARTING_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "Starting…")
STARTING_TEXT = QT_TRANSLATE_NOOP("RadioVideo", "Preparing the conversion engine.")
CONVERTING_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "Converting…")
CONVERTING_WHAT = QT_TRANSLATE_NOOP("RadioVideo", "{format}, {quality}")
PROGRESS_PERCENT = QT_TRANSLATE_NOOP("RadioVideo", "{percent}%")
PROGRESS_SPEED = QT_TRANSLATE_NOOP("RadioVideo", "{speed}×")
PROGRESS_REMAINING = QT_TRANSLATE_NOOP("RadioVideo", "{time} remaining")
PROGRESS_SEPARATOR = QT_TRANSLATE_NOOP("RadioVideo", " · ")
CONVERTING_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Settings and opening files are locked until this finishes. Canceling deletes the "
    "unfinished file.",
)
CANCEL_CONVERSION = QT_TRANSLATE_NOOP("RadioVideo", "Cancel Conversion")
SPEED_TOOLTIP = QT_TRANSLATE_NOOP(
    "RadioVideo", "{speed}× means one minute of media takes about {seconds} seconds to convert."
)
SUCCESS_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "Saved {name} ({size})")
SUCCESS_TEXT = QT_TRANSLATE_NOOP("RadioVideo", "In {folder} · took {time}")
SHOW_IN_FOLDER = QT_TRANSLATE_NOOP("RadioVideo", "Show in Folder")
DONE = QT_TRANSLATE_NOOP("RadioVideo", "Done")
CANCELED_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "Conversion canceled")
CANCELED_TEXT = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Stopped at {percent}%. No file was saved and temporary files were removed. Your original "
    "is untouched.",
)
CONVERT_AGAIN = QT_TRANSLATE_NOOP("RadioVideo", "Convert Again")
DISMISS = QT_TRANSLATE_NOOP("RadioVideo", "Dismiss")
NOTIFY_DONE_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "Conversion finished")
NOTIFY_DONE_TEXT = QT_TRANSLATE_NOOP("RadioVideo", "{name} is ready.")
NOTIFY_FAILED_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "Conversion didn’t finish")
NOTIFY_FAILED_TEXT = QT_TRANSLATE_NOOP("RadioVideo", "Open Radio/Video to see what happened.")

# Dialogs
QUIT_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "Stop the conversion and quit?")
QUIT_TEXT = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "“{name}” is {percent}% done. If you quit now, the unfinished file is deleted. Your "
    "original file stays untouched.",
)
KEEP_CONVERTING = QT_TRANSLATE_NOOP("RadioVideo", "Keep Converting")
STOP_AND_QUIT = QT_TRANSLATE_NOOP("RadioVideo", "Stop and Quit")
QUIT_PREVIEW_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "Stop the preview and quit?")
QUIT_PREVIEW_TEXT = QT_TRANSLATE_NOOP("RadioVideo", "Nothing has been saved yet.")
KEEP_WORKING = QT_TRANSLATE_NOOP("RadioVideo", "Keep Working")
QUIT = QT_TRANSLATE_NOOP("RadioVideo", "Quit")
FAILED_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "The conversion didn’t finish")
WHAT_HAPPENED = QT_TRANSLATE_NOOP("RadioVideo", "What happened")
WHAT_TO_DO = QT_TRANSLATE_NOOP("RadioVideo", "What to do")
FAILED_REASSURANCE = QT_TRANSLATE_NOOP(
    "RadioVideo", "Your original file is untouched, and the unfinished file was deleted."
)
TECHNICAL_DETAILS = QT_TRANSLATE_NOOP("RadioVideo", "Technical details")
COPY_DETAILS = QT_TRANSLATE_NOOP("RadioVideo", "Copy Details")
COPY_DETAILS_TOOLTIP = QT_TRANSLATE_NOOP(
    "RadioVideo", "Copy the technical details, for example to report a problem"
)
DETAILS_COPIED = QT_TRANSLATE_NOOP("RadioVideo", "Copied. Paste it into a bug report or a message.")
CLOSE = QT_TRANSLATE_NOOP("RadioVideo", "Close")
ABOUT_VERSION = QT_TRANSLATE_NOOP("RadioVideo", "Version {version}")
ABOUT_TAGLINE = QT_TRANSLATE_NOOP(
    "RadioVideo", "Converts audio and video files, with honest previews of the result."
)
ABOUT_LICENSE_LABEL = QT_TRANSLATE_NOOP("RadioVideo", "License")
ABOUT_LICENSE = QT_TRANSLATE_NOOP("RadioVideo", "Free and open source, MIT License")
ABOUT_THIRD_PARTY_LABEL = QT_TRANSLATE_NOOP("RadioVideo", "Third-party")
ABOUT_THIRD_PARTY = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Qt 6 and PySide6 (LGPL v3). FFmpeg is installed separately and keeps its own license "
    "(LGPL or GPL, depending on the build).",
)
ABOUT_SOURCE_LABEL = QT_TRANSLATE_NOOP("RadioVideo", "Source code")
ABOUT_SOURCE = QT_TRANSLATE_NOOP("RadioVideo", "Repository on GitHub")

# Errors: what happened, what to do, primary action
ERROR_DISK_FULL_WHAT = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Drive {drive} ran out of free space at {percent}%, while saving the converted file.",
)
ERROR_DISK_FULL_DO = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Free up space on drive {drive}, or choose a folder on another drive, then convert again. "
    "You’ll need about {size}.",
)
ERROR_DISK_FULL_DO_NO_SIZE = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Free up space on drive {drive}, or choose a folder on another drive, then convert again.",
)
ERROR_NOT_WRITABLE_WHAT = QT_TRANSLATE_NOOP(
    "RadioVideo", "Radio/Video isn’t allowed to save in this folder."
)
ERROR_NOT_WRITABLE_DO = QT_TRANSLATE_NOOP(
    "RadioVideo", "Choose another folder, like Videos or Documents."
)
ERROR_PATH_TOO_LONG_WHAT = QT_TRANSLATE_NOOP(
    "RadioVideo", "The full path of the new file is longer than Windows allows."
)
ERROR_PATH_TOO_LONG_DO = QT_TRANSLATE_NOOP(
    "RadioVideo", "Choose a folder closer to the top of the drive, like C:\\Videos."
)
ERROR_SOURCE_MISSING_WHAT = QT_TRANSLATE_NOOP(
    "RadioVideo", "The original file was moved, renamed or deleted during the conversion."
)
ERROR_SOURCE_MISSING_DO = QT_TRANSLATE_NOOP("RadioVideo", "Open it again from its new location.")
ERROR_UNREADABLE_WHAT = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "This file couldn’t be read. It may be damaged, or not an audio or video file.",
)
ERROR_UNREADABLE_DO = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Try opening it in a media player. If it plays there, copy the technical details and "
    "report the problem.",
)
ERROR_NO_MEDIA_WHAT = QT_TRANSLATE_NOOP(
    "RadioVideo", "This file doesn’t contain any audio or video."
)
ERROR_NO_MEDIA_DO = QT_TRANSLATE_NOOP("RadioVideo", "Open an audio or video file instead.")
ERROR_ENCODER_WHAT = QT_TRANSLATE_NOOP(
    "RadioVideo", "The {encoder} encoder isn’t available in your FFmpeg build."
)
ERROR_ENCODER_DO = QT_TRANSLATE_NOOP(
    "RadioVideo", "Pick another format, or install a full FFmpeg build with winget."
)
ERROR_HARDWARE_WHAT = QT_TRANSLATE_NOOP(
    "RadioVideo", "The graphics card encoder stopped unexpectedly."
)
ERROR_HARDWARE_DO = QT_TRANSLATE_NOOP(
    "RadioVideo", "Convert again with software encoding; it’s slower but more reliable."
)
ERROR_UNKNOWN_WHAT = QT_TRANSLATE_NOOP(
    "RadioVideo", "FFmpeg stopped unexpectedly (exit code {code})."
)
ERROR_UNKNOWN_DO = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Try again. If it keeps happening, copy the technical details and report the problem.",
)
ACTION_CHOOSE_FOLDER = QT_TRANSLATE_NOOP("RadioVideo", "Choose Another Folder…")
ACTION_OPEN_ANOTHER = QT_TRANSLATE_NOOP("RadioVideo", "Open Another File…")
ACTION_CHOOSE_FORMAT = QT_TRANSLATE_NOOP("RadioVideo", "Choose Another Format")
ACTION_SOFTWARE = QT_TRANSLATE_NOOP("RadioVideo", "Convert with Software")
ACTION_TRY_AGAIN = QT_TRANSLATE_NOOP("RadioVideo", "Try Again")

# Planned screens

# Preview window
PREVIEW_WINDOW_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "Converted preview: {name}")
PREVIEW_BADGE = QT_TRANSLATE_NOOP("RadioVideo", "Converted preview")
PREVIEW_PART_SAMPLE = QT_TRANSLATE_NOOP("RadioVideo", "{length} starting at {start} of {total}")
PREVIEW_PART_FULL = QT_TRANSLATE_NOOP("RadioVideo", "The whole file, {total}")
PREVIEW_CREATING_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "Creating the preview…")
PREVIEW_CREATING_SAMPLE = QT_TRANSLATE_NOOP(
    "RadioVideo", "Converting a 15-second sample with your exact settings."
)
PREVIEW_CREATING_FULL = QT_TRANSLATE_NOOP(
    "RadioVideo", "Converting the whole file with your exact settings."
)
CANCEL = QT_TRANSLATE_NOOP("RadioVideo", "Cancel")
PREVIEW_READY_NOTE = QT_TRANSLATE_NOOP(
    "RadioVideo", "This is the converted output, not the original file."
)
PREVIEW_SIDE_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "This preview")
PREVIEW_PART = QT_TRANSLATE_NOOP("RadioVideo", "Part")
PREVIEW_SIZE = QT_TRANSLATE_NOOP("RadioVideo", "Preview size")
PREVIEW_SIZE_VALUE = QT_TRANSLATE_NOOP("RadioVideo", "{size} for {length}")
PREVIEW_FULL_SIZE = QT_TRANSLATE_NOOP("RadioVideo", "Estimated full size")
PREVIEW_FULL_SIZE_PENDING = QT_TRANSLATE_NOOP("RadioVideo", "Measured when the preview is ready")
PREVIEW_MEASURED_HERE = QT_TRANSLATE_NOOP("RadioVideo", "Measured from this preview")
PREVIEW_CALCULATED = QT_TRANSLATE_NOOP("RadioVideo", "Calculated from the bitrate")
PREVIEW_SETTINGS_USED = QT_TRANSLATE_NOOP("RadioVideo", "Settings used")
PREVIEW_AUDIO_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "Audio preview")
PREVIEW_AUDIO_TEXT = QT_TRANSLATE_NOOP("RadioVideo", "{settings} · {track}")
PREVIEW_FAILED_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "The preview couldn’t be created")
PREVIEW_FAILED_AT = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "FFmpeg stopped while reading the file around {time}. The original may be damaged at that "
    "point.",
)
PREVIEW_FAILED_AT_DO = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Try again. If it keeps failing, open the original in a media player to check that part.",
)
PREVIEW_CANCELED_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "Preview canceled")
PREVIEW_CANCELED_TEXT = QT_TRANSLATE_NOOP(
    "RadioVideo", "Nothing was saved. Your settings haven’t changed."
)
PREVIEW_AGAIN = QT_TRANSLATE_NOOP("RadioVideo", "Create Preview Again")
PREVIEW_CONVERT_FULL = QT_TRANSLATE_NOOP("RadioVideo", "Convert Full File")
PREVIEW_OUTDATED = QT_TRANSLATE_NOOP("RadioVideo", "Your settings changed after this preview.")
PREVIEW_UPDATE = QT_TRANSLATE_NOOP("RadioVideo", "Update Preview")
PREVIEW_PLAY_ORIGINAL = QT_TRANSLATE_NOOP("RadioVideo", "Play Original")
PREVIEW_PLAY_ORIGINAL_TOOLTIP = QT_TRANSLATE_NOOP(
    "RadioVideo", "Play the file you opened as it is, to compare"
)

# Original player: the opened file played as it is, nothing converted
ORIGINAL_WINDOW_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "Original: {name}")
ORIGINAL_BADGE = QT_TRANSLATE_NOOP("RadioVideo", "Original")
ORIGINAL_NOTE = QT_TRANSLATE_NOOP(
    "RadioVideo", "This is the file you opened, played as it is. Nothing was converted."
)
ORIGINAL_SIDE_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "This file")
ORIGINAL_SIZE = QT_TRANSLATE_NOOP("RadioVideo", "Size")
ORIGINAL_CONTENTS = QT_TRANSLATE_NOOP("RadioVideo", "Inside")
ORIGINAL_AUDIO_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "Original audio")
ORIGINAL_FAILED_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "This file can’t be played here")
ORIGINAL_FAILED_TEXT = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "The built-in player doesn’t support something in this file. It can still be converted.",
)
ORIGINAL_FAILED_DO = QT_TRANSLATE_NOOP(
    "RadioVideo", "Create a converted preview to watch it with your settings."
)
ORIGINAL_PREVIEW_CONVERTED = QT_TRANSLATE_NOOP("RadioVideo", "Preview Converted")
ORIGINAL_PREVIEW_CONVERTED_TOOLTIP = QT_TRANSLATE_NOOP(
    "RadioVideo", "Convert a 15-second sample with your settings and play it"
)
PLAY_SOURCE = QT_TRANSLATE_NOOP("RadioVideo", "Play")
PLAY_SOURCE_TOOLTIP = QT_TRANSLATE_NOOP(
    "RadioVideo", "Play the file as it is, without converting anything (Ctrl+Shift+Space)"
)

# Advanced Mode
ADV_TAB_VIDEO = QT_TRANSLATE_NOOP("RadioVideo", "Video")
ADV_TAB_AUDIO = QT_TRANSLATE_NOOP("RadioVideo", "Audio")
ADV_TAB_TRACKS = QT_TRANSLATE_NOOP("RadioVideo", "Tracks")
ADV_TAB_OUTPUT = QT_TRANSLATE_NOOP("RadioVideo", "Output and filters")
RECOMMENDED_VALUE = QT_TRANSLATE_NOOP("RadioVideo", "Recommended: {value}")
ADV_STREAM_COPY = QT_TRANSLATE_NOOP("RadioVideo", "Keep original video, no re-encode (stream copy)")
ADV_STREAM_COPY_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Copies the video exactly as it is: fastest and lossless, but the quality and size "
    "settings below don’t apply.",
)
ADV_ENCODER = QT_TRANSLATE_NOOP("RadioVideo", "Encoder")
ADV_ENCODER_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Software is slower but makes the smallest files. Hardware is 3–10× faster.",
)
ADV_QUALITY_METHOD = QT_TRANSLATE_NOOP("RadioVideo", "Quality method")
ADV_CONSTANT_QUALITY = QT_TRANSLATE_NOOP("RadioVideo", "Constant quality")
ADV_TARGET_BITRATE = QT_TRANSLATE_NOOP("RadioVideo", "Target bitrate")
ADV_QUALITY_METHOD_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Constant quality keeps the picture steady and lets the size vary. Target bitrate fixes "
    "the size.",
)
ADV_CRF = QT_TRANSLATE_NOOP("RadioVideo", "Quality (CRF)")
ADV_CRF_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Lower is better quality and a larger file. 18 looks near-original; 28 is visibly softer.",
)
ADV_PRESET = QT_TRANSLATE_NOOP("RadioVideo", "Preset")
ADV_PRESET_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo", "Slower presets make smaller files at the same quality, but take longer."
)
ADV_RESOLUTION = QT_TRANSLATE_NOOP("RadioVideo", "Resolution")
ADV_RESOLUTION_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo", "Lower resolutions make smaller files. Never upscales."
)
ADV_ASPECT = QT_TRANSLATE_NOOP("RadioVideo", "Aspect ratio")
ADV_ASPECT_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo", "Only changes how the picture is shaped on screen."
)
ADV_FRAME_RATE = QT_TRANSLATE_NOOP("RadioVideo", "Frame rate")
ADV_FRAME_RATE_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo", "Frames per second. Changing it can make motion look uneven."
)
ADV_PIXEL_FORMAT = QT_TRANSLATE_NOOP("RadioVideo", "Pixel format")
ADV_PIXEL_FORMAT_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo", "How colour is stored. yuv420p plays everywhere."
)
ADV_KEEP_ORIGINAL = QT_TRANSLATE_NOOP("RadioVideo", "Keep original")
ADV_KEEP_ORIGINAL_VALUE = QT_TRANSLATE_NOOP("RadioVideo", "Keep original ({value})")
ADV_CODEC = QT_TRANSLATE_NOOP("RadioVideo", "Codec")
ADV_CODEC_HELP = QT_TRANSLATE_NOOP("RadioVideo", "AAC fits MP4 and plays everywhere.")
ADV_BITRATE = QT_TRANSLATE_NOOP("RadioVideo", "Bitrate")
ADV_BITRATE_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "How much data per second. Higher means better quality and a larger file.",
)
ADV_SAMPLE_RATE = QT_TRANSLATE_NOOP("RadioVideo", "Sample rate")
ADV_SAMPLE_RATE_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo", "Samples per second. 48 kHz is standard for video."
)
ADV_CHANNELS = QT_TRANSLATE_NOOP("RadioVideo", "Channels")
ADV_CHANNELS_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo", "Stereo mixes surround sound down to two speakers."
)
ADV_AUDIO_NOTE = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "These settings apply to every audio track you keep. Choose tracks on the Tracks tab.",
)
ADV_TRACKS_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Choose which tracks go into the converted file. Unchecked tracks are left out. "
    "{kept} of {total} kept.",
)
ADV_TRACKS_KEEP = QT_TRANSLATE_NOOP("RadioVideo", "Keep")
ADV_TRACKS_TYPE = QT_TRANSLATE_NOOP("RadioVideo", "Type")
ADV_TRACKS_NAME = QT_TRANSLATE_NOOP("RadioVideo", "Language · Title")
ADV_TRACKS_OUTPUT = QT_TRANSLATE_NOOP("RadioVideo", "In the output")
ADV_TRACK_CONVERT = QT_TRANSLATE_NOOP("RadioVideo", "Convert to {codec}")
ADV_TRACK_COPY = QT_TRANSLATE_NOOP("RadioVideo", "Copy as it is")
ADV_TRACK_LEFT_OUT = QT_TRANSLATE_NOOP("RadioVideo", "Left out")
ADV_CONTAINER = QT_TRANSLATE_NOOP("RadioVideo", "Container")
ADV_CONTAINER_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "The file type that holds the tracks. Only containers that fit your codecs are listed.",
)
ADV_DEINTERLACE = QT_TRANSLATE_NOOP("RadioVideo", "Deinterlace")
ADV_DEINTERLACE_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo", "Removes comb-like lines from old TV and camcorder recordings."
)
ADV_DEINTERLACE_AUTO = QT_TRANSLATE_NOOP("RadioVideo", "Auto (only if needed)")
ADV_FAST_START = QT_TRANSLATE_NOOP("RadioVideo", "Fast start for web playback")
ADV_FAST_START_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Moves the file index to the start so web playback can begin before the download finishes.",
)
ADV_METADATA = QT_TRANSLATE_NOOP("RadioVideo", "Keep metadata and chapters")
ADV_METADATA_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Keeps the title, chapters, language labels and other tags from the original.",
)
ADV_LOUDNESS = QT_TRANSLATE_NOOP("RadioVideo", "Normalize loudness")
ADV_LOUDNESS_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Evens out volume so quiet and loud parts sound closer together. Re-encodes the audio.",
)
ADV_SUMMARY = QT_TRANSLATE_NOOP("RadioVideo", "Output summary")
ADV_SIZE_AFTER_PREVIEW = QT_TRANSLATE_NOOP("RadioVideo", "≈ size after preview")
ADV_STREAM_COPY_UNAVAILABLE = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "{container} can’t hold {codec} video as it is. Choose MKV on the Output tab to copy it.",
)
ADV_NO_VIDEO = QT_TRANSLATE_NOOP(
    "RadioVideo", "{format} has no video. Pick a video format to change video settings."
)
ADV_ENCODER_SOFTWARE = QT_TRANSLATE_NOOP("RadioVideo", "{codec} · Software ({encoder})")
ADV_ENCODER_HARDWARE = QT_TRANSLATE_NOOP("RadioVideo", "{codec} · Graphics card ({technology})")
ADV_ENCODER_DETECTED = QT_TRANSLATE_NOOP("RadioVideo", "{technology} detected")
ADV_ENCODER_SOFTWARE_ONLY = QT_TRANSLATE_NOOP(
    "RadioVideo", "No graphics card encoder for {codec} was found on this computer."
)
ADV_PRESET_HARDWARE = QT_TRANSLATE_NOOP(
    "RadioVideo", "The graphics card uses its own balanced preset."
)
ADV_VIDEO_BITRATE = QT_TRANSLATE_NOOP("RadioVideo", "Video bitrate")
ADV_VIDEO_BITRATE_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo", "Bits per second for the picture. 8 Mb/s suits 1080p; 5 Mb/s suits 720p."
)
ADV_SET_BY_QUALITY = QT_TRANSLATE_NOOP("RadioVideo", "Set by quality ({value})")
ADV_VARIABLE_QUALITY = QT_TRANSLATE_NOOP("RadioVideo", "variable, quality {value}")
ADV_PIXEL_8BIT = QT_TRANSLATE_NOOP("RadioVideo", "8-bit, most compatible")
ADV_PIXEL_422 = QT_TRANSLATE_NOOP("RadioVideo", "8-bit, more colour detail, less compatible")
ADV_PIXEL_444 = QT_TRANSLATE_NOOP("RadioVideo", "8-bit, full colour detail, least compatible")
ADV_PIXEL_10BIT = QT_TRANSLATE_NOOP("RadioVideo", "10-bit, smoother gradients, newer devices")
ADV_AUDIO_COPY = QT_TRANSLATE_NOOP("RadioVideo", "Keep original audio (copy)")
ADV_AUDIO_COPY_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo", "Copies the audio exactly as it is. Bitrate and channel settings don’t apply."
)
ADV_CODEC_HELP_VIDEO = QT_TRANSLATE_NOOP(
    "RadioVideo", "Only codecs that {container} can hold are listed."
)
ADV_CODEC_HELP_AUDIO = QT_TRANSLATE_NOOP(
    "RadioVideo", "The codec is the format itself. Pick another format to change it."
)
ADV_NO_AUDIO_KEPT = QT_TRANSLATE_NOOP(
    "RadioVideo", "No audio track is kept. Choose tracks on the Tracks tab."
)
ADV_TRACK_NOT_SUPPORTED = QT_TRANSLATE_NOOP("RadioVideo", "{format} can’t store this track")
ADV_TRACK_ONE_OF = QT_TRANSLATE_NOOP(
    "RadioVideo", "Only one {kind} track fits; checking another replaces it."
)
ADV_DEINTERLACE_OFF = QT_TRANSLATE_NOOP("RadioVideo", "Off")
ADV_DEINTERLACE_ALWAYS = QT_TRANSLATE_NOOP("RadioVideo", "Always")
ADV_LOUDNESS_COPY = QT_TRANSLATE_NOOP(
    "RadioVideo", "Not available while the audio is copied as it is."
)
CUSTOM_QUALITY = QT_TRANSLATE_NOOP("RadioVideo", "Quality: Custom (set in Advanced)")
CUSTOM_RESET = QT_TRANSLATE_NOOP("RadioVideo", "Reset to Balanced")

# Queue
QUEUE_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "Queue")
QUEUE_TEXT = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Convert many files one after another. Each file keeps its own format and quality.",
)
QUEUE_PAUSE_AFTER = QT_TRANSLATE_NOOP("RadioVideo", "Pause after the current file")
QUEUE_STOP = QT_TRANSLATE_NOOP("RadioVideo", "Stop Queue")
QUEUE_ADD = QT_TRANSLATE_NOOP("RadioVideo", "Add Files…")
QUEUE_UP = QT_TRANSLATE_NOOP("RadioVideo", "Move Up")
QUEUE_DOWN = QT_TRANSLATE_NOOP("RadioVideo", "Move Down")
QUEUE_RETRY = QT_TRANSLATE_NOOP("RadioVideo", "Retry")
QUEUE_REMOVE = QT_TRANSLATE_NOOP("RadioVideo", "Remove")
QUEUE_START = QT_TRANSLATE_NOOP("RadioVideo", "Start Queue")
QUEUE_CLEAR = QT_TRANSLATE_NOOP("RadioVideo", "Clear Finished")
QUEUE_SHORTCUTS = QT_TRANSLATE_NOOP("RadioVideo", "Delete removes · Alt+Up/Down moves")
QUEUE_EMPTY_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "The queue is empty")
QUEUE_EMPTY_TEXT = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Add files here with Add Files…, drop several files on the window, or set up a file on "
    "the Convert tab and choose Add to Queue. Each file is converted with its own settings.",
)
QUEUE_START_BLOCKED = QT_TRANSLATE_NOOP(
    "RadioVideo", "The queue can start when the conversion on the Convert tab finishes."
)
QUEUE_NOTHING_WAITING = QT_TRANSLATE_NOOP("RadioVideo", "No file is waiting.")
QUEUE_SAVED = QT_TRANSLATE_NOOP("RadioVideo", "Saved · took {time}")
QUEUE_CANCELED_AT = QT_TRANSLATE_NOOP("RadioVideo", "Canceled at {percent}%")
QUEUE_CANT_READ = QT_TRANSLATE_NOOP("RadioVideo", "Can’t read this file")
QUEUE_CUSTOM = QT_TRANSLATE_NOOP("RadioVideo", "{what} · Custom")
QUEUE_DONE_PART = QT_TRANSLATE_NOOP("RadioVideo", "{count} done")
QUEUE_CONVERTING_PART = QT_TRANSLATE_NOOP("RadioVideo", "{count} converting")
QUEUE_WAITING_PART = QT_TRANSLATE_NOOP("RadioVideo", "{count} waiting")
QUEUE_FAILED_PART = QT_TRANSLATE_NOOP("RadioVideo", "{count} failed")
QUEUE_CANCELED_PART = QT_TRANSLATE_NOOP("RadioVideo", "{count} canceled")
QUEUE_FINISHED_STATUS = QT_TRANSLATE_NOOP("RadioVideo", "Queue finished")
QUEUE_RUNNING_STATUS = QT_TRANSLATE_NOOP(
    "RadioVideo", "Converting file {current} of {total}… {percent}%"
)
QUEUE_TAB_COUNT = QT_TRANSLATE_NOOP("RadioVideo", "Queue · {count}")
ADD_TO_QUEUE = QT_TRANSLATE_NOOP("RadioVideo", "Add to Queue")
ADD_TO_QUEUE_TOOLTIP = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Convert this file later with these settings, after the files already in the queue "
    "(Ctrl+Shift+Enter)",
)
QUEUE_ADDED = QT_TRANSLATE_NOOP("RadioVideo", "Added to the queue: {name}")
QUEUE_ADD_DIALOG = QT_TRANSLATE_NOOP("RadioVideo", "Add Files to the Queue")
CONVERT_BLOCKED_QUEUE = QT_TRANSLATE_NOOP(
    "RadioVideo", "The queue is converting. Stop it on the Queue tab, or add this file to it."
)
NOTIFY_QUEUE_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "Queue finished")
QUIT_QUEUE_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "Stop the queue and quit?")
QUEUE_COLUMNS = (
    QT_TRANSLATE_NOOP("RadioVideo", "#"),
    QT_TRANSLATE_NOOP("RadioVideo", "File"),
    QT_TRANSLATE_NOOP("RadioVideo", "Convert to"),
    QT_TRANSLATE_NOOP("RadioVideo", "Status"),
    QT_TRANSLATE_NOOP("RadioVideo", "Progress"),
    QT_TRANSLATE_NOOP("RadioVideo", "Size"),
)
STATUS_DONE = QT_TRANSLATE_NOOP("RadioVideo", "Done")
STATUS_CONVERTING_BADGE = QT_TRANSLATE_NOOP("RadioVideo", "Converting")
STATUS_WAITING = QT_TRANSLATE_NOOP("RadioVideo", "Waiting")
STATUS_FAILED = QT_TRANSLATE_NOOP("RadioVideo", "Failed")
STATUS_CANCELED = QT_TRANSLATE_NOOP("RadioVideo", "Canceled")
QUEUE_FILE_OF = QT_TRANSLATE_NOOP("RadioVideo", "File {current} of {total}")
QUEUE_COUNTS = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "{done} done · {converting} converting · {waiting} waiting · {failed} failed · "
    "{canceled} canceled",
)

# History
HISTORY_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "History")
HISTORY_TEXT = QT_TRANSLATE_NOOP(
    "RadioVideo", "Your past conversions, with the settings used. Stored only on this computer."
)
HISTORY_CLEAR = QT_TRANSLATE_NOOP("RadioVideo", "Clear History…")
HISTORY_COLUMNS = (
    QT_TRANSLATE_NOOP("RadioVideo", "When"),
    QT_TRANSLATE_NOOP("RadioVideo", "File"),
    QT_TRANSLATE_NOOP("RadioVideo", "Format and quality"),
    QT_TRANSLATE_NOOP("RadioVideo", "Result"),
    QT_TRANSLATE_NOOP("RadioVideo", "Size"),
    QT_TRANSLATE_NOOP("RadioVideo", "Took"),
    QT_TRANSLATE_NOOP("RadioVideo", "Actions"),
)
HISTORY_SAVED = QT_TRANSLATE_NOOP("RadioVideo", "Saved")
HISTORY_MOVED = QT_TRANSLATE_NOOP("RadioVideo", "File moved")
HISTORY_OPEN = QT_TRANSLATE_NOOP("RadioVideo", "Open")
HISTORY_DETAILS = QT_TRANSLATE_NOOP("RadioVideo", "Details")
HISTORY_NO_FILE = QT_TRANSLATE_NOOP("RadioVideo", "No file saved")
HISTORY_GONE = QT_TRANSLATE_NOOP("RadioVideo", "The output file was moved or deleted")
HISTORY_EMPTY = QT_TRANSLATE_NOOP("RadioVideo", "Conversions you finish will appear here.")
HISTORY_TODAY = QT_TRANSLATE_NOOP("RadioVideo", "Today, {time}")
HISTORY_YESTERDAY = QT_TRANSLATE_NOOP("RadioVideo", "Yesterday, {time}")
HISTORY_DATE = QT_TRANSLATE_NOOP("RadioVideo", "{date}, {time}")
HISTORY_CANCELED_AT = QT_TRANSLATE_NOOP("RadioVideo", "No file saved · canceled at {percent}%")
HISTORY_CLEAR_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "Clear the history?")
HISTORY_CLEAR_TEXT = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "This removes the list of past conversions from this computer. The converted files "
    "themselves are kept.",
)
HISTORY_CLEAR_CONFIRM = QT_TRANSLATE_NOOP("RadioVideo", "Clear History")
HISTORY_DETAILS_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "{name} wasn’t converted")

# Settings
SETTINGS_TITLE = QT_TRANSLATE_NOOP("RadioVideo", "Settings")
SETTINGS_TEXT = QT_TRANSLATE_NOOP("RadioVideo", "Changes are saved as you make them.")
SETTINGS_ENGINE = QT_TRANSLATE_NOOP("RadioVideo", "Conversion engine")
SETTINGS_ENGINE_TEXT = QT_TRANSLATE_NOOP(
    "RadioVideo", "Radio/Video uses FFmpeg to read and convert files."
)
SETTINGS_WORKING = QT_TRANSLATE_NOOP("RadioVideo", "Working")
SETTINGS_FOUND = QT_TRANSLATE_NOOP("RadioVideo", "FFmpeg {version}, {source}")
SETTINGS_SOURCE_CHOSEN = QT_TRANSLATE_NOOP("RadioVideo", "chosen here")
SETTINGS_SOURCE_BUNDLED = QT_TRANSLATE_NOOP("RadioVideo", "included with Radio/Video")
SETTINGS_SOURCE_ENV = QT_TRANSLATE_NOOP("RadioVideo", "set by {variable}")
SETTINGS_SOURCE_PATH = QT_TRANSLATE_NOOP("RadioVideo", "found on the system PATH")
SETTINGS_NOT_FOUND = QT_TRANSLATE_NOOP("RadioVideo", "Not found")
SETTINGS_MISSING = QT_TRANSLATE_NOOP(
    "RadioVideo", "FFmpeg wasn’t found. Choose ffmpeg.exe and ffprobe.exe, or install it."
)
SETTINGS_NOT_CHOSEN = QT_TRANSLATE_NOOP("RadioVideo", "Not found")
SETTINGS_FIND_AUTOMATICALLY = QT_TRANSLATE_NOOP("RadioVideo", "Find Automatically")
SETTINGS_RESTART = QT_TRANSLATE_NOOP(
    "RadioVideo", "Restart Radio/Video to switch to the FFmpeg chosen here."
)
SETTINGS_RESTART_AUTOMATIC = QT_TRANSLATE_NOOP(
    "RadioVideo", "Restart Radio/Video to go back to the FFmpeg it finds by itself."
)
SETTINGS_NOT_PROGRAM = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "{name} didn’t answer as {program}. Choose {program}.exe from an FFmpeg build.",
)
SETTINGS_CHOOSE_PROGRAM = QT_TRANSLATE_NOOP("RadioVideo", "Choose {program}.exe")
SETTINGS_PROGRAM_FILTER = QT_TRANSLATE_NOOP("RadioVideo", "Programs (*.exe)")
SETTINGS_AUTOMATIC_FOLDER = QT_TRANSLATE_NOOP(
    "RadioVideo", "Your Videos folder (Music for audio files)"
)
SETTINGS_TEMP_DEFAULT = QT_TRANSLATE_NOOP("RadioVideo", "{path} (the Windows temporary folder)")
SETTINGS_USE_DEFAULT = QT_TRANSLATE_NOOP("RadioVideo", "Use Default")
SETTINGS_FOLDER_NOT_WRITABLE = QT_TRANSLATE_NOOP(
    "RadioVideo", "Radio/Video can’t write to {folder}. Choose another folder."
)
SETTINGS_DEFAULTS = QT_TRANSLATE_NOOP("RadioVideo", "Defaults")
SETTINGS_DEFAULTS_TEXT = QT_TRANSLATE_NOOP("RadioVideo", "What a newly opened file starts with.")
SETTINGS_SAVE_TO = QT_TRANSLATE_NOOP("RadioVideo", "Save converted files to")
SETTINGS_SAME_FOLDER = QT_TRANSLATE_NOOP("RadioVideo", "The same folder as the original file")
SETTINGS_THIS_FOLDER = QT_TRANSLATE_NOOP("RadioVideo", "This folder:")
SETTINGS_VIDEO_FORMAT = QT_TRANSLATE_NOOP("RadioVideo", "Format for video files")
SETTINGS_AUDIO_FORMAT = QT_TRANSLATE_NOOP("RadioVideo", "Format for audio files")
SETTINGS_PERFORMANCE = QT_TRANSLATE_NOOP("RadioVideo", "Performance")
SETTINGS_PERFORMANCE_TEXT = QT_TRANSLATE_NOOP(
    "RadioVideo", "Speed up conversions on supported graphics cards."
)
SETTINGS_HARDWARE = QT_TRANSLATE_NOOP("RadioVideo", "Use hardware acceleration when available")
SETTINGS_HARDWARE_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo", "Files may be slightly larger at the same quality."
)
SETTINGS_HARDWARE_DETECTED = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Detected: {adapter} ({technology}). Files may be slightly larger at the same quality.",
)
SETTINGS_HARDWARE_CHECKING = QT_TRANSLATE_NOOP("RadioVideo", "Checking your graphics card…")
SETTINGS_HARDWARE_NONE = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "No supported graphics card found (NVIDIA, AMD or Intel). Conversions use the processor.",
)
SETTINGS_TEMP = QT_TRANSLATE_NOOP("RadioVideo", "Temporary files")
SETTINGS_TEMP_TEXT = QT_TRANSLATE_NOOP(
    "RadioVideo",
    "Previews are made here and deleted when the preview window closes. Unfinished "
    "conversions are written next to the final file instead.",
)
SETTINGS_LOCATION = QT_TRANSLATE_NOOP("RadioVideo", "Location")
SETTINGS_LOCATION_HELP = QT_TRANSLATE_NOOP(
    "RadioVideo", "Needs free space roughly the size of your largest conversion."
)
SETTINGS_APPEARANCE = QT_TRANSLATE_NOOP("RadioVideo", "Appearance")
SETTINGS_APPEARANCE_TEXT = QT_TRANSLATE_NOOP("RadioVideo", "Light or dark.")
SETTINGS_THEME = QT_TRANSLATE_NOOP("RadioVideo", "Theme")
SETTINGS_THEME_SYSTEM = QT_TRANSLATE_NOOP("RadioVideo", "Use Windows setting")
SETTINGS_THEME_LIGHT = QT_TRANSLATE_NOOP("RadioVideo", "Light")
SETTINGS_THEME_DARK = QT_TRANSLATE_NOOP("RadioVideo", "Dark")
