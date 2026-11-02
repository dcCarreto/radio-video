from __future__ import annotations

from typing import get_args

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from radio_video.ui import icons


def test_every_icon_name_has_a_file() -> None:
    assert set(get_args(icons.IconName)) == set(icons.FILE_NAMES)
    for name, file_name in icons.FILE_NAMES.items():
        assert (icons.ICON_DIR / f"{file_name}.svg").is_file(), name


def test_license_is_shipped() -> None:
    text = (icons.ICON_DIR / "LICENSE").read_text(encoding="utf-8")
    assert "ISC License" in text


def test_icons_are_recoloured(qapp: QApplication) -> None:
    red = QColor("#d42a10")
    image = icons.pixmap("Square", 24, red).toImage()
    opaque = [
        image.pixelColor(x, y)
        for x in range(image.width())
        for y in range(image.height())
        if image.pixelColor(x, y).alpha() == 255
    ]
    assert opaque
    assert all(color.name() == red.name() for color in opaque)


def test_stroke_gets_lighter_above_24_px() -> None:
    assert icons.stroke_width(16) == 2.0
    assert icons.stroke_width(28) == 1.5


def test_app_icon_has_all_sizes(qapp: QApplication) -> None:
    sizes = {size.width() for size in icons.app_icon().availableSizes()}
    assert {16, 24, 32, 48, 256} <= sizes
