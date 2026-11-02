"""Main tab strip: icon tabs, a "Planned" badge on unbuilt pages, Settings pushed right."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QFont, QKeyEvent, QPaintEvent
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QRadioButton, QSizePolicy, QWidget

from radio_video.ui import icons, theme
from radio_video.ui.icons import IconName
from radio_video.ui.theme import fonts
from radio_video.ui.widgets.badge import BadgeTone, badge_size, paint_badge
from radio_video.ui.widgets.painting import antialiased, follow_theme, text_width

HEIGHT = 44
PADDING_X = 12
GAP = 8
INDICATOR = 3


@dataclass(frozen=True)
class TabSpec:
    key: str
    label: str
    icon: IconName
    planned: bool = False
    planned_text: str = "Planned"
    trailing: bool = False


class TabButton(QRadioButton):
    def __init__(self, spec: TabSpec, parent: QWidget | None = None) -> None:
        super().__init__(spec.label, parent)
        self.spec = spec
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setFont(fonts.make_font(14, QFont.Weight.DemiBold))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setProperty("focusRadius", 2)
        if spec.planned:
            self.setAccessibleDescription(spec.planned_text)
        follow_theme(self)

    def sizeHint(self) -> QSize:  # noqa: N802
        width = PADDING_X * 2 + 16 + GAP + text_width(self.font(), self.text())
        if self.spec.planned:
            width += GAP + badge_size(self.spec.planned_text, BadgeTone.PLANNED).width()
        return QSize(width, HEIGHT - 1)

    def hitButton(self, pos: QPoint) -> bool:  # noqa: N802
        return self.rect().contains(pos)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        p = theme.palette()
        rect = QRectF(self.rect())
        active = self.isChecked()
        hovered = self.underMouse()
        if hovered:
            painter.fillRect(rect, p.hover)
        if active:
            painter.fillRect(QRectF(0, rect.height() - INDICATOR, rect.width(), INDICATOR), p.text)
        color = p.text if active or hovered else p.text_2
        x = float(PADDING_X)
        icons.paint_icon(
            painter, QRectF(x, (rect.height() - 16) / 2, 16, 16), self.spec.icon, color
        )
        x += 16 + GAP
        painter.setFont(self.font())
        painter.setPen(color)
        label_width = text_width(self.font(), self.text())
        painter.drawText(
            QRectF(x, 0, label_width + 1, rect.height()),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            self.text(),
        )
        if self.spec.planned:
            badge = badge_size(self.spec.planned_text, BadgeTone.PLANNED)
            paint_badge(
                painter,
                QRectF(
                    x + label_width + GAP,
                    (rect.height() - badge.height()) / 2,
                    badge.width(),
                    badge.height(),
                ),
                self.spec.planned_text,
                BadgeTone.PLANNED,
            )

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        strip = self.parentWidget()
        step = {Qt.Key.Key_Left: -1, Qt.Key.Key_Right: 1}.get(Qt.Key(event.key()))
        if step is not None and isinstance(strip, TabStrip):
            strip.step(step)
            return
        super().keyPressEvent(event)


class TabStrip(QWidget):
    current_changed = Signal(str)

    def __init__(self, tabs: list[TabSpec], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._buttons: list[TabButton] = []
        self._group = QButtonGroup(self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(PADDING_X, 0, PADDING_X, 1)
        layout.setSpacing(2)
        trailing_started = False
        for spec in tabs:
            if spec.trailing and not trailing_started:
                layout.addStretch(1)
                trailing_started = True
            button = TabButton(spec, self)
            self._group.addButton(button)
            layout.addWidget(button, 0, Qt.AlignmentFlag.AlignBottom)
            self._buttons.append(button)
        if not trailing_started:
            layout.addStretch(1)
        self.setFixedHeight(HEIGHT)
        self.setAccessibleName("Pages")
        self._group.buttonToggled.connect(self._on_toggled)
        follow_theme(self)
        if self._buttons:
            self._buttons[0].setChecked(True)

    def buttons(self) -> list[TabButton]:
        return list(self._buttons)

    def current(self) -> str | None:
        checked = self._group.checkedButton()
        return checked.spec.key if isinstance(checked, TabButton) else None

    def set_current(self, key: str) -> None:
        for button in self._buttons:
            if button.spec.key == key:
                button.setChecked(True)

    def step(self, delta: int) -> None:
        keys = [button.spec.key for button in self._buttons]
        current = self.current()
        index = keys.index(current) if current in keys else 0
        target = self._buttons[(index + delta) % len(keys)]
        target.setChecked(True)
        target.setFocus(Qt.FocusReason.TabFocusReason)

    def _on_toggled(self, button: TabButton, checked: bool) -> None:
        if not checked:
            return
        for other in self._buttons:
            other.setFocusPolicy(
                Qt.FocusPolicy.StrongFocus if other is button else Qt.FocusPolicy.ClickFocus
            )
        self.current_changed.emit(button.spec.key)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        p = theme.palette()
        painter.fillRect(self.rect(), p.bg)
        painter.fillRect(QRectF(0, self.height() - 1, self.width(), 1), p.border)
