"""Helpers for stacked widgets whose pages hold wrapped text."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QSizePolicy, QStackedWidget


def fit_stack_height(stack: QStackedWidget) -> None:
    """Make ``stack`` exactly as tall as its current page at its current width.

    A stacked widget otherwise takes the height of its tallest page and ignores
    height-for-width, so wrapped text gets too much or too little room.
    """
    current = stack.currentWidget()
    for index in range(stack.count()):
        page = stack.widget(index)
        if page is not None:
            vertical = (
                QSizePolicy.Policy.Preferred if page is current else QSizePolicy.Policy.Ignored
            )
            page.setSizePolicy(QSizePolicy.Policy.Preferred, vertical)
    if current is None:
        return
    width = stack.width()
    layout = current.layout()
    if isinstance(current, QLabel) and current.wordWrap() and width > 0:
        height = current.heightForWidth(width)
    elif layout is not None and layout.hasHeightForWidth() and width > 0:
        height = layout.heightForWidth(width)
    else:
        height = current.sizeHint().height()
    stack.setFixedHeight(max(height, 0))
