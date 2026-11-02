from __future__ import annotations

from collections.abc import Collection
from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt, Slot
from PySide6.QtGui import QAction, QCloseEvent, QDragEnterEvent, QDropEvent, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStackedWidget,
    QWidget,
)

from radio_video import APP_NAME, __version__
from radio_video.ffmpeg.locator import FFmpegTools
from radio_video.models.media import MediaInfo
from radio_video.services.analysis import MediaAnalyzer
from radio_video.services.conversion import ConversionRunner
from radio_video.ui.drop_area import DropArea, local_files
from radio_video.ui.file_types import open_file_filter
from radio_video.ui.media_info_view import MediaInfoView
from radio_video.ui.simple_mode import SimpleModePanel

REPOSITORY_URL = "https://github.com/dcCarreto/radio-video"


class MainWindow(QMainWindow):
    def __init__(
        self,
        tools: FFmpegTools | None,
        tools_error: str | None = None,
        encoders: Collection[str] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(APP_NAME)
        self.resize(960, 720)
        self.setAcceptDrops(True)

        self._tools = tools
        self._media: MediaInfo | None = None
        self._last_dir = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.MoviesLocation
        )

        self.drop_area = DropArea()
        self.info_view = MediaInfoView()
        self.media_page = QSplitter(Qt.Orientation.Vertical)
        self.media_page.setChildrenCollapsible(False)
        self.media_page.addWidget(self.info_view)
        self.pages = QStackedWidget()
        self.pages.addWidget(self.drop_area)
        self.pages.addWidget(self.media_page)
        self.setCentralWidget(self.pages)

        self.analyzer: MediaAnalyzer | None = None
        self.runner: ConversionRunner | None = None
        self.simple_panel: SimpleModePanel | None = None
        if tools is not None:
            self.analyzer = MediaAnalyzer(tools.ffprobe, parent=self)
            self.analyzer.started.connect(self._on_analysis_started)
            self.analyzer.analyzed.connect(self._on_analyzed)
            self.analyzer.failed.connect(self._on_analysis_failed)
            self.runner = ConversionRunner(tools.ffmpeg, parent=self)
            self.simple_panel = SimpleModePanel(self.runner, encoders)
            self.simple_panel.busy_changed.connect(self._on_busy_changed)
            self.media_page.addWidget(self.simple_panel)
            self.media_page.setStretchFactor(0, 1)

        self._create_actions()
        self._create_menus()
        self.drop_area.open_requested.connect(self.open_file_dialog)
        self.drop_area.file_dropped.connect(self.open_file)

        if tools is None:
            message = tools_error or "FFmpeg was not found."
            self.drop_area.set_message(message)
            self.drop_area.open_button.setEnabled(False)
            self.open_action.setEnabled(False)
            self.drop_area.setAcceptDrops(False)
            self.setAcceptDrops(False)
            self.statusBar().showMessage("FFmpeg not found")
        else:
            self.statusBar().showMessage(f"Using FFprobe at {tools.ffprobe}", 5000)

    @property
    def media(self) -> MediaInfo | None:
        return self._media

    def _create_actions(self) -> None:
        self.open_action = QAction("&Open…", self)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.triggered.connect(self.open_file_dialog)

        self.exit_action = QAction("E&xit", self)
        self.exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.exit_action.triggered.connect(self.close)

        self.about_action = QAction(f"&About {APP_NAME}", self)
        self.about_action.triggered.connect(self._show_about)

        self.about_qt_action = QAction("About &Qt", self)
        self.about_qt_action.triggered.connect(QApplication.aboutQt)

    def _create_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self.open_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction(self.about_action)
        help_menu.addAction(self.about_qt_action)

    @Slot()
    def open_file_dialog(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open Media File", self._last_dir, open_file_filter()
        )
        if filename:
            self.open_file(Path(filename))

    @Slot(Path)
    def open_file(self, path: Path) -> None:
        if self.analyzer is None or self.converting:
            return
        self._last_dir = str(path.parent)
        self.analyzer.analyze(path)

    @property
    def converting(self) -> bool:
        return self.runner is not None and self.runner.is_running

    @Slot(bool)
    def _on_busy_changed(self, busy: bool) -> None:
        self.open_action.setEnabled(not busy)
        self.setAcceptDrops(not busy)

    @Slot(Path)
    def _on_analysis_started(self, path: Path) -> None:
        self.statusBar().showMessage(f"Analyzing {path.name}…")

    @Slot(MediaInfo)
    def _on_analyzed(self, info: MediaInfo) -> None:
        self._media = info
        self.info_view.set_media(info)
        if self.simple_panel is not None:
            self.simple_panel.set_media(info)
        self.pages.setCurrentWidget(self.media_page)
        self.setWindowTitle(f"{info.path.name} — {APP_NAME}")
        self.statusBar().showMessage(f"Loaded {info.path.name}", 5000)

    @Slot(Path, str)
    def _on_analysis_failed(self, path: Path, message: str) -> None:
        self.statusBar().showMessage(f"Could not open {path.name}", 5000)
        QMessageBox.warning(self, "Cannot Open File", message)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"<h3>{APP_NAME} {__version__}</h3>"
            "<p>Free and open-source audio and video converter.</p>"
            "<p>Released under the MIT License. Uses Qt, PySide6 and FFmpeg, "
            "which are distributed under their own licenses.</p>"
            f'<p><a href="{REPOSITORY_URL}">{REPOSITORY_URL}</a></p>',
        )

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if len(local_files(event)) == 1:
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        files = local_files(event)
        if len(files) == 1:
            event.acceptProposedAction()
            self.open_file(files[0])

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.runner is not None and self.runner.is_running:
            answer = QMessageBox.question(
                self,
                "Conversion in Progress",
                "A conversion is still running. Cancel it and quit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.runner.cancel()
            self.runner.wait()
        super().closeEvent(event)
