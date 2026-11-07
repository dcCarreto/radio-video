"""Format picker: a combo box whose popup groups formats and describes each one."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import (
    QModelIndex,
    QPersistentModelIndex,
    QPoint,
    QRect,
    QRectF,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QFont,
    QFontMetrics,
    QPainter,
    QPaintEvent,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QListView,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

from radio_video.ui import icons, theme
from radio_video.ui.theme import fonts
from radio_video.ui.theme.fonts import TextStyle
from radio_video.ui.widgets.badge import BadgeTone, badge_size, paint_badge
from radio_video.ui.widgets.focus_ring import FocusRing
from radio_video.ui.widgets.painting import (
    antialiased,
    elide,
    fill_rounded,
    follow_theme,
    text_width,
)

KIND_ROLE = Qt.ItemDataRole.UserRole + 1
KEY_ROLE = Qt.ItemDataRole.UserRole + 2
DESCRIPTION_ROLE = Qt.ItemDataRole.UserRole + 3
RECOMMENDED_ROLE = Qt.ItemDataRole.UserRole + 4
HEADER = "header"
OPTION = "option"

FIELD_HEIGHT = 32
POPUP_GAP = 4
POPUP_PADDING = 4
ITEM_PADDING_X = 10
ITEM_PADDING_Y = 7
CHECK_COLUMN = 16
CHECK_GAP = 10
HEADER_HEIGHT = 30
DEFAULT_MAX_POPUP_HEIGHT = 520

IndexLike = QModelIndex | QPersistentModelIndex


@dataclass(frozen=True)
class FormatOption:
    key: str
    name: str
    description: str
    recommended: bool = False


@dataclass(frozen=True)
class FormatGroup:
    title: str
    options: tuple[FormatOption, ...]


class FormatDelegate(QStyledItemDelegate):
    def __init__(self, combo: FormatCombo) -> None:
        super().__init__(combo)
        self._combo = combo
        self.recommended_text = "Recommended"

    def _name_font(self, current: bool) -> QFont:
        return fonts.make_font(14, QFont.Weight.DemiBold if current else QFont.Weight.Normal)

    def _text_width(self, width: int) -> int:
        return width - ITEM_PADDING_X * 2 - CHECK_COLUMN - CHECK_GAP

    def _description_rect(self, description: str, width: int) -> QRect:
        metrics = QFontMetrics(fonts.font(TextStyle.CAPTION))
        return metrics.boundingRect(
            QRect(0, 0, max(self._text_width(width), 40), 10_000),
            int(Qt.TextFlag.TextWordWrap),
            description,
        )

    def sizeHint(self, option: QStyleOptionViewItem, index: IndexLike) -> QSize:  # noqa: N802
        width = self._combo.view().viewport().width() or option.rect.width()
        if index.data(KIND_ROLE) == HEADER:
            return QSize(width, HEADER_HEIGHT)
        description = str(index.data(DESCRIPTION_ROLE) or "")
        if not description:
            return QSize(width, ITEM_PADDING_Y * 2 + 20)
        lines = self._description_rect(description, width).height()
        return QSize(width, ITEM_PADDING_Y * 2 + 20 + max(lines, 16))

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: IndexLike) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        p = theme.palette()
        rect = QRectF(option.rect)
        if index.data(KIND_ROLE) == HEADER:
            painter.setFont(fonts.font(TextStyle.KICKER))
            painter.setPen(p.text_2)
            painter.drawText(
                rect.adjusted(ITEM_PADDING_X, 10, -ITEM_PADDING_X, -4),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                str(index.data(Qt.ItemDataRole.DisplayRole)),
            )
            painter.restore()
            return

        current = index.row() == self._combo.currentIndex()
        highlighted = bool(
            option.state & (QStyle.StateFlag.State_MouseOver | QStyle.StateFlag.State_Selected)
        )
        if current:
            fill_rounded(painter, rect, 4, p.accent_tint)
        elif highlighted:
            fill_rounded(painter, rect, 4, p.hover)

        x = rect.left() + ITEM_PADDING_X
        top = rect.top() + ITEM_PADDING_Y
        if current:
            icons.paint_icon(painter, QRectF(x, top + 2, 16, 16), "Check", p.text)
        x += CHECK_COLUMN + CHECK_GAP
        name = str(index.data(Qt.ItemDataRole.DisplayRole))
        font = self._name_font(current)
        painter.setFont(font)
        painter.setPen(p.text)
        name_width = text_width(font, name)
        painter.drawText(
            QRectF(x, top, name_width + 1, 20),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            name,
        )
        if index.data(RECOMMENDED_ROLE):
            size = badge_size(self.recommended_text, BadgeTone.ACCENT)
            paint_badge(
                painter,
                QRectF(x + name_width + 8, top, size.width(), size.height()),
                self.recommended_text,
                BadgeTone.ACCENT,
            )
        description = str(index.data(DESCRIPTION_ROLE) or "")
        if description:
            painter.setFont(fonts.font(TextStyle.CAPTION))
            painter.setPen(p.text_2)
            room = self._text_width(int(rect.width()))
            painter.drawText(
                QRectF(x, top + 20, room, rect.bottom() - top - 20 - ITEM_PADDING_Y + 1),
                int(
                    Qt.AlignmentFlag.AlignLeft
                    | Qt.AlignmentFlag.AlignTop
                    | Qt.TextFlag.TextWordWrap
                ),
                description,
            )
        painter.restore()


class FormatCombo(QComboBox):
    format_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = QStandardItemModel(self)
        self.setModel(self._model)
        view = QListView()
        view.setUniformItemSizes(False)
        view.setWordWrap(True)
        view.setMouseTracking(True)
        view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setView(view)
        self.delegate = FormatDelegate(self)
        view.setItemDelegate(self.delegate)
        self.max_popup_height = DEFAULT_MAX_POPUP_HEIGHT
        self._popup_open = False
        self.setProperty("ownFocusStyle", True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setFont(fonts.font(TextStyle.BODY))
        self.setFixedHeight(FIELD_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.currentIndexChanged.connect(self._on_index_changed)
        follow_theme(self)

    def set_groups(self, groups: list[FormatGroup], current_key: str | None = None) -> None:
        self.blockSignals(True)
        self._model.clear()
        for group in groups:
            header = QStandardItem(group.title)
            header.setData(HEADER, KIND_ROLE)
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            header.setData(group.title, Qt.ItemDataRole.AccessibleTextRole)
            self._model.appendRow(header)
            for option in group.options:
                item = QStandardItem(option.name)
                item.setData(OPTION, KIND_ROLE)
                item.setData(option.key, KEY_ROLE)
                item.setData(option.description, DESCRIPTION_ROLE)
                item.setData(option.recommended, RECOMMENDED_ROLE)
                item.setData(
                    f"{option.name}. {option.description}",
                    Qt.ItemDataRole.AccessibleDescriptionRole,
                )
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self._model.appendRow(item)
        self.setMaxVisibleItems(max(self._model.rowCount(), 1))
        target = current_key if current_key is not None else self.current_key()
        row = self._row_for(target) if target is not None else -1
        if row < 0:
            row = next(
                (
                    r
                    for r in range(self._model.rowCount())
                    if self._model.item(r).data(KIND_ROLE) == OPTION
                ),
                -1,
            )
        self.setCurrentIndex(row)
        self.blockSignals(False)
        self.update()

    def keys(self) -> list[str]:
        return [
            str(self._model.item(row).data(KEY_ROLE))
            for row in range(self._model.rowCount())
            if self._model.item(row).data(KIND_ROLE) == OPTION
        ]

    def current_key(self) -> str | None:
        value = self.currentData(KEY_ROLE)
        return str(value) if value is not None else None

    def set_current_key(self, key: str) -> None:
        row = self._row_for(key)
        if row >= 0:
            self.setCurrentIndex(row)

    def _row_for(self, key: str) -> int:
        for row in range(self._model.rowCount()):
            if self._model.item(row).data(KEY_ROLE) == key:
                return row
        return -1

    def _on_index_changed(self, _row: int) -> None:
        key = self.current_key()
        self.setAccessibleDescription(str(self.currentData(DESCRIPTION_ROLE) or ""))
        if key is not None:
            self.format_changed.emit(key)

    def showPopup(self) -> None:  # noqa: N802
        self._popup_open = True
        self.update()
        super().showPopup()
        container = self.view().window()
        content = sum(self.view().sizeHintForRow(r) for r in range(self.count()))
        height = min(content + POPUP_PADDING * 2 + 2, self.max_popup_height)
        below = self.mapToGlobal(QPoint(0, self.height() + POPUP_GAP))
        container.setGeometry(below.x(), below.y(), self.width(), height)

    def hidePopup(self) -> None:  # noqa: N802
        super().hidePopup()
        self._popup_open = False
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        p = theme.palette()
        rect = QRectF(self.rect())
        enabled = self.isEnabled()
        ring = FocusRing._instance
        focused = self._popup_open or (self.hasFocus() and ring is not None and ring.keyboard_mode)
        if not enabled:
            fill_rounded(painter, rect, 4, p.sunken, p.border)
        else:
            border = p.accent if focused else p.text_2 if self.underMouse() else p.border_ctl
            fill_rounded(painter, rect, 4, p.raised, border)
            if focused:
                painter.fillRect(QRectF(2, rect.height() - 2, rect.width() - 4, 1), p.accent)
        color = p.text if enabled else p.text_dis
        painter.setPen(color)
        painter.setFont(self.font())
        text_rect = QRectF(10, 0, rect.width() - 10 - 8 - 16 - 10, rect.height())
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            elide(
                self.font(), self.currentText(), Qt.TextElideMode.ElideRight, int(text_rect.width())
            ),
        )
        icons.paint_icon(
            painter,
            QRectF(rect.width() - 10 - 16, (rect.height() - 16) / 2, 16, 16),
            "ChevronDown",
            color,
        )


@dataclass(frozen=True)
class Choice:
    key: str
    name: str
    description: str = ""
    recommended: bool = False


class ChoiceCombo(FormatCombo):
    """The format picker's look for a plain list of choices, without group headers.

    ``format_changed`` carries the chosen key.
    """

    def __init__(self, accessible_name: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._choices: tuple[Choice, ...] = ()
        if accessible_name:
            self.setAccessibleName(accessible_name)

    def set_choices(self, choices: list[Choice] | tuple[Choice, ...], current: str) -> None:
        """Replace the list (only when it changed) and select ``current`` without signals."""
        self.blockSignals(True)
        if tuple(choices) != self._choices:
            self._choices = tuple(choices)
            self._model.clear()
            for choice in choices:
                item = QStandardItem(choice.name)
                item.setData(OPTION, KIND_ROLE)
                item.setData(choice.key, KEY_ROLE)
                item.setData(choice.description, DESCRIPTION_ROLE)
                item.setData(choice.recommended, RECOMMENDED_ROLE)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self._model.appendRow(item)
            self.setMaxVisibleItems(max(len(choices), 1))
        row = self._row_for(current)
        self.setCurrentIndex(row if row >= 0 else 0)
        self.setToolTip(self.currentText())
        self.blockSignals(False)
        self.update()
