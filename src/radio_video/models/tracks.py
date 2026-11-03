"""Which source tracks go into the output, decided per output format."""

from __future__ import annotations

from dataclasses import dataclass

from radio_video.models.media import MediaInfo, StreamInfo, StreamType

# Subtitle codecs that are text and can be converted to MP4 text or WebVTT. Image-based
# subtitles (PGS, DVD, DVB) can only be copied into containers that support them.
TEXT_SUBTITLE_CODECS = frozenset(
    {
        "subrip",
        "srt",
        "ass",
        "ssa",
        "webvtt",
        "mov_text",
        "text",
        "microdvd",
        "subviewer",
        "subviewer1",
        "jacosub",
        "sami",
        "realtext",
        "stl",
        "mpl2",
        "pjs",
        "vplayer",
    }
)

SUBTITLE_COPY = "copy"
STEREO = 2


@dataclass(frozen=True)
class TrackPolicy:
    """What an output format keeps.

    ``subtitle_codec`` is ``"copy"``, an encoder such as ``"mov_text"``, or None to leave
    subtitles out. Lossy audio-only formats mix surround sound down to stereo.
    """

    all_audio: bool = False
    subtitle_codec: str | None = None
    cover_art: bool = False
    downmix_to_stereo: bool = False


@dataclass(frozen=True)
class StreamMap:
    """Source stream indices mapped into the output, in output order."""

    video: int | None = None
    audio: tuple[int, ...] = ()
    subtitles: tuple[int, ...] = ()
    cover_art: int | None = None
    subtitle_codec: str | None = None
    downmix_to_stereo: bool = False

    @property
    def is_empty(self) -> bool:
        return self.video is None and not self.audio


def is_text_subtitle(stream: StreamInfo) -> bool:
    return (stream.codec_name or "").lower() in TEXT_SUBTITLE_CODECS


def main_audio(media: MediaInfo) -> StreamInfo | None:
    """The default audio track, or the first one."""
    tracks = media.audio_streams
    return next((s for s in tracks if s.is_default), tracks[0] if tracks else None)


def cover_art_stream(media: MediaInfo) -> StreamInfo | None:
    return next((s for s in media.streams_of(StreamType.VIDEO) if s.is_attached_picture), None)


def plan_streams(media: MediaInfo, policy: TrackPolicy, *, include_video: bool) -> StreamMap:
    video = media.video_streams[0].index if include_video and media.has_video else None

    if policy.all_audio:
        audio_streams = media.audio_streams
    else:
        main = main_audio(media)
        audio_streams = (main,) if main is not None else ()

    subtitles: tuple[int, ...] = ()
    if policy.subtitle_codec is not None:
        subtitles = tuple(
            s.index
            for s in media.subtitle_streams
            if policy.subtitle_codec == SUBTITLE_COPY or is_text_subtitle(s)
        )

    cover = cover_art_stream(media) if policy.cover_art else None
    downmix = policy.downmix_to_stereo and any((s.channels or 0) > STEREO for s in audio_streams)
    return StreamMap(
        video=video,
        audio=tuple(s.index for s in audio_streams),
        subtitles=subtitles,
        cover_art=cover.index if cover is not None else None,
        subtitle_codec=policy.subtitle_codec if subtitles else None,
        downmix_to_stereo=downmix,
    )
