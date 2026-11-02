"""Status badges and count chips."""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent
from PySide6.QtWidgets import QSizePolicy, QWidget

from radio_video.ui import icons, theme
from radio_video.ui.icons import IconName
from radio_video.ui.theme import fonts
from radio_video.ui.theme.tokens import Palette
from radio_video.ui.widgets.painting import antialiased, fill_rounded, follow_theme, text_width

ICON_PX = 12
GAP = 4
RADIUS = 2


class BadgeTone(Enum):
    NEUTRAL = "neutral"
    ACCENT = "accent"
    SUCCESS = "success"
    WARNING = "warning"
    DANGER = "danger"
    INK = "ink"
    PLANNED = "planned"


def badge_colors(p: Palette, tone: BadgeTone) -> tuple[QColor | None, QColor]:
    return {
        BadgeTone.NEUTRAL: (p.sunken, p.text_2),
        BadgeTone.ACCENT: (p.accent_tint, p.accent_text),
        BadgeTone.SUCCESS: (p.success_tint, p.success),
        BadgeTone.WARNING: (p.warning_tint, p.warning),
        BadgeTone.DANGER: (p.danger_tint, p.danger),
        BadgeTone.INK: (p.sel, p.on_sel),
        BadgeTone.PLANNED: (None, p.text_2),
    }[tone]


def badge_font(tone: BadgeTone) -> QFont:
    if tone is BadgeTone.PLANNED:
        font = fonts.make_font(10, QFont.Weight.DemiBold)
        font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 106)
        font.setCapitalization(QFont.Capitalization.AllUppercase)
        return font
    return fonts.make_font(12, QFont.Weight.DemiBold)


def badge_size(text: str, tone: BadgeTone, icon: IconName | None = None) -> QSize:
    planned = tone is BadgeTone.PLANNED
    padding = 5 if planned else 6
    width = padding * 2 + text_width(badge_font(tone), text)
    if icon:
        width += ICON_PX + GAP
    return QSize(width, 18 if planned else 20)


def paint_badge(
    painter: QPainter,
    rect: QRectF,
    text: str,
    tone: BadgeTone,
    icon: IconName | None = None,
    color_override: QColor | None = None,
) -> None:
    """Paint a badge into ``rect``; also used inside segments, tabs and table cells."""
    fill, color = badge_colors(theme.palette(), tone)
    if color_override is not None:
        color = color_override
    planned = tone is BadgeTone.PLANNED
    # The planned badge is outlined; on a selected control it takes the control's text colour.
    border = (color_override or theme.palette().border_ctl) if planned else None
    fill_rounded(painter, rect, RADIUS, fill, border, dashed=planned)
    x = rect.left() + (5 if planned else 6)
    if icon:
        icons.paint_icon(
            painter,
            QRectF(x, rect.top() + (rect.height() - ICON_PX) / 2, ICON_PX, ICON_PX),
            icon,
            color,
        )
        x += ICON_PX + GAP
    painter.save()
    painter.setFont(badge_font(tone))
    painter.setPen(color)
    painter.drawText(
        QRectF(x, rect.top(), rect.right() - x, rect.height()),
        int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
        text,
    )
    painter.restore()


class Badge(QWidget):
    def __init__(
        self,
        text: str,
        tone: BadgeTone = BadgeTone.NEUTRAL,
        icon: IconName | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._tone = tone
        self._icon = icon
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAccessibleName(text)
        follow_theme(self)

    def set_badge(self, text: str, tone: BadgeTone, icon: IconName | None = None) -> None:
        self._text, self._tone, self._icon = text, tone, icon
        self.setAccessibleName(text)
        self.updateGeometry()
        self.update()

    def text(self) -> str:
        return self._text

    @property
    def tone(self) -> BadgeTone:
        return self._tone

    def sizeHint(self) -> QSize:  # noqa: N802
        return badge_size(self._text, self._tone, self._icon)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        paint_badge(painter, QRectF(self.rect()), self._text, self._tone, self._icon)
