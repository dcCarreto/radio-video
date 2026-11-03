"""Dialog frame: icon tile and title, a body, and a footer bar with right-aligned buttons."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPaintEvent, QShowEvent
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QVBoxLayout, QWidget

from radio_video.ui import icons, theme
from radio_video.ui import strings as s
from radio_video.ui.icons import IconName
from radio_video.ui.native.dwm import style_title_bar
from radio_video.ui.strings import tr
from radio_video.ui.theme.fonts import TextStyle
from radio_video.ui.widgets.button import Button
from radio_video.ui.widgets.labels import label
from radio_video.ui.widgets.painting import antialiased, fill_rounded, follow_theme

FOOTER_BUTTON_MIN = 120
TONES = {
    None: ("sunken", "text"),
    "warning": ("warning_tint", "warning"),
    "danger": ("danger_tint", "danger"),
}


class IconTile(QWidget):
    def __init__(
        self, name: IconName, tone: str | None = None, size: int = 36, icon_size: int = 20
    ) -> None:
        super().__init__()
        self._name, self._tone, self._icon_size = name, tone, icon_size
        self.setFixedSize(size, size)
        follow_theme(self)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        fill, color = TONES[self._tone]
        p = theme.palette()
        fill_rounded(painter, QRectF(self.rect()), 4, p.color(fill))
        rect = QRectF(0, 0, self._icon_size, self._icon_size)
        rect.moveCenter(QRectF(self.rect()).center())
        icons.paint_icon(painter, rect, self._name, p.color(color))


class _Footer(QFrame):
    def __init__(self) -> None:
        super().__init__()
        follow_theme(self)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        p = theme.palette()
        painter.fillRect(self.rect(), p.surface)
        painter.fillRect(QRectF(0, 0, self.width(), 1), p.border)


class Dialog(QDialog):
    def __init__(
        self,
        title: str = "",
        *,
        icon: IconName | None = None,
        tone: str | None = None,
        width: int = 480,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr(s.APP_NAME))
        self.setWindowIcon(icons.app_icon())
        self.setFixedWidth(width)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        self.body = QVBoxLayout()
        self.body.setContentsMargins(24, 20, 24, 24)
        self.body.setSpacing(12)
        if title or icon:
            header = QHBoxLayout()
            header.setSpacing(12)
            if icon:
                header.addWidget(IconTile(icon, tone))
            self.title = label(title, TextStyle.TITLE, wrap=True)
            header.addWidget(self.title, 1)
            self.body.addLayout(header)
            self.setAccessibleName(title)

        self.footer = _Footer()
        self.buttons = QHBoxLayout(self.footer)
        self.buttons.setContentsMargins(24, 16, 24, 16)
        self.buttons.setSpacing(8)
        self.buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(self.body)
        layout.addWidget(self.footer)
        theme.current().changed.connect(self._on_theme_changed)

    def add_button(self, button: Button, *, leading: bool = False) -> Button:
        button.setMinimumWidth(FOOTER_BUTTON_MIN)
        if leading:
            self.buttons.insertWidget(0, button)
            self.buttons.insertStretch(1, 0)
        else:
            self.buttons.addWidget(button)
        return button

    def fit_height(self) -> None:
        """Size to the content at the fixed width; wrapped text needs height-for-width."""
        layout = self.layout()
        if layout is not None and layout.hasHeightForWidth():
            self.setFixedHeight(layout.heightForWidth(self.width()))
        else:
            self.adjustSize()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        self.fit_height()
        super().showEvent(event)
        self._style_title_bar()

    def _on_theme_changed(self, _palette: object) -> None:
        self._style_title_bar()

    def _style_title_bar(self) -> None:
        if self.isVisible():
            p = theme.palette()
            style_title_bar(self, dark=p.is_dark, caption=p.raised, text=p.text)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        painter.fillRect(self.rect(), theme.palette().raised)
