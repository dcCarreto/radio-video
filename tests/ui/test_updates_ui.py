"""Updates in the main window: checking, downloading, installing and the Settings rows."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from pytestqt.qtbot import QtBot

from radio_video import __version__
from radio_video.ffmpeg import FFmpegTools
from radio_video.models.presets import OUTPUT_FORMATS
from radio_video.services.updates import Update, UpdateService
from radio_video.ui.pages.settings_page import UPDATE_DOWNLOAD, UPDATE_OPEN_PAGE, UPDATE_RESTART
from radio_video.ui.state import Page
from radio_video.ui.widgets.badge import BadgeTone
from radio_video.ui.windows.main_window import (
    UPDATES_AUTOMATIC_KEY,
    Engine,
    MainWindow,
    UpdateStatus,
)

ALL_ENCODERS = frozenset(e for fmt in OUTPUT_FORMATS for e in fmt.encoders)
UPDATE = Update("9.0.0", "https://example.com/v9", "https://example.com/s.exe", "s.exe", 1000, "0")


class _FakeUpdates(UpdateService):
    """Records requests; tests emit the results themselves."""

    def __init__(self, folder: Path) -> None:
        super().__init__(folder)
        self.checks = 0
        self.downloads: list[Update] = []
        self.canceled = False

    def check(self) -> bool:
        self.checks += 1
        return True

    def download(self, update: Update) -> bool:
        self.downloads.append(update)
        return True

    def cancel(self) -> None:
        self.canceled = True


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> Iterator[MainWindow]:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    engine = Engine(FFmpegTools(tmp_path / "ffmpeg.exe", tmp_path / "ffprobe.exe"), ALL_ENCODERS)
    main = MainWindow(
        engine,
        settings=settings,
        history_path=tmp_path / "history.json",
        updates=_FakeUpdates(tmp_path / "updates"),
    )
    main.installable = True
    main.launched = []  # type: ignore[attr-defined]
    main.launch_installer = lambda path, relaunch: main.launched.append((path, relaunch)) or True  # type: ignore[attr-defined]
    main.opened = []  # type: ignore[attr-defined]
    main.open_url = main.opened.append  # type: ignore[attr-defined]
    qtbot.addWidget(main)
    yield main
    main.machine._state = main.machine.state.__class__()


def _fake(window: MainWindow) -> _FakeUpdates:
    assert isinstance(window.updates, _FakeUpdates)
    return window.updates


def _status(window: MainWindow) -> UpdateStatus:
    return window.update_status


def _installer(tmp_path: Path) -> Path:
    path = tmp_path / "Radio-Video-Setup-9.0.0.exe"
    path.write_bytes(b"MZ")
    return path


def test_settings_show_the_running_version_and_automatic_updates_on(window: MainWindow) -> None:
    page = window.settings_page
    assert page.update_badge.text() == f"Version {__version__}"
    assert page.automatic_switch.isChecked()
    assert page.update_action.isHidden() and page.update_notes.isHidden()


def test_check_now_reports_the_latest_version(window: MainWindow) -> None:
    page = window.settings_page
    page.update_check.click()
    assert _fake(window).checks == 1
    assert _status(window) is UpdateStatus.CHECKING
    assert not page.update_check.isEnabled()
    assert page.update_text.text() == "Checking for a new version…"
    # A second click while checking does nothing.
    window.check_for_updates()
    assert _fake(window).checks == 1

    window.updates.checked.emit(None)
    assert _status(window) is UpdateStatus.CURRENT
    assert page.update_badge.text() == "Up to date"
    assert page.update_badge._tone is BadgeTone.SUCCESS
    assert page.update_text.text() == f"Version {__version__} is the latest."
    assert page.update_check.isEnabled()


def test_automatic_updates_download_and_offer_a_restart(
    window: MainWindow, qtbot: QtBot, tmp_path: Path
) -> None:
    window.show()
    window.check_for_updates(automatic=True)
    window.updates.checked.emit(UPDATE)
    assert _fake(window).downloads == [UPDATE]
    assert _status(window) is UpdateStatus.DOWNLOADING
    window.updates.progressed.emit(450, 1000)
    page = window.settings_page
    assert page.update_text.text() == "Downloading version 9.0.0… 45%"
    assert page.update_action.isHidden()

    window.updates.downloaded.emit(_installer(tmp_path))
    assert _status(window) is UpdateStatus.READY
    assert page.update_badge.text() == "Ready to install"
    assert page.update_action.text() == "Restart and Update"
    assert window.status_item.text.text() == "Version 9.0.0 installs when you close Radio/Video"
    dialog = window.update_dialog
    assert dialog is not None and dialog.isVisible()
    assert "9.0.0" in dialog.title.text()

    dialog.restart_button.click()
    assert window.launched == [(tmp_path / "Radio-Video-Setup-9.0.0.exe", True)]  # type: ignore[attr-defined]
    assert not window.isVisible()


def test_later_installs_when_the_window_closes(
    window: MainWindow, qtbot: QtBot, tmp_path: Path
) -> None:
    window.show()
    window.check_for_updates(automatic=True)
    window.updates.checked.emit(UPDATE)
    window.updates.downloaded.emit(_installer(tmp_path))
    dialog = window.update_dialog
    assert dialog is not None
    dialog.later_button.click()
    assert window.update_dialog is None and window.launched == []  # type: ignore[attr-defined]
    window.close()
    # Installed on the way out, without opening Radio/Video again.
    assert window.launched == [(tmp_path / "Radio-Video-Setup-9.0.0.exe", False)]  # type: ignore[attr-defined]
    assert _fake(window).canceled


def test_with_automatic_updates_off_the_user_starts_the_download(
    window: MainWindow, tmp_path: Path
) -> None:
    page = window.settings_page
    page.automatic_switch.click()
    assert window.settings.value(UPDATES_AUTOMATIC_KEY, type=bool) is False
    window.start_automatic_updates(0)
    window.check_for_updates(automatic=True)
    assert _fake(window).checks == 0

    window.check_for_updates()
    window.updates.checked.emit(UPDATE)
    assert _fake(window).downloads == []
    assert _status(window) is UpdateStatus.AVAILABLE
    assert page.update_badge.text() == "New version"
    assert page.update_text.text() == f"Version 9.0.0 is available. You have {__version__}."
    assert page.update_action.text() == "Download and Install"
    assert not page.update_notes.isHidden()

    page.update_notes.click()
    assert window.opened == ["https://example.com/v9"]  # type: ignore[attr-defined]
    page.update_action.click()
    assert _fake(window).downloads == [UPDATE]
    # Asked for by the user, so it installs as soon as it is downloaded.
    window.updates.downloaded.emit(_installer(tmp_path))
    assert window.update_dialog is None
    assert window.launched == [(tmp_path / "Radio-Video-Setup-9.0.0.exe", True)]  # type: ignore[attr-defined]


def test_turning_automatic_updates_on_checks_right_away(window: MainWindow) -> None:
    window.settings.setValue(UPDATES_AUTOMATIC_KEY, False)
    window.settings_page.show_view(window.settings_view())
    assert not window.settings_page.automatic_switch.isChecked()
    window.settings_page.automatic_switch.click()
    assert window.updates_automatic
    assert _fake(window).checks == 1


def test_a_copy_not_installed_with_the_installer_opens_the_download_page(
    window: MainWindow,
) -> None:
    window.installable = False
    window.check_for_updates(automatic=True)
    window.updates.checked.emit(UPDATE)
    assert _fake(window).downloads == []
    page = window.settings_page
    assert page.update_action.text() == "Open Download Page"
    assert page.update_notes.isHidden()
    assert "download page" in page.automatic_help.text()
    window._on_update_action(UPDATE_OPEN_PAGE)
    assert window.opened == ["https://example.com/v9"]  # type: ignore[attr-defined]
    window._on_update_action(UPDATE_DOWNLOAD)
    assert _fake(window).downloads == []


def test_failures_are_shown_and_can_be_retried(window: MainWindow) -> None:
    page = window.settings_page
    window.check_for_updates()
    window.updates.check_failed.emit("Could not reach GitHub (offline)")
    assert _status(window) is UpdateStatus.FAILED
    assert page.update_badge._tone is BadgeTone.WARNING
    assert page.update_text.text() == "Couldn’t check for updates: Could not reach GitHub (offline)"
    assert page.update_action.isHidden()

    window.check_for_updates()
    window.updates.checked.emit(UPDATE)
    window.updates.download_failed.emit("The download failed (timed out)")
    assert page.update_text.text() == (
        "Version 9.0.0 couldn’t be downloaded: The download failed (timed out)"
    )
    assert page.update_action.text() == "Download and Install"
    page.update_action.click()
    assert len(_fake(window).downloads) == 2


def test_no_restart_during_a_conversion(window: MainWindow, tmp_path: Path) -> None:
    window.check_for_updates(automatic=True)
    window.updates.checked.emit(UPDATE)
    window._busy = lambda: True  # type: ignore[method-assign]
    window.updates.downloaded.emit(_installer(tmp_path))
    # Not offered over a conversion; the Settings button refuses until it ends.
    assert window.update_dialog is None
    window._on_update_action(UPDATE_RESTART)
    assert window.launched == []  # type: ignore[attr-defined]
    assert "Finish or stop the conversion" in window.statusBar().currentMessage()


def test_the_help_menu_checks_for_updates(window: MainWindow) -> None:
    window.update_action.trigger()
    assert window.machine.state.page is Page.SETTINGS
    assert _fake(window).checks == 1


def test_closing_without_a_downloaded_update_runs_nothing(window: MainWindow) -> None:
    window.close()
    assert window.launched == []  # type: ignore[attr-defined]


def test_a_failed_installer_start_keeps_the_window_open(window: MainWindow, tmp_path: Path) -> None:
    window.show()
    window.launch_installer = lambda _path, _relaunch: False
    window.check_for_updates()
    window.updates.checked.emit(UPDATE)
    window.updates.downloaded.emit(_installer(tmp_path))
    assert window.update_dialog is not None
    window.update_dialog.reject()
    assert not window.install_update()
    assert window.isVisible()
    assert "didn’t start" in window.statusBar().currentMessage()
