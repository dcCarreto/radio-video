from __future__ import annotations

import logging
import shutil
import tempfile
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from radio_video.ffmpeg.progress import ProgressUpdate
from radio_video.models.conversion import ConversionJob, ConversionSettings
from radio_video.models.media import MediaInfo
from radio_video.models.tracks import StreamMap
from radio_video.services.conversion import ConversionRunner

logger = logging.getLogger(__name__)

SHORT_PREVIEW_SECONDS = 15.0
SHORT_PREVIEW_OFFSET = 1 / 3
TEMP_PREFIX = "radio-video-preview-"
STALE_PREVIEW_SECONDS = 12 * 3600


class PreviewKind(Enum):
    SHORT = "short"
    FULL = "full"


@dataclass(frozen=True)
class PreviewSample:
    """A converted preview file and the part of the source it covers."""

    path: Path
    kind: PreviewKind
    start: float
    length: float | None
    size: int

    def estimated_full_size(self, duration: float | None) -> int | None:
        """Extrapolate the full output size from a short preview."""
        if self.kind is PreviewKind.FULL or self.length is None:
            return self.size
        if not duration or self.length <= 0:
            return None
        return round(self.size * duration / self.length)


def purge_stale_previews(
    max_age_seconds: float = STALE_PREVIEW_SECONDS, temp_root: Path | None = None
) -> int:
    """Delete preview folders left behind by earlier sessions. Returns how many were removed."""
    root = temp_root or Path(tempfile.gettempdir())
    cutoff = time.time() - max_age_seconds
    removed = 0
    for folder in root.glob(f"{TEMP_PREFIX}*"):
        try:
            if folder.is_dir() and folder.stat().st_mtime < cutoff:
                shutil.rmtree(folder)
                removed += 1
        except OSError:
            logger.debug("Could not remove stale preview folder %s", folder, exc_info=True)
    return removed


def short_preview_range(duration: float | None) -> tuple[float, float | None]:
    """Start and length of a short preview.

    The sample starts a third of the way into the file to skip typical intros and black
    frames, and is shifted back so it never runs past the end.
    """
    if duration is None:
        return 0.0, SHORT_PREVIEW_SECONDS
    if duration <= SHORT_PREVIEW_SECONDS:
        return 0.0, None
    start = min(duration * SHORT_PREVIEW_OFFSET, duration - SHORT_PREVIEW_SECONDS)
    return round(start, 3), SHORT_PREVIEW_SECONDS


class PreviewGenerator(QObject):
    """Produces temporary preview files with the real conversion settings.

    Each preview replaces the previous one; temporary files are deleted on ``discard()``.
    """

    started = Signal(PreviewKind)
    progress = Signal(ProgressUpdate)
    ready = Signal(PreviewSample)
    failed = Signal(str)
    canceled = Signal()

    def __init__(self, ffmpeg: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.runner = ConversionRunner(ffmpeg, self)
        self._temp_dir: Path | None = None
        self._kind = PreviewKind.SHORT
        self._start = 0.0
        self._length: float | None = None
        self.runner.progress.connect(self.progress)
        self.runner.succeeded.connect(self._on_succeeded)
        self.runner.failed.connect(self.failed)
        self.runner.canceled.connect(self.canceled)

    @property
    def is_running(self) -> bool:
        return self.runner.is_running

    def generate(
        self,
        media: MediaInfo,
        settings: ConversionSettings,
        extension: str,
        kind: PreviewKind,
        streams: StreamMap | None = None,
    ) -> None:
        self.discard()
        self._temp_dir = Path(tempfile.mkdtemp(prefix=TEMP_PREFIX))
        if kind is PreviewKind.SHORT:
            self._start, self._length = short_preview_range(media.duration)
        else:
            self._start, self._length = 0.0, None
        self._kind = kind
        job = ConversionJob(
            source=media.path,
            destination=self._temp_dir / f"preview{extension}",
            settings=settings,
            duration=media.duration,
            start=self._start or None,
            length=self._length,
            overwrite=True,
            streams=streams,
        )
        self.runner.start(job)
        self.started.emit(kind)

    def cancel(self) -> None:
        self.runner.cancel()

    def discard(self) -> None:
        """Cancel any running preview and delete temporary files."""
        if self.runner.is_running:
            self.runner.cancel()
            self.runner.wait()
        if self._temp_dir is not None:
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            logger.debug("Removed preview directory %s", self._temp_dir)
            self._temp_dir = None

    @Slot(Path)
    def _on_succeeded(self, path: Path) -> None:
        sample = PreviewSample(
            path=path,
            kind=self._kind,
            start=self._start,
            length=self._length,
            size=path.stat().st_size,
        )
        self.ready.emit(sample)
