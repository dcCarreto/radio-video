import pytest

from radio_video.ffmpeg.command import video_arguments
from radio_video.models.presets import OUTPUT_FORMATS, OutputFormat, Quality, available_formats

ALL_ENCODERS = frozenset(encoder for fmt in OUTPUT_FORMATS for encoder in fmt.encoders)


def _format(key: str) -> OutputFormat:
    return next(fmt for fmt in OUTPUT_FORMATS if fmt.key == key)


def test_keys_are_unique() -> None:
    keys = [fmt.key for fmt in OUTPUT_FORMATS]
    assert len(keys) == len(set(keys))


@pytest.mark.parametrize("fmt", OUTPUT_FORMATS, ids=lambda fmt: fmt.key)
@pytest.mark.parametrize("quality", list(Quality))
def test_every_preset_builds_valid_settings(fmt: OutputFormat, quality: Quality) -> None:
    settings = fmt.settings(quality)
    assert (settings.video is not None) is fmt.is_video
    assert settings.audio is not None
    used = {settings.audio.codec} | ({settings.video.codec} if settings.video else set())
    assert used <= set(fmt.encoders)


def test_higher_quality_means_lower_crf_and_higher_bitrate() -> None:
    fmt = _format("mp4-h264")
    high, small = fmt.settings(Quality.HIGH), fmt.settings(Quality.SMALL)
    assert high.video and small.video and high.audio and small.audio
    assert high.video.crf is not None and small.video.crf is not None
    assert high.video.crf < small.video.crf
    assert (high.audio.bitrate or 0) > (small.audio.bitrate or 0)


def test_lossless_formats_ignore_quality() -> None:
    fmt = _format("flac")
    assert fmt.lossless
    assert fmt.settings(Quality.SMALL) == fmt.settings(Quality.HIGH)


def test_vp9_uses_constant_quality() -> None:
    args = video_arguments(_format("webm-vp9").settings(Quality.BALANCED).video)
    assert args[args.index("-b:v") + 1] == "0"
    assert "-crf" in args


def test_available_formats_require_encoders() -> None:
    formats = available_formats({"aac", "libx264"}, source_has_video=True)
    assert [fmt.key for fmt in formats] == ["mp4-h264", "mkv-h264", "m4a-aac"]


def test_audio_sources_only_get_audio_formats() -> None:
    formats = available_formats(ALL_ENCODERS, source_has_video=False)
    assert formats
    assert not any(fmt.is_video for fmt in formats)


def test_video_sources_can_extract_audio() -> None:
    formats = available_formats(ALL_ENCODERS, source_has_video=True)
    assert any(fmt.is_video for fmt in formats)
    assert any(not fmt.is_video for fmt in formats)
