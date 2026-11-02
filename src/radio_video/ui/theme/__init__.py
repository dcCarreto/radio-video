"""Theme manager: follows the Windows colour scheme and restyles the application."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtWidgets import QApplication, QStyleFactory

from radio_video.ui.theme import fonts
from radio_video.ui.theme.qss import build_palette, build_stylesheet
from radio_video.ui.theme.tokens import Palette, Scheme, palette_for

logger = logging.getLogger(__name__)

NATIVE_STYLE = "windows11"

__all__ = ["Palette", "Scheme", "ThemeManager", "current", "palette"]


def scheme_from_qt(value: Qt.ColorScheme) -> Scheme:
    return Scheme.DARK if value is Qt.ColorScheme.Dark else Scheme.LIGHT


class ThemeManager(QObject):
    """Applies the palette, style sheet and base font, and re-applies them on scheme changes.

    ``override`` forces light or dark (used by the UI gallery and later by Settings);
    ``None`` follows Windows.
    """

    changed = Signal(Palette)

    def __init__(self, app: QApplication) -> None:
        super().__init__(app)
        self._app = app
        self._override: Scheme | None = None
        self._applying = False
        self._palette = palette_for(self._system_scheme())
        styles = [key.lower() for key in QStyleFactory.keys()]  # noqa: SIM118
        if NATIVE_STYLE in styles:
            app.setStyle(NATIVE_STYLE)
        app.styleHints().colorSchemeChanged.connect(self._on_system_scheme_changed)
        self.apply()

    @property
    def app(self) -> QApplication:
        return self._app

    @property
    def palette(self) -> Palette:
        return self._palette

    @property
    def scheme(self) -> Scheme:
        return self._palette.scheme

    @property
    def override(self) -> Scheme | None:
        return self._override

    def set_override(self, scheme: Scheme | None) -> None:
        self._override = scheme
        hints = self._app.styleHints()
        self._applying = True
        try:
            if scheme is None:
                hints.unsetColorScheme()
            else:
                hints.setColorScheme(
                    Qt.ColorScheme.Dark if scheme is Scheme.DARK else Qt.ColorScheme.Light
                )
        finally:
            self._applying = False
        self.apply()

    def apply(self) -> None:
        scheme = self._override or self._system_scheme()
        self._palette = palette_for(scheme)
        self._app.setFont(fonts.base_font())
        self._app.setPalette(build_palette(self._palette))
        self._app.setStyleSheet(build_stylesheet(self._palette))
        logger.debug("Applied %s theme", scheme.value)
        self.changed.emit(self._palette)

    def _system_scheme(self) -> Scheme:
        return scheme_from_qt(self._app.styleHints().colorScheme())

    @Slot(Qt.ColorScheme)
    def _on_system_scheme_changed(self, _scheme: Qt.ColorScheme) -> None:
        if self._applying or self._override is not None:
            return
        self.apply()


_manager: ThemeManager | None = None


def install(app: QApplication) -> ThemeManager:
    global _manager
    if _manager is None or _manager.app is not app:
        _manager = ThemeManager(app)
    return _manager


def current() -> ThemeManager:
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        raise RuntimeError("The theme needs a QApplication")
    return install(app)


def palette() -> Palette:
    return current().palette
