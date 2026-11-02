from __future__ import annotations

from pathlib import Path


def unique_output_path(folder: Path, stem: str, extension: str) -> Path:
    """Return ``folder/stem.extension``, adding `` (n)`` to the stem if the file exists."""
    candidate = folder / f"{stem}{extension}"
    counter = 1
    while candidate.exists():
        candidate = folder / f"{stem} ({counter}){extension}"
        counter += 1
    return candidate
