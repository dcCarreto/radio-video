from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget


def local_files(event: QDragEnterEvent | QDropEvent) -> list[Path]:
    mime = event.mimeData()
    if not mime.hasUrls():
        return []
    return [Path(url.toLocalFile()) for url in mime.urls() if url.isLocalFile()]


class DropArea(QFrame):
    """Landing area shown when no file is loaded."""

    file_dropped = Signal(Path)
    open_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dropArea")
        self.setAcceptDrops(True)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "#dropArea { border: 2px dashed palette(mid); border-radius: 12px; }"
            "#dropArea[dragActive='true'] { border-color: palette(highlight); }"
        )

        title = QLabel("Drop an audio or video file here")
        font = title.font()
        font.setPointSizeF(font.pointSizeF() * 1.4)
        title.setFont(font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._message = QLabel("or")
        self._message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message.setWordWrap(True)

        self.open_button = QPushButton("Open File…")
        self.open_button.clicked.connect(self.open_requested)

        layout = QVBoxLayout(self)
        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(self._message)
        layout.addWidget(self.open_button, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()

    def set_message(self, text: str) -> None:
        self._message.setText(text)

    def _set_drag_active(self, active: bool) -> None:
        self.setProperty("dragActive", active)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if len(local_files(event)) == 1:
            self._set_drag_active(True)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:  # noqa: N802
        self._set_drag_active(False)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        self._set_drag_active(False)
        files = local_files(event)
        if len(files) == 1:
            event.acceptProposedAction()
            self.file_dropped.emit(files[0])
