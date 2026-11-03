from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from radio_video.errors import RadioVideoError

FFMPEG_ENV = "RADIO_VIDEO_FFMPEG"
FFPROBE_ENV = "RADIO_VIDEO_FFPROBE"
# The Windows installer places FFmpeg in this folder next to the executable.
BUNDLED_FOLDER = "ffmpeg"


class FFmpegNotFoundError(RadioVideoError):
    def __init__(self, program: str, env_var: str) -> None:
        super().__init__(
            f"{program} was not found. Install FFmpeg and add it to PATH, "
            f"or set {env_var} to the full path of the executable."
        )
        self.program = program
        self.env_var = env_var


@dataclass(frozen=True)
class FFmpegTools:
    ffmpeg: Path
    ffprobe: Path


def _executable_name(program: str) -> str:
    return f"{program}.exe" if sys.platform == "win32" else program


def _find(
    program: str,
    env_var: str,
    search_dirs: Iterable[Path],
    environ: Mapping[str, str],
) -> Path:
    override = environ.get(env_var)
    if override:
        path = Path(override)
        if path.is_file():
            return path.resolve()
        raise FFmpegNotFoundError(program, env_var)

    name = _executable_name(program)
    for directory in search_dirs:
        candidate = directory / name
        if candidate.is_file():
            return candidate.resolve()

    found = shutil.which(program, path=environ.get("PATH"))
    if found:
        return Path(found).resolve()
    raise FFmpegNotFoundError(program, env_var)


def bundled_dirs() -> tuple[Path, ...]:
    """Folders with the FFmpeg that ships with the installed application, if any."""
    if getattr(sys, "frozen", False):
        return (Path(sys.executable).resolve().parent / BUNDLED_FOLDER,)
    return ()


def locate_tools(
    search_dirs: Iterable[Path] | None = None,
    environ: Mapping[str, str] | None = None,
) -> FFmpegTools:
    """Find the ffmpeg and ffprobe executables.

    Lookup order: environment variable override, ``search_dirs`` (by default the FFmpeg bundled
    with the installed application), then ``PATH``.
    """
    env = os.environ if environ is None else environ
    dirs = tuple(bundled_dirs() if search_dirs is None else search_dirs)
    return FFmpegTools(
        ffmpeg=_find("ffmpeg", FFMPEG_ENV, dirs, env),
        ffprobe=_find("ffprobe", FFPROBE_ENV, dirs, env),
    )
