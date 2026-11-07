"""Conversion history: past conversions and their settings, kept in a JSON file on this
computer only."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 100
FORMAT_VERSION = 1


class HistoryResult(Enum):
    SAVED = "saved"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass(frozen=True)
class HistoryRecord:
    when: datetime
    source: Path
    output: Path | None
    format_key: str
    # None for lossless formats, which have no quality.
    quality: str | None
    custom: bool
    result: HistoryResult
    size: int | None = None
    took: float | None = None
    # How far a canceled conversion got, from 0 to 1.
    fraction: float = 0.0
    error: str = ""

    def to_json(self) -> dict[str, object]:
        data = asdict(self)
        data["when"] = self.when.isoformat(timespec="seconds")
        data["source"] = str(self.source)
        data["output"] = str(self.output) if self.output is not None else None
        data["result"] = self.result.value
        return data

    @classmethod
    def from_json(cls, data: dict[str, object]) -> HistoryRecord:
        output = data.get("output")
        size, took = data.get("size"), data.get("took")
        quality = data.get("quality")
        return cls(
            when=datetime.fromisoformat(str(data["when"])),
            source=Path(str(data["source"])),
            output=Path(str(output)) if output else None,
            format_key=str(data["format_key"]),
            quality=str(quality) if quality is not None else None,
            custom=bool(data.get("custom", False)),
            result=HistoryResult(str(data["result"])),
            size=int(size) if isinstance(size, int | float) else None,
            took=float(took) if isinstance(took, int | float) else None,
            fraction=float(data.get("fraction", 0.0) or 0.0),  # type: ignore[arg-type]
            error=str(data.get("error", "") or ""),
        )


class HistoryStore:
    """Newest first, at most ``limit`` records. A damaged file is set aside, not lost."""

    def __init__(self, path: Path, limit: int = HISTORY_LIMIT) -> None:
        self.path = path
        self.limit = limit
        self._records: list[HistoryRecord] = self._load()

    @property
    def records(self) -> tuple[HistoryRecord, ...]:
        return tuple(self._records)

    def add(self, record: HistoryRecord) -> None:
        self._records = [record, *self._records][: self.limit]
        self._save()

    def clear(self) -> None:
        self._records = []
        self._save()

    def _load(self) -> list[HistoryRecord]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            items = data["records"] if isinstance(data, dict) else []
            records = [HistoryRecord.from_json(item) for item in items]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            logger.warning("History file %s could not be read: %s", self.path, exc)
            self._set_aside()
            return []
        return records[: self.limit]

    def _set_aside(self) -> None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        try:
            self.path.replace(self.path.with_name(f"{self.path.stem}.damaged-{stamp}.json"))
        except OSError:
            logger.debug("Could not set the damaged history file aside", exc_info=True)

    def _save(self) -> None:
        payload = {
            "version": FORMAT_VERSION,
            "records": [record.to_json() for record in self._records],
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Written next to the file and swapped in, so a crash never leaves half a file.
            handle, temp = tempfile.mkstemp(prefix="history-", suffix=".tmp", dir=self.path.parent)
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=1)
            Path(temp).replace(self.path)
        except OSError:
            logger.warning("Could not save the history to %s", self.path, exc_info=True)


def output_missing(record: HistoryRecord) -> bool:
    """True when a saved file is no longer where it was written."""
    return (
        record.result is HistoryResult.SAVED
        and record.output is not None
        and not record.output.exists()
    )
