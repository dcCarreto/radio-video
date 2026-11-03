from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLineEdit, QPushButton, QWidget
from pytestqt.qtbot import QtBot

from radio_video.ui.widgets.focus_ring import MARGIN, FocusRing


def _window(qtbot: QtBot) -> tuple[QWidget, QPushButton, QPushButton, QLineEdit]:
    window = QWidget()
    layout = QHBoxLayout(window)
    first, second = QPushButton("First"), QPushButton("Second")
    edit = QLineEdit()
    for widget in (first, second, edit):
        widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout.addWidget(widget)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    window.activateWindow()
    first.setFocus(Qt.FocusReason.OtherFocusReason)
    return window, first, second, edit


def test_ring_follows_keyboard_focus(qapp: QApplication, qtbot: QtBot) -> None:
    ring = FocusRing.install(qapp)
    _, first, second, _edit = _window(qtbot)

    qtbot.keyClick(first, Qt.Key.Key_Tab)
    qtbot.waitUntil(lambda: second.hasFocus())

    assert ring.keyboard_mode
    assert ring.target is second
    expected = QRect(second.mapTo(second.window(), second.rect().topLeft()), second.size())
    assert ring.ring_geometry() == expected.adjusted(-MARGIN, -MARGIN, MARGIN, MARGIN)


def test_mouse_press_hides_ring(qapp: QApplication, qtbot: QtBot) -> None:
    ring = FocusRing.install(qapp)
    _, first, second, _edit = _window(qtbot)
    qtbot.keyClick(first, Qt.Key.Key_Tab)
    qtbot.waitUntil(lambda: second.hasFocus())

    qtbot.mouseClick(first, Qt.MouseButton.LeftButton)

    assert not ring.keyboard_mode
    assert ring.ring_geometry() is None


def test_text_fields_draw_their_own_focus(qapp: QApplication, qtbot: QtBot) -> None:
    ring = FocusRing.install(qapp)
    _, first, second, edit = _window(qtbot)
    qtbot.keyClick(first, Qt.Key.Key_Tab)
    qtbot.keyClick(second, Qt.Key.Key_Tab)
    qtbot.waitUntil(lambda: edit.hasFocus())

    assert ring.target is None
    assert ring.ring_geometry() is None
