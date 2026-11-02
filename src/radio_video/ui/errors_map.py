"""Classifies FFmpeg and FFprobe failures into plain-language messages.

Each message says what happened in one sentence, what to do in one or two, and offers the
most likely fix as the primary action. The raw output stays available as technical details.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from radio_video.ui import strings as s
from radio_video.ui.strings import tr
from radio_video.ui.viewmodel import format_estimate_size

WINDOWS_MAX_PATH = 259

_DISK_FULL = re.compile(
    r"no space left on device|not enough space on the disk|disk (is )?full", re.IGNORECASE
)
_PATH_TOO_LONG = re.compile(r"file ?name too long|path too long", re.IGNORECASE)
_NOT_WRITABLE = re.compile(
    r"permission denied|access is denied|operation not permitted|read-only file system",
    re.IGNORECASE,
)
_ENCODER = re.compile(
    r"unknown encoder '([^']+)'|encoder '?([\w-]+)'? not found|"
    r"encoder \(codec ([\w-]+)\) not found",
    re.IGNORECASE,
)
_HARDWARE = re.compile(r"\b(\w+_(nvenc|qsv|amf|vaapi|mf))\b|nvenc|cuda", re.IGNORECASE)
_NO_MEDIA = re.compile(
    r"contains no audio or video|does not contain any stream|matches no streams", re.IGNORECASE
)
_UNREADABLE = re.compile(
    r"invalid data found when processing input|moov atom not found|not a readable media file|"
    r"not a recognized media file|error while decoding|corrupt",
    re.IGNORECASE,
)
_EXIT_CODE = re.compile(r"exit(?:ed with)? code (-?\d+)", re.IGNORECASE)


class ErrorKind(Enum):
    DISK_FULL = "disk_full"
    NOT_WRITABLE = "not_writable"
    PATH_TOO_LONG = "path_too_long"
    SOURCE_MISSING = "source_missing"
    UNREADABLE = "unreadable"
    NO_MEDIA = "no_media"
    ENCODER_UNAVAILABLE = "encoder_unavailable"
    HARDWARE_ENCODER = "hardware_encoder"
    UNKNOWN = "unknown"


class NextStep(Enum):
    CHOOSE_FOLDER = "choose_folder"
    OPEN_FILE = "open_file"
    OPEN_ANOTHER = "open_another"
    CHOOSE_FORMAT = "choose_format"
    CONVERT_WITH_SOFTWARE = "software"
    TRY_AGAIN = "try_again"


ACTION_TEXT = {
    NextStep.CHOOSE_FOLDER: s.ACTION_CHOOSE_FOLDER,
    NextStep.OPEN_FILE: s.ACTION_OPEN,
    NextStep.OPEN_ANOTHER: s.ACTION_OPEN_ANOTHER,
    NextStep.CHOOSE_FORMAT: s.ACTION_CHOOSE_FORMAT,
    NextStep.CONVERT_WITH_SOFTWARE: s.ACTION_SOFTWARE,
    NextStep.TRY_AGAIN: s.ACTION_TRY_AGAIN,
}


@dataclass(frozen=True)
class Failure:
    """What is known when something fails."""

    details: str
    source: Path
    destination: Path | None = None
    fraction: float = 0.0
    needed_bytes: int | None = None


@dataclass(frozen=True)
class ErrorReport:
    kind: ErrorKind
    what_happened: str
    what_to_do: str
    next_step: NextStep
    details: str

    @property
    def action_text(self) -> str:
        return tr(ACTION_TEXT[self.next_step])


def classify(failure: Failure) -> ErrorKind:
    details = failure.details
    if not failure.source.exists():
        return ErrorKind.SOURCE_MISSING
    if _DISK_FULL.search(details) or exit_code(details) == "-28":
        return ErrorKind.DISK_FULL
    if _PATH_TOO_LONG.search(details) or (
        failure.destination is not None and len(str(failure.destination)) > WINDOWS_MAX_PATH
    ):
        return ErrorKind.PATH_TOO_LONG
    if _NOT_WRITABLE.search(details):
        return ErrorKind.NOT_WRITABLE
    if _ENCODER.search(details):
        return ErrorKind.ENCODER_UNAVAILABLE
    if _NO_MEDIA.search(details):
        return ErrorKind.NO_MEDIA
    if _UNREADABLE.search(details):
        return ErrorKind.UNREADABLE
    if _HARDWARE.search(details):
        return ErrorKind.HARDWARE_ENCODER
    return ErrorKind.UNKNOWN


def exit_code(details: str) -> str | None:
    matches = _EXIT_CODE.findall(details)
    return matches[-1] if matches else None


def encoder_name(details: str) -> str:
    match = _ENCODER.search(details)
    if match is None:
        return "?"
    return next(group for group in match.groups() if group)


def _drive(path: Path | None) -> str:
    if path is None:
        return ""
    return path.drive or path.anchor or str(path)


def describe(failure: Failure) -> ErrorReport:
    kind = classify(failure)
    destination = failure.destination
    if kind is ErrorKind.DISK_FULL:
        drive = _drive(destination)
        percent = min(100, max(0, round(failure.fraction * 100)))
        what = tr(s.ERROR_DISK_FULL_WHAT).format(drive=drive, percent=percent)
        if failure.needed_bytes:
            todo = tr(s.ERROR_DISK_FULL_DO).format(
                drive=drive, size=format_estimate_size(failure.needed_bytes)
            )
        else:
            todo = tr(s.ERROR_DISK_FULL_DO_NO_SIZE).format(drive=drive)
        step = NextStep.CHOOSE_FOLDER
    elif kind is ErrorKind.NOT_WRITABLE:
        what, todo = tr(s.ERROR_NOT_WRITABLE_WHAT), tr(s.ERROR_NOT_WRITABLE_DO)
        step = NextStep.CHOOSE_FOLDER
    elif kind is ErrorKind.PATH_TOO_LONG:
        what, todo = tr(s.ERROR_PATH_TOO_LONG_WHAT), tr(s.ERROR_PATH_TOO_LONG_DO)
        step = NextStep.CHOOSE_FOLDER
    elif kind is ErrorKind.SOURCE_MISSING:
        what, todo = tr(s.ERROR_SOURCE_MISSING_WHAT), tr(s.ERROR_SOURCE_MISSING_DO)
        step = NextStep.OPEN_FILE
    elif kind is ErrorKind.UNREADABLE:
        what, todo = tr(s.ERROR_UNREADABLE_WHAT), tr(s.ERROR_UNREADABLE_DO)
        step = NextStep.OPEN_ANOTHER
    elif kind is ErrorKind.NO_MEDIA:
        what, todo = tr(s.ERROR_NO_MEDIA_WHAT), tr(s.ERROR_NO_MEDIA_DO)
        step = NextStep.OPEN_ANOTHER
    elif kind is ErrorKind.ENCODER_UNAVAILABLE:
        what = tr(s.ERROR_ENCODER_WHAT).format(encoder=encoder_name(failure.details))
        todo = tr(s.ERROR_ENCODER_DO)
        step = NextStep.CHOOSE_FORMAT
    elif kind is ErrorKind.HARDWARE_ENCODER:
        what, todo = tr(s.ERROR_HARDWARE_WHAT), tr(s.ERROR_HARDWARE_DO)
        step = NextStep.CONVERT_WITH_SOFTWARE
    else:
        what = tr(s.ERROR_UNKNOWN_WHAT).format(code=exit_code(failure.details) or "?")
        todo = tr(s.ERROR_UNKNOWN_DO)
        step = NextStep.TRY_AGAIN
    return ErrorReport(kind, what, todo, step, failure.details)
