from __future__ import annotations

from pathlib import Path

from radio_video.models.conversion import (
    AudioOptions,
    ConversionJob,
    ConversionSettings,
    VideoOptions,
)


def _number(value: float) -> str:
    return f"{value:g}"


def _scale_filter(video: VideoOptions) -> str | None:
    if video.width is None and video.height is None:
        return None
    width = video.width if video.width is not None else -2
    height = video.height if video.height is not None else -2
    return f"scale={width}:{height}"


def video_arguments(video: VideoOptions | None) -> list[str]:
    if video is None:
        return ["-vn"]
    args = ["-map", "0:v:0?", "-c:v", video.codec]
    if video.crf is not None:
        args += ["-crf", str(video.crf)]
    if video.bitrate is not None:
        args += ["-b:v", str(video.bitrate)]
    if video.preset is not None:
        args += ["-preset", video.preset]
    if scale := _scale_filter(video):
        args += ["-vf", scale]
    if video.frame_rate is not None:
        args += ["-r", _number(video.frame_rate)]
    if video.pixel_format is not None:
        args += ["-pix_fmt", video.pixel_format]
    return args


def audio_arguments(audio: AudioOptions | None) -> list[str]:
    if audio is None:
        return ["-an"]
    args = ["-map", "0:a:0?", "-c:a", audio.codec]
    if audio.bitrate is not None:
        args += ["-b:a", str(audio.bitrate)]
    if audio.sample_rate is not None:
        args += ["-ar", str(audio.sample_rate)]
    if audio.channels is not None:
        args += ["-ac", str(audio.channels)]
    return args


def settings_arguments(settings: ConversionSettings) -> list[str]:
    return [
        *video_arguments(settings.video),
        *audio_arguments(settings.audio),
        "-sn",
        "-dn",
        "-map_metadata",
        "0" if settings.preserve_metadata else "-1",
    ]


def build_conversion_command(ffmpeg: Path, job: ConversionJob, output: Path) -> list[str]:
    """Build the FFmpeg argument list that converts ``job.source`` into ``output``.

    ``output`` is passed separately so callers can write to a temporary file first.
    """
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
    args += settings_arguments(job.settings)
    args.append(str(output))
    return args
