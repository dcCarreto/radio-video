from __future__ import annotations

from dataclasses import fields

import pytest
from PySide6.QtGui import QColor

from radio_video.ui.theme.tokens import (
    DARK,
    LIGHT,
    TOKENS,
    Palette,
    Scheme,
    css,
    palette_for,
    parse_color,
)


def _luminance(color: QColor) -> float:
    def channel(value: int) -> float:
        c = value / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return (
        0.2126 * channel(color.red())
        + 0.7152 * channel(color.green())
        + 0.0722 * channel(color.blue())
    )


def contrast(a: QColor, b: QColor) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_palette_fields_match_token_table() -> None:
    names = {f.name for f in fields(Palette)} - {"scheme"}
    assert names == {token.name for token in TOKENS}


def test_exact_design_values() -> None:
    assert LIGHT.bg.name() == "#f3f2f2"
    assert DARK.bg.name() == "#1b1a19"
    assert LIGHT.accent.name() == "#d42a10"
    assert DARK.accent.name() == "#ff6a4d"
    assert LIGHT.sel.name() == "#201e1d"


def test_parse_rgba_with_fractional_alpha() -> None:
    color = parse_color("rgba(32,30,29,.06)")
    assert (color.red(), color.green(), color.blue(), color.alpha()) == (32, 30, 29, 15)
    assert css(color) == "rgba(32, 30, 29, 15)"
    assert css(parse_color("#ffffff")) == "#ffffff"


def test_parse_color_rejects_garbage() -> None:
    with pytest.raises(ValueError, match="Invalid colour"):
        parse_color("not-a-colour")


def test_palette_for_scheme() -> None:
    assert palette_for(Scheme.DARK) is DARK
    assert palette_for(Scheme.LIGHT).is_dark is False


TEXT_PAIRS = [
    ("text", "bg"),
    ("text", "surface"),
    ("text", "raised"),
    ("text", "sunken"),
    ("text_2", "bg"),
    ("text_2", "surface"),
    ("text_2", "raised"),
    ("on_accent", "accent"),
    ("on_sel", "sel"),
    ("accent_text", "bg"),
    ("accent_text", "raised"),
    ("accent_text", "accent_tint"),
    ("success", "success_tint"),
    ("warning", "warning_tint"),
    ("danger", "danger_tint"),
    ("danger", "raised"),
    ("tip_fg", "tip_bg"),
]

NON_TEXT_PAIRS = [("border_ctl", "raised"), ("focus", "bg"), ("focus", "surface")]


@pytest.mark.parametrize("palette", [LIGHT, DARK], ids=["light", "dark"])
@pytest.mark.parametrize(("fg", "bg"), TEXT_PAIRS)
def test_text_contrast_meets_aa(palette: Palette, fg: str, bg: str) -> None:
    assert contrast(palette.color(fg), palette.color(bg)) >= 4.5


@pytest.mark.parametrize("palette", [LIGHT, DARK], ids=["light", "dark"])
@pytest.mark.parametrize(("fg", "bg"), NON_TEXT_PAIRS)
def test_control_contrast_meets_3_to_1(palette: Palette, fg: str, bg: str) -> None:
    assert contrast(palette.color(fg), palette.color(bg)) >= 3.0
