from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from radio_video.ffmpeg import FFmpegTools, ProbeError, probe
from radio_video.ffmpeg.probe import build_probe_command, parse_probe_output
from radio_video.models import StreamType

MEDIA = Path("movie.mkv")


def _probe_data(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "streams": [
            {
                "index": 0,
                "codec_name": "h264",
                "codec_long_name": "H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10",
                "profile": "High",
                "codec_type": "video",
                "width": 1920,
                "height": 1080,
                "pix_fmt": "yuv420p",
                "display_aspect_ratio": "16:9",
                "r_frame_rate": "24000/1001",
                "avg_frame_rate": "24000/1001",
                "disposition": {"default": 1, "attached_pic": 0},
            },
            {
                "index": 1,
                "codec_name": "aac",
                "codec_type": "audio",
                "sample_rate": "48000",
                "channels": 6,
                "channel_layout": "5.1",
                "bit_rate": "384000",
                "disposition": {"default": 1},
                "tags": {"LANGUAGE": "por", "title": "Portuguese 5.1"},
            },
            {
                "index": 2,
                "codec_name": "subrip",
                "codec_type": "subtitle",
                "tags": {"language": "eng"},
            },
            {
                "index": 3,
                "codec_name": "mjpeg",
                "codec_type": "video",
                "width": 600,
                "height": 600,
                "avg_frame_rate": "0/0",
                "disposition": {"attached_pic": 1},
            },
        ],
        "format": {
            "format_name": "matroska,webm",
            "format_long_name": "Matroska / WebM",
            "duration": "5400.250000",
            "size": "2147483648",
            "bit_rate": "3181000",
            "tags": {"title": "Movie"},
        },
    }
    data.update(overrides)
    return data


def test_build_probe_command_uses_argument_list() -> None:
    command = build_probe_command(Path("ffprobe"), Path("my file; rm -rf.mkv"))
    assert command[0] == "ffprobe"
    assert command[-1] == "my file; rm -rf.mkv"
    assert "-show_streams" in command
    assert "-show_format" in command


def test_parse_format() -> None:
    info = parse_probe_output(MEDIA, _probe_data())
    assert info.path == MEDIA
    assert info.format_name == "matroska,webm"
    assert info.format_long_name == "Matroska / WebM"
    assert info.duration == pytest.approx(5400.25)
    assert info.size == 2147483648
    assert info.bit_rate == 3181000
    assert info.tags == {"title": "Movie"}


def test_parse_video_stream() -> None:
    video = parse_probe_output(MEDIA, _probe_data()).video_streams
    assert len(video) == 1
    stream = video[0]
    assert stream.codec_name == "h264"
    assert stream.profile == "High"
    assert (stream.width, stream.height) == (1920, 1080)
    assert stream.pixel_format == "yuv420p"
    assert stream.frame_rate == pytest.approx(23.976, abs=1e-3)
    assert stream.display_aspect_ratio == "16:9"
    assert stream.is_default


def test_parse_audio_stream_with_case_insensitive_tags() -> None:
    (audio,) = parse_probe_output(MEDIA, _probe_data()).audio_streams
    assert audio.type is StreamType.AUDIO
    assert audio.sample_rate == 48000
    assert audio.channels == 6
    assert audio.channel_layout == "5.1"
    assert audio.bit_rate == 384000
    assert audio.language == "por"
    assert audio.title == "Portuguese 5.1"


def test_attached_picture_is_not_a_video_stream() -> None:
    info = parse_probe_output(MEDIA, _probe_data())
    assert len(info.streams_of(StreamType.VIDEO)) == 2
    assert len(info.video_streams) == 1
    assert info.has_video


def test_subtitle_stream() -> None:
    (subtitle,) = parse_probe_output(MEDIA, _probe_data()).subtitle_streams
    assert subtitle.codec_name == "subrip"
    assert subtitle.language == "eng"


def test_missing_and_invalid_values_become_none() -> None:
    data = _probe_data(
        streams=[
            {
                "index": 0,
                "codec_type": "video",
                "width": "N/A",
                "avg_frame_rate": "0/0",
                "r_frame_rate": "0/0",
                "display_aspect_ratio": "0:1",
            },
            {"index": 1, "codec_type": "something_new"},
        ],
        format={"format_name": "mpegts", "duration": "N/A"},
    )
    info = parse_probe_output(MEDIA, data)
    video, unknown = info.streams
    assert video.width is None
    assert video.frame_rate is None
    assert video.display_aspect_ratio is None
    assert unknown.type is StreamType.UNKNOWN
    assert info.duration is None
    assert info.size is None


def test_undetermined_language_is_none() -> None:
    data = _probe_data(streams=[{"index": 0, "codec_type": "audio", "tags": {"language": "und"}}])
    (audio,) = parse_probe_output(MEDIA, data).audio_streams
    assert audio.language is None


def test_audio_only_file() -> None:
    data = _probe_data(streams=[{"index": 0, "codec_type": "audio", "codec_name": "mp3"}])
    info = parse_probe_output(MEDIA, data)
    assert info.has_audio
    assert not info.has_video


def test_rejects_output_without_streams() -> None:
    with pytest.raises(ProbeError, match="no audio or video streams"):
        parse_probe_output(MEDIA, _probe_data(streams=[]))


def test_rejects_output_without_format() -> None:
    with pytest.raises(ProbeError, match="not a recognized media file"):
        parse_probe_output(MEDIA, {"streams": []})


def test_probe_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ProbeError, match="File not found"):
        probe(tmp_path / "missing.mp4", Path("ffprobe"))


@pytest.mark.ffmpeg
def test_probe_video_file(ffmpeg_tools: FFmpegTools, sample_video: Path) -> None:
    info = probe(sample_video, ffmpeg_tools.ffprobe)
    assert "matroska" in info.format_name
    assert info.duration == pytest.approx(3.0, abs=0.2)
    assert info.size == sample_video.stat().st_size
    assert info.tags.get("title") == "Sample Clip"

    (video,) = info.video_streams
    assert video.codec_name == "h264"
    assert (video.width, video.height) == (320, 240)
    assert video.frame_rate == pytest.approx(25.0)
    assert video.pixel_format == "yuv420p"

    (audio,) = info.audio_streams
    assert audio.codec_name == "aac"
    assert audio.sample_rate == 48000
    assert audio.channels == 2
    assert audio.language == "eng"

    (subtitle,) = info.subtitle_streams
    assert subtitle.codec_name == "subrip"


@pytest.mark.ffmpeg
def test_probe_audio_file(ffmpeg_tools: FFmpegTools, sample_audio: Path) -> None:
    info = probe(sample_audio, ffmpeg_tools.ffprobe)
    assert info.format_name == "flac"
    assert not info.has_video
    (audio,) = info.audio_streams
    assert audio.codec_name == "flac"
    assert audio.sample_rate == 44100
    assert audio.channels == 1


@pytest.mark.ffmpeg
def test_probe_rejects_non_media_file(ffmpeg_tools: FFmpegTools, tmp_path: Path) -> None:
    text_file = tmp_path / "notes.mp4"
    text_file.write_text("this is not a video", encoding="utf-8")
    with pytest.raises(ProbeError, match=r"notes\.mp4"):
        probe(text_file, ffmpeg_tools.ffprobe)
