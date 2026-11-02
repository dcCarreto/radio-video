"""Check boxes, radio buttons and switches with ink-coloured selection."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, QSize, Qt
from PySide6.QtGui import QPaintEvent
from PySide6.QtWidgets import (
    QAbstractButton,
    QCheckBox,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from radio_video.ui import icons, theme
from radio_video.ui.theme import fonts
from radio_video.ui.theme.fonts import TextStyle
from radio_video.ui.widgets.labels import label
from radio_video.ui.widgets.painting import antialiased, fill_rounded, follow_theme, text_width

BOX = 18
GAP = 10


class _Indicator:
    @staticmethod
    def paint(button: QAbstractButton, round_: bool) -> None:
        painter = antialiased(button)
        p = theme.palette()
        if not button.isEnabled():
            painter.setOpacity(0.5)
        box = QRectF(0, (button.height() - BOX) / 2 if not button.text() else 1, BOX, BOX)
        checked = button.isChecked()
        if round_:
            fill_rounded(painter, box, BOX / 2, p.raised, p.border_ctl)
            if checked:
                dot = box.adjusted(4, 4, -4, -4)
                fill_rounded(painter, dot, dot.width() / 2, p.sel)
        else:
            if checked:
                fill_rounded(painter, box, 3, p.sel)
                check = QRectF(0, 0, 14, 14)
                check.moveCenter(box.center())
                icons.paint_icon(painter, check, "Check", p.on_sel)
            else:
                fill_rounded(painter, box, 3, p.raised, p.border_ctl)
        if button.text():
            painter.setFont(button.font())
            painter.setPen(p.text)
            painter.drawText(
                QRectF(BOX + GAP, 0, button.width() - BOX - GAP, 20),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                button.text(),
            )

    @staticmethod
    def size(button: QAbstractButton) -> QSize:
        if not button.text():
            return QSize(BOX, BOX)
        return QSize(BOX + GAP + text_width(button.font(), button.text()), 20)


class CheckBox(QCheckBox):
    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setFont(fonts.font(TextStyle.BODY))
        self.setProperty("focusRadius", 3)
        follow_theme(self)

    def sizeHint(self) -> QSize:  # noqa: N802
        return _Indicator.size(self)

    def hitButton(self, pos: QPoint) -> bool:  # noqa: N802
        return self.rect().contains(pos)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        _Indicator.paint(self, round_=False)


class RadioButton(QRadioButton):
    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setFont(fonts.font(TextStyle.BODY))
        self.setProperty("focusRadius", 9)
        follow_theme(self)

    def sizeHint(self) -> QSize:  # noqa: N802
        return _Indicator.size(self)

    def hitButton(self, pos: QPoint) -> bool:  # noqa: N802
        return self.rect().contains(pos)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        _Indicator.paint(self, round_=True)


class Switch(QAbstractButton):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(40, 20)
        self.setProperty("focusRadius", 10)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        follow_theme(self)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        p = theme.palette()
        on = self.isChecked()
        rect = QRectF(self.rect())
        fill_rounded(painter, rect, 10, p.sel if on else p.raised, p.sel if on else p.border_ctl)
        knob = QRectF(23 if on else 4, 4, 12, 12)
        fill_rounded(painter, knob, 6, p.on_sel if on else p.text_2)


class LabeledCheck(QWidget):
    """Check box or radio button with a help line under its label."""

    def __init__(
        self,
        button: CheckBox | RadioButton,
        help_text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.button = button
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(button)
        self.help: QWidget | None = None
        if help_text:
            help_label = label(help_text, TextStyle.CAPTION, "secondary", wrap=True)
            help_label.setContentsMargins(BOX + GAP, 0, 0, 0)
            layout.addWidget(help_label)
            button.setAccessibleDescription(help_text)
            self.help = help_label
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
