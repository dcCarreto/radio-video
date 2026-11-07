from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtCore import QObject, Signal

from radio_video.ffmpeg.progress import ProgressUpdate
from radio_video.models.advanced import AdvancedChoices
from radio_video.models.conversion import ConversionJob
from radio_video.models.presets import Quality, format_by_key
from radio_video.services.conversion import ConversionError, ConversionRunner
from radio_video.services.queue import ConversionQueue, QueueEntry, QueueStatus
from radio_video.ui.demo import DEMO_MEDIA


class FakeRunner(QObject):
    started = Signal(ConversionJob)
    progress = Signal(ProgressUpdate)
    succeeded = Signal(Path)
    failed = Signal(str)
    canceled = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.jobs: list[ConversionJob] = []
        self.job: ConversionJob | None = None
        self.is_running = False

    def start(self, job: ConversionJob) -> None:
        self.jobs.append(job)
        self.job = job
        self.is_running = True

    def cancel(self) -> None:
        self.is_running = False
        self.canceled.emit()

    def succeed(self, tmp: Path) -> None:
        self.is_running = False
        assert self.job is not None
        self.job.destination.write_bytes(b"x" * 10)
        self.succeeded.emit(self.job.destination)

    def fail(self, message: str) -> None:
        self.is_running = False
        self.failed.emit(message)


def _queue(tmp_path: Path) -> tuple[ConversionQueue, FakeRunner]:
    runner = FakeRunner()
    fmt = format_by_key("mp3")

    def make_job(entry: QueueEntry) -> ConversionJob:
        assert entry.media is not None
        return ConversionJob(
            source=entry.path,
            destination=tmp_path / f"{entry.path.stem}-{entry.id}{fmt.extension}",
            settings=fmt.settings(entry.quality),
            duration=entry.media.duration,
        )

    return ConversionQueue(cast(ConversionRunner, runner), make_job), runner


def _add(queue: ConversionQueue, name: str, readable: bool = True) -> QueueEntry:
    path = Path(f"C:/videos/{name}")
    return queue.add(
        path,
        "mp3",
        Quality.BALANCED,
        AdvancedChoices(),
        Path("C:/out"),
        DEMO_MEDIA if readable else None,
        "" if readable else "Invalid data",
    )


def _statuses(queue: ConversionQueue) -> list[QueueStatus]:
    return [entry.status for entry in queue.entries]


def test_runs_entries_in_order(tmp_path: Path) -> None:
    queue, runner = _queue(tmp_path)
    first, second = _add(queue, "a.mkv"), _add(queue, "b.mkv")
    finished: list[QueueEntry] = []
    queue.entry_finished.connect(finished.append)
    assert queue.start()
    assert queue.running
    assert runner.jobs[-1].source.name == "a.mkv"
    assert _statuses(queue) == [QueueStatus.CONVERTING, QueueStatus.WAITING]
    runner.progress.emit(
        ProgressUpdate(out_time=66.5, total_size=None, speed=2.0, fps=None, finished=False)
    )
    current = queue.current
    assert current is not None and current.fraction == 0.5
    assert queue.overall_fraction() == 0.25
    runner.succeed(tmp_path)
    assert runner.jobs[-1].source.name == "b.mkv"
    runner.succeed(tmp_path)
    assert _statuses(queue) == [QueueStatus.DONE, QueueStatus.DONE]
    assert not queue.running
    assert [e.id for e in finished] == [first.id, second.id]
    assert finished[0].size == 10 and finished[0].took is not None


def test_failures_continue_with_the_next_file(tmp_path: Path) -> None:
    queue, runner = _queue(tmp_path)
    _add(queue, "a.mkv")
    _add(queue, "b.mkv")
    queue.start()
    runner.fail("Invalid data found when processing input")
    assert _statuses(queue) == [QueueStatus.FAILED, QueueStatus.CONVERTING]
    assert queue.entries[0].error.startswith("Invalid data")


def test_unreadable_files_are_listed_but_skipped(tmp_path: Path) -> None:
    queue, runner = _queue(tmp_path)
    broken = _add(queue, "broken.mkv", readable=False)
    _add(queue, "a.mkv")
    assert broken.status is QueueStatus.FAILED
    queue.start()
    assert runner.jobs[-1].source.name == "a.mkv"
    assert not queue.retry(broken.id)


def test_stop_cancels_the_current_file_and_keeps_the_rest(tmp_path: Path) -> None:
    queue, runner = _queue(tmp_path)
    _add(queue, "a.mkv")
    _add(queue, "b.mkv")
    queue.start()
    queue.stop()
    assert not queue.running
    assert _statuses(queue) == [QueueStatus.CANCELED, QueueStatus.WAITING]
    assert len(runner.jobs) == 1


def test_pause_after_the_current_file(tmp_path: Path) -> None:
    queue, runner = _queue(tmp_path)
    _add(queue, "a.mkv")
    _add(queue, "b.mkv")
    queue.start()
    queue.pause_after_current = True
    runner.succeed(tmp_path)
    assert not queue.running
    assert not queue.pause_after_current
    assert _statuses(queue) == [QueueStatus.DONE, QueueStatus.WAITING]
    assert queue.start()
    assert runner.jobs[-1].source.name == "b.mkv"


def test_retry_move_and_remove(tmp_path: Path) -> None:
    queue, runner = _queue(tmp_path)
    a, b, c = _add(queue, "a.mkv"), _add(queue, "b.mkv"), _add(queue, "c.mkv")
    assert queue.move(c.id, -1)
    assert [e.id for e in queue.entries] == [a.id, c.id, b.id]
    assert not queue.move(a.id, -1)
    queue.start()
    runner.fail("boom")
    assert queue.retry(a.id)
    assert queue.entries[0].status is QueueStatus.WAITING
    # Removing the file being converted cancels it and drops it.
    converting = queue.current
    assert converting is not None
    queue.remove(converting.id)
    assert converting.id not in [e.id for e in queue.entries]
    assert queue.current is not None


def test_job_errors_fail_the_entry(tmp_path: Path) -> None:
    runner = FakeRunner()

    def make_job(entry: QueueEntry) -> ConversionJob:
        raise ConversionError("Destination folder does not exist")

    queue = ConversionQueue(cast(ConversionRunner, runner), make_job)
    _add(queue, "a.mkv")
    queue.start()
    assert _statuses(queue) == [QueueStatus.FAILED]
    assert not queue.running


def test_counts(tmp_path: Path) -> None:
    queue, _runner = _queue(tmp_path)
    _add(queue, "a.mkv")
    _add(queue, "b.mkv")
    _add(queue, "c.mkv", readable=False)
    queue.start()
    counts = queue.counts()
    assert (counts.converting, counts.waiting, counts.failed) == (1, 1, 1)
    queue.clear_finished()
    assert len(queue.entries) == 2
