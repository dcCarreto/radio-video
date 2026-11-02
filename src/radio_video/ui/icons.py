"""Lucide icons (ISC license, see icons/lucide/LICENSE), recoloured at runtime."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Literal

from PySide6.QtCore import QByteArray, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QPolygonF
from PySide6.QtSvg import QSvgRenderer

ICON_DIR = Path(__file__).with_name("icons") / "lucide"

IconName = Literal[
    "Upload", "ArrowDownToLine", "Ban", "FolderOpen", "Folder", "Film", "Music", "Captions",
    "Image", "ArrowRightLeft", "ListOrdered", "History", "Settings", "Eye", "MonitorPlay",
    "LoaderCircle", "CircleCheck", "CircleX", "TriangleAlert", "Info", "ShieldCheck", "Files",
    "Eraser", "Copy", "RefreshCw", "RotateCcw", "X", "Check", "ChevronDown", "ChevronRight",
    "Play", "Pause", "Volume2", "VolumeX", "Cpu", "Clock", "Plus", "ArrowUp", "ArrowDown",
    "Trash2", "Square", "FileText", "ExternalLink", "LogOut", "Minus",
]  # fmt: skip

FILE_NAMES: dict[IconName, str] = {
    "Upload": "upload",
    "ArrowDownToLine": "arrow-down-to-line",
    "Ban": "ban",
    "FolderOpen": "folder-open",
    "Folder": "folder",
    "Film": "film",
    "Music": "music",
    "Captions": "captions",
    "Image": "image",
    "ArrowRightLeft": "arrow-right-left",
    "ListOrdered": "list-ordered",
    "History": "history",
    "Settings": "settings",
    "Eye": "eye",
    "MonitorPlay": "monitor-play",
    "LoaderCircle": "loader-circle",
    "CircleCheck": "circle-check",
    "CircleX": "circle-x",
    "TriangleAlert": "triangle-alert",
    "Info": "info",
    "ShieldCheck": "shield-check",
    "Files": "files",
    "Eraser": "eraser",
    "Copy": "copy",
    "RefreshCw": "refresh-cw",
    "RotateCcw": "rotate-ccw",
    "X": "x",
    "Check": "check",
    "ChevronDown": "chevron-down",
    "ChevronRight": "chevron-right",
    "Play": "play",
    "Pause": "pause",
    "Volume2": "volume-2",
    "VolumeX": "volume-x",
    "Cpu": "cpu",
    "Clock": "clock",
    "Plus": "plus",
    "ArrowUp": "arrow-up",
    "ArrowDown": "arrow-down",
    "Trash2": "trash-2",
    "Square": "square",
    "FileText": "file-text",
    "ExternalLink": "external-link",
    "LogOut": "log-out",
    "Minus": "minus",
}

# Icons above 24 px use a lighter stroke so they keep the same visual weight.
LARGE_ICON_PX = 24


def stroke_width(size: float) -> float:
    return 1.5 if size > LARGE_ICON_PX else 2.0


@cache
def _svg_source(name: IconName) -> str:
    return (ICON_DIR / f"{FILE_NAMES[name]}.svg").read_text(encoding="utf-8")


@cache
def _renderer(name: IconName, rgba: int, stroke: float) -> QSvgRenderer:
    color = QColor.fromRgba(rgba)
    svg = (
        _svg_source(name)
        .replace('stroke="currentColor"', f'stroke="{color.name()}"')
        .replace('stroke-width="2"', f'stroke-width="{stroke:g}"')
    )
    if color.alpha() < 255:
        svg = svg.replace("<svg", f'<svg opacity="{color.alphaF():.3f}"', 1)
    return QSvgRenderer(QByteArray(svg.encode("utf-8")))


def paint_icon(painter: QPainter, rect: QRectF, name: IconName, color: QColor) -> None:
    _renderer(name, color.rgba(), stroke_width(rect.width())).render(painter, rect)


def pixmap(name: IconName, size: int, color: QColor, device_pixel_ratio: float = 1.0) -> QPixmap:
    physical = round(size * device_pixel_ratio)
    result = QPixmap(physical, physical)
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    _renderer(name, color.rgba(), stroke_width(size)).render(
        painter, QRectF(0, 0, physical, physical)
    )
    painter.end()
    result.setDevicePixelRatio(device_pixel_ratio)
    return result


def icon(name: IconName, color: QColor, size: int = 16) -> QIcon:
    result = QIcon()
    for ratio in (1.0, 1.25, 1.5, 2.0):
        result.addPixmap(pixmap(name, size, color, ratio))
    return result


# App icon: an ink tile cut by the red "/" of the name, a dot for sound and a square for
# picture. Geometry on a 32-unit grid; the small variant moves the shapes for 16 px clarity.
APP_INK = QColor("#201e1d")
APP_RED = QColor("#ec3013")
APP_PAPER = QColor("#f3f2f2")


def paint_app_icon(painter: QPainter, rect: QRectF) -> None:
    size = rect.width()
    scale = size / 32
    radius = 4 if size <= 16 else 5 if size <= 32 else 6
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.translate(rect.topLeft())
    painter.scale(scale, scale)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(APP_INK)
    painter.drawRoundedRect(QRectF(0, 0, 32, 32), radius, radius)
    painter.setBrush(APP_RED)
    painter.drawPolygon(
        QPolygonF([QPointF(20, 3), QPointF(27, 3), QPointF(12, 29), QPointF(5, 29)])
    )
    painter.setBrush(APP_PAPER)
    if size >= LARGE_ICON_PX:
        painter.drawEllipse(QPointF(8.5, 9.5), 3.5, 3.5)
        painter.drawRect(QRectF(20, 19.5, 7, 7))
    else:
        painter.drawEllipse(QPointF(8, 9), 3, 3)
        painter.drawRect(QRectF(20, 20, 7, 7))
    painter.restore()


def app_icon() -> QIcon:
    result = QIcon()
    for size in (16, 20, 24, 32, 40, 48, 64, 256):
        image = QPixmap(QSize(size, size))
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        paint_app_icon(painter, QRectF(0, 0, size, size))
        painter.end()
        result.addPixmap(image)
    return result
