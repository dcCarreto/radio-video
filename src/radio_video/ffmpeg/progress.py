from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProgressUpdate:
    """One block of FFmpeg ``-progress`` output."""

    out_time: float | None
    total_size: int | None
    speed: float | None
    fps: float | None
    finished: bool

    def fraction(self, duration: float | None) -> float | None:
        """Completed fraction in [0, 1], or None when it cannot be determined."""
        if self.finished:
            return 1.0
        if self.out_time is None or not duration or duration <= 0:
            return None
        return min(max(self.out_time / duration, 0.0), 1.0)

    def remaining_seconds(self, duration: float | None) -> float | None:
        if self.finished:
            return 0.0
        if self.out_time is None or not self.speed or not duration:
            return None
        return max(duration - self.out_time, 0.0) / self.speed


class ProgressParser:
    """Incremental parser for ``ffmpeg -progress pipe:1 -nostats`` output.

    FFmpeg writes ``key=value`` lines and terminates each block with
    ``progress=continue`` or ``progress=end``.
    """

    def __init__(self) -> None:
        self._values: dict[str, str] = {}
        self._buffer = ""

    def feed(self, data: str) -> list[ProgressUpdate]:
        self._buffer += data
        *lines, self._buffer = self._buffer.split("\n")
        updates: list[ProgressUpdate] = []
        for line in lines:
            update = self._feed_line(line.strip())
            if update is not None:
                updates.append(update)
        return updates

    def _feed_line(self, line: str) -> ProgressUpdate | None:
        key, sep, value = line.partition("=")
        if not sep:
            return None
        key, value = key.strip(), value.strip()
        if key != "progress":
            self._values[key] = value
            return None
        update = ProgressUpdate(
            out_time=_out_time(self._values),
            total_size=_int(self._values.get("total_size")),
            speed=_speed(self._values.get("speed")),
            fps=_float(self._values.get("fps")),
            finished=value == "end",
        )
        self._values.clear()
        return update


def _out_time(values: dict[str, str]) -> float | None:
    # out_time_ms is in microseconds despite its name; prefer out_time_us when present.
    for key in ("out_time_us", "out_time_ms"):
        micros = _int(values.get(key))
        if micros is not None and micros >= 0:
            return micros / 1_000_000
    return None


def _int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _float(value: str | None) -> float | None:
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def _speed(value: str | None) -> float | None:
    if value is None:
        return None
    speed = _float(value.removesuffix("x"))
    return speed if speed and speed > 0 else None
