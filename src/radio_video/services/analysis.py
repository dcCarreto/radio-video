from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from radio_video.errors import RadioVideoError
from radio_video.ffmpeg.probe import probe
from radio_video.models.media import MediaInfo

logger = logging.getLogger(__name__)


class _ProbeTask(QRunnable):
    def __init__(self, analyzer: MediaAnalyzer, request: int, path: Path, ffprobe: Path) -> None:
        super().__init__()
        self._completed = analyzer._completed
        self._request = request
        self._path = path
        self._ffprobe = ffprobe

    def run(self) -> None:
        try:
            result: MediaInfo | str = probe(self._path, self._ffprobe)
        except RadioVideoError as exc:
            result = str(exc)
        except Exception as exc:
            logger.exception("Unexpected error while analyzing %s", self._path)
            result = f"Unexpected error while analyzing {self._path.name}: {exc}"
        self._completed.emit(self._request, self._path, result)


class MediaAnalyzer(QObject):
    """Runs FFprobe on a worker thread and reports results on the owner's thread.

    Only the most recent request is reported; results of superseded requests are dropped.
    """

    started = Signal(Path)
    analyzed = Signal(MediaInfo)
    failed = Signal(Path, str)

    _completed = Signal(int, Path, object)

    def __init__(
        self,
        ffprobe: Path,
        pool: QThreadPool | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._ffprobe = ffprobe
        self._pool = pool or QThreadPool.globalInstance()
        self._request = 0
        self._busy = False
        self._completed.connect(self._on_completed)

    @property
    def busy(self) -> bool:
        return self._busy

    def analyze(self, path: Path) -> None:
        self._request += 1
        self._busy = True
        self.started.emit(path)
        self._pool.start(_ProbeTask(self, self._request, path, self._ffprobe))

    @Slot(int, Path, object)
    def _on_completed(self, request: int, path: Path, result: MediaInfo | str) -> None:
        if request != self._request:
            return
        self._busy = False
        if isinstance(result, MediaInfo):
            self.analyzed.emit(result)
        else:
            logger.warning("Analysis failed: %s", result)
            self.failed.emit(path, result)
