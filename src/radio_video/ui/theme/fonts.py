"""Type scale. Fonts are set in code because style sheet fonts override ``setFont()``."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget

TEXT_FAMILIES = ["Segoe UI Variable Text", "Segoe UI"]
DISPLAY_FAMILIES = ["Segoe UI Variable Display", "Segoe UI"]
MONO_FAMILIES = ["Cascadia Mono", "Consolas"]

# Segoe UI Variable switches to its Display optical size at 20 px.
DISPLAY_FROM_PX = 20


@dataclass(frozen=True)
class TextSpec:
    size: int
    line: int
    weight: QFont.Weight
    mono: bool = False
    kicker: bool = False


class TextStyle(Enum):
    DISPLAY = TextSpec(40, 48, QFont.Weight.Bold)
    TITLE_LARGE = TextSpec(28, 36, QFont.Weight.Bold)
    TITLE = TextSpec(20, 28, QFont.Weight.DemiBold)
    SUBTITLE = TextSpec(16, 22, QFont.Weight.DemiBold)
    BODY_STRONG = TextSpec(14, 20, QFont.Weight.DemiBold)
    BODY = TextSpec(14, 20, QFont.Weight.Normal)
    CAPTION = TextSpec(12, 16, QFont.Weight.Normal)
    CAPTION_STRONG = TextSpec(12, 16, QFont.Weight.DemiBold)
    KICKER = TextSpec(11, 16, QFont.Weight.DemiBold, kicker=True)
    MONO = TextSpec(13, 18, QFont.Weight.Normal, mono=True)
    MONO_SMALL = TextSpec(12, 18, QFont.Weight.Normal, mono=True)


def make_font(
    size: int, weight: QFont.Weight = QFont.Weight.Normal, *, mono: bool = False
) -> QFont:
    font = QFont()
    if mono:
        font.setFamilies(MONO_FAMILIES)
        font.setStyleHint(QFont.StyleHint.Monospace)
    else:
        font.setFamilies(DISPLAY_FAMILIES if size >= DISPLAY_FROM_PX else TEXT_FAMILIES)
    font.setPixelSize(size)
    font.setWeight(weight)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return font


def font(style: TextStyle) -> QFont:
    spec = style.value
    result = make_font(spec.size, spec.weight, mono=spec.mono)
    if spec.kicker:
        # CSS letter-spacing .08em, text-transform uppercase.
        result.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 108)
        result.setCapitalization(QFont.Capitalization.AllUppercase)
    return result


def line_height(style: TextStyle) -> int:
    return style.value.line


def apply(widget: QWidget, style: TextStyle) -> None:
    widget.setFont(font(style))


def base_font() -> QFont:
    return font(TextStyle.BODY)
