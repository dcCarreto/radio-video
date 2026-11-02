from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

from radio_video.errors import RadioVideoError
from radio_video.ffmpeg.process import CREATION_FLAGS

logger = logging.getLogger(__name__)

# " V....D libx264              libx264 H.264 / AVC / ..." -> flags, name
# "ffmpeg version 7.1-full_build-www.gyan.dev Copyright ..." -> "7.1"
_VERSION_LINE = re.compile(r"^ffmpeg version n?(\d+(?:\.\d+)*)", re.IGNORECASE)
_ENCODER_LINE = re.compile(r"^\s*([VAS][F.][S.][X.][B.][D.])\s+([A-Za-z0-9_-]+)\s")


class CapabilityError(RadioVideoError):
    """FFmpeg capabilities could not be determined."""


def parse_encoders(output: str) -> frozenset[str]:
    return frozenset(
        match.group(2) for line in output.splitlines() if (match := _ENCODER_LINE.match(line))
    )


def list_encoders(ffmpeg: Path, timeout: float = 15.0) -> frozenset[str]:
    try:
        result = subprocess.run(
            [str(ffmpeg), "-hide_banner", "-encoders"],
            capture_output=True,
            timeout=timeout,
            check=False,
            creationflags=CREATION_FLAGS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CapabilityError(f"Could not query FFmpeg encoders: {exc}") from exc
    if result.returncode != 0:
        raise CapabilityError(f"FFmpeg exited with code {result.returncode} listing encoders")
    encoders = parse_encoders(result.stdout.decode("utf-8", errors="replace"))
    logger.debug("FFmpeg provides %d encoders", len(encoders))
    return encoders


def parse_version(output: str) -> str | None:
    match = _VERSION_LINE.match(output.strip())
    return match.group(1) if match else None


def ffmpeg_version(ffmpeg: Path, timeout: float = 15.0) -> str | None:
    """The FFmpeg release number, such as "7.1", or None if it cannot be read."""
    try:
        result = subprocess.run(
            [str(ffmpeg), "-hide_banner", "-version"],
            capture_output=True,
            timeout=timeout,
            check=False,
            creationflags=CREATION_FLAGS,
        )
    except (OSError, subprocess.TimeoutExpired):
        logger.debug("Could not read the FFmpeg version", exc_info=True)
        return None
    return parse_version(result.stdout.decode("utf-8", errors="replace"))
