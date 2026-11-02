"""Cards, rules, notes, read-only fields, code blocks and the planned banner."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QPaintEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from radio_video.ui import icons, theme
from radio_video.ui.icons import IconName
from radio_video.ui.theme import fonts
from radio_video.ui.theme.fonts import TextStyle
from radio_video.ui.widgets.badge import Badge, BadgeTone
from radio_video.ui.widgets.button import Button, ButtonKind, ButtonSize
from radio_video.ui.widgets.labels import label
from radio_video.ui.widgets.painting import antialiased, elide, fill_rounded, follow_theme
from radio_video.ui.widgets.progress import StatusIcon


class Card(QFrame):
    """Raised card: 1 px border, 6 px radius, no shadow."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("card", True)


class Rule(QFrame):
    """Structural 2 px rule, or a 1 px hairline."""

    def __init__(
        self,
        *,
        hairline: bool = False,
        vertical: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._hairline = hairline
        width = 1 if hairline else 2
        if vertical:
            self.setFixedWidth(width)
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        else:
            self.setFixedHeight(width)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        follow_theme(self)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        p = theme.palette()
        painter.fillRect(self.rect(), p.border if self._hairline else p.rule)


class Surface(QFrame):
    """Plain panel filled with a palette colour."""

    def __init__(self, color_name: str = "bg", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color_name = color_name
        follow_theme(self)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        painter.fillRect(self.rect(), theme.palette().color(self._color_name))


NOTE_TONES = {
    None: ("sunken", "text"),
    "accent": ("accent_tint", "accent_text"),
    "warning": ("warning_tint", "warning"),
    "danger": ("danger_tint", "danger"),
}


class Note(QFrame):
    """Tinted note with an icon: neutral, accent, warning or danger."""

    def __init__(
        self,
        text: str,
        icon: IconName = "Info",
        tone: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tone = tone
        self._icon_name = icon
        self.icon = StatusIcon(16)
        self.text = label(text, TextStyle.BODY, wrap=True)
        self.text.setFont(fonts.make_font(13))
        self.text.setTextFormat(Qt.TextFormat.PlainText)
        icon_column = QVBoxLayout()
        icon_column.setContentsMargins(0, 1, 0, 0)
        icon_column.addWidget(self.icon)
        icon_column.addStretch()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)
        layout.addLayout(icon_column)
        layout.addWidget(self.text, 1)
        self.set_tone(tone, icon)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        follow_theme(self)

    def set_text(self, text: str) -> None:
        self.text.setText(text)

    def set_tone(self, tone: str | None, icon: IconName | None = None) -> None:
        self._tone = tone
        if icon is not None:
            self._icon_name = icon
        self.icon.set_icon(self._icon_name, NOTE_TONES[tone][1])
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        fill_rounded(
            painter, QRectF(self.rect()), 4, theme.palette().color(NOTE_TONES[self._tone][0])
        )


class FieldBox(QWidget):
    """Read-only field showing a path with an icon, eliding on the left."""

    def __init__(
        self,
        text: str = "",
        icon: IconName | None = "Folder",
        *,
        mode: Qt.TextElideMode = Qt.TextElideMode.ElideLeft,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._icon = icon
        self._mode = mode
        self.setFixedHeight(32)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFont(fonts.font(TextStyle.BODY))
        follow_theme(self)
        self.set_text(text)

    def text(self) -> str:
        return self._text

    def set_text(self, text: str) -> None:
        self._text = text
        self.setToolTip(text)
        self.setAccessibleName(text)
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(200, 32)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(80, 32)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        p = theme.palette()
        enabled = self.isEnabled()
        fill_rounded(
            painter,
            QRectF(self.rect()),
            4,
            p.surface if enabled else p.sunken,
            p.border_ctl if enabled else p.border,
        )
        x = 10.0
        color = p.text if enabled else p.text_dis
        if self._icon:
            icons.paint_icon(painter, QRectF(x, 8, 16, 16), self._icon, color)
            x += 16 + 8
        painter.setPen(color)
        painter.setFont(self.font())
        width = self.width() - x - 10
        painter.drawText(
            QRectF(x, 0, width, self.height()),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            elide(self.font(), self._text, self._mode, int(width)),
        )


class CodeBlock(QFrame):
    """Monospaced command or value on a sunken ground, with an optional Copy button."""

    def __init__(
        self,
        text: str,
        *,
        copy_text: str | None = None,
        copy_tooltip: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.label = QLabel(text)
        fonts.apply(self.label, TextStyle.MONO)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.label.setTextFormat(Qt.TextFormat.PlainText)
        self.copy_button: Button | None = None
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 4, 4)
        layout.setSpacing(8)
        layout.addWidget(self.label, 1)
        if copy_text is not None:
            self.copy_button = Button(
                copy_text, ButtonKind.SUBTLE, icon="Copy", size=ButtonSize.SMALL
            )
            if copy_tooltip:
                self.copy_button.setToolTip(copy_tooltip)
            layout.addWidget(self.copy_button)
        self.setMinimumHeight(40)
        follow_theme(self)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        p = theme.palette()
        fill_rounded(painter, QRectF(self.rect()), 4, p.sunken, p.border)


class PlannedBanner(QFrame):
    """Warning-tinted strip that marks a screen as not built yet."""

    def __init__(
        self, text: str, badge_text: str = "Planned", parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.text = label(text, TextStyle.BODY, wrap=True)
        self.text.setFont(fonts.make_font(13))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 8, 24, 8)
        layout.setSpacing(10)
        layout.addWidget(Badge(badge_text, BadgeTone.PLANNED))
        layout.addWidget(self.text, 1)
        follow_theme(self)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        p = theme.palette()
        painter.fillRect(self.rect(), p.warning_tint)
        painter.fillRect(QRectF(0, self.height() - 1, self.width(), 1), p.border)
