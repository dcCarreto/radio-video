"""Finds the hardware video encoders that work on this computer."""

from __future__ import annotations

import ctypes
import logging
import subprocess
import sys
from collections.abc import Callable, Collection, Iterable
from pathlib import Path

from radio_video.ffmpeg.process import CREATION_FLAGS
from radio_video.models.hardware import (
    FAMILIES,
    HARDWARE_PIXEL_FORMAT,
    HardwareFamily,
    HardwareSupport,
)

logger = logging.getLogger(__name__)

# Large enough for every encoder's minimum frame size.
_TEST_SOURCE = "color=black:size=256x144:rate=25"


def probe_encoder(ffmpeg: Path, encoder: str, timeout: float = 15.0) -> bool:
    """Whether ``encoder`` can encode one frame.

    FFmpeg lists hardware encoders even without the graphics card or driver they need, so
    only a test encode tells whether they work.
    """
    args = [
        str(ffmpeg),
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        _TEST_SOURCE,
        "-frames:v",
        "1",
        "-pix_fmt",
        HARDWARE_PIXEL_FORMAT,
        "-c:v",
        encoder,
        "-f",
        "null",
        "-",
    ]
    try:
        result = subprocess.run(
            args, capture_output=True, timeout=timeout, check=False, creationflags=CREATION_FLAGS
        )
    except (OSError, subprocess.TimeoutExpired):
        logger.debug("Test encode with %s did not finish", encoder, exc_info=True)
        return False
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        logger.debug("%s is not usable: %s", encoder, detail)
    return result.returncode == 0


def adapter_names() -> list[str]:
    """Names of the display adapters, such as "NVIDIA GeForce RTX 4070 SUPER"."""
    if sys.platform != "win32":
        return []
    from ctypes import wintypes

    class DisplayDevice(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("DeviceName", wintypes.WCHAR * 32),
            ("DeviceString", wintypes.WCHAR * 128),
            ("StateFlags", wintypes.DWORD),
            ("DeviceID", wintypes.WCHAR * 128),
            ("DeviceKey", wintypes.WCHAR * 128),
        ]

    enum_devices = ctypes.WinDLL("user32").EnumDisplayDevicesW
    names: list[str] = []
    index = 0
    while True:
        device = DisplayDevice()
        device.cb = ctypes.sizeof(device)
        if not enum_devices(None, index, ctypes.byref(device), 0):
            break
        if device.DeviceString and device.DeviceString not in names:
            names.append(device.DeviceString)
        index += 1
    return names


def adapter_for(family: HardwareFamily, names: Iterable[str]) -> str | None:
    return next(
        (
            name
            for name in names
            if any(vendor.lower() in name.lower() for vendor in family.vendors)
        ),
        None,
    )


def detect_hardware(
    ffmpeg: Path,
    encoders: Collection[str],
    probe: Callable[[Path, str], bool] = probe_encoder,
    adapters: Callable[[], list[str]] = adapter_names,
) -> HardwareSupport | None:
    """The first hardware family, in order of preference, with at least one working encoder."""
    for family in FAMILIES:
        working = tuple(
            encoder
            for encoder in family.encoders
            if encoder.name in encoders and probe(ffmpeg, encoder.name)
        )
        if working:
            support = HardwareSupport(family, working, adapter_for(family, adapters()))
            logger.info(
                "Hardware encoding available: %s (%s) on %s",
                family.technology,
                ", ".join(encoder.name for encoder in working),
                support.adapter or "an unnamed adapter",
            )
            return support
    logger.info("No working hardware video encoder found")
    return None
