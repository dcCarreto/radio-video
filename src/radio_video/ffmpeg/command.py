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

# Muxers that can move their index to the start of the file (fast start).
FAST_START_MUXERS = frozenset({"mp4", "ipod", "mov"})

# EBU R128 targets for loudness normalization, as used by most streaming services.
LOUDNORM_FILTER = "loudnorm=I=-16:TP=-1.5:LRA=11"
# loudnorm resamples to 192 kHz internally, so the output rate is set back explicitly.
LOUDNORM_SAMPLE_RATE = 48000

# Encoder speed options. libvpx-vp9 defaults to its slowest setting (cpu-used 0) on a
# single row of threads; cpu-used 4 with row multithreading is about 8 times faster at
# 1080p for practically the same quality (SSIM 0.9751 against 0.9757).
ENCODER_OPTIONS = {
    "libvpx-vp9": [("-deadline", "good"), ("-cpu-used", "4"), ("-row-mt", "1")],
    "h264_amf": [("-quality", "balanced")],
    "hevc_amf": [("-quality", "balanced")],
}

# Rate control on the graphics card. Constant quality: NVENC through VBR with a quality
# target, AMF through constant QP. Target bitrate: VBR on both.
QUALITY_RATE_CONTROL = {
    "h264_nvenc": "vbr",
    "hevc_nvenc": "vbr",
    "h264_amf": "cqp",
    "hevc_amf": "cqp",
}
BITRATE_RATE_CONTROL = {
    "h264_nvenc": "vbr",
    "hevc_nvenc": "vbr",
    "h264_amf": "vbr_peak",
    "hevc_amf": "vbr_peak",
}

# yadif "deint" values: 1 deinterlaces only frames marked as interlaced, 0 every frame.
DEINTERLACE_FILTERS = {"auto": "yadif=deint=1", "always": "yadif=deint=0"}

# Options that take the constant-quality level (VideoOptions.crf) for each encoder.
QUALITY_OPTIONS = {
    "h264_nvenc": ("-cq",),
    "hevc_nvenc": ("-cq",),
    "h264_amf": ("-qp_i", "-qp_p", "-qp_b"),
    "hevc_amf": ("-qp_i", "-qp_p"),
    "h264_qsv": ("-global_quality",),
    "hevc_qsv": ("-global_quality",),
}


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


def video_filters(video: VideoOptions) -> str | None:
    """The video filter chain: deinterlace first, then scale, then the display shape."""
    filters = []
    if video.deinterlace is not None:
        filters.append(DEINTERLACE_FILTERS[video.deinterlace])
    if scale := _scale_filter(video):
        filters.append(scale)
    if video.aspect is not None:
        filters.append(f"setdar={video.aspect.replace(':', '/')}")
    return ",".join(filters) or None


def _video_encoding(video: VideoOptions, stream: str | None) -> list[str]:
    """Encoder options for every video output, or for one output stream such as ``v:0``."""

    def name(option: str) -> str:
        return f"{option}:{stream}" if stream else option

    args = [f"-c:{stream or 'v'}", video.codec]
    for option, value in ENCODER_OPTIONS.get(video.codec, []):
        args += [name(option), value]
    controls = QUALITY_RATE_CONTROL if video.crf is not None else BITRATE_RATE_CONTROL
    if (rate_control := controls.get(video.codec)) is not None:
        args += [name("-rc"), rate_control]
    if video.crf is not None:
        for option in QUALITY_OPTIONS.get(video.codec, ("-crf",)):
            args += [name(option), str(video.crf)]
    if video.bitrate is not None:
        args += [f"-b:{stream or 'v'}", str(video.bitrate)]
    if video.preset is not None:
        args += [name("-preset"), video.preset]
    if filters := video_filters(video):
        args += [f"-filter:{stream}" if stream else "-vf", filters]
    if video.frame_rate is not None:
        args += [name("-r"), _number(video.frame_rate)]
    if video.pixel_format is not None:
        args += [name("-pix_fmt"), video.pixel_format]
    return args


def _audio_encoding(audio: AudioOptions, normalize: bool = False) -> list[str]:
    args = ["-c:a", audio.codec]
    if audio.bitrate is not None:
        args += ["-b:a", str(audio.bitrate)]
    if audio.quality is not None:
        args += ["-q:a", _number(audio.quality)]
    if normalize:
        args += ["-af", LOUDNORM_FILTER]
    sample_rate = audio.sample_rate or (LOUDNORM_SAMPLE_RATE if normalize else None)
    if sample_rate is not None:
        args += ["-ar", str(sample_rate)]
    if audio.channels is not None:
        args += ["-ac", str(audio.channels)]
    return args


def video_arguments(video: VideoOptions | None) -> list[str]:
    if video is None:
        return ["-vn"]
    return ["-map", "0:v:0?", *_video_encoding(video, None)]


def audio_arguments(audio: AudioOptions | None, normalize: bool = False) -> list[str]:
    if audio is None:
        return ["-an"]
    return ["-map", "0:a:0?", *_audio_encoding(audio, normalize)]


def _metadata_arguments(settings: ConversionSettings) -> list[str]:
    if settings.preserve_metadata:
        return ["-map_metadata", "0"]
    return ["-map_metadata", "-1", "-map_chapters", "-1"]


def settings_arguments(settings: ConversionSettings) -> list[str]:
    """Arguments when no track map is given: the first video and audio stream only."""
    return [
        *video_arguments(settings.video),
        *audio_arguments(settings.audio, settings.normalize_loudness),
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
        args += _audio_encoding(settings.audio, settings.normalize_loudness)
        copy = settings.audio.is_copy
        if streams.downmix_to_stereo and settings.audio.channels is None and not copy:
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
    args += MUXER_OPTIONS.get(muxer, [])
    if job.settings.fast_start and muxer in FAST_START_MUXERS:
        args += ["-movflags", "+faststart"]
    args += ["-f", muxer, str(output)]
    return args
