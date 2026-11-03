"""Progress bar, spinner and the progress block used by conversions and previews."""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QEasingCurve, QRectF, QSize, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QHideEvent, QPaintEvent, QShowEvent
from PySide6.QtWidgets import QHBoxLayout, QProgressBar, QSizePolicy, QVBoxLayout, QWidget

from radio_video.ui import icons, theme
from radio_video.ui.icons import IconName
from radio_video.ui.theme.fonts import TextStyle
from radio_video.ui.theme.tokens import Palette
from radio_video.ui.widgets.labels import ElidedLabel
from radio_video.ui.widgets.painting import antialiased, fill_rounded, follow_theme

BAR_HEIGHT = 6
INDETERMINATE_MS = 1600
INDETERMINATE_WIDTH = 0.3
ACCESSIBLE_STEP = 10


class ProgressState(Enum):
    ACTIVE = "active"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELED = "canceled"


def chunk_color(p: Palette, state: ProgressState) -> QColor:
    return {
        ProgressState.ACTIVE: p.accent,
        ProgressState.SUCCESS: p.success,
        ProgressState.FAILED: p.danger,
        ProgressState.CANCELED: p.text_2,
    }[state]


class ProgressBar(QProgressBar):
    """Thin painted bar. The fraction is drawn exactly; the accessible value moves in 10% steps
    so screen readers announce progress every 10%."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setRange(0, 100)
        self.setTextVisible(False)
        self.setFixedHeight(BAR_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._fraction = 0.0
        self._state = ProgressState.ACTIVE
        self._indeterminate = False
        self._phase = 0.0
        self._animation = QVariantAnimation(self)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setDuration(INDETERMINATE_MS)
        self._animation.setLoopCount(-1)
        self._animation.setEasingCurve(QEasingCurve.Type.Linear)
        self._animation.valueChanged.connect(self._on_phase)
        follow_theme(self)

    def fraction(self) -> float:
        return self._fraction

    def state(self) -> ProgressState:
        return self._state

    def is_indeterminate(self) -> bool:
        return self._indeterminate

    def set_fraction(self, fraction: float) -> None:
        self._fraction = min(max(fraction, 0.0), 1.0)
        self.set_indeterminate(False)
        step = int(self._fraction * 100) // ACCESSIBLE_STEP * ACCESSIBLE_STEP
        if step != self.value():
            self.setValue(step)
        self.update()

    def set_state(self, state: ProgressState) -> None:
        self._state = state
        self.update()

    def set_indeterminate(self, indeterminate: bool) -> None:
        if indeterminate == self._indeterminate:
            return
        self._indeterminate = indeterminate
        if indeterminate and self.isVisible():
            self._animation.start()
        else:
            self._animation.stop()
        self.update()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        if self._indeterminate:
            self._animation.start()

    def hideEvent(self, event: QHideEvent) -> None:  # noqa: N802
        self._animation.stop()
        super().hideEvent(event)

    def _on_phase(self, value: object) -> None:
        self._phase = float(value) if isinstance(value, (int, float)) else 0.0
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        p = theme.palette()
        rect = QRectF(self.rect())
        radius = rect.height() / 2
        fill_rounded(painter, rect, radius, p.border)
        color = chunk_color(p, self._state)
        painter.setClipRect(rect)
        if self._indeterminate:
            width = rect.width() * INDETERMINATE_WIDTH
            left = -width + (rect.width() + width) * self._phase
            fill_rounded(painter, QRectF(left, 0, width, rect.height()), radius, color)
        elif self._fraction > 0:
            fill_rounded(
                painter, QRectF(0, 0, rect.width() * self._fraction, rect.height()), radius, color
            )


class Spinner(QWidget):
    """Rotating LoaderCircle icon."""

    def __init__(self, size: int = 16, tone: str = "text", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._size = size
        self._tone = tone
        self._angle = 0.0
        self.setFixedSize(size, size)
        self._animation = QVariantAnimation(self)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(360.0)
        self._animation.setDuration(1000)
        self._animation.setLoopCount(-1)
        self._animation.valueChanged.connect(self._on_angle)
        self.setAccessibleName("Working")
        follow_theme(self)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self._animation.start()

    def hideEvent(self, event: QHideEvent) -> None:  # noqa: N802
        self._animation.stop()
        super().hideEvent(event)

    def _on_angle(self, value: object) -> None:
        self._angle = float(value) if isinstance(value, (int, float)) else 0.0
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        center = QRectF(self.rect()).center()
        painter.translate(center)
        painter.rotate(self._angle)
        painter.translate(-center)
        icons.paint_icon(
            painter, QRectF(self.rect()), "LoaderCircle", theme.palette().color(self._tone)
        )


class StatusIcon(QWidget):
    """Static icon in a palette colour, swapped by the progress block."""

    def __init__(self, size: int = 16, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icon: IconName = "Info"
        self._tone = "text"
        self.setFixedSize(size, size)
        follow_theme(self)

    def set_icon(self, name: IconName, tone: str = "text") -> None:
        self._icon, self._tone = name, tone
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.size()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        icons.paint_icon(
            painter, QRectF(self.rect()), self._icon, theme.palette().color(self._tone)
        )


class ProgressBlock(QWidget):
    """Header (spinner or status icon, title, detail) above a progress bar."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.spinner = Spinner(16)
        self.icon = StatusIcon(16)
        # File names in the title elide in the middle so the size at the end stays visible.
        self.title = ElidedLabel("", TextStyle.BODY_STRONG, mode=Qt.TextElideMode.ElideMiddle)
        self.title.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.detail = ElidedLabel("", TextStyle.BODY, tone="secondary")
        self.bar = ProgressBar()

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        header.addWidget(self.spinner)
        header.addWidget(self.icon)
        header.addWidget(self.title)
        header.addWidget(self.detail, 1)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)
        self._layout.addLayout(header)
        self._layout.addWidget(self.bar)
        self.set_busy(True)

    def add_widget(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)

    def set_busy(self, busy: bool) -> None:
        self.spinner.setVisible(busy)
        self.icon.setVisible(not busy)

    def set_status_icon(self, name: IconName, tone: str = "text") -> None:
        self.icon.set_icon(name, tone)
        self.set_busy(False)

    def set_header(self, title: str, detail: str = "") -> None:
        self.title.setText(title)
        self.detail.setText(detail)
        self.detail.setVisible(bool(detail))
