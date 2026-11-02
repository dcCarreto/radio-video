"""Debug gallery (``--ui-gallery``): every design foundation and screen state with demo data.

``--capture DIR`` saves each page in the light and dark themes as PNG files and exits, for
side-by-side comparison with the design canvas.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPoint, QRectF, QSize, Qt
from PySide6.QtGui import QPainter, QPaintEvent, QPixmap, QRegion
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from radio_video.ui import icons, theme
from radio_video.ui.gallery_components import components_page
from radio_video.ui.native.dwm import style_title_bar
from radio_video.ui.theme import fonts
from radio_video.ui.theme.fonts import TextStyle
from radio_video.ui.theme.tokens import TOKENS, Palette, Scheme
from radio_video.ui.widgets.focus_ring import FocusRing

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GalleryPage:
    title: str
    build: Callable[[], QWidget]
    size: QSize | None = None


def _label(text: str, style: TextStyle = TextStyle.BODY, tone: str | None = None) -> QLabel:
    label = QLabel(text)
    fonts.apply(label, style)
    if tone:
        label.setProperty("tone", tone)
    return label


class _Swatch(QWidget):
    def __init__(self, token: str) -> None:
        super().__init__()
        self._token = token
        self.setFixedSize(44, 24)
        theme.current().changed.connect(self.update)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(theme.palette().border_ctl)
        painter.setBrush(theme.palette().color(self._token))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 2, 2)


class _IconTile(QWidget):
    def __init__(self, name: icons.IconName, size: int) -> None:
        super().__init__()
        self._name = name
        self._size = size
        self.setFixedSize(size + 8, size + 8)
        self.setToolTip(name)
        theme.current().changed.connect(self.update)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        icons.paint_icon(
            painter, QRectF(4, 4, self._size, self._size), self._name, theme.palette().text
        )


class _AppIconTile(QWidget):
    def __init__(self, size: int) -> None:
        super().__init__()
        self._size = size
        self.setFixedSize(size, size)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        icons.paint_app_icon(painter, QRectF(0, 0, self._size, self._size))


def _page(*widgets: QWidget) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(32, 32, 32, 32)
    layout.setSpacing(16)
    for widget in widgets:
        layout.addWidget(widget)
    layout.addStretch()
    return page


def colours_page() -> QWidget:
    grid = QWidget()
    layout = QGridLayout(grid)
    layout.setHorizontalSpacing(16)
    layout.setVerticalSpacing(6)
    for column, heading in enumerate(("", "Token", "Role")):
        layout.addWidget(_label(heading, TextStyle.KICKER, "secondary"), 0, column)
    for row, token in enumerate(TOKENS, start=1):
        layout.addWidget(_Swatch(token.name), row, 0)
        layout.addWidget(_label(token.name, TextStyle.MONO), row, 1)
        layout.addWidget(_label(token.role, tone="secondary"), row, 2)
    layout.setColumnStretch(2, 1)
    return _page(_label("Colour roles", TextStyle.TITLE_LARGE), grid)


def type_page() -> QWidget:
    rows: list[QWidget] = [_label("Type", TextStyle.TITLE_LARGE)]
    for style in TextStyle:
        spec = style.value
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        name = _label(f"{style.name.lower()} · {spec.size}/{spec.line}", tone="secondary")
        name.setFixedWidth(220)
        layout.addWidget(name)
        layout.addWidget(_label("Convert to MP4", style), 1)
        rows.append(row)
    return _page(*rows)


def icons_page() -> QWidget:
    grid = QWidget()
    layout = QGridLayout(grid)
    layout.setSpacing(12)
    names = list(icons.FILE_NAMES)
    for index, name in enumerate(names):
        cell = QWidget()
        cell_layout = QHBoxLayout(cell)
        cell_layout.setContentsMargins(0, 0, 0, 0)
        cell_layout.addWidget(_IconTile(name, 16))
        cell_layout.addWidget(_IconTile(name, 28))
        cell_layout.addWidget(_label(name, TextStyle.CAPTION, "secondary"), 1)
        layout.addWidget(cell, index // 4, index % 4)
    app_row = QWidget()
    app_layout = QHBoxLayout(app_row)
    app_layout.setContentsMargins(0, 0, 0, 0)
    app_layout.setSpacing(28)
    for size in (256, 32, 16):
        app_layout.addWidget(_AppIconTile(size), 0, Qt.AlignmentFlag.AlignBottom)
    app_layout.addStretch()
    return _page(
        _label("Icons", TextStyle.TITLE_LARGE),
        _label("Lucide, 2 px stroke at 16 px, 1.5 px above 24 px.", tone="secondary"),
        grid,
        _label("App icon", TextStyle.SUBTITLE),
        app_row,
    )


def focus_page() -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    for text in ("First", "Second", "Third"):
        layout.addWidget(QPushButton(text))
    layout.addStretch()
    return _page(
        _label("Focus ring", TextStyle.TITLE_LARGE),
        _label(
            "Press Tab: a 2 px accent ring, offset 1 px. A mouse press hides it.", tone="secondary"
        ),
        row,
    )


def foundation_pages() -> list[GalleryPage]:
    return [
        GalleryPage("Foundations: colour", colours_page),
        GalleryPage("Foundations: type", type_page),
        GalleryPage("Foundations: icons", icons_page),
        GalleryPage("Foundations: focus", focus_page),
        GalleryPage("Components", components_page),
    ]


class GalleryWindow(QMainWindow):
    def __init__(self, pages: Sequence[GalleryPage]) -> None:
        super().__init__()
        self.setWindowTitle("Radio/Video · UI gallery")
        self.setWindowIcon(icons.app_icon())
        self._pages = list(pages)
        self._built: dict[int, QScrollArea] = {}

        self.list = QListWidget()
        self.list.setFixedWidth(260)
        for page in self._pages:
            self.list.addItem(page.title)
        self.stack = QStackedWidget()

        self.scheme_buttons = QButtonGroup(self)
        bar = QHBoxLayout()
        bar.addWidget(_label("Theme", TextStyle.KICKER, "secondary"))
        for label, scheme in (("System", None), ("Light", Scheme.LIGHT), ("Dark", Scheme.DARK)):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setChecked(scheme is None)
            button.clicked.connect(lambda _=False, s=scheme: theme.current().set_override(s))
            self.scheme_buttons.addButton(button)
            bar.addWidget(button)
        bar.addStretch()

        right = QVBoxLayout()
        right.addLayout(bar)
        right.addWidget(self.stack, 1)
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.addWidget(self.list)
        layout.addLayout(right, 1)
        self.setCentralWidget(central)

        self.list.currentRowChanged.connect(self.show_page)
        theme.current().changed.connect(self._on_theme_changed)
        self.list.setCurrentRow(0)

    def show_page(self, index: int) -> QScrollArea:
        if index not in self._built:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            content = self._pages[index].build()
            content.setProperty("transparent", True)
            scroll.setWidget(content)
            self._built[index] = scroll
            self.stack.addWidget(scroll)
        widget = self._built[index]
        self.stack.setCurrentWidget(widget)
        return widget

    def showEvent(self, event: object) -> None:  # noqa: N802
        self._on_theme_changed(theme.palette())

    def _on_theme_changed(self, palette: Palette) -> None:
        if self.isVisible():
            style_title_bar(self, dark=palette.is_dark, caption=palette.bg, text=palette.text)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def render_page(scroll: QScrollArea) -> QPixmap:
    """Render the whole page, beyond the visible area, over the window background."""
    content = scroll.widget()
    if content is None:
        return scroll.grab()
    content.resize(
        scroll.viewport().width(), max(content.sizeHint().height(), scroll.viewport().height())
    )
    QApplication.processEvents()
    image = QPixmap(content.size())
    image.fill(theme.palette().bg)
    content.render(image, QPoint(0, 0), QRegion(), QWidget.RenderFlag.DrawChildren)
    return image


def capture(window: GalleryWindow, pages: Sequence[GalleryPage], folder: Path) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    manager = theme.current()
    for scheme in Scheme:
        manager.set_override(scheme)
        for index, page in enumerate(pages):
            scroll = window.show_page(index)
            QApplication.processEvents()
            path = folder / f"{_slug(page.title)}-{scheme.value}.png"
            render_page(scroll).save(str(path))
            saved.append(path)
    manager.set_override(None)
    return saved


def run(app: QApplication, args: Sequence[str]) -> int:
    theme.install(app)
    FocusRing.install(app)
    pages = foundation_pages()
    window = GalleryWindow(pages)
    window.resize(1280, 860)
    window.show()
    if "--capture" in args:
        position = list(args).index("--capture")
        folder = Path(args[position + 1]) if position + 1 < len(args) else Path("gallery")
        for path in capture(window, pages, folder):
            logger.info("Saved %s", path)
        return 0
    return app.exec()
