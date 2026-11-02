"""Small painting helpers shared by the custom-painted widgets."""

from __future__ import annotations

import math

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from radio_video.ui import theme


def antialiased(widget: QWidget) -> QPainter:
    painter = QPainter(widget)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    return painter


def with_alpha(color: QColor, alpha: float) -> QColor:
    result = QColor(color)
    result.setAlphaF(color.alphaF() * alpha)
    return result


def fill_rounded(
    painter: QPainter,
    rect: QRectF,
    radius: float,
    fill: QColor | None,
    border: QColor | None = None,
    border_width: float = 1.0,
    dashed: bool = False,
) -> None:
    """Fill and stroke a rounded rectangle with the border drawn inside ``rect``."""
    painter.save()
    if fill is not None and fill.alpha() > 0:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, radius, radius)
    if border is not None and border.alpha() > 0 and border_width > 0:
        half = border_width / 2
        inner = rect.adjusted(half, half, -half, -half)
        pen = QPen(border, border_width)
        if dashed:
            pen.setDashPattern([3.0, 3.0])
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(inner, max(radius - half, 0), max(radius - half, 0))
    painter.restore()


def rounded_path(rect: QRectF, radii: tuple[float, float, float, float]) -> QPainterPath:
    """Path with per-corner radii: top-left, top-right, bottom-right, bottom-left."""
    tl, tr, br, bl = radii
    path = QPainterPath()
    path.moveTo(rect.left() + tl, rect.top())
    path.lineTo(rect.right() - tr, rect.top())
    path.quadTo(rect.right(), rect.top(), rect.right(), rect.top() + tr)
    path.lineTo(rect.right(), rect.bottom() - br)
    path.quadTo(rect.right(), rect.bottom(), rect.right() - br, rect.bottom())
    path.lineTo(rect.left() + bl, rect.bottom())
    path.quadTo(rect.left(), rect.bottom(), rect.left(), rect.bottom() - bl)
    path.lineTo(rect.left(), rect.top() + tl)
    path.quadTo(rect.left(), rect.top(), rect.left() + tl, rect.top())
    path.closeSubpath()
    return path


def text_width(font: QFont, text: str) -> int:
    """Width in whole pixels, rounded up so the text never elides in its own size hint."""
    return math.ceil(QFontMetricsF(font).horizontalAdvance(text))


def elide(font: QFont, text: str, mode: Qt.TextElideMode, width: float) -> str:
    # A sub-pixel tolerance keeps text that fits in its rounded width from eliding.
    return QFontMetricsF(font).elidedText(text, mode, max(width, 0.0) + 0.5)


def follow_theme(widget: QWidget) -> None:
    """Repaint ``widget`` whenever the theme changes."""
    theme.current().changed.connect(widget.update)
