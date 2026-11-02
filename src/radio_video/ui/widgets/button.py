"""Push buttons: labels flush left, optional icon, shortcut hint pushed to the right edge."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPaintEvent
from PySide6.QtWidgets import QAbstractButton, QPushButton, QSizePolicy, QWidget

from radio_video.ui import icons, theme
from radio_video.ui.icons import IconName
from radio_video.ui.theme import fonts
from radio_video.ui.theme.tokens import Palette
from radio_video.ui.widgets.painting import (
    antialiased,
    elide,
    fill_rounded,
    follow_theme,
    text_width,
    with_alpha,
)


class ButtonKind(Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    SUBTLE = "subtle"
    DANGER = "danger"


@dataclass(frozen=True)
class _Metrics:
    height: int
    padding: int
    font_px: int


class ButtonSize(Enum):
    SMALL = _Metrics(28, 10, 13)
    MEDIUM = _Metrics(32, 12, 14)
    LARGE = _Metrics(40, 16, 15)


ICON_PX = 16
GAP = 8
SHORTCUT_GAP = 16
SHORTCUT_PX = 12
RADIUS = 4


@dataclass(frozen=True)
class ButtonColors:
    fill: QColor | None
    border: QColor | None
    text: QColor
    border_width: float = 1.0


def button_colors(
    p: Palette, kind: ButtonKind, *, enabled: bool, hovered: bool, pressed: bool
) -> ButtonColors:
    if not enabled:
        fill = None if kind is ButtonKind.SUBTLE else p.sunken
        return ButtonColors(fill, None, p.text_dis)
    if kind is ButtonKind.PRIMARY:
        fill = p.accent_press if pressed else p.accent_hover if hovered else p.accent
        return ButtonColors(fill, None, p.on_accent)
    if kind is ButtonKind.SUBTLE:
        fill = p.press if pressed else p.hover if hovered else None
        return ButtonColors(fill, None, p.text)
    if kind is ButtonKind.DANGER:
        fill = p.danger_tint if pressed or hovered else p.raised
        return ButtonColors(fill, p.danger, p.danger, 2.0 if pressed else 1.0)
    fill = p.raised_press if pressed else p.raised_hover if hovered else p.raised
    return ButtonColors(fill, p.border_ctl, p.text)


class Button(QPushButton):
    def __init__(
        self,
        text: str = "",
        kind: ButtonKind = ButtonKind.SECONDARY,
        *,
        icon: IconName | None = None,
        shortcut_hint: str | None = None,
        size: ButtonSize = ButtonSize.MEDIUM,
        block: bool = False,
        icon_only: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self._kind = kind
        self._icon_name = icon
        self._shortcut_hint = shortcut_hint
        self._size = size
        self._icon_only = icon_only
        self.setAutoDefault(False)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setProperty("focusRadius", RADIUS)
        self._apply_font()
        horizontal = QSizePolicy.Policy.Expanding if block else QSizePolicy.Policy.Fixed
        self.setSizePolicy(horizontal, QSizePolicy.Policy.Fixed)
        follow_theme(self)
        if icon_only and text:
            self.setAccessibleName(text)
            self.setToolTip(self.toolTip() or text)
        if shortcut_hint:
            self.setAccessibleDescription(shortcut_hint)

    @property
    def kind(self) -> ButtonKind:
        return self._kind

    def set_kind(self, kind: ButtonKind) -> None:
        self._kind = kind
        self.update()

    def icon_name(self) -> IconName | None:
        return self._icon_name

    def set_icon_name(self, name: IconName | None) -> None:
        self._icon_name = name
        self.updateGeometry()
        self.update()

    def shortcut_hint(self) -> str | None:
        return self._shortcut_hint

    def set_shortcut_hint(self, hint: str | None) -> None:
        self._shortcut_hint = hint
        self.setAccessibleDescription(hint or "")
        self.updateGeometry()
        self.update()

    def _apply_font(self) -> None:
        self.setFont(fonts.make_font(self._size.value.font_px, QFont.Weight.DemiBold))

    def _shortcut_font(self) -> QFont:
        return fonts.make_font(SHORTCUT_PX)

    def _label_text(self) -> str:
        return "" if self._icon_only else self.text()

    def sizeHint(self) -> QSize:  # noqa: N802
        metrics = self._size.value
        if self._icon_only:
            return QSize(metrics.height, metrics.height)
        width = metrics.padding * 2 + text_width(self.font(), self.text())
        if self._icon_name:
            width += ICON_PX + (GAP if self.text() else 0)
        if self._shortcut_hint:
            width += SHORTCUT_GAP + text_width(self._shortcut_font(), self._shortcut_hint)
        return QSize(width, metrics.height)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        metrics = self._size.value
        if self._icon_only:
            return self.sizeHint()
        width = metrics.padding * 2 + text_width(self.font(), "M…")
        if self._icon_name:
            width += ICON_PX + GAP
        return QSize(width, metrics.height)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        metrics = self._size.value
        colors = button_colors(
            theme.palette(),
            self._kind,
            enabled=self.isEnabled(),
            hovered=self.underMouse() or bool(self.property("demoHover")),
            pressed=self.isDown() or (self.isCheckable() and self.isChecked()),
        )
        rect = QRectF(self.rect())
        fill_rounded(painter, rect, RADIUS, colors.fill, colors.border, colors.border_width)

        if self._icon_only:
            if self._icon_name:
                icon_rect = QRectF(0, 0, ICON_PX, ICON_PX)
                icon_rect.moveCenter(rect.center())
                icons.paint_icon(painter, icon_rect, self._icon_name, colors.text)
            return

        x = float(metrics.padding)
        right = rect.width() - metrics.padding
        if self._icon_name:
            icons.paint_icon(
                painter,
                QRectF(x, (rect.height() - ICON_PX) / 2, ICON_PX, ICON_PX),
                self._icon_name,
                colors.text,
            )
            x += ICON_PX + GAP
        if self._shortcut_hint:
            hint_font = self._shortcut_font()
            hint_width = text_width(hint_font, self._shortcut_hint)
            hint_room = right - x - text_width(self.font(), "M…")
            if hint_width + SHORTCUT_GAP <= hint_room:
                painter.setFont(hint_font)
                painter.setPen(with_alpha(colors.text, 0.85))
                painter.drawText(
                    QRectF(right - hint_width, 0, hint_width, rect.height()),
                    int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                    self._shortcut_hint,
                )
                right -= hint_width + SHORTCUT_GAP
        painter.setFont(self.font())
        painter.setPen(colors.text)
        text = elide(self.font(), self._label_text(), Qt.TextElideMode.ElideRight, int(right - x))
        painter.drawText(
            QRectF(x, 0, right - x, rect.height()),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            text,
        )


class Expander(QAbstractButton):
    """Disclosure toggle, such as "Technical details"."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setText(text)
        self.setCheckable(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFont(fonts.make_font(13, QFont.Weight.DemiBold))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.toggled.connect(
            lambda checked: self.setAccessibleDescription("expanded" if checked else "collapsed")
        )
        follow_theme(self)

    def sizeHint(self) -> QSize:  # noqa: N802
        width = ICON_PX + 6 + text_width(self.font(), self.text())
        return QSize(width, 28)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        p = theme.palette()
        color = p.text if self.isEnabled() else p.text_dis
        name: IconName = "ChevronDown" if self.isChecked() else "ChevronRight"
        icons.paint_icon(
            painter, QRectF(0, (self.height() - ICON_PX) / 2, ICON_PX, ICON_PX), name, color
        )
        painter.setPen(color)
        painter.setFont(self.font())
        painter.drawText(
            QRectF(ICON_PX + 6, 0, self.width() - ICON_PX - 6, self.height()),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            self.text(),
        )
