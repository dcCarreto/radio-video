"""Text labels in the design's type scale, plus an eliding label for names and paths."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPaintEvent
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from radio_video.ui import theme
from radio_video.ui.theme import fonts
from radio_video.ui.theme.fonts import TextStyle
from radio_video.ui.widgets.painting import antialiased, elide, follow_theme, text_width

# Tones map to QLabel[tone=...] rules in the style sheet and to palette colours when painted.
TONE_COLORS = {
    None: "text",
    "secondary": "text_2",
    "disabled": "text_dis",
    "accent": "accent_text",
    "success": "success",
    "warning": "warning",
    "danger": "danger",
}


def repolish(widget: QWidget) -> None:
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def set_tone(label: QLabel, tone: str | None) -> None:
    label.setProperty("tone", tone or "")
    repolish(label)


def label(
    text: str = "",
    style: TextStyle = TextStyle.BODY,
    tone: str | None = None,
    *,
    wrap: bool = False,
    selectable: bool = False,
    parent: QWidget | None = None,
) -> QLabel:
    result = QLabel(text, parent)
    fonts.apply(result, style)
    if tone:
        result.setProperty("tone", tone)
    if wrap:
        result.setWordWrap(True)
        result.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
    if selectable:
        result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return result


def kicker(text: str, tone: str | None = "secondary", parent: QWidget | None = None) -> QLabel:
    return label(text, TextStyle.KICKER, tone, parent=parent)


class ElidedLabel(QWidget):
    """Single-line text that elides to fit; the full text is always in the tooltip.

    File names elide in the middle, paths on the left so the folder name stays visible.
    """

    def __init__(
        self,
        text: str = "",
        style: TextStyle = TextStyle.BODY,
        *,
        mode: Qt.TextElideMode = Qt.TextElideMode.ElideRight,
        tone: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._text = ""
        self._mode = mode
        self._tone = tone
        self._style = style
        fonts.apply(self, style)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        follow_theme(self)
        self.setText(text)

    def text(self) -> str:
        return self._text

    def setText(self, text: str) -> None:  # noqa: N802
        self._text = text
        self.setToolTip(text)
        self.setAccessibleName(text)
        self.updateGeometry()
        self.update()

    def set_tone(self, tone: str | None) -> None:
        self._tone = tone
        self.update()

    def elided_text(self) -> str:
        return elide(self.font(), self._text, self._mode, self.width())

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(text_width(self.font(), self._text), fonts.line_height(self._style))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(text_width(self.font(), "…") * 4, self.sizeHint().height())

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        color_name = TONE_COLORS.get(self._tone, "text")
        palette = theme.palette()
        painter.setPen(palette.color(color_name) if self.isEnabled() else palette.text_dis)
        painter.setFont(self.font())
        painter.drawText(
            self.rect(),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            self.elided_text(),
        )
