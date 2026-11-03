"""Colour tokens of the Radio/Video design system for the light and dark themes.

Every text pair meets WCAG 2.1 AA (4.5:1); control borders and the focus ring meet 3:1.
Do not change these values without re-checking contrast (see tests/ui/theme).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from PySide6.QtGui import QColor


class Scheme(Enum):
    LIGHT = "light"
    DARK = "dark"


@dataclass(frozen=True)
class Token:
    name: str
    light: str
    dark: str
    role: str


TOKENS: tuple[Token, ...] = (
    Token("bg", "#f3f2f2", "#1b1a19", "Background"),
    Token("surface", "#f9f8f8", "#222120", "Surface: convert panel, preview body"),
    Token("raised", "#ffffff", "#2c2a29", "Raised surface: buttons, inputs, cards, dialogs"),
    Token("raised_hover", "#f4f3f2", "#343231", "Raised: hover"),
    Token("raised_press", "#eae8e7", "#3b3937", "Raised: pressed"),
    Token("sunken", "#eae9e9", "#171615", "Sunken: code, logs, disabled fills"),
    Token("border", "#dcd9d7", "#3a3735", "Border: hairlines, cards, table rows"),
    Token("border_ctl", "#8c8785", "#8a8582", "Control border (≥3:1)"),
    Token("rule", "#a19d9b", "#5e5a57", "Structural rule, 2px"),
    Token("text", "#201e1d", "#f3f2f2", "Primary text"),
    Token("text_2", "#5c5856", "#b3aeab", "Secondary text, helper text"),
    Token("text_dis", "#a19d9b", "#6b6764", "Disabled text (exempt from contrast)"),
    Token("accent", "#d42a10", "#ff6a4d", "Accent: primary action, progress"),
    Token("accent_hover", "#b82208", "#ff8166", "Accent: hover"),
    Token("accent_press", "#9a1a03", "#e85a3e", "Accent: pressed"),
    Token("on_accent", "#ffffff", "#1b0a05", "Text on accent"),
    Token("accent_text", "#ae1800", "#ff8a70", "Accent text: links, accent badges"),
    Token("accent_tint", "#fde8e3", "#3f1d16", "Accent tint: drag-over, selected rows"),
    Token("sel", "#201e1d", "#f3f2f2", "Selected control: segments, checks, sliders"),
    Token("on_sel", "#f9f8f8", "#1b1a19", "Text on selected control"),
    Token("success", "#1d7a3c", "#5cc27a", "Success"),
    Token("success_tint", "#e1f1e5", "#173020", "Success tint"),
    Token("warning", "#8a5300", "#e3ab45", "Warning"),
    Token("warning_tint", "#fbefd9", "#33270f", "Warning tint, planned banner"),
    Token("danger", "#a3123a", "#ff86a5", "Danger: failed, destructive"),
    Token("danger_tint", "#fbe4ea", "#3b1622", "Danger tint"),
    Token("focus", "#d42a10", "#ff6a4d", "Focus ring, 2px"),
    Token("hover", "rgba(32,30,29,.06)", "rgba(243,242,242,.07)", "Hover overlay"),
    Token("press", "rgba(32,30,29,.11)", "rgba(243,242,242,.12)", "Pressed overlay"),
    Token("tip_bg", "#2d2b2a", "#f3f2f2", "Tooltip background"),
    Token("tip_fg", "#f3f2f2", "#201e1d", "Tooltip text"),
    Token("video", "#0e0d0d", "#0e0d0d", "Video canvas (both themes)"),
)

_RGBA = re.compile(r"^rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([0-9.]+)\s*\)$")


def parse_color(value: str) -> QColor:
    """Parse ``#rrggbb`` or CSS ``rgba(r,g,b,a)`` with a fractional alpha."""
    if match := _RGBA.match(value):
        r, g, b = (int(match.group(i)) for i in (1, 2, 3))
        return QColor(r, g, b, round(float(match.group(4)) * 255))
    color = QColor(value)
    if not color.isValid():
        raise ValueError(f"Invalid colour: {value!r}")
    return color


def css(color: QColor) -> str:
    """Format a colour for Qt style sheets, which take alpha as 0 to 255."""
    if color.alpha() == 255:
        return color.name()
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"


@dataclass(frozen=True)
class Palette:
    scheme: Scheme
    bg: QColor
    surface: QColor
    raised: QColor
    raised_hover: QColor
    raised_press: QColor
    sunken: QColor
    border: QColor
    border_ctl: QColor
    rule: QColor
    text: QColor
    text_2: QColor
    text_dis: QColor
    accent: QColor
    accent_hover: QColor
    accent_press: QColor
    on_accent: QColor
    accent_text: QColor
    accent_tint: QColor
    sel: QColor
    on_sel: QColor
    success: QColor
    success_tint: QColor
    warning: QColor
    warning_tint: QColor
    danger: QColor
    danger_tint: QColor
    focus: QColor
    hover: QColor
    press: QColor
    tip_bg: QColor
    tip_fg: QColor
    video: QColor

    @classmethod
    def for_scheme(cls, scheme: Scheme) -> Palette:
        values = {token.name: parse_color(getattr(token, scheme.value)) for token in TOKENS}
        return cls(scheme=scheme, **values)

    @property
    def is_dark(self) -> bool:
        return self.scheme is Scheme.DARK

    def color(self, name: str) -> QColor:
        value = getattr(self, name)
        if not isinstance(value, QColor):
            raise KeyError(name)
        return QColor(value)


LIGHT = Palette.for_scheme(Scheme.LIGHT)
DARK = Palette.for_scheme(Scheme.DARK)


def palette_for(scheme: Scheme) -> Palette:
    return DARK if scheme is Scheme.DARK else LIGHT
