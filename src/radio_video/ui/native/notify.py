"""Windows notifications when a conversion ends while the window is in the background.

Qt Widgets has no toast API, so a tray icon is shown only while a conversion runs and its
balloon message, which Windows 10 and 11 display as a notification, reports the result.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QSystemTrayIcon, QWidget

from radio_video.ui import icons
from radio_video.ui import strings as s
from radio_video.ui.strings import tr

LINGER_MS = 10_000
MESSAGE_MS = 8_000


class Notifier(QObject):
    activated = Signal()

    def __init__(self, window: QWidget) -> None:
        super().__init__(window)
        self._window = window
        self._tray: QSystemTrayIcon | None = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray = QSystemTrayIcon(icons.app_icon(), self)
            self._tray.setToolTip(tr(s.APP_NAME))
            self._tray.messageClicked.connect(self.activated)
            self._tray.activated.connect(lambda _reason: self.activated.emit())
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._hide)

    def conversion_started(self) -> None:
        self._hide_timer.stop()
        if self._tray is not None:
            self._tray.show()

    def conversion_finished(self, name: str) -> None:
        self._notify(tr(s.NOTIFY_DONE_TITLE), tr(s.NOTIFY_DONE_TEXT).format(name=name), False)

    def conversion_failed(self) -> None:
        self._notify(tr(s.NOTIFY_FAILED_TITLE), tr(s.NOTIFY_FAILED_TEXT), True)

    def conversion_stopped(self) -> None:
        self._hide()

    def _notify(self, title: str, text: str, error: bool) -> None:
        if self._tray is None:
            return
        if not self._window.isActiveWindow():
            icon = (
                QSystemTrayIcon.MessageIcon.Warning
                if error
                else QSystemTrayIcon.MessageIcon.Information
            )
            self._tray.show()
            self._tray.showMessage(title, text, icon, MESSAGE_MS)
            self._hide_timer.start(LINGER_MS)
        else:
            self._hide()

    def _hide(self) -> None:
        if self._tray is not None:
            self._tray.hide()
