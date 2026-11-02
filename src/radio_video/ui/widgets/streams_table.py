"""Streams table: one row per track with type icon, codec, details, language and title."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import (
    QAbstractTableModel,
    QEvent,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QRect,
    QRectF,
    QSize,
    Qt,
)
from PySide6.QtGui import QFont, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QWidget,
)

from radio_video.ui import icons, theme
from radio_video.ui.icons import IconName
from radio_video.ui.theme import fonts
from radio_video.ui.theme.fonts import TextStyle
from radio_video.ui.widgets.badge import BadgeTone, badge_size, paint_badge
from radio_video.ui.widgets.painting import elide, text_width

ROW_HEIGHT = 37
HEADER_HEIGHT = 34
CELL_PADDING = 10

COLUMN_NUMBER, COLUMN_TYPE, COLUMN_CODEC, COLUMN_DETAILS, COLUMN_LANGUAGE, COLUMN_TITLE = range(6)
WIDE_WIDTHS = {
    COLUMN_NUMBER: 36,
    COLUMN_TYPE: 120,
    COLUMN_CODEC: 120,
    COLUMN_LANGUAGE: 150,
    COLUMN_TITLE: 200,
}
NARROW_WIDTHS = {COLUMN_NUMBER: 36, COLUMN_TYPE: 104, COLUMN_CODEC: 96, COLUMN_LANGUAGE: 104}

IndexLike = QModelIndex | QPersistentModelIndex
ROW_ROLE = Qt.ItemDataRole.UserRole + 1


@dataclass(frozen=True)
class StreamRow:
    number: int
    kind: str
    icon: IconName
    codec: str
    details: str
    language: str
    title: str
    is_default: bool = False
    codec_tooltip: str = ""
    tooltip: str = ""
    accessible: str = ""


class StreamsModel(QAbstractTableModel):
    def __init__(self, headers: list[str], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._headers = headers
        self._rows: list[StreamRow] = []

    def set_rows(self, rows: list[StreamRow]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def rows(self) -> list[StreamRow]:
        return list(self._rows)

    def rowCount(self, parent: IndexLike = QModelIndex()) -> int:  # noqa: N802, B008
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: IndexLike = QModelIndex()) -> int:  # noqa: N802, B008
        return 0 if parent.isValid() else len(self._headers)

    def headerData(  # noqa: N802
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if orientation is Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self._headers[section]
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return None

    def data(self, index: IndexLike, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        column = index.column()
        if role == ROW_ROLE:
            return row
        if role == Qt.ItemDataRole.DisplayRole:
            return [
                str(row.number),
                row.kind,
                row.codec,
                row.details,
                row.language,
                row.title or "—",
            ][column]
        if role == Qt.ItemDataRole.ToolTipRole:
            if column == COLUMN_CODEC and row.codec_tooltip:
                return row.codec_tooltip
            return row.tooltip or None
        if role == Qt.ItemDataRole.AccessibleTextRole:
            return row.accessible if column == COLUMN_NUMBER else None
        return None

    def flags(self, index: IndexLike) -> Qt.ItemFlag:
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


class KickerHeader(QHeaderView):
    """Table header painted in the kicker style: 11 px semibold capitals over a 2 px rule."""

    def __init__(self, parent: QWidget | None = None, *, on_surface: bool = False) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.on_surface = on_surface
        font = fonts.make_font(11, QFont.Weight.DemiBold)
        font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 106)
        font.setCapitalization(QFont.Capitalization.AllUppercase)
        self.setFont(font)
        self.setFixedHeight(HEADER_HEIGHT)
        self.setHighlightSections(False)
        self.setSectionsClickable(False)
        self.setMinimumSectionSize(24)

    def paintSection(self, painter: QPainter, rect: QRect, logical_index: int) -> None:  # noqa: N802
        painter.save()
        p = theme.palette()
        area = QRectF(rect)
        painter.fillRect(area, p.surface if self.on_surface else p.bg)
        painter.fillRect(QRectF(area.left(), area.bottom() - 1, area.width() + 1, 2), p.rule)
        model = self.model()
        text = str(model.headerData(logical_index, self.orientation())) if model else ""
        painter.setFont(self.font())
        painter.setPen(p.text_2)
        room = area.adjusted(CELL_PADDING, 0, -CELL_PADDING, -2)
        painter.drawText(
            room,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            elide(self.font(), text, Qt.TextElideMode.ElideRight, room.width()),
        )
        painter.restore()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self.viewport())
        p = theme.palette()
        painter.fillRect(self.viewport().rect(), p.surface if self.on_surface else p.bg)
        painter.fillRect(QRectF(0, self.height() - 2, self.width(), 2), p.rule)
        painter.end()
        super().paintEvent(event)


class StreamsDelegate(QStyledItemDelegate):
    def __init__(self, table: StreamsTable) -> None:
        super().__init__(table)
        self._table = table
        self.default_text = "Default"

    def sizeHint(self, option: QStyleOptionViewItem, index: IndexLike) -> QSize:  # noqa: N802
        return QSize(option.rect.width(), ROW_HEIGHT)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: IndexLike) -> None:
        row = index.data(ROW_ROLE)
        if not isinstance(row, StreamRow):
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        p = theme.palette()
        rect = QRectF(option.rect)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(rect, p.accent_tint)
        elif index.row() == self._table.hovered_row:
            painter.fillRect(rect, p.hover)
        painter.fillRect(QRectF(rect.left(), rect.bottom(), rect.width(), 1), p.border)

        column = index.column()
        font = fonts.font(TextStyle.BODY)
        font.setPixelSize(13)
        painter.setFont(font)
        x = rect.left() + CELL_PADDING
        width = rect.width() - CELL_PADDING * 2
        painter.setPen(p.text_2 if column in (COLUMN_NUMBER, COLUMN_TITLE) else p.text)
        text = str(index.data(Qt.ItemDataRole.DisplayRole))

        if column == COLUMN_TYPE:
            icons.paint_icon(painter, QRectF(x, rect.center().y() - 8, 16, 16), row.icon, p.text)
            x += 16 + 8
            width -= 16 + 8
        badge_room = 0.0
        if column == COLUMN_LANGUAGE and row.is_default and not self._table.compact:
            size = badge_size(self.default_text, BadgeTone.NEUTRAL)
            badge_room = size.width() + 6
            shown = min(text_width(font, text), width - badge_room)
            paint_badge(
                painter,
                QRectF(
                    x + shown + 6,
                    rect.center().y() - size.height() / 2,
                    size.width(),
                    size.height(),
                ),
                self.default_text,
                BadgeTone.NEUTRAL,
            )
        elided = elide(font, text, Qt.TextElideMode.ElideRight, width - badge_room)
        painter.drawText(
            QRectF(x, rect.top(), width - badge_room, rect.height()),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            elided,
        )
        painter.restore()


class StreamsTable(QTableView):
    """Read-only. Arrow keys move rows; below 1200 px windows the Title column hides and its
    text is in the row tooltip."""

    def __init__(
        self, headers: list[str], *, on_surface: bool = False, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.streams = StreamsModel(headers, self)
        self.setModel(self.streams)
        self.delegate = StreamsDelegate(self)
        self.setItemDelegate(self.delegate)
        self.hovered_row = -1
        self.compact = False
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setMouseTracking(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setProperty("focusRadius", 0)
        self.setAccessibleName("Tracks")
        vertical = self.verticalHeader()
        vertical.hide()
        vertical.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        vertical.setDefaultSectionSize(ROW_HEIGHT)
        self.setHorizontalHeader(KickerHeader(self, on_surface=on_surface))
        self.viewport().installEventFilter(self)
        theme.current().changed.connect(self.viewport().update)
        self.set_compact(False)

    def set_rows(self, rows: list[StreamRow]) -> None:
        self.streams.set_rows(rows)

    def set_compact(self, compact: bool) -> None:
        self.compact = compact
        header = self.horizontalHeader()
        widths = NARROW_WIDTHS if compact else WIDE_WIDTHS
        for column in range(self.streams.columnCount()):
            if column == COLUMN_DETAILS:
                header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
                continue
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            if column in widths:
                header.resizeSection(column, widths[column])
        self.setColumnHidden(COLUMN_TITLE, compact)
        self.viewport().update()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self.viewport():
            if event.type() == QEvent.Type.MouseMove and isinstance(event, QMouseEvent):
                row = self.rowAt(int(event.position().y()))
                if row != self.hovered_row:
                    self.hovered_row = row
                    self.viewport().update()
            elif event.type() == QEvent.Type.Leave:
                self.hovered_row = -1
                self.viewport().update()
        return super().eventFilter(watched, event)
