"""Style sheet and QPalette generated from the colour tokens.

The native ``windows11`` style stays underneath; the sheet only covers the widgets listed in
the design notes. Fonts are deliberately absent: style sheet fonts override ``setFont()``.
Custom-painted widgets read the palette from the theme manager instead.
"""

from __future__ import annotations

from PySide6.QtGui import QPalette

from radio_video.ui.theme.tokens import Palette, css

ColorGroup = QPalette.ColorGroup
ColorRole = QPalette.ColorRole


def build_palette(p: Palette) -> QPalette:
    result = QPalette()
    roles = {
        ColorRole.Window: p.bg,
        ColorRole.WindowText: p.text,
        ColorRole.Base: p.raised,
        ColorRole.AlternateBase: p.surface,
        ColorRole.Text: p.text,
        ColorRole.Button: p.raised,
        ColorRole.ButtonText: p.text,
        ColorRole.BrightText: p.on_accent,
        ColorRole.Highlight: p.accent_tint,
        ColorRole.HighlightedText: p.text,
        ColorRole.Link: p.accent_text,
        ColorRole.LinkVisited: p.accent_text,
        ColorRole.ToolTipBase: p.tip_bg,
        ColorRole.ToolTipText: p.tip_fg,
        ColorRole.PlaceholderText: p.text_2,
        ColorRole.Accent: p.accent,
        ColorRole.Mid: p.border_ctl,
        ColorRole.Midlight: p.border,
        ColorRole.Dark: p.rule,
        ColorRole.Shadow: p.rule,
        ColorRole.Light: p.raised,
    }
    for role, color in roles.items():
        result.setColor(role, color)
    for role in (ColorRole.WindowText, ColorRole.Text, ColorRole.ButtonText):
        result.setColor(ColorGroup.Disabled, role, p.text_dis)
    result.setColor(ColorGroup.Disabled, ColorRole.Base, p.sunken)
    result.setColor(ColorGroup.Disabled, ColorRole.Button, p.sunken)
    return result


def build_stylesheet(p: Palette) -> str:
    c = {name: css(p.color(name)) for name in p.__dataclass_fields__ if name != "scheme"}
    return f"""
QMainWindow, QDialog {{ background: {c["bg"]}; }}
QToolTip {{
    background: {c["tip_bg"]}; color: {c["tip_fg"]};
    border: none; border-radius: 4px; padding: 6px 10px;
}}
QMenuBar {{ background: {c["bg"]}; color: {c["text"]}; padding: 2px 4px; spacing: 2px; }}
QMenuBar::item {{ background: transparent; padding: 2px 10px; border-radius: 4px; }}
QMenuBar::item:selected, QMenuBar::item:pressed {{ background: {c["hover"]}; }}
QStatusBar {{ background: {c["bg"]}; color: {c["text_2"]}; border-top: 1px solid {c["border"]}; }}
QStatusBar::item {{ border: none; }}
QSplitter::handle {{ background: {c["rule"]}; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget[transparent="true"] {{ background: transparent; }}

QFrame[surface="bg"] {{ background: {c["bg"]}; }}
QFrame[surface="surface"] {{ background: {c["surface"]}; }}
QFrame[surface="sunken"] {{ background: {c["sunken"]}; }}
QFrame[card="true"] {{
    background: {c["raised"]}; border: 1px solid {c["border"]}; border-radius: 6px;
}}
QFrame[rule="h"] {{ background: {c["rule"]}; border: none; }}
QFrame[hairline="true"] {{ background: {c["border"]}; border: none; }}

QLabel {{ color: {c["text"]}; background: transparent; }}
QLabel[tone="secondary"] {{ color: {c["text_2"]}; }}
QLabel[tone="disabled"] {{ color: {c["text_dis"]}; }}
QLabel[tone="accent"] {{ color: {c["accent_text"]}; }}
QLabel[tone="success"] {{ color: {c["success"]}; }}
QLabel[tone="warning"] {{ color: {c["warning"]}; }}
QLabel[tone="danger"] {{ color: {c["danger"]}; }}
QLabel:disabled {{ color: {c["text_dis"]}; }}

QPlainTextEdit#Log {{
    background: {c["sunken"]}; color: {c["text"]};
    border: 1px solid {c["border"]}; border-radius: 4px; padding: 6px 8px;
}}

QLineEdit {{
    background: {c["raised"]}; color: {c["text"]};
    border: 1px solid {c["border_ctl"]}; border-radius: 4px; padding: 0 10px; min-height: 30px;
    selection-background-color: {c["accent_tint"]}; selection-color: {c["text"]};
}}
QLineEdit:hover {{ border-color: {c["text_2"]}; }}
QLineEdit:focus {{ border-color: {c["accent"]}; border-bottom: 2px solid {c["accent"]}; }}
QLineEdit:disabled {{
    background: {c["sunken"]}; color: {c["text_dis"]}; border-color: {c["border"]};
}}

QTableView {{
    background: transparent; color: {c["text"]}; border: none; outline: 0;
    gridline-color: {c["border"]};
    selection-background-color: {c["accent_tint"]}; selection-color: {c["text"]};
}}
QTableView::item {{ border-bottom: 1px solid {c["border"]}; padding: 0 10px; }}
QTableView::item:hover {{ background: {c["hover"]}; }}
QTableView::item:selected {{ background: {c["accent_tint"]}; color: {c["text"]}; }}
QHeaderView {{ background: transparent; border: none; }}
QTableCornerButton::section {{ background: transparent; border: none; }}

QComboBox QAbstractItemView {{
    background: {c["raised"]}; color: {c["text"]};
    border: 1px solid {c["border"]}; border-radius: 6px; padding: 4px; outline: 0;
    selection-background-color: transparent;
}}
"""
