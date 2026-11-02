"""Step strip: where the user is in Open → Check → Choose → Preview → Convert."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QFont, QPainter, QPaintEvent
from PySide6.QtWidgets import QSizePolicy, QWidget

from radio_video.ui import icons, theme
from radio_video.ui.theme import fonts
from radio_video.ui.widgets.painting import antialiased, fill_rounded, follow_theme, text_width

HEIGHT = 40
PADDING_X = 24
BOX = 20
GAP = 8
CONNECTOR = (28, 12)
CONNECTOR_COMPACT = (16, 8)
RULE = 2


class StepStrip(QWidget):
    """Paints numbered steps. Steps before ``current`` are done; ``current`` is highlighted.

    Uses the long labels when they fit, otherwise the short ones (as at 960 px).
    """

    def __init__(
        self,
        labels: list[str],
        short_labels: list[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if len(labels) != len(short_labels):
            raise ValueError("labels and short_labels must have the same length")
        self._labels = labels
        self._short = short_labels
        self._current = 0
        self.setFixedHeight(HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setFont(fonts.make_font(13))
        follow_theme(self)
        self._update_accessibility()

    def current(self) -> int:
        return self._current

    def set_current(self, index: int) -> None:
        self._current = max(0, min(index, len(self._labels)))
        self._update_accessibility()
        self.update()

    def _update_accessibility(self) -> None:
        self.setAccessibleName("Steps")
        if self._current < len(self._labels):
            self.setAccessibleDescription(
                f"Step {self._current + 1} of {len(self._labels)}: {self._labels[self._current]}"
            )
        else:
            self.setAccessibleDescription("All steps done")

    def _bold(self) -> QFont:
        font = QFont(self.font())
        font.setWeight(QFont.Weight.DemiBold)
        return font

    def _width(self, labels: list[str], connector: tuple[int, int]) -> int:
        width = PADDING_X * 2
        for index, text in enumerate(labels):
            font = self._bold() if index == self._current else self.font()
            width += BOX + GAP + text_width(font, text)
            if index:
                width += connector[0] + connector[1] * 2
        return width

    def compact(self) -> bool:
        return self._width(self._labels, CONNECTOR) > self.width()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self._width(self._labels, CONNECTOR), HEIGHT)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        p = theme.palette()
        painter.fillRect(self.rect(), p.bg)
        painter.fillRect(QRectF(0, self.height() - RULE, self.width(), RULE), p.rule)
        compact = self.compact()
        labels = self._short if compact else self._labels
        connector = CONNECTOR_COMPACT if compact else CONNECTOR
        middle = (self.height() - RULE) / 2
        x = float(PADDING_X)
        for index, text in enumerate(labels):
            if index:
                x += connector[1]
                painter.fillRect(QRectF(x, middle, connector[0], 1), p.border_ctl)
                x += connector[0] + connector[1]
            done = index < self._current
            active = index == self._current
            box = QRectF(x, middle - BOX / 2, BOX, BOX)
            if done:
                fill_rounded(painter, box, 2, p.sel)
                check = QRectF(0, 0, 12, 12)
                check.moveCenter(box.center())
                icons.paint_icon(painter, check, "Check", p.on_sel)
            elif active:
                fill_rounded(painter, box, 2, p.accent)
            else:
                fill_rounded(painter, box, 2, None, p.border_ctl)
            if not done:
                self._draw_number(painter, box, index + 1, p.on_accent if active else p.text_2)
            x += BOX + GAP
            font = self._bold() if active else self.font()
            painter.setFont(font)
            painter.setPen(p.text if done or active else p.text_2)
            width = text_width(font, text)
            painter.drawText(
                QRectF(x, 0, width + 1, self.height() - RULE),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                text,
            )
            x += width

    @staticmethod
    def _draw_number(painter: QPainter, box: QRectF, number: int, color: object) -> None:
        painter.save()
        painter.setFont(fonts.make_font(11, QFont.Weight.Bold))
        painter.setPen(color)
        painter.drawText(box, int(Qt.AlignmentFlag.AlignCenter), str(number))
        painter.restore()
