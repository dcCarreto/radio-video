from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from radio_video.models.tracks import StreamMap

COPY = "copy"

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def _check_name(kind: str, value: str | None) -> None:
    if value is not None and not _NAME.match(value):
        raise ValueError(f"Invalid {kind}: {value!r}")


def _check_positive(name: str, value: float | None) -> None:
    if value is not None and value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")


@dataclass(frozen=True)
class VideoOptions:
    """Video encoding options.

    ``bitrate=0`` removes the bitrate cap, which encoders such as libvpx-vp9 require for
    constant-quality (CRF-only) encoding.
    """

    codec: str
    crf: int | None = None
    bitrate: int | None = None
    preset: str | None = None
    width: int | None = None
    height: int | None = None
    frame_rate: float | None = None
    pixel_format: str | None = None

    def __post_init__(self) -> None:
        _check_name("video codec", self.codec)
        _check_name("preset", self.preset)
        _check_name("pixel format", self.pixel_format)
        for name in ("width", "height", "frame_rate"):
            _check_positive(name, getattr(self, name))
        if self.bitrate is not None and self.bitrate < 0:
            raise ValueError(f"bitrate must not be negative, got {self.bitrate}")
        if self.crf is not None and not 0 <= self.crf <= 63:
            raise ValueError(f"CRF must be between 0 and 63, got {self.crf}")
        if self.is_copy and self.has_encoding_options:
            raise ValueError("Encoding options cannot be combined with stream copy")

    @property
    def is_copy(self) -> bool:
        return self.codec == COPY

    @property
    def has_encoding_options(self) -> bool:
        return any(
            value is not None
            for value in (
                self.crf,
                self.bitrate,
                self.preset,
                self.width,
                self.height,
                self.frame_rate,
                self.pixel_format,
            )
        )


@dataclass(frozen=True)
class AudioOptions:
    """Audio encoding options. ``quality`` is the encoder's variable-bitrate scale (``-q:a``)."""

    codec: str
    bitrate: int | None = None
    sample_rate: int | None = None
    channels: int | None = None
    quality: float | None = None

    def __post_init__(self) -> None:
        _check_name("audio codec", self.codec)
        for name in ("bitrate", "sample_rate", "channels"):
            _check_positive(name, getattr(self, name))
        if self.bitrate is not None and self.quality is not None:
            raise ValueError("Use either a bitrate or a quality level, not both")
        if self.is_copy and any(
            value is not None
            for value in (self.bitrate, self.sample_rate, self.channels, self.quality)
        ):
            raise ValueError("Encoding options cannot be combined with stream copy")

    @property
    def is_copy(self) -> bool:
        return self.codec == COPY


@dataclass(frozen=True)
class ConversionSettings:
    """Output streams and encoding. ``None`` for video or audio drops that stream type."""

    video: VideoOptions | None
    audio: AudioOptions | None
    preserve_metadata: bool = True

    def __post_init__(self) -> None:
        if self.video is None and self.audio is None:
            raise ValueError("Output must contain video, audio or both")


@dataclass(frozen=True)
class ConversionJob:
    source: Path
    destination: Path
    settings: ConversionSettings
    duration: float | None = None
    start: float | None = None
    length: float | None = None
    overwrite: bool = False
    # Tracks to map. None keeps the first video and audio stream.
    streams: StreamMap | None = None

    def __post_init__(self) -> None:
        if self.source.resolve() == self.destination.resolve():
            raise ValueError("The output file must be different from the source file")
        if not self.destination.suffix:
            raise ValueError("The output file needs an extension")
        if self.start is not None and self.start < 0:
            raise ValueError("start must not be negative")
        _check_positive("length", self.length)

    @property
    def expected_duration(self) -> float | None:
        """Duration of the output, used to compute progress."""
        if self.duration is None:
            return self.length
        remaining = self.duration - (self.start or 0.0)
        if self.length is not None:
            remaining = min(remaining, self.length)
        return remaining if remaining > 0 else None
