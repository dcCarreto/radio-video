"""Describe conversion settings and estimate output size where it is predictable."""

from __future__ import annotations

from radio_video.models.conversion import AudioOptions, ConversionSettings, VideoOptions
from radio_video.models.media import MediaInfo
from radio_video.utils.formatting import format_bitrate

CODEC_NAMES = {
    "libx264": "H.264",
    "libx265": "H.265",
    "libvpx-vp9": "VP9",
    "aac": "AAC",
    "libopus": "Opus",
    "libmp3lame": "MP3",
    "libvorbis": "Vorbis",
    "flac": "FLAC",
    "pcm_s16le": "PCM 16-bit",
    "copy": "Original",
}

_PCM_BYTES_PER_SAMPLE = {"pcm_s16le": 2}


def codec_display_name(codec: str) -> str:
    return CODEC_NAMES.get(codec, codec)


def _describe_video(video: VideoOptions) -> str:
    parts = [f"{codec_display_name(video.codec)} video"]
    if video.crf is not None:
        parts.append(f"quality CRF {video.crf}")
    if video.bitrate:
        parts.append(format_bitrate(video.bitrate))
    if video.width or video.height:
        parts.append(f"{video.width or 'auto'}×{video.height or 'auto'}")
    return ", ".join(parts)


def _describe_audio(audio: AudioOptions) -> str:
    parts = [f"{codec_display_name(audio.codec)} audio"]
    if audio.bitrate:
        parts.append(format_bitrate(audio.bitrate))
    if audio.codec in _PCM_BYTES_PER_SAMPLE or audio.codec == "flac":
        parts.append("lossless")
    return ", ".join(parts)


def describe_settings(settings: ConversionSettings, media: MediaInfo | None = None) -> str:
    parts = []
    if settings.video is not None and (media is None or media.has_video):
        parts.append(_describe_video(settings.video))
    if settings.audio is not None and (media is None or media.has_audio):
        parts.append(_describe_audio(settings.audio))
    return " · ".join(parts) if parts else "No streams"


def _audio_bits_per_second(audio: AudioOptions, media: MediaInfo) -> int | None:
    if audio.bitrate:
        return audio.bitrate
    bytes_per_sample = _PCM_BYTES_PER_SAMPLE.get(audio.codec)
    source = media.audio_streams[0] if media.audio_streams else None
    if bytes_per_sample is None or source is None:
        return None
    sample_rate = audio.sample_rate or source.sample_rate
    channels = audio.channels or source.channels
    if not sample_rate or not channels:
        return None
    return sample_rate * channels * bytes_per_sample * 8


def estimate_output_size(settings: ConversionSettings, media: MediaInfo) -> int | None:
    """Approximate output size in bytes, or None when it depends on the content.

    Only bitrate-based and uncompressed streams are predictable. Quality-based (CRF) video and
    lossless compression such as FLAC are not.
    """
    if media.duration is None:
        return None
    bits_per_second = 0
    if settings.video is not None and media.has_video:
        if not settings.video.bitrate:
            return None
        bits_per_second += settings.video.bitrate
    if settings.audio is not None and media.has_audio:
        audio_bits = _audio_bits_per_second(settings.audio, media)
        if audio_bits is None:
            return None
        bits_per_second += audio_bits
    if bits_per_second == 0:
        return None
    return round(bits_per_second * media.duration / 8)
