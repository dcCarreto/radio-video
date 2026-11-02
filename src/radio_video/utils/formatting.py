from __future__ import annotations

_SIZE_UNITS = ("B", "KB", "MB", "GB", "TB")


def format_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "—"
    total = round(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_size(size: int | None) -> str:
    if size is None or size < 0:
        return "—"
    value = float(size)
    for unit in _SIZE_UNITS:
        if value < 1024 or unit == _SIZE_UNITS[-1]:
            return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    raise AssertionError("unreachable")


def format_bitrate(bits_per_second: int | None) -> str:
    if bits_per_second is None or bits_per_second <= 0:
        return "—"
    if bits_per_second >= 1_000_000:
        return f"{bits_per_second / 1_000_000:.1f} Mb/s"
    return f"{round(bits_per_second / 1000)} kb/s"


def format_frame_rate(fps: float | None) -> str:
    if fps is None or fps <= 0:
        return "—"
    return f"{fps:.3f}".rstrip("0").rstrip(".") + " fps"
