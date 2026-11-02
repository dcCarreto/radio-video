from pathlib import Path

import pytest

from radio_video.ffmpeg.command import (
    audio_arguments,
    build_conversion_command,
    video_arguments,
)
from radio_video.models.conversion import (
    AudioOptions,
    ConversionJob,
    ConversionSettings,
    VideoOptions,
)

H264_AAC = ConversionSettings(
    video=VideoOptions(codec="libx264", crf=23, preset="medium", pixel_format="yuv420p"),
    audio=AudioOptions(codec="aac", bitrate=192_000),
)


def _job(**overrides: object) -> ConversionJob:
    values: dict[str, object] = {
        "source": Path("C:/in/movie.mkv"),
        "destination": Path("C:/out/movie.mp4"),
        "settings": H264_AAC,
    }
    values.update(overrides)
    return ConversionJob(**values)  # type: ignore[arg-type]


def _option(args: list[str], name: str) -> str:
    return args[args.index(name) + 1]


def test_command_structure() -> None:
    args = build_conversion_command(Path("ffmpeg"), _job(), Path("C:/out/.movie.partial.mp4"))
    assert args[0] == "ffmpeg"
    assert _option(args, "-progress") == "pipe:1"
    assert "-nostdin" in args
    assert "-y" in args
    assert _option(args, "-i") == str(Path("C:/in/movie.mkv"))
    assert args[-1] == str(Path("C:/out/.movie.partial.mp4"))
    assert args.index("-i") < args.index("-c:v")


def test_video_encoding_options() -> None:
    args = video_arguments(H264_AAC.video)
    assert _option(args, "-map") == "0:v:0?"
    assert _option(args, "-c:v") == "libx264"
    assert _option(args, "-crf") == "23"
    assert _option(args, "-preset") == "medium"
    assert _option(args, "-pix_fmt") == "yuv420p"
    assert "-vf" not in args


@pytest.mark.parametrize(
    ("width", "height", "expected"),
    [(1280, 720, "scale=1280:720"), (1280, None, "scale=1280:-2"), (None, 480, "scale=-2:480")],
)
def test_scale_filter(width: int | None, height: int | None, expected: str) -> None:
    args = video_arguments(VideoOptions(codec="libx264", width=width, height=height))
    assert _option(args, "-vf") == expected


def test_frame_rate_and_bitrate() -> None:
    args = video_arguments(VideoOptions(codec="libvpx-vp9", bitrate=2_000_000, frame_rate=29.97))
    assert _option(args, "-b:v") == "2000000"
    assert _option(args, "-r") == "29.97"


def test_audio_options() -> None:
    args = audio_arguments(AudioOptions(codec="libopus", bitrate=128_000, sample_rate=48000))
    assert _option(args, "-map") == "0:a:0?"
    assert _option(args, "-c:a") == "libopus"
    assert _option(args, "-b:a") == "128000"
    assert _option(args, "-ar") == "48000"
    assert "-ac" not in args


def test_dropped_streams() -> None:
    assert video_arguments(None) == ["-vn"]
    assert audio_arguments(None) == ["-an"]


def test_stream_copy() -> None:
    assert video_arguments(VideoOptions(codec="copy")) == ["-map", "0:v:0?", "-c:v", "copy"]


def test_metadata() -> None:
    preserved = build_conversion_command(Path("ffmpeg"), _job(), Path("o.mp4"))
    assert _option(preserved, "-map_metadata") == "0"
    stripped_settings = ConversionSettings(
        video=None, audio=AudioOptions(codec="flac"), preserve_metadata=False
    )
    stripped = build_conversion_command(
        Path("ffmpeg"), _job(settings=stripped_settings), Path("o.flac")
    )
    assert _option(stripped, "-map_metadata") == "-1"


def test_time_range_for_previews() -> None:
    args = build_conversion_command(Path("ffmpeg"), _job(start=30.5, length=15), Path("o.mp4"))
    assert _option(args, "-ss") == "30.5"
    assert _option(args, "-t") == "15"
    assert args.index("-ss") < args.index("-i") < args.index("-t")


def test_paths_with_special_characters_stay_single_arguments() -> None:
    source = Path("C:/in/my movie; & del *.mkv")
    args = build_conversion_command(Path("ffmpeg"), _job(source=source), Path("C:/o/x y.mp4"))
    assert str(source) in args
    assert str(Path("C:/o/x y.mp4")) == args[-1]
