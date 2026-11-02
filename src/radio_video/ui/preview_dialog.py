from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from radio_video.ffmpeg.progress import ProgressUpdate
from radio_video.models.estimate import describe_settings
from radio_video.models.media import MediaInfo
from radio_video.models.presets import OutputFormat, Quality
from radio_video.services.conversion import ConversionError
from radio_video.services.preview import PreviewGenerator, PreviewKind, PreviewSample
from radio_video.ui.preview_player import PreviewPlayer
from radio_video.utils.formatting import format_duration, format_size

PROGRESS_STEPS = 1000


class PreviewDialog(QDialog):
    """Generates a converted preview with the selected settings and plays it."""

    size_estimated = Signal(int)

    def __init__(
        self,
        ffmpeg: Path,
        media: MediaInfo,
        output_format: OutputFormat,
        quality: Quality,
        kind: PreviewKind,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._media = media
        self._format = output_format
        self._quality = quality
        self._kind = kind
        self._settings = output_format.settings(quality)
        self._range_text = ""
        self.generator = PreviewGenerator(ffmpeg, self)

        title = "Short Preview" if kind is PreviewKind.SHORT else "Full Preview"
        self.setWindowTitle(f"{title} — {media.path.name}")
        self.resize(720, 520)

        quality_text = "" if output_format.lossless else f", {quality.value}"
        self.settings_label = QLabel(
            f"<b>{output_format.label}{quality_text}</b><br>"
            f"{describe_settings(self._settings, media)}"
        )
        self.range_label = QLabel()
        self.result_label = QLabel()
        self.result_label.setWordWrap(True)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, PROGRESS_STEPS)
        self.progress_bar.setTextVisible(False)
        self.status_label = QLabel()

        self.player = PreviewPlayer()
        self.player.setEnabled(False)

        self.buttons = QDialogButtonBox()
        self.cancel_button = QPushButton("Cancel Preview")
        self.buttons.addButton(self.cancel_button, QDialogButtonBox.ButtonRole.ActionRole)
        self.buttons.addButton(QDialogButtonBox.StandardButton.Close)

        layout = QVBoxLayout(self)
        layout.addWidget(self.settings_label)
        layout.addWidget(self.range_label)
        layout.addWidget(self.player, stretch=1)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        layout.addWidget(self.result_label)
        layout.addWidget(self.buttons)

        self.cancel_button.clicked.connect(self.generator.cancel)
        self.buttons.rejected.connect(self.reject)
        self.generator.progress.connect(self._on_progress)
        self.generator.ready.connect(self._on_ready)
        self.generator.failed.connect(self._on_failed)
        self.generator.canceled.connect(self._on_canceled)

    def start(self) -> bool:
        try:
            self.generator.generate(self._media, self._settings, self._format.extension, self._kind)
        except (ConversionError, ValueError, OSError) as exc:
            self.status_label.setText(f"Could not create the preview: {exc}")
            self.cancel_button.hide()
            return False
        job = self.generator.runner.job
        if job is not None and job.length is not None:
            self._range_text = (
                f"{format_duration(job.length)} starting at "
                f"{format_duration(job.start or 0)} of {format_duration(self._media.duration)}"
            )
        else:
            self._range_text = f"the whole file ({format_duration(self._media.duration)})"
        self.range_label.setText(f"Converting {self._range_text}")
        self.status_label.setText("Creating preview…")
        return True

    @Slot(ProgressUpdate)
    def _on_progress(self, update: ProgressUpdate) -> None:
        job = self.generator.runner.job
        fraction = update.fraction(job.expected_duration if job else None)
        if fraction is not None:
            self.progress_bar.setValue(round(fraction * PROGRESS_STEPS))
            self.status_label.setText(f"Creating preview… {fraction:.0%}")

    @Slot(PreviewSample)
    def _on_ready(self, sample: PreviewSample) -> None:
        self.progress_bar.setValue(PROGRESS_STEPS)
        self.progress_bar.hide()
        self.cancel_button.hide()
        self.range_label.setText(f"Converted {self._range_text}")
        self.status_label.setText("This is the converted output, not the original file.")
        estimate = sample.estimated_full_size(self._media.duration)
        lines = [f"Preview size: {format_size(sample.size)}"]
        if estimate is not None and sample.kind is PreviewKind.SHORT and sample.length:
            lines.append(f"Estimated size of the full conversion: ≈ {format_size(estimate)}")
        self.result_label.setText("<br>".join(lines))
        if estimate is not None:
            self.size_estimated.emit(estimate)
        self.player.setEnabled(True)
        self.player.load(sample.path)
        self.player.player.play()

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self.progress_bar.hide()
        self.cancel_button.hide()
        self.status_label.setText("The preview could not be created.")
        self.result_label.setText(message.splitlines()[-1] if message else "")
        self.result_label.setToolTip(message)

    @Slot()
    def _on_canceled(self) -> None:
        self.progress_bar.hide()
        self.cancel_button.hide()
        self.status_label.setText("Preview canceled.")

    def done(self, result: int) -> None:
        self.player.unload()
        self.generator.discard()
        super().done(result)
