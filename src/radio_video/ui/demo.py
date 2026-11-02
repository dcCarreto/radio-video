"""Demo media from the design, used by the UI gallery and tests."""

from __future__ import annotations

from pathlib import Path

from radio_video.models.media import MediaInfo, StreamInfo, StreamType

DEMO_FOLDER = Path("C:/Users/Ana/Videos/Exports")
DEMO_NAME = "Interview – Lisbon Studio Session (Final Cut, 2026-03-14)"


def _subtitle(
    index: int, language: str, title: str | None = None, default: bool = False
) -> StreamInfo:
    return StreamInfo(
        index=index,
        type=StreamType.SUBTITLE,
        codec_name="subrip",
        language=language,
        title=title,
        is_default=default,
    )


DEMO_STREAMS = (
    StreamInfo(
        index=0,
        type=StreamType.VIDEO,
        codec_name="h264",
        profile="High",
        width=1920,
        height=1080,
        frame_rate=24000 / 1001,
        bit_rate=10_400_000,
        title="Main",
    ),
    StreamInfo(
        index=1,
        type=StreamType.AUDIO,
        codec_name="aac",
        profile="LC",
        sample_rate=48000,
        channels=6,
        channel_layout="5.1",
        bit_rate=384_000,
        language="por",
        title="Original mix",
        is_default=True,
    ),
    StreamInfo(
        index=2,
        type=StreamType.AUDIO,
        codec_name="aac",
        profile="LC",
        sample_rate=48000,
        channels=2,
        channel_layout="stereo",
        bit_rate=192_000,
        language="eng",
        title="English dub",
    ),
    StreamInfo(
        index=3,
        type=StreamType.AUDIO,
        codec_name="opus",
        sample_rate=48000,
        channels=2,
        channel_layout="stereo",
        bit_rate=128_000,
        language="por",
        title="Director’s commentary",
    ),
    _subtitle(4, "por", default=True),
    _subtitle(5, "eng"),
    _subtitle(6, "spa"),
    _subtitle(7, "fra"),
    _subtitle(8, "deu"),
    _subtitle(9, "ita"),
    _subtitle(10, "eng", "Hearing impaired (SDH)"),
    StreamInfo(
        index=11,
        type=StreamType.VIDEO,
        codec_name="mjpeg",
        width=600,
        height=600,
        is_attached_picture=True,
        title="cover.jpg",
    ),
)

DEMO_MEDIA = MediaInfo(
    path=DEMO_FOLDER / f"{DEMO_NAME}.mkv",
    format_name="matroska,webm",
    format_long_name="Matroska / WebM",
    duration=133.0,
    size=195_456_614,
    bit_rate=11_200_000,
    tags={"title": "Lisbon Studio Session: full interview, director’s cut"},
    streams=DEMO_STREAMS,
)
