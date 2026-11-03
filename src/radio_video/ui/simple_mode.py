from __future__ import annotations

import logging
from collections.abc import Collection
from pathlib import Path

from PySide6.QtCore import QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from radio_video.ffmpeg.progress import ProgressUpdate
from radio_video.models.conversion import ConversionJob
from radio_video.models.estimate import describe_settings, estimate_output_size
from radio_video.models.media import MediaInfo
from radio_video.models.presets import OutputFormat, Quality, available_formats
from radio_video.services.conversion import ConversionError, ConversionRunner
from radio_video.services.preview import SHORT_PREVIEW_SECONDS, PreviewKind
from radio_video.ui.preview_dialog import PreviewDialog
from radio_video.utils.formatting import format_duration, format_size
from radio_video.utils.paths import unique_output_path

logger = logging.getLogger(__name__)

PROGRESS_STEPS = 1000


class SimpleModePanel(QGroupBox):
    """Format and quality presets, destination, output summary and conversion controls."""

    busy_changed = Signal(bool)

    def __init__(
        self,
        runner: ConversionRunner,
        encoders: Collection[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Convert", parent)
        self._runner = runner
        self._encoders = frozenset(encoders)
        self._media: MediaInfo | None = None
        self._folder: Path | None = None
        self._chosen_folder: Path | None = None
        self._last_output: Path | None = None
        self._preview_estimate: tuple[Path, str, Quality, int] | None = None
        self.preview_dialog: PreviewDialog | None = None

        self.format_combo = QComboBox()
        self.quality_combo = QComboBox()
        for quality in Quality:
            self.quality_combo.addItem(quality.value, quality)
        self.quality_combo.setCurrentIndex(list(Quality).index(Quality.BALANCED))

        self.folder_edit = QLineEdit()
        self.folder_edit.setReadOnly(True)
        self.browse_button = QPushButton("Browse…")
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder_edit, stretch=1)
        folder_row.addWidget(self.browse_button)

        self.output_label = QLabel()
        self.details_label = QLabel()
        self.details_label.setWordWrap(True)
        self.size_label = QLabel()
        self.size_label.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Format:", self.format_combo)
        form.addRow("Quality:", self.quality_combo)
        form.addRow("Save to:", folder_row)
        form.addRow("Output file:", self.output_label)
        form.addRow("Output streams:", self.details_label)
        form.addRow("Estimated size:", self.size_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, PROGRESS_STEPS)
        self.progress_bar.setTextVisible(False)
        self.status_label = QLabel()
        self.convert_button = QPushButton("Convert")
        self.convert_button.setDefault(True)
        self.cancel_button = QPushButton("Cancel")
        self.show_button = QPushButton("Show in Folder")
        self.show_button.hide()
        self.short_preview_button = QPushButton(f"Preview {SHORT_PREVIEW_SECONDS:g} s")
        self.short_preview_button.setToolTip(
            f"Convert a {SHORT_PREVIEW_SECONDS:g}-second sample with these settings and play it"
        )
        self.full_preview_button = QPushButton("Full Preview")
        self.full_preview_button.setToolTip(
            "Convert the whole file to a temporary preview with these settings and play it"
        )

        buttons = QHBoxLayout()
        buttons.addWidget(self.status_label, stretch=1)
        buttons.addWidget(self.short_preview_button)
        buttons.addWidget(self.full_preview_button)
        buttons.addWidget(self.show_button)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.convert_button)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.progress_bar)
        layout.addLayout(buttons)

        self.format_combo.currentIndexChanged.connect(self._update_summary)
        self.quality_combo.currentIndexChanged.connect(self._update_summary)
        self.browse_button.clicked.connect(self._choose_folder)
        self.convert_button.clicked.connect(self.start_conversion)
        self.cancel_button.clicked.connect(self._runner.cancel)
        self.show_button.clicked.connect(self._show_output)
        self.short_preview_button.clicked.connect(lambda: self.open_preview(PreviewKind.SHORT))
        self.full_preview_button.clicked.connect(lambda: self.open_preview(PreviewKind.FULL))

        runner.started.connect(self._on_started)
        runner.progress.connect(self._on_progress)
        runner.succeeded.connect(self._on_succeeded)
        runner.failed.connect(self._on_failed)
        runner.canceled.connect(self._on_canceled)

        self._set_running(False)

    @property
    def selected_format(self) -> OutputFormat | None:
        data = self.format_combo.currentData()
        return data if isinstance(data, OutputFormat) else None

    @property
    def selected_quality(self) -> Quality:
        data = self.quality_combo.currentData()
        return data if isinstance(data, Quality) else Quality.BALANCED

    @property
    def output_path(self) -> Path | None:
        fmt = self.selected_format
        if self._media is None or self._folder is None or fmt is None:
            return None
        return unique_output_path(self._folder, self._media.path.stem, fmt.extension)

    def set_media(self, media: MediaInfo) -> None:
        previous = self.selected_format
        self._media = media
        self._folder = self._chosen_folder or media.path.parent
        self.folder_edit.setText(str(self._folder))
        self.show_button.hide()
        self.status_label.clear()
        self.progress_bar.setRange(0, PROGRESS_STEPS)
        self.progress_bar.setValue(0)

        formats = available_formats(self._encoders, media.has_video)
        self.format_combo.blockSignals(True)
        self.format_combo.clear()
        for fmt in formats:
            self.format_combo.addItem(fmt.label, fmt)
        if previous in formats:
            self.format_combo.setCurrentIndex(formats.index(previous))
        self.format_combo.blockSignals(False)

        if not formats:
            self.status_label.setText("The installed FFmpeg has none of the supported encoders.")
        self._set_running(False)
        self._update_summary()

    @Slot()
    def _update_summary(self) -> None:
        fmt = self.selected_format
        media = self._media
        self.quality_combo.setEnabled(fmt is not None and not fmt.lossless and not self.running)
        self.quality_combo.setToolTip(
            "Lossless formats keep the full quality of the source."
            if fmt is not None and fmt.lossless
            else ""
        )
        output = self.output_path
        if fmt is None or media is None or output is None:
            self.output_label.setText("—")
            self.details_label.setText("—")
            self.size_label.setText("—")
            self.convert_button.setEnabled(False)
            return

        settings = fmt.settings(self.selected_quality)
        self.output_label.setText(output.name)
        self.output_label.setToolTip(str(output))
        self.details_label.setText(describe_settings(settings, media))
        size = estimate_output_size(settings, media)
        measured = self._matching_preview_estimate()
        if size is not None:
            self.size_label.setText(f"≈ {format_size(size)}")
        elif measured is not None:
            self.size_label.setText(f"≈ {format_size(measured)} (measured from a preview)")
        else:
            self.size_label.setText(
                "Depends on the content (quality-based encoding). Create a preview to measure it."
            )
        self.convert_button.setEnabled(not self.running)
        self.short_preview_button.setEnabled(not self.running)
        self.full_preview_button.setEnabled(not self.running)

    def _matching_preview_estimate(self) -> int | None:
        fmt = self.selected_format
        if self._preview_estimate is None or self._media is None or fmt is None:
            return None
        path, key, quality, size = self._preview_estimate
        if (path, key, quality) != (self._media.path, fmt.key, self.selected_quality):
            return None
        return size

    def open_preview(self, kind: PreviewKind) -> PreviewDialog | None:
        fmt = self.selected_format
        media = self._media
        if fmt is None or media is None or self.running:
            return None
        quality = self.selected_quality
        dialog = PreviewDialog(self._runner.ffmpeg, media, fmt, quality, kind, self)
        dialog.setModal(True)
        dialog.size_estimated.connect(
            lambda size: self._store_preview_estimate(media.path, fmt.key, quality, size)
        )
        dialog.finished.connect(dialog.deleteLater)
        self.preview_dialog = dialog
        dialog.show()
        dialog.start()
        return dialog

    def _store_preview_estimate(self, path: Path, key: str, quality: Quality, size: int) -> None:
        self._preview_estimate = (path, key, quality, size)
        self._update_summary()

    @property
    def running(self) -> bool:
        return self._runner.is_running

    @Slot()
    def _choose_folder(self) -> None:
        start = str(self._folder) if self._folder else ""
        folder = QFileDialog.getExistingDirectory(self, "Choose Destination Folder", start)
        if folder:
            self._chosen_folder = Path(folder)
            self._folder = self._chosen_folder
            self.folder_edit.setText(folder)
            self._update_summary()

    @Slot()
    def start_conversion(self) -> None:
        fmt = self.selected_format
        output = self.output_path
        if self._media is None or fmt is None or output is None:
            return
        try:
            job = ConversionJob(
                source=self._media.path,
                destination=output,
                settings=fmt.settings(self.selected_quality),
                duration=self._media.duration,
                streams=fmt.plan(self._media),
            )
            self._runner.start(job)
        except (ConversionError, ValueError) as exc:
            QMessageBox.warning(self, "Cannot Start Conversion", str(exc))

    def _set_running(self, running: bool) -> None:
        for widget in (self.format_combo, self.browse_button):
            widget.setEnabled(not running)
        self.quality_combo.setEnabled(
            not running and self.selected_format is not None and not self.selected_format.lossless
        )
        self.convert_button.setEnabled(not running and self.selected_format is not None)
        for button in (self.short_preview_button, self.full_preview_button):
            button.setEnabled(not running and self.selected_format is not None)
        self.cancel_button.setVisible(running)
        self.busy_changed.emit(running)

    @Slot(ConversionJob)
    def _on_started(self, job: ConversionJob) -> None:
        self.show_button.hide()
        self.progress_bar.setRange(0, PROGRESS_STEPS if job.expected_duration else 0)
        self.progress_bar.setValue(0)
        self.status_label.setText(f"Converting to {job.destination.name}…")
        self._set_running(True)

    @Slot(ProgressUpdate)
    def _on_progress(self, update: ProgressUpdate) -> None:
        job = self._runner.job
        duration = job.expected_duration if job else None
        fraction = update.fraction(duration)
        if fraction is None:
            return
        self.progress_bar.setValue(round(fraction * PROGRESS_STEPS))
        parts = [f"{fraction:.0%}"]
        if update.speed:
            parts.append(f"{update.speed:.1f}×")
        remaining = update.remaining_seconds(duration)
        if remaining is not None and not update.finished:
            parts.append(f"{format_duration(remaining)} remaining")
        self.status_label.setText(" · ".join(parts))

    @Slot(Path)
    def _on_succeeded(self, output: Path) -> None:
        self._last_output = output
        self.progress_bar.setRange(0, PROGRESS_STEPS)
        self.progress_bar.setValue(PROGRESS_STEPS)
        size = output.stat().st_size if output.exists() else None
        self.status_label.setText(f"Saved {output.name} ({format_size(size)})")
        self.show_button.show()
        self._set_running(False)
        self._update_summary()

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self._reset_progress("Conversion failed")
        box = QMessageBox(QMessageBox.Icon.Critical, "Conversion Failed", "", parent=self)
        box.setText("FFmpeg could not convert the file.")
        box.setDetailedText(message)
        box.open()

    @Slot()
    def _on_canceled(self) -> None:
        self._reset_progress("Conversion canceled")

    def _reset_progress(self, status: str) -> None:
        self.progress_bar.setRange(0, PROGRESS_STEPS)
        self.progress_bar.setValue(0)
        self.status_label.setText(status)
        self._set_running(False)
        self._update_summary()

    @Slot()
    def _show_output(self) -> None:
        if self._last_output is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_output.parent)))
