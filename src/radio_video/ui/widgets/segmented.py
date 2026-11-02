"""Segmented control: exclusive options in one bordered row, each with an optional second line.

Segments are radio buttons, so screen readers announce them as a radio group and arrow keys
move the selection. Only the selected segment is in the Tab chain.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QFont, QKeyEvent, QPaintEvent
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QRadioButton, QSizePolicy, QWidget

from radio_video.ui import theme
from radio_video.ui.theme import fonts
from radio_video.ui.widgets.badge import BadgeTone, badge_size, paint_badge
from radio_video.ui.widgets.painting import (
    antialiased,
    elide,
    fill_rounded,
    follow_theme,
    rounded_path,
    text_width,
    with_alpha,
)

RADIUS = 4
PADDING_X = 12
PADDING_Y = 5
MIN_HEIGHT = 32
BADGE_GAP = 6
DISABLED_OPACITY = 0.5


@dataclass(frozen=True)
class SegmentOption:
    value: str
    label: str
    sublabel: str | None = None
    tooltip: str | None = None
    planned: bool = False
    planned_text: str = "Planned"


class SegmentButton(QRadioButton):
    def __init__(self, option: SegmentOption, parent: QWidget | None = None) -> None:
        super().__init__(option.label, parent)
        self.option = option
        self.first = False
        self.last = False
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setProperty("focusRadius", 2)
        self.setFont(fonts.make_font(14, QFont.Weight.DemiBold))
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        if option.tooltip:
            self.setToolTip(option.tooltip)
        description = " ".join(
            filter(None, [option.sublabel, option.planned_text if option.planned else None])
        )
        if description:
            self.setAccessibleDescription(description)
        follow_theme(self)

    def _sub_font(self) -> QFont:
        return fonts.make_font(12)

    def sizeHint(self) -> QSize:  # noqa: N802
        main = text_width(self.font(), self.option.label)
        if self.option.planned:
            main += BADGE_GAP + badge_size(self.option.planned_text, BadgeTone.PLANNED).width()
        width = main
        height = 20
        if self.option.sublabel:
            width = max(width, text_width(self._sub_font(), self.option.sublabel))
            height += 16
        return QSize(width + PADDING_X * 2, max(MIN_HEIGHT, height + PADDING_Y * 2))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(PADDING_X * 2 + 24, self.sizeHint().height())

    def hitButton(self, pos: QPoint) -> bool:  # noqa: N802
        return self.rect().contains(pos)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        if not self.isEnabled():
            painter.setOpacity(DISABLED_OPACITY)
        p = theme.palette()
        rect = QRectF(self.rect())
        inner = RADIUS - 1
        radii = (
            inner if self.first else 0,
            inner if self.last else 0,
            inner if self.last else 0,
            inner if self.first else 0,
        )
        fill = p.sel if self.isChecked() else p.raised_hover if self.underMouse() else None
        if fill is not None:
            painter.fillPath(rounded_path(rect, radii), fill)
        if not self.first:
            painter.fillRect(QRectF(0, 0, 1, rect.height()), p.border_ctl)

        color = p.on_sel if self.isChecked() else p.text
        left = 1 if not self.first else 0
        x = PADDING_X + left
        width = rect.width() - PADDING_X * 2 - left
        main_height = 20
        total = main_height + (16 if self.option.sublabel else 0)
        top = (rect.height() - total) / 2

        painter.setFont(self.font())
        painter.setPen(color)
        badge_width = (
            badge_size(self.option.planned_text, BadgeTone.PLANNED).width()
            if self.option.planned
            else 0
        )
        label_room = width - (badge_width + BADGE_GAP if badge_width else 0)
        label = elide(self.font(), self.option.label, Qt.TextElideMode.ElideRight, label_room)
        painter.drawText(
            QRectF(x, top, label_room, main_height),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            label,
        )
        if self.option.planned:
            badge_x = x + text_width(self.font(), label) + BADGE_GAP
            paint_badge(
                painter,
                QRectF(badge_x, top + 1, badge_width, 18),
                self.option.planned_text,
                BadgeTone.PLANNED,
                color_override=color if self.isChecked() else None,
            )
        if self.option.sublabel:
            sub_font = self._sub_font()
            painter.setFont(sub_font)
            painter.setPen(with_alpha(color, 0.85))
            painter.drawText(
                QRectF(x, top + main_height, width, 16),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                elide(sub_font, self.option.sublabel, Qt.TextElideMode.ElideRight, int(width)),
            )

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        control = self.parentWidget()
        step = {
            Qt.Key.Key_Left: -1,
            Qt.Key.Key_Up: -1,
            Qt.Key.Key_Right: 1,
            Qt.Key.Key_Down: 1,
        }.get(Qt.Key(event.key()))
        if step is not None and isinstance(control, SegmentedControl):
            control.step(step)
            return
        super().keyPressEvent(event)


class SegmentedControl(QFrame):
    changed = Signal(str)

    def __init__(
        self,
        options: list[SegmentOption] | None = None,
        *,
        accessible_name: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._buttons: list[SegmentButton] = []
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._group.buttonToggled.connect(self._on_toggled)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(1, 1, 1, 1)
        self._layout.setSpacing(0)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setAccessibleName(accessible_name)
        follow_theme(self)
        if options:
            self.set_options(options)

    def set_options(self, options: list[SegmentOption]) -> None:
        current = self.value()
        for button in self._buttons:
            self._group.removeButton(button)
            button.deleteLater()
        self._buttons = []
        for index, option in enumerate(options):
            button = SegmentButton(option, self)
            button.first = index == 0
            button.last = index == len(options) - 1
            self._group.addButton(button)
            self._layout.addWidget(button, 1)
            self._buttons.append(button)
        if current is not None and any(o.value == current for o in options):
            self.set_value(current)
        self._update_focus_chain()

    def options(self) -> list[SegmentOption]:
        return [button.option for button in self._buttons]

    def buttons(self) -> list[SegmentButton]:
        return list(self._buttons)

    def value(self) -> str | None:
        checked = self._group.checkedButton()
        return checked.option.value if isinstance(checked, SegmentButton) else None

    def set_value(self, value: str) -> None:
        for button in self._buttons:
            if button.option.value == value:
                button.setChecked(True)
                break
        self._update_focus_chain()

    def step(self, delta: int) -> None:
        if not self._buttons:
            return
        values = [button.option.value for button in self._buttons]
        current = self.value()
        index = values.index(current) if current in values else 0
        target = self._buttons[max(0, min(len(values) - 1, index + delta))]
        if not target.isChecked():
            target.setChecked(True)
        target.setFocus(Qt.FocusReason.TabFocusReason)

    def _on_toggled(self, button: SegmentButton, checked: bool) -> None:
        if checked:
            self._update_focus_chain()
            self.changed.emit(button.option.value)

    def _update_focus_chain(self) -> None:
        checked = self._group.checkedButton()
        for button in self._buttons:
            in_chain = button is checked or (checked is None and button is self._buttons[0])
            button.setFocusPolicy(
                Qt.FocusPolicy.StrongFocus if in_chain else Qt.FocusPolicy.ClickFocus
            )

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        if not self.isEnabled():
            painter.setOpacity(DISABLED_OPACITY)
        p = theme.palette()
        fill_rounded(painter, QRectF(self.rect()), RADIUS, p.raised, p.border_ctl)
