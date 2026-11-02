"""Shared focus ring: a 2 px accent outline offset 1 px from the focused control.

Style sheets cannot offset an outline, so one ring widget per window is painted above the
focused control. Like CSS ``:focus-visible`` it shows after keyboard interaction and hides
after a mouse press. Text fields and combo boxes draw their own accent border instead.
"""

from __future__ import annotations

import shiboken6
from PySide6.QtCore import QEvent, QObject, QRect, QRectF, Qt, Slot
from PySide6.QtGui import QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
    QWidget,
)

from radio_video.ui import theme

RING_WIDTH = 2
RING_OFFSET = 1
MARGIN = RING_WIDTH + RING_OFFSET

# Widgets may set this property to the corner radius of their own frame (default 4 px).
RADIUS_PROPERTY = "focusRadius"
# Widgets that draw their own focus indication set this property to True.
OWN_FOCUS_PROPERTY = "ownFocusStyle"

_OWN_FOCUS_TYPES = (QLineEdit, QAbstractSpinBox, QPlainTextEdit, QTextEdit, QComboBox)

_TRACKED_EVENTS = {
    QEvent.Type.Move,
    QEvent.Type.Resize,
    QEvent.Type.Show,
    QEvent.Type.Hide,
    QEvent.Type.ParentChange,
}
_KEYBOARD_EVENTS = {QEvent.Type.KeyPress, QEvent.Type.ShortcutOverride}
_POINTER_EVENTS = {
    QEvent.Type.MouseButtonPress,
    QEvent.Type.MouseButtonDblClick,
    QEvent.Type.TouchBegin,
}


def wants_ring(widget: QWidget | None) -> bool:
    if widget is None or widget.isWindow() or not widget.isVisible():
        return False
    if widget.property(OWN_FOCUS_PROPERTY):
        return False
    if isinstance(widget, _OWN_FOCUS_TYPES):
        return False
    # The viewport of a scroll area focuses its owner; ring the owner.
    return widget.focusPolicy() != Qt.FocusPolicy.NoFocus


class _Ring(QWidget):
    def __init__(self, host: QWidget) -> None:
        super().__init__(host)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.radius = 4.0
        self.clip = QRect()
        self.hide()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.clip.isNull():
            painter.setClipRect(self.clip)
        pen = QPen(theme.palette().focus, RING_WIDTH)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        half = RING_WIDTH / 2
        rect = QRectF(self.rect()).adjusted(half, half, -half, -half)
        radius = self.radius + RING_OFFSET + half
        painter.drawRoundedRect(rect, radius, radius)


class FocusRing(QObject):
    """Install once per application with :meth:`install`."""

    _instance: FocusRing | None = None

    def __init__(self, app: QApplication) -> None:
        super().__init__(app)
        self._keyboard = False
        self._target: QWidget | None = None
        self._watched: list[QWidget] = []
        self._rings: dict[int, _Ring] = {}
        app.installEventFilter(self)
        app.focusChanged.connect(self._on_focus_changed)
        theme.current().changed.connect(self._repaint)

    @classmethod
    def install(cls, app: QApplication) -> FocusRing:
        if cls._instance is None:
            cls._instance = cls(app)
        return cls._instance

    @property
    def keyboard_mode(self) -> bool:
        return self._keyboard

    @property
    def target(self) -> QWidget | None:
        return self._target if self._is_showing() else None

    def ring_geometry(self) -> QRect | None:
        ring = self._current_ring()
        return ring.geometry() if ring is not None and ring.isVisible() else None

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        kind = event.type()
        if kind in _KEYBOARD_EVENTS:
            if not self._keyboard:
                self._keyboard = True
                self._update()
        elif kind in _POINTER_EVENTS:
            if self._keyboard:
                self._keyboard = False
                self._update()
        elif kind in _TRACKED_EVENTS and watched in self._watched:
            self._update()
        return False

    @Slot(QWidget, QWidget)
    def _on_focus_changed(self, _old: QWidget | None, new: QWidget | None) -> None:
        self._set_target(new if wants_ring(new) else None)

    def _set_target(self, widget: QWidget | None) -> None:
        for watched in self._watched:
            if shiboken6.isValid(watched):
                watched.removeEventFilter(self)
        self._watched = []
        self._target = widget
        if widget is not None:
            current: QWidget | None = widget
            while current is not None:
                self._watched.append(current)
                current.installEventFilter(self)
                if current.isWindow():
                    break
                current = current.parentWidget()
        self._update()

    def _is_showing(self) -> bool:
        target = self._target
        return (
            self._keyboard
            and target is not None
            and target.isVisible()
            and target.isEnabled()
            and target.hasFocus()
        )

    def _current_ring(self) -> _Ring | None:
        if self._target is None:
            return None
        return self._rings.get(id(self._target.window()))

    def _ring_for(self, window: QWidget) -> _Ring:
        ring = self._rings.get(id(window))
        if ring is None:
            ring = _Ring(window)
            self._rings[id(window)] = ring
            window.destroyed.connect(lambda: self._rings.pop(id(window), None))
        return ring

    def _update(self) -> None:
        for ring in self._rings.values():
            ring.hide()
        target = self._target
        if target is None or not self._is_showing():
            return
        window = target.window()
        ring = self._ring_for(window)
        top_left = target.mapTo(window, target.rect().topLeft())
        geometry = QRect(top_left, target.size()).adjusted(-MARGIN, -MARGIN, MARGIN, MARGIN)
        radius = target.property(RADIUS_PROPERTY)
        ring.radius = float(radius) if isinstance(radius, (int, float)) else 4.0
        ring.clip = self._visible_clip(target, window, geometry)
        ring.setGeometry(geometry)
        ring.raise_()
        ring.show()
        ring.update()

    @staticmethod
    def _visible_clip(target: QWidget, window: QWidget, geometry: QRect) -> QRect:
        """Clip to scroll area viewports, like CSS overflow clips an outline."""
        clip = QRect(geometry)
        parent = target.parentWidget()
        while parent is not None and parent is not window:
            if isinstance(parent, QAbstractScrollArea):
                viewport = parent.viewport()
                origin = viewport.mapTo(window, viewport.rect().topLeft())
                clip = clip.intersected(QRect(origin, viewport.size()))
            parent = parent.parentWidget()
        if clip == geometry:
            return QRect()
        return clip.translated(-geometry.topLeft())

    @Slot()
    def _repaint(self) -> None:
        for ring in self._rings.values():
            ring.update()
