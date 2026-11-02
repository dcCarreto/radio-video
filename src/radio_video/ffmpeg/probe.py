from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Mapping
from fractions import Fraction
from pathlib import Path
from typing import Any

from radio_video.errors import RadioVideoError
from radio_video.ffmpeg.process import CREATION_FLAGS
from radio_video.models.media import MediaInfo, StreamInfo, StreamType

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 60.0


class ProbeError(RadioVideoError):
    """The file could not be analyzed."""


def build_probe_command(ffprobe: Path, media: Path) -> list[str]:
    return [
        str(ffprobe),
        "-v",
        "error",
        "-hide_banner",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(media),
    ]


def probe(media: Path, ffprobe: Path, timeout: float = DEFAULT_TIMEOUT) -> MediaInfo:
    """Analyze a media file with FFprobe. Blocking; run off the GUI thread."""
    if not media.is_file():
        raise ProbeError(f"File not found: {media}")

    command = build_probe_command(ffprobe, media)
    logger.debug("Running %s", command)
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            timeout=timeout,
            check=False,
            creationflags=CREATION_FLAGS,
        )
    except subprocess.TimeoutExpired as exc:
        raise ProbeError(f"Analyzing {media.name} timed out after {timeout:.0f} s") from exc
    except OSError as exc:
        raise ProbeError(f"Could not run FFprobe: {exc}") from exc

    stderr = result.stderr.decode("utf-8", errors="replace").strip()
    if result.returncode != 0:
        detail = stderr.splitlines()[-1] if stderr else f"exit code {result.returncode}"
        raise ProbeError(f"{media.name} is not a readable media file ({detail})")

    try:
        data = json.loads(result.stdout.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise ProbeError(f"FFprobe returned invalid output for {media.name}") from exc
    return parse_probe_output(media, data)


def parse_probe_output(media: Path, data: Mapping[str, Any]) -> MediaInfo:
    fmt = data.get("format")
    if not isinstance(fmt, Mapping):
        raise ProbeError(f"{media.name} is not a recognized media file")

    streams = tuple(
        _parse_stream(stream) for stream in data.get("streams", []) if isinstance(stream, Mapping)
    )
    if not streams:
        raise ProbeError(f"{media.name} contains no audio or video streams")

    return MediaInfo(
        path=media,
        format_name=str(fmt.get("format_name", "")),
        format_long_name=_str(fmt.get("format_long_name")),
        duration=_positive_float(fmt.get("duration")),
        size=_int(fmt.get("size")),
        bit_rate=_int(fmt.get("bit_rate")),
        tags=_tags(fmt.get("tags")),
        streams=streams,
    )


def _parse_stream(stream: Mapping[str, Any]) -> StreamInfo:
    tags = _tags(stream.get("tags"))
    disposition = stream.get("disposition")
    if not isinstance(disposition, Mapping):
        disposition = {}
    return StreamInfo(
        index=_int(stream.get("index")) or 0,
        type=StreamType.from_codec_type(_str(stream.get("codec_type"))),
        codec_name=_str(stream.get("codec_name")),
        codec_long_name=_str(stream.get("codec_long_name")),
        profile=_str(stream.get("profile")),
        bit_rate=_int(stream.get("bit_rate")),
        duration=_positive_float(stream.get("duration")),
        language=_language(tags),
        title=_tag(tags, "title"),
        is_default=bool(disposition.get("default")),
        is_attached_picture=bool(disposition.get("attached_pic")),
        width=_int(stream.get("width")),
        height=_int(stream.get("height")),
        pixel_format=_str(stream.get("pix_fmt")),
        frame_rate=_frame_rate(stream.get("avg_frame_rate"))
        or _frame_rate(stream.get("r_frame_rate")),
        display_aspect_ratio=_aspect_ratio(stream.get("display_aspect_ratio")),
        sample_rate=_int(stream.get("sample_rate")),
        channels=_int(stream.get("channels")),
        channel_layout=_str(stream.get("channel_layout")),
        tags=tags,
    )


def _str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _positive_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _frame_rate(value: Any) -> float | None:
    try:
        rate = Fraction(str(value))
    except (ValueError, ZeroDivisionError):
        return None
    return float(rate) if rate > 0 else None


def _aspect_ratio(value: Any) -> str | None:
    text = _str(value)
    if text is None or text in {"0:1", "N/A"}:
        return None
    return text


def _tags(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def _tag(tags: Mapping[str, str], name: str) -> str | None:
    for key, value in tags.items():
        if key.lower() == name:
            return _str(value)
    return None


def _language(tags: Mapping[str, str]) -> str | None:
    language = _tag(tags, "language")
    return None if language == "und" else language
