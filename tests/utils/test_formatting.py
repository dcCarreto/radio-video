import pytest

from radio_video.utils.formatting import (
    format_bitrate,
    format_duration,
    format_frame_rate,
    format_size,
)


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(None, "—"), (-1, "—"), (0, "0:00"), (59.6, "1:00"), (61, "1:01"), (5400.25, "1:30:00")],
)
def test_format_duration(seconds: float | None, expected: str) -> None:
    assert format_duration(seconds) == expected


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        (None, "—"),
        (0, "0 B"),
        (1023, "1023 B"),
        (1536, "1.5 KB"),
        (2147483648, "2.0 GB"),
        (5 * 1024**5, "5120.0 TB"),
    ],
)
def test_format_size(size: int | None, expected: str) -> None:
    assert format_size(size) == expected


@pytest.mark.parametrize(
    ("bitrate", "expected"),
    [(None, "—"), (0, "—"), (128_000, "128 kb/s"), (3_181_000, "3.2 Mb/s")],
)
def test_format_bitrate(bitrate: int | None, expected: str) -> None:
    assert format_bitrate(bitrate) == expected


@pytest.mark.parametrize(
    ("fps", "expected"),
    [(None, "—"), (25.0, "25 fps"), (24000 / 1001, "23.976 fps"), (29.97, "29.97 fps")],
)
def test_format_frame_rate(fps: float | None, expected: str) -> None:
    assert format_frame_rate(fps) == expected
