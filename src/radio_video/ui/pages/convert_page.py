"""Convert tab: the step strip above the start, engine-missing or file view."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QGridLayout,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from radio_video.ui import strings as s
from radio_video.ui import theme
from radio_video.ui.pages.convert_panel import PANEL_WIDTH, PANEL_WIDTH_COMPACT, ConvertPanel
from radio_video.ui.pages.missing_view import EngineMissingView
from radio_video.ui.pages.source_pane import SourcePane
from radio_video.ui.pages.start_view import StartView
from radio_video.ui.strings import tr
from radio_video.ui.theme.tokens import Palette
from radio_video.ui.widgets.drop_zone import DropZone
from radio_video.ui.widgets.step_strip import StepStrip

SPLITTER_HANDLE = 2
OVERLAY_MARGIN = 16


class FileView(QWidget):
    """Source pane and convert panel, with a drop overlay for drags over the window."""

    def __init__(self, overlay: DropZone, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.source = SourcePane()
        self.panel = ConvertPanel()
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(SPLITTER_HANDLE)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self.source)
        self.splitter.addWidget(self.panel)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.handle(1).setToolTip(tr(s.SPLITTER_TOOLTIP))

        # The window handles drags; the overlay only shows the state.
        self.overlay = overlay
        self.overlay.setAcceptDrops(False)
        self.overlay.open_button.hide()
        self._shadow = QGraphicsDropShadowEffect(self.overlay)
        self._shadow.setOffset(0, 2)
        self._shadow.setBlurRadius(16)
        self.overlay.setGraphicsEffect(self._shadow)
        self.overlay_box = QWidget()
        self.overlay_box.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        box = QVBoxLayout(self.overlay_box)
        box.setContentsMargins(OVERLAY_MARGIN, OVERLAY_MARGIN, OVERLAY_MARGIN, OVERLAY_MARGIN)
        box.addWidget(self.overlay)
        self.overlay_box.hide()

        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.addWidget(self.splitter, 0, 0)
        grid.addWidget(self.overlay_box, 0, 0)
        theme.current().changed.connect(self._on_theme)
        self._on_theme(theme.palette())

    def _on_theme(self, palette: Palette) -> None:
        self._shadow.setColor(QColor(0, 0, 0, 128) if palette.is_dark else QColor(32, 30, 29, 36))

    def set_overlay_visible(self, visible: bool) -> None:
        self.overlay_box.setVisible(visible)
        if visible:
            self.overlay_box.raise_()

    def set_panel_width(self, width: int) -> None:
        total = max(self.splitter.width(), width + 200)
        self.splitter.setSizes([total - width - SPLITTER_HANDLE, width])

    def set_compact(self, compact: bool) -> None:
        self.source.set_compact(compact)
        self.panel.set_compact(compact)
        self.set_panel_width(PANEL_WIDTH_COMPACT if compact else PANEL_WIDTH)


class ConvertPage(QWidget):
    def __init__(
        self, drop_zone: DropZone, overlay: DropZone, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.steps = StepStrip([tr(x) for x in s.STEPS], [tr(x) for x in s.STEPS_SHORT])
        self.start = StartView(drop_zone)
        self.missing = EngineMissingView()
        self.file = FileView(overlay)
        self.views = QStackedWidget()
        for view in (self.start, self.missing, self.file):
            self.views.addWidget(view)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.steps)
        layout.addWidget(self.views, 1)

    def show_view(self, view: QWidget) -> None:
        self.views.setCurrentWidget(view)
        self.steps.setVisible(view is not self.missing)

    def set_compact(self, compact: bool) -> None:
        self.steps.set_compact(compact)
        self.start.set_compact(compact)
        self.missing.set_compact(compact)
        self.file.set_compact(compact)
