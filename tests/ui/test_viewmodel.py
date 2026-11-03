from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from radio_video.models.media import MediaInfo, StreamInfo, StreamType
from radio_video.models.presets import OUTPUT_FORMATS, Quality, available_formats, format_by_key
from radio_video.ui import viewmodel as vm
from radio_video.ui.demo import DEMO_MEDIA
from radio_video.ui.state import Progress

ALL_ENCODERS = frozenset(e for fmt in OUTPUT_FORMATS for e in fmt.encoders)

AUDIO_FILE = MediaInfo(
    path=Path("C:/music/song.flac"),
    format_name="flac",
    duration=60.0,
    streams=(
        StreamInfo(
            index=0, type=StreamType.AUDIO, codec_name="flac", sample_rate=44100, channels=2
        ),
    ),
)


@pytest.fixture(autouse=True)
def _app(qapp: QApplication) -> None:
    """Translation and QLocale need an application object."""


def test_source_summary_matches_the_design() -> None:
    assert vm.source_summary(DEMO_MEDIA) == (
        "1 video track, 3 audio tracks (Portuguese, English), 7 subtitle tracks and 1 cover image."
    )
    assert vm.source_summary(AUDIO_FILE) == "Audio-only file: 1 audio track (stereo, 44.1 kHz)."


def test_track_header_and_chips() -> None:
    assert vm.inside_header(DEMO_MEDIA) == "What’s inside · 12 tracks"
    assert [text for _, text in vm.track_chips(DEMO_MEDIA)] == [
        "1 video",
        "3 audio",
        "7 subtitles",
        "1 cover image",
    ]


def test_facts() -> None:
    values, title = vm.facts(DEMO_MEDIA)
    assert values == ["Matroska / WebM", "2:13", "186.4 MB", "11.2 Mb/s"]
    assert title == "Lisbon Studio Session: full interview, director’s cut"
    _, no_title = vm.facts(AUDIO_FILE)
    assert no_title == "—"


def test_stream_rows() -> None:
    rows = vm.stream_rows(DEMO_MEDIA)
    assert len(rows) == 12
    video, original, dub = rows[0], rows[1], rows[2]
    assert (video.kind, video.codec, video.details) == (
        "Video",
        "h264 (High)",
        "1920×1080 · 23.976 fps · 10.4 Mb/s",
    )
    assert video.language == "—"
    assert original.details == "48 kHz · 5.1 · 384 kb/s"
    assert original.language == "Portuguese"
    assert original.is_default
    assert dub.details == "48 kHz · Stereo · 192 kb/s"
    assert dub.accessible.startswith("Audio 2, AAC, 48 kHz Stereo 192 kb/s, English")
    assert dub.tooltip == "Audio 3: English dub"
    assert rows[4].details == "Text"
    cover = rows[11]
    assert (cover.kind, cover.icon, cover.details) == ("Cover art", "Image", "600×600 · JPEG image")
    assert not cover.is_default


def test_format_groups_for_video_and_audio_sources() -> None:
    formats = available_formats(ALL_ENCODERS, source_has_video=True)
    groups = vm.format_groups(formats, source_has_video=True)
    assert [g.title for g in groups] == ["Video", "Audio only: extracts the audio"]
    assert groups[0].options[0].recommended
    audio_groups = vm.format_groups(available_formats(ALL_ENCODERS, False), source_has_video=False)
    assert [g.title for g in audio_groups] == ["Audio"]


def test_format_help_mentions_extraction_only_for_video_sources() -> None:
    mp3 = format_by_key("mp3")
    assert vm.format_help(mp3, source_has_video=True) == (
        "Plays everywhere. Extracts the audio; the video is left out."
    )
    assert vm.format_help(mp3, source_has_video=False) == "Plays everywhere."


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        (
            "mp4-h264",
            [
                ("Video", "H.264, 1920×1080, 23.976 fps"),
                ("Audio", "3 tracks, converted to AAC"),
                ("Subtitles", "7 tracks, converted to MP4 text"),
                ("Cover art", "Kept"),
            ],
        ),
        (
            "mkv-h264",
            [
                ("Video", "H.264, 1920×1080, 23.976 fps"),
                ("Audio", "3 tracks, converted to AAC"),
                ("Subtitles", "7 tracks, copied as they are"),
                ("Cover art", "Kept"),
            ],
        ),
        (
            "webm-vp9",
            [
                ("Video", "VP9, 1920×1080, 23.976 fps"),
                ("Audio", "3 tracks, converted to Opus"),
                ("Subtitles", "7 tracks, converted to WebVTT"),
                ("Cover art", "Left out: WebM can’t store it"),
            ],
        ),
        (
            "mp3",
            [
                ("Audio", "Track 1 (Portuguese), 5.1 mixed down to stereo"),
                ("Left out", "Video, 2 other audio tracks, subtitles"),
                ("Cover art", "Kept"),
            ],
        ),
        (
            "opus",
            [
                ("Audio", "Track 1 (Portuguese), 5.1 mixed down to stereo"),
                ("Left out", "Video, 2 other audio tracks, subtitles, cover art"),
            ],
        ),
        (
            "flac",
            [
                ("Audio", "Track 1 (Portuguese), 5.1 kept"),
                ("Left out", "Video, 2 other audio tracks, subtitles"),
                ("Cover art", "Kept"),
            ],
        ),
    ],
)
def test_output_contents_match_the_design(key: str, expected: list[tuple[str, str]]) -> None:
    fmt = format_by_key(key)
    assert vm.output_contents(fmt, DEMO_MEDIA, fmt.plan(DEMO_MEDIA)) == expected


def test_audio_only_source_contents() -> None:
    fmt = format_by_key("mp3")
    assert vm.output_contents(fmt, AUDIO_FILE, fmt.plan(AUDIO_FILE)) == [
        ("Audio", "Track 1, stereo")
    ]


def test_estimate_is_calculated_for_bitrate_formats() -> None:
    result = vm.estimate(format_by_key("mp3"), Quality.BALANCED, DEMO_MEDIA, None)
    assert result.known
    assert result.value == "≈ 3.0 MB"
    assert result.how == "Calculated from the bitrate and length."


def test_estimate_needs_a_preview_for_quality_based_formats() -> None:
    fmt = format_by_key("mp4-h264")
    unknown = vm.estimate(fmt, Quality.BALANCED, DEMO_MEDIA, None)
    assert not unknown.known
    assert (unknown.value, unknown.how) == (
        "Depends on the content",
        "Create a preview to measure it.",
    )
    measured = vm.estimate(fmt, Quality.BALANCED, DEMO_MEDIA, 22 * 1024 * 1024)
    assert (measured.value, measured.how) == ("≈ 22 MB", "Measured from a preview.")


@pytest.mark.parametrize("key", ["ogg-vorbis", "flac"])
def test_variable_and_lossless_formats_depend_on_content(key: str) -> None:
    assert not vm.estimate(format_by_key(key), Quality.BALANCED, DEMO_MEDIA, None).known


@pytest.mark.parametrize(
    ("size", "text"),
    [(512, "512 B"), (118_900, "116 KB"), (3_355_443, "3.2 MB"), (23_068_672, "22 MB")],
)
def test_estimate_size_format(size: int, text: str) -> None:
    assert vm.format_estimate_size(size) == text


def test_output_name_never_overwrites(tmp_path: Path) -> None:
    media = MediaInfo(path=tmp_path / "clip.mkv", format_name="matroska")
    fmt = format_by_key("mp4-h264")
    first = vm.output_name(tmp_path, media, fmt)
    assert first == vm.OutputName(tmp_path / "clip.mp4", None)
    assert vm.name_bumped_text(first) == ""

    (tmp_path / "clip.mp4").write_bytes(b"")
    second = vm.output_name(tmp_path, media, fmt)
    assert second == vm.OutputName(tmp_path / "clip (1).mp4", 1)
    assert "so “(1)” was added" in vm.name_bumped_text(second)

    (tmp_path / "clip (1).mp4").write_bytes(b"")
    assert vm.output_name(tmp_path, media, fmt).path.name == "clip (2).mp4"


def test_progress_text() -> None:
    assert vm.progress_detail(Progress(0.42, 3.1, 25)) == "42% · 3.1× · 0:25 remaining"
    assert vm.progress_detail(Progress(0.0)) == "0%"
    assert vm.speed_tooltip(3.0) == (
        "3.0× means one minute of media takes about 20 seconds to convert."
    )


def test_format_and_quality_label() -> None:
    assert vm.format_and_quality(format_by_key("mp4-h264"), Quality.BALANCED) == (
        "MP4 (H.264 + AAC), Balanced"
    )
    assert vm.format_and_quality(format_by_key("flac"), Quality.HIGH) == "FLAC (lossless)"


def test_quality_options_round_trip() -> None:
    options = vm.quality_options()
    assert [o.label for o in options] == ["High", "Balanced", "Small file"]
    assert options[1].sublabel == "Recommended"
    for quality in Quality:
        assert vm.quality_from_value(vm.quality_value(quality)) is quality


def test_language_names() -> None:
    assert vm.language_name("por") == "Portuguese"
    assert vm.language_name("en") == "English"
    assert vm.language_name("und") == "—"
    assert vm.language_name(None) == "—"
