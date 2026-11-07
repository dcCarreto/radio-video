"""Pieces shared by the full-page tabs: page background, header, footer and status badges."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPaintEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from radio_video.ui import strings as s
from radio_video.ui import theme
from radio_video.ui.icons import IconName
from radio_video.ui.strings import tr
from radio_video.ui.theme.fonts import TextStyle
from radio_video.ui.widgets.badge import Badge, BadgeTone
from radio_video.ui.widgets.labels import ElidedLabel, label
from radio_video.ui.widgets.painting import antialiased, follow_theme


class Page(QWidget):
    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        painter.fillRect(self.rect(), theme.palette().bg)


class PageHeader(QFrame):
    """Page title and description over a 2 px rule, with actions on the right."""

    def __init__(self, title: str, text: str, actions: list[QWidget]) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(16)
        names = QVBoxLayout()
        names.setSpacing(0)
        names.addWidget(label(title, TextStyle.TITLE_LARGE))
        names.addWidget(label(text, tone="secondary", wrap=True))
        layout.addLayout(names, 1)
        for action in actions:
            layout.addWidget(action, 0, Qt.AlignmentFlag.AlignBottom)
        follow_theme(self)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        painter.fillRect(QRectF(0, self.height() - 2, self.width(), 2), theme.palette().rule)


def page_scroll(content: QWidget) -> QScrollArea:
    content.setProperty("transparent", True)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(content)
    return scroll


def elided(text: str, style: TextStyle = TextStyle.BODY, tone: str | None = None) -> ElidedLabel:
    return ElidedLabel(text, style, mode=Qt.TextElideMode.ElideMiddle, tone=tone)


STATUS_BADGES: dict[str, tuple[BadgeTone, IconName, object]] = {
    "done": (BadgeTone.SUCCESS, "CircleCheck", s.STATUS_DONE),
    "converting": (BadgeTone.ACCENT, "LoaderCircle", s.STATUS_CONVERTING_BADGE),
    "waiting": (BadgeTone.NEUTRAL, "Clock", s.STATUS_WAITING),
    "failed": (BadgeTone.DANGER, "CircleX", s.STATUS_FAILED),
    "canceled": (BadgeTone.NEUTRAL, "Ban", s.STATUS_CANCELED),
}


def status_badge(status: str, text: object | None = None) -> Badge:
    tone, icon, default = STATUS_BADGES[status]
    return Badge(tr(text or default), tone, icon)


class FooterBand(QFrame):
    def __init__(self) -> None:
        super().__init__()
        follow_theme(self)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        p = theme.palette()
        painter.fillRect(self.rect(), p.surface)
        painter.fillRect(QRectF(0, 0, self.width(), 2), p.rule)
