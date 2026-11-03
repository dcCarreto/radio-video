from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from radio_video.ui.errors_map import ErrorKind, Failure, NextStep, classify, describe


@pytest.fixture
def source(tmp_path: Path) -> Path:
    path = tmp_path / "clip.mkv"
    path.write_bytes(b"")
    return path


@pytest.mark.parametrize(
    ("details", "kind"),
    [
        ("av_interleaved_write_frame(): No space left on device", ErrorKind.DISK_FULL),
        ("Conversion failed!\nFFmpeg exited with code -28", ErrorKind.DISK_FULL),
        ("out.mp4.part: Permission denied", ErrorKind.NOT_WRITABLE),
        ("Unknown encoder 'libx265'", ErrorKind.ENCODER_UNAVAILABLE),
        ("Encoder (codec hevc) not found for output stream #0:0", ErrorKind.ENCODER_UNAVAILABLE),
        ("Output file does not contain any stream", ErrorKind.NO_MEDIA),
        ("in.mkv: Invalid data found when processing input", ErrorKind.UNREADABLE),
        ("[h264_nvenc @ 0x1] OpenEncodeSessionEx failed", ErrorKind.HARDWARE_ENCODER),
        ("something odd\nFFmpeg exited with code 1", ErrorKind.UNKNOWN),
    ],
)
def test_classify(source: Path, details: str, kind: ErrorKind) -> None:
    assert classify(Failure(details, source)) is kind


def test_missing_source_wins(tmp_path: Path) -> None:
    failure = Failure("Invalid data found when processing input", tmp_path / "gone.mkv")
    assert classify(failure) is ErrorKind.SOURCE_MISSING


def test_long_destination_path(source: Path) -> None:
    long_path = Path("C:/" + "a" * 300 + ".mp4")
    assert classify(Failure("No such file or directory", source, long_path)) is (
        ErrorKind.PATH_TOO_LONG
    )


def test_disk_full_report_matches_the_copy(qapp: QApplication, source: Path) -> None:
    report = describe(
        Failure(
            "No space left on device",
            source,
            Path("C:/Videos/clip.mp4"),
            fraction=0.66,
            needed_bytes=22 * 1024 * 1024,
        )
    )
    assert report.what_happened == (
        "Drive C: ran out of free space at 66%, while saving the converted file."
    )
    assert report.what_to_do == (
        "Free up space on drive C:, or choose a folder on another drive, then convert again. "
        "You’ll need about 22 MB."
    )
    assert report.next_step is NextStep.CHOOSE_FOLDER
    assert report.action_text == "Choose Another Folder…"


def test_encoder_report_names_the_encoder(qapp: QApplication, source: Path) -> None:
    report = describe(Failure("Unknown encoder 'libx265'", source))
    assert report.what_happened == "The libx265 encoder isn’t available in your FFmpeg build."
    assert report.action_text == "Choose Another Format"


def test_unknown_report_shows_exit_code(qapp: QApplication, source: Path) -> None:
    report = describe(Failure("odd\nFFmpeg exited with code 3", source))
    assert report.what_happened == "FFmpeg stopped unexpectedly (exit code 3)."
    assert report.next_step is NextStep.TRY_AGAIN
    assert report.details.endswith("code 3")


def test_source_missing_offers_open_file(qapp: QApplication, tmp_path: Path) -> None:
    report = describe(Failure("", tmp_path / "gone.mkv"))
    assert report.action_text == "Open File…"
