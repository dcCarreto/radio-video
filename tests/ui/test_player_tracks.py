from __future__ import annotations

from PySide6.QtCore import QLocale
from PySide6.QtGui import QColor, QImage
from PySide6.QtMultimedia import QMediaMetaData
from pytestqt.qtbot import QtBot

from radio_video.ui.widgets.player import Player
from radio_video.ui.widgets.video_canvas import VideoCanvas
from radio_video.ui.windows.preview_window import track_label


def _metadata(language: QLocale.Language | None = None, title: str | None = None) -> QMediaMetaData:
    data = QMediaMetaData()
    if language is not None:
        data.insert(QMediaMetaData.Key.Language, language)
    if title is not None:
        data.insert(QMediaMetaData.Key.Title, title)
    return data


def test_track_labels() -> None:
    assert track_label(0, _metadata()) == "Track 1"
    assert track_label(1, _metadata(QLocale.Language.English, "English dub")) == (
        "Track 2 · English · English dub"
    )
    assert track_label(2, _metadata(QLocale.Language.AnyLanguage, "  ")) == "Track 3"


def test_track_menus_emit_the_chosen_track(qtbot: QtBot) -> None:
    bar = Player()
    qtbot.addWidget(bar)
    bar.audio_menu.set_tracks([(0, "Track 1"), (1, "Track 2")], 0, visible=True)
    bar.subtitle_menu.set_tracks([(-1, "Off"), (0, "Track 1")], -1, visible=True)
    assert bar.audio_menu.button.isVisibleTo(bar)
    assert [a.isChecked() for a in bar.subtitle_menu.menu.actions()] == [True, False]
    with qtbot.waitSignal(bar.audio_track_chosen) as audio:
        bar.audio_menu.menu.actions()[1].trigger()
    assert audio.args == [1]
    with qtbot.waitSignal(bar.subtitle_track_chosen) as subtitle:
        bar.subtitle_menu.menu.actions()[0].trigger()
    assert subtitle.args == [-1]
    bar.audio_menu.set_active(1, [0, 1])
    assert [a.isChecked() for a in bar.audio_menu.menu.actions()] == [False, True]
    # Rebuilding the list replaces it instead of adding to it.
    bar.audio_menu.set_tracks([(0, "Track 1")], 0, visible=False)
    assert len(bar.audio_menu.menu.actions()) == 1
    assert not bar.audio_menu.button.isVisibleTo(bar)


def test_canvas_draws_subtitles_over_the_picture(qtbot: QtBot) -> None:
    canvas = VideoCanvas("Original", "Play")
    qtbot.addWidget(canvas)
    canvas.resize(640, 360)
    frame = QImage(640, 360, QImage.Format.Format_RGB32)
    frame.fill(QColor("#3060a0"))
    canvas.show_image(frame)
    plain = canvas.grab().toImage()
    canvas.set_subtitle("Ola, mundo")
    assert canvas.subtitle == "Ola, mundo"
    with_text = canvas.grab().toImage()
    # The band under the text darkens the lower middle of the picture.
    point = (320, 360 - 40)
    assert with_text.pixelColor(*point).lightness() < plain.pixelColor(*point).lightness()
    canvas.clear()
    assert canvas.subtitle == ""
