import pytest

from radio_video.ffmpeg.progress import ProgressParser, ProgressUpdate

BLOCK = (
    "frame=50\n"
    "fps=24.5\n"
    "bitrate= 512.3kbits/s\n"
    "total_size=65536\n"
    "out_time_us=2000000\n"
    "out_time_ms=2000000\n"
    "out_time=00:00:02.000000\n"
    "speed=2.5x\n"
    "progress=continue\n"
)


def test_parses_complete_block() -> None:
    (update,) = ProgressParser().feed(BLOCK)
    assert update.out_time == pytest.approx(2.0)
    assert update.total_size == 65536
    assert update.speed == pytest.approx(2.5)
    assert update.fps == pytest.approx(24.5)
    assert not update.finished


def test_handles_chunks_split_mid_line() -> None:
    parser = ProgressParser()
    updates = []
    for i in range(0, len(BLOCK), 7):
        updates += parser.feed(BLOCK[i : i + 7])
    assert len(updates) == 1
    assert updates[0].out_time == pytest.approx(2.0)


def test_handles_windows_line_endings_and_multiple_blocks() -> None:
    data = BLOCK.replace("\n", "\r\n") + "out_time_us=3000000\r\nprogress=end\r\n"
    first, last = ProgressParser().feed(data)
    assert first.out_time == pytest.approx(2.0)
    assert last.out_time == pytest.approx(3.0)
    assert last.finished


def test_values_do_not_leak_between_blocks() -> None:
    parser = ProgressParser()
    parser.feed(BLOCK)
    (update,) = parser.feed("progress=continue\n")
    assert update.out_time is None
    assert update.speed is None


def test_invalid_values_become_none() -> None:
    data = "out_time_us=N/A\nout_time_ms=N/A\nspeed=N/A\ntotal_size=N/A\nprogress=continue\n"
    (update,) = ProgressParser().feed(data)
    assert update.out_time is None
    assert update.speed is None
    assert update.total_size is None


def test_falls_back_to_out_time_ms() -> None:
    (update,) = ProgressParser().feed("out_time_ms=1500000\nprogress=continue\n")
    assert update.out_time == pytest.approx(1.5)


@pytest.mark.parametrize(
    ("out_time", "duration", "finished", "expected"),
    [
        (5.0, 10.0, False, 0.5),
        (12.0, 10.0, False, 1.0),
        (5.0, None, False, None),
        (None, 10.0, False, None),
        (None, None, True, 1.0),
    ],
)
def test_fraction(
    out_time: float | None, duration: float | None, finished: bool, expected: float | None
) -> None:
    update = ProgressUpdate(out_time, None, None, None, finished)
    assert update.fraction(duration) == expected


def test_remaining_seconds() -> None:
    update = ProgressUpdate(out_time=4.0, total_size=None, speed=2.0, fps=None, finished=False)
    assert update.remaining_seconds(10.0) == pytest.approx(3.0)
    assert ProgressUpdate(4.0, None, None, None, False).remaining_seconds(10.0) is None
