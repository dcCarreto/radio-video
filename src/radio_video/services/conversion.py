from __future__ import annotations

import logging
from collections import deque
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal, Slot

from radio_video.errors import RadioVideoError
from radio_video.ffmpeg.command import build_conversion_command
from radio_video.ffmpeg.progress import ProgressParser, ProgressUpdate
from radio_video.models.conversion import ConversionJob

logger = logging.getLogger(__name__)

STDERR_TAIL_LINES = 40


class ConversionError(RadioVideoError):
    """A conversion could not be started."""


def partial_path(destination: Path) -> Path:
    """Temporary file next to the destination, keeping its extension so FFmpeg picks the muxer."""
    return destination.with_name(f".{destination.stem}.partial{destination.suffix}")


class ConversionRunner(QObject):
    """Runs one FFmpeg conversion at a time without blocking the event loop.

    Output is written to a temporary file in the destination folder and moved into place only
    when FFmpeg succeeds, so a failed or canceled conversion never leaves a truncated file.
    """

    started = Signal(ConversionJob)
    progress = Signal(ProgressUpdate)
    succeeded = Signal(Path)
    failed = Signal(str)
    canceled = Signal()

    def __init__(self, ffmpeg: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._ffmpeg = ffmpeg
        self._process: QProcess | None = None
        self._job: ConversionJob | None = None
        self._partial: Path | None = None
        self._parser = ProgressParser()
        self._stderr: deque[str] = deque(maxlen=STDERR_TAIL_LINES)
        self._cancel_requested = False

    @property
    def is_running(self) -> bool:
        return self._process is not None

    @property
    def job(self) -> ConversionJob | None:
        return self._job

    def start(self, job: ConversionJob) -> None:
        if self.is_running:
            raise ConversionError("A conversion is already running")
        if not job.source.is_file():
            raise ConversionError(f"Source file not found: {job.source}")
        destination = job.destination.resolve()
        if not destination.parent.is_dir():
            raise ConversionError(f"Destination folder does not exist: {destination.parent}")
        if destination.exists() and not job.overwrite:
            raise ConversionError(f"{destination.name} already exists")

        self._job = job
        self._partial = partial_path(destination)
        self._parser = ProgressParser()
        self._stderr.clear()
        self._cancel_requested = False

        command = build_conversion_command(self._ffmpeg, job, self._partial)
        logger.info("Starting conversion: %s", command)

        process = QProcess(self)
        process.setProgram(command[0])
        process.setArguments(command[1:])
        process.readyReadStandardOutput.connect(self._read_stdout)
        process.readyReadStandardError.connect(self._read_stderr)
        process.finished.connect(self._on_finished)
        process.errorOccurred.connect(self._on_error)
        self._process = process
        process.start()
        self.started.emit(job)

    def cancel(self) -> None:
        if self._process is None:
            return
        logger.info("Canceling conversion of %s", self._job.source if self._job else "?")
        self._cancel_requested = True
        self._process.kill()

    def wait(self, msecs: int = 30000) -> bool:
        """Block until the running process exits. Intended for shutdown and tests."""
        if self._process is None:
            return True
        return self._process.waitForFinished(msecs)

    @Slot()
    def _read_stdout(self) -> None:
        if self._process is None:
            return
        data = bytes(self._process.readAllStandardOutput().data()).decode("utf-8", "replace")
        for update in self._parser.feed(data):
            self.progress.emit(update)

    @Slot()
    def _read_stderr(self) -> None:
        if self._process is None:
            return
        data = bytes(self._process.readAllStandardError().data()).decode("utf-8", "replace")
        for line in data.splitlines():
            if line.strip():
                self._stderr.append(line.rstrip())

    @Slot(QProcess.ProcessError)
    def _on_error(self, error: QProcess.ProcessError) -> None:
        if error is QProcess.ProcessError.FailedToStart:
            message = f"Could not start FFmpeg ({self._ffmpeg}): {self._process_error_text()}"
            self._finish_failed(message)

    @Slot(int, QProcess.ExitStatus)
    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        if self._process is None:
            return
        self._read_stdout()
        self._read_stderr()
        if self._cancel_requested:
            self._cleanup_partial()
            self._reset()
            self.canceled.emit()
            return
        if exit_status is QProcess.ExitStatus.NormalExit and exit_code == 0:
            self._finish_succeeded()
            return
        detail = "\n".join(self._stderr) or f"FFmpeg exited with code {exit_code}"
        self._finish_failed(detail)

    def _finish_succeeded(self) -> None:
        if self._job is None or self._partial is None:
            return
        destination = self._job.destination.resolve()
        try:
            self._partial.replace(destination)
        except OSError as exc:
            self._finish_failed(f"Could not write {destination}: {exc}")
            return
        logger.info("Conversion finished: %s", destination)
        self._reset()
        self.succeeded.emit(destination)

    def _finish_failed(self, message: str) -> None:
        logger.error("Conversion failed: %s", message)
        self._cleanup_partial()
        self._reset()
        self.failed.emit(message)

    def _process_error_text(self) -> str:
        return self._process.errorString() if self._process is not None else "unknown error"

    def _cleanup_partial(self) -> None:
        if self._partial is None:
            return
        try:
            self._partial.unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not remove temporary file %s", self._partial, exc_info=True)

    def _reset(self) -> None:
        if self._process is not None:
            self._process.deleteLater()
        self._process = None
        self._partial = None
        self._job = None
