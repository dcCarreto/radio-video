from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class StreamType(StrEnum):
    VIDEO = "video"
    AUDIO = "audio"
    SUBTITLE = "subtitle"
    DATA = "data"
    ATTACHMENT = "attachment"
    UNKNOWN = "unknown"

    @classmethod
    def from_codec_type(cls, value: str | None) -> StreamType:
        try:
            return cls(value or "unknown")
        except ValueError:
            return cls.UNKNOWN


@dataclass(frozen=True)
class StreamInfo:
    index: int
    type: StreamType
    codec_name: str | None = None
    codec_long_name: str | None = None
    profile: str | None = None
    bit_rate: int | None = None
    duration: float | None = None
    language: str | None = None
    title: str | None = None
    is_default: bool = False
    is_attached_picture: bool = False
    width: int | None = None
    height: int | None = None
    pixel_format: str | None = None
    frame_rate: float | None = None
    display_aspect_ratio: str | None = None
    sample_rate: int | None = None
    channels: int | None = None
    channel_layout: str | None = None
    tags: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class MediaInfo:
    path: Path
    format_name: str
    format_long_name: str | None = None
    duration: float | None = None
    size: int | None = None
    bit_rate: int | None = None
    tags: Mapping[str, str] = field(default_factory=dict)
    streams: tuple[StreamInfo, ...] = ()

    def streams_of(self, stream_type: StreamType) -> tuple[StreamInfo, ...]:
        return tuple(stream for stream in self.streams if stream.type is stream_type)

    @property
    def video_streams(self) -> tuple[StreamInfo, ...]:
        """Video streams, excluding embedded cover art."""
        return tuple(s for s in self.streams_of(StreamType.VIDEO) if not s.is_attached_picture)

    @property
    def audio_streams(self) -> tuple[StreamInfo, ...]:
        return self.streams_of(StreamType.AUDIO)

    @property
    def subtitle_streams(self) -> tuple[StreamInfo, ...]:
        return self.streams_of(StreamType.SUBTITLE)

    @property
    def has_video(self) -> bool:
        return bool(self.video_streams)

    @property
    def has_audio(self) -> bool:
        return bool(self.audio_streams)
