from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from radio_video.ui import theme
from radio_video.ui.theme import fonts
from radio_video.ui.theme.fonts import TextStyle
from radio_video.ui.theme.qss import build_stylesheet
from radio_video.ui.theme.tokens import DARK, LIGHT, Palette, Scheme


@pytest.fixture
def manager(qapp: QApplication) -> Iterator[theme.ThemeManager]:
    manager = theme.install(qapp)
    yield manager
    manager.set_override(None)


def test_override_switches_palette_and_style_sheet(
    manager: theme.ThemeManager, qapp: QApplication, qtbot: QtBot
) -> None:
    with qtbot.waitSignal(manager.changed) as blocker:
        manager.set_override(Scheme.DARK)
    assert blocker.args == [DARK]
    assert theme.palette() is DARK
    assert qapp.palette().color(QPalette.ColorRole.Window).name() == "#1b1a19"
    assert "#1b1a19" in qapp.styleSheet()

    manager.set_override(Scheme.LIGHT)
    assert manager.scheme is Scheme.LIGHT
    assert qapp.palette().color(QPalette.ColorRole.Window).name() == "#f3f2f2"


def test_disabled_text_uses_disabled_token(manager: theme.ThemeManager, qapp: QApplication) -> None:
    manager.set_override(Scheme.LIGHT)
    color = qapp.palette().color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText)
    assert color.name() == LIGHT.text_dis.name()


@pytest.mark.parametrize("palette", [LIGHT, DARK], ids=["light", "dark"])
def test_style_sheet_has_no_fonts_and_qt_alpha(palette: Palette) -> None:
    sheet = build_stylesheet(palette)
    assert "font" not in sheet
    assert ".06)" not in sheet and ".07)" not in sheet
    assert palette.rule.name() in sheet


def test_type_scale() -> None:
    kicker = fonts.font(TextStyle.KICKER)
    assert kicker.pixelSize() == 11
    assert kicker.capitalization() is kicker.Capitalization.AllUppercase
    assert fonts.font(TextStyle.DISPLAY).families()[0] == "Segoe UI Variable Display"
    assert fonts.font(TextStyle.BODY).families()[0] == "Segoe UI Variable Text"
    assert fonts.font(TextStyle.BODY_STRONG).families()[0] == "Segoe UI Variable Text Semibold"
    assert fonts.font(TextStyle.TITLE).families()[0] == "Segoe UI Variable Display Semibold"
    assert fonts.font(TextStyle.MONO).families()[0] == "Cascadia Mono"
    assert fonts.line_height(TextStyle.TITLE) == 28
