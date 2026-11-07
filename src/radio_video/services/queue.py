"""Conversion queue: many files converted one after another, each with its own settings."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from radio_video.errors import RadioVideoError
from radio_video.ffmpeg.probe import probe
from radio_video.ffmpeg.progress import ProgressUpdate
from radio_video.models.advanced import AdvancedChoices
from radio_video.models.conversion import ConversionJob
from radio_video.models.media import MediaInfo
from radio_video.models.presets import Quality
from radio_video.services.conversion import ConversionError, ConversionRunner

logger = logging.getLogger(__name__)


class QueueStatus(Enum):
    WAITING = "waiting"
    CONVERTING = "converting"
    DONE = "done"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass(frozen=True)
class QueueEntry:
    """One file and the settings it will be converted with."""

    id: int
    path: Path
    format_key: str
    quality: Quality
    choices: AdvancedChoices
    folder: Path
    # None when the file couldn't be read; such entries can't be converted.
    media: MediaInfo | None = None
    status: QueueStatus = QueueStatus.WAITING
    fraction: float = 0.0
    speed: float | None = None
    remaining: float | None = None
    error: str = ""
    output: Path | None = None
    size: int | None = None
    took: float | None = None

    @property
    def readable(self) -> bool:
        return self.media is not None

    @property
    def finished(self) -> bool:
        return self.status in (QueueStatus.DONE, QueueStatus.FAILED, QueueStatus.CANCELED)


@dataclass(frozen=True)
class QueueCounts:
    done: int = 0
    converting: int = 0
    waiting: int = 0
    failed: int = 0
    canceled: int = 0


JobMaker = Callable[[QueueEntry], ConversionJob]


class ConversionQueue(QObject):
    """Runs the waiting entries in order, one at a time.

    ``make_job`` turns an entry into a conversion job when its turn comes, so the output
    name is chosen against the files that exist at that moment.
    """

    changed = Signal()
    progressed = Signal(int)
    entry_finished = Signal(object)
    run_finished = Signal()

    def __init__(
        self, runner: ConversionRunner, make_job: JobMaker, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self.runner = runner
        self._make_job = make_job
        self._entries: list[QueueEntry] = []
        self._next_id = 1
        self._running = False
        self._current: int | None = None
        self._started_at = 0.0
        self._remove_when_stopped: set[int] = set()
        self.pause_after_current = False
        runner.progress.connect(self._on_progress)
        runner.succeeded.connect(self._on_succeeded)
        runner.failed.connect(self._on_failed)
        runner.canceled.connect(self._on_canceled)

    # Reading
    @property
    def entries(self) -> tuple[QueueEntry, ...]:
        return tuple(self._entries)

    @property
    def running(self) -> bool:
        return self._running

    @property
    def current(self) -> QueueEntry | None:
        return self.entry(self._current) if self._current is not None else None

    def entry(self, entry_id: int) -> QueueEntry | None:
        return next((e for e in self._entries if e.id == entry_id), None)

    def counts(self) -> QueueCounts:
        totals = {status: 0 for status in QueueStatus}
        for entry in self._entries:
            totals[entry.status] += 1
        return QueueCounts(
            done=totals[QueueStatus.DONE],
            converting=totals[QueueStatus.CONVERTING],
            waiting=totals[QueueStatus.WAITING],
            failed=totals[QueueStatus.FAILED],
            canceled=totals[QueueStatus.CANCELED],
        )

    def can_start(self) -> bool:
        return not self._running and any(
            e.status is QueueStatus.WAITING and e.readable for e in self._entries
        )

    def overall_fraction(self) -> float:
        """Progress through the whole queue: finished files plus the current one's part."""
        if not self._entries:
            return 0.0
        finished = sum(1 for e in self._entries if e.finished)
        current = self.current
        part = current.fraction if current is not None else 0.0
        return min(1.0, (finished + part) / len(self._entries))

    # Changing
    def add(
        self,
        path: Path,
        format_key: str,
        quality: Quality,
        choices: AdvancedChoices,
        folder: Path,
        media: MediaInfo | None,
        error: str = "",
    ) -> QueueEntry:
        status = QueueStatus.WAITING if media is not None else QueueStatus.FAILED
        entry = QueueEntry(
            self._next_id, path, format_key, quality, choices, folder, media, status, error=error
        )
        self._next_id += 1
        self._entries.append(entry)
        self.changed.emit()
        return entry

    def remove(self, entry_id: int) -> None:
        """Remove an entry; the one converting is canceled first."""
        if entry_id == self._current and self.runner.is_running:
            self._remove_when_stopped.add(entry_id)
            self.runner.cancel()
            return
        self._entries = [e for e in self._entries if e.id != entry_id]
        self.changed.emit()

    def clear_finished(self) -> None:
        self._entries = [e for e in self._entries if not e.finished]
        self.changed.emit()

    def move(self, entry_id: int, delta: int) -> bool:
        index = next((i for i, e in enumerate(self._entries) if e.id == entry_id), None)
        if index is None:
            return False
        target = index + delta
        if not 0 <= target < len(self._entries):
            return False
        entries = self._entries
        entries[index], entries[target] = entries[target], entries[index]
        self.changed.emit()
        return True

    def retry(self, entry_id: int) -> bool:
        entry = self.entry(entry_id)
        if (
            entry is None
            or not entry.readable
            or entry.status
            not in (
                QueueStatus.FAILED,
                QueueStatus.CANCELED,
            )
        ):
            return False
        self._replace(
            replace(entry, status=QueueStatus.WAITING, fraction=0.0, error="", output=None)
        )
        self.changed.emit()
        return True

    # Running
    def start(self) -> bool:
        if not self.can_start():
            return False
        self._running = True
        self.changed.emit()
        self._next()
        return True

    def stop(self) -> None:
        """Stop the queue: the current file is canceled and the rest keep waiting."""
        if not self._running:
            return
        self._running = False
        if self.runner.is_running:
            self.runner.cancel()
        self.changed.emit()

    def _next(self) -> None:
        upcoming = next(
            (e for e in self._entries if e.status is QueueStatus.WAITING and e.readable), None
        )
        if not self._running or upcoming is None:
            self._end_run()
            return
        try:
            job = self._make_job(upcoming)
        except (ConversionError, RadioVideoError, ValueError, OSError) as exc:
            self._finish(upcoming, QueueStatus.FAILED, error=str(exc))
            self._next()
            return
        self._current = upcoming.id
        self._started_at = time.monotonic()
        self._replace(replace(upcoming, status=QueueStatus.CONVERTING, output=job.destination))
        self.changed.emit()
        try:
            self.runner.start(job)
        except (ConversionError, ValueError, OSError) as exc:
            self._current = None
            self._finish(self._entry_or(upcoming), QueueStatus.FAILED, error=str(exc))
            self._next()

    def _end_run(self) -> None:
        was_running = self._running
        self._running = False
        self._current = None
        self.changed.emit()
        if was_running:
            self.run_finished.emit()

    def _entry_or(self, fallback: QueueEntry) -> QueueEntry:
        return self.entry(fallback.id) or fallback

    def _replace(self, entry: QueueEntry) -> None:
        self._entries = [entry if e.id == entry.id else e for e in self._entries]

    def _finish(self, entry: QueueEntry, status: QueueStatus, **changes: object) -> None:
        finished = replace(entry, status=status, speed=None, remaining=None, **changes)  # type: ignore[arg-type]
        self._replace(finished)
        self.entry_finished.emit(finished)

    def _after_current(self, status: QueueStatus, **changes: object) -> None:
        current = self.current
        self._current = None
        if current is not None:
            if current.id in self._remove_when_stopped:
                self._remove_when_stopped.discard(current.id)
                self._entries = [e for e in self._entries if e.id != current.id]
            else:
                self._finish(current, status, **changes)
        if self.pause_after_current and self._running:
            self.pause_after_current = False
            self._end_run()
            return
        self._next()

    @Slot(ProgressUpdate)
    def _on_progress(self, update: ProgressUpdate) -> None:
        current = self.current
        job = self.runner.job
        if current is None or job is None:
            return
        fraction = update.fraction(job.expected_duration)
        if fraction is None:
            return
        self._replace(
            replace(
                current,
                fraction=fraction,
                speed=update.speed,
                remaining=update.remaining_seconds(job.expected_duration),
            )
        )
        self.progressed.emit(current.id)

    @Slot(Path)
    def _on_succeeded(self, output: Path) -> None:
        size = output.stat().st_size if output.exists() else None
        took = time.monotonic() - self._started_at
        self._after_current(QueueStatus.DONE, fraction=1.0, output=output, size=size, took=took)

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self._after_current(QueueStatus.FAILED, error=message, output=None)

    @Slot()
    def _on_canceled(self) -> None:
        self._after_current(QueueStatus.CANCELED, output=None)


class _ReadTask(QRunnable):
    def __init__(self, reader: FileReader, request: int, paths: list[Path], ffprobe: Path) -> None:
        super().__init__()
        self._signal = reader._read
        self._request = request
        self._paths = paths
        self._ffprobe = ffprobe

    def run(self) -> None:
        for path in self._paths:
            try:
                result: MediaInfo | str = probe(path, self._ffprobe)
            except RadioVideoError as exc:
                result = str(exc)
            except Exception as exc:
                logger.exception("Unexpected error while reading %s", path)
                result = f"Unexpected error while reading {path.name}: {exc}"
            self._signal.emit(self._request, path, result)


class FileReader(QObject):
    """Reads several files on a worker thread and reports each one, in order."""

    read = Signal(Path, object)
    _read = Signal(int, Path, object)

    def __init__(
        self, ffprobe: Path, pool: QThreadPool | None = None, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._ffprobe = ffprobe
        self._pool = pool or QThreadPool.globalInstance()
        self._request = 0
        self._read.connect(self._on_read)

    def read_files(self, paths: Iterable[Path]) -> None:
        self._request += 1
        self._pool.start(_ReadTask(self, self._request, list(paths), self._ffprobe))

    @Slot(int, Path, object)
    def _on_read(self, _request: int, path: Path, result: MediaInfo | str) -> None:
        self.read.emit(path, result)
