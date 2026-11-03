from __future__ import annotations

from pathlib import Path

from radio_video.models.conversion import (
    AudioOptions,
    ConversionJob,
    ConversionSettings,
    VideoOptions,
)
from radio_video.models.tracks import StreamMap

# Output is written to "name.ext.part", so the muxer is passed explicitly.
MUXERS = {
    ".mp4": "mp4",
    ".m4v": "mp4",
    ".mov": "mov",
    ".mkv": "matroska",
    ".webm": "webm",
    ".mp3": "mp3",
    ".m4a": "ipod",
    ".opus": "opus",
    ".ogg": "ogg",
    ".flac": "flac",
    ".wav": "wav",
}

# Muxer options that improve compatibility: ID3v2.3 tags (with cover art) are read by
# Windows Explorer and most players, unlike the default v2.4.
MUXER_OPTIONS = {"mp3": ["-id3v2_version", "3"]}


def muxer_for(destination: Path) -> str:
    try:
        return MUXERS[destination.suffix.lower()]
    except KeyError:
        raise ValueError(f"Unsupported output extension: {destination.suffix}") from None


def _number(value: float) -> str:
    return f"{value:g}"


def _scale_filter(video: VideoOptions) -> str | None:
    if video.width is None and video.height is None:
        return None
    width = video.width if video.width is not None else -2
    height = video.height if video.height is not None else -2
    return f"scale={width}:{height}"


def _video_encoding(video: VideoOptions, stream: str | None) -> list[str]:
    """Encoder options for every video output, or for one output stream such as ``v:0``."""

    def name(option: str) -> str:
        return f"{option}:{stream}" if stream else option

    args = [f"-c:{stream or 'v'}", video.codec]
    if video.crf is not None:
        args += [name("-crf"), str(video.crf)]
    if video.bitrate is not None:
        args += [f"-b:{stream or 'v'}", str(video.bitrate)]
    if video.preset is not None:
        args += [name("-preset"), video.preset]
    if scale := _scale_filter(video):
        args += [f"-filter:{stream}" if stream else "-vf", scale]
    if video.frame_rate is not None:
        args += [name("-r"), _number(video.frame_rate)]
    if video.pixel_format is not None:
        args += [name("-pix_fmt"), video.pixel_format]
    return args


def _audio_encoding(audio: AudioOptions) -> list[str]:
    args = ["-c:a", audio.codec]
    if audio.bitrate is not None:
        args += ["-b:a", str(audio.bitrate)]
    if audio.quality is not None:
        args += ["-q:a", _number(audio.quality)]
    if audio.sample_rate is not None:
        args += ["-ar", str(audio.sample_rate)]
    if audio.channels is not None:
        args += ["-ac", str(audio.channels)]
    return args


def video_arguments(video: VideoOptions | None) -> list[str]:
    if video is None:
        return ["-vn"]
    return ["-map", "0:v:0?", *_video_encoding(video, None)]


def audio_arguments(audio: AudioOptions | None) -> list[str]:
    if audio is None:
        return ["-an"]
    return ["-map", "0:a:0?", *_audio_encoding(audio)]


def _metadata_arguments(settings: ConversionSettings) -> list[str]:
    return ["-map_metadata", "0" if settings.preserve_metadata else "-1"]


def settings_arguments(settings: ConversionSettings) -> list[str]:
    """Arguments when no track map is given: the first video and audio stream only."""
    return [
        *video_arguments(settings.video),
        *audio_arguments(settings.audio),
        "-sn",
        "-dn",
        *_metadata_arguments(settings),
    ]


def mapped_arguments(settings: ConversionSettings, streams: StreamMap) -> list[str]:
    """Arguments that map exactly the tracks in ``streams``, in output order.

    Output video stream 0 is the main video; cover art follows it, copied as an attached
    picture. Every mapped audio track is encoded alike; subtitles are copied or converted.
    """
    if streams.is_empty:
        raise ValueError("The output would contain no audio or video")
    args: list[str] = []
    main_video = streams.video if settings.video is not None else None
    audio = streams.audio if settings.audio is not None else ()
    if main_video is not None:
        args += ["-map", f"0:{main_video}"]
    if streams.cover_art is not None:
        args += ["-map", f"0:{streams.cover_art}"]
    for index in (*audio, *streams.subtitles):
        args += ["-map", f"0:{index}"]

    if main_video is not None and settings.video is not None:
        args += _video_encoding(settings.video, "v:0")
    if streams.cover_art is not None:
        cover = "v:1" if main_video is not None else "v:0"
        args += [f"-c:{cover}", "copy", f"-disposition:{cover}", "attached_pic"]
    if audio and settings.audio is not None:
        args += _audio_encoding(settings.audio)
        if streams.downmix_to_stereo and settings.audio.channels is None:
            args += ["-ac", "2"]
    if streams.subtitles and streams.subtitle_codec is not None:
        args += ["-c:s", streams.subtitle_codec]
    args += ["-dn", *_metadata_arguments(settings)]
    return args


def build_conversion_command(ffmpeg: Path, job: ConversionJob, output: Path) -> list[str]:
    """Build the FFmpeg argument list that converts ``job.source`` into ``output``.

    ``output`` is passed separately so callers can write to a temporary file first; the
    muxer comes from ``job.destination``.
    """
    muxer = muxer_for(job.destination)
    args = [
        str(ffmpeg),
        "-hide_banner",
        "-nostdin",
        "-nostats",
        "-loglevel",
        "error",
        "-progress",
        "pipe:1",
        "-y",
    ]
    if job.start is not None:
        args += ["-ss", _number(job.start)]
    args += ["-i", str(job.source)]
    if job.length is not None:
        args += ["-t", _number(job.length)]
    if job.streams is None:
        args += settings_arguments(job.settings)
    else:
        args += mapped_arguments(job.settings, job.streams)
    args += [*MUXER_OPTIONS.get(muxer, []), "-f", muxer, str(output)]
    return args
