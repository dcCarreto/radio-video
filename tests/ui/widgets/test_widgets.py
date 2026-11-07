from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QApplication, QWidget
from pytestqt.qtbot import QtBot

from radio_video.ui.gallery_components import (
    DEMO_STREAMS,
    demo_format_groups,
    make_drop_zone,
    quality_options,
)
from radio_video.ui.theme import fonts
from radio_video.ui.theme.fonts import TextStyle
from radio_video.ui.widgets.button import Button, ButtonKind, ButtonSize
from radio_video.ui.widgets.drop_zone import DropRefusal, DropState, check_drop
from radio_video.ui.widgets.facts_grid import FactsGrid
from radio_video.ui.widgets.format_combo import KEY_ROLE, FormatCombo
from radio_video.ui.widgets.painting import elide, text_width
from radio_video.ui.widgets.player import Player, format_clock
from radio_video.ui.widgets.progress import ProgressBar
from radio_video.ui.widgets.segmented import SegmentedControl
from radio_video.ui.widgets.step_strip import StepStrip
from radio_video.ui.widgets.streams_table import COLUMN_TITLE, StreamsTable
from radio_video.ui.widgets.tab_strip import TabSpec, TabStrip


@pytest.mark.parametrize("text", ["Pressed", "Open File…", "Copy", "Interview – Lisbon (1).mp4"])
def test_text_never_elides_at_its_own_width(qapp: QApplication, text: str) -> None:
    font = fonts.font(TextStyle.BODY_STRONG)
    assert elide(font, text, Qt.TextElideMode.ElideRight, text_width(font, text)) == text


def test_button_size_hint_fits_label_icon_and_shortcut(qapp: QApplication) -> None:
    button = Button(
        "Convert",
        ButtonKind.PRIMARY,
        icon="ArrowRightLeft",
        shortcut_hint="Ctrl+Enter",
        size=ButtonSize.LARGE,
    )
    hint = button.sizeHint()
    assert hint.height() == 40
    label = text_width(button.font(), "Convert")
    shortcut = text_width(fonts.make_font(12), "Ctrl+Enter")
    assert hint.width() == 16 * 2 + 16 + 8 + label + 16 + shortcut
    assert button.accessibleDescription() == "Ctrl+Enter"


def test_icon_only_button_is_square_and_named(qapp: QApplication) -> None:
    button = Button("Play (Space)", ButtonKind.SUBTLE, icon="Play", icon_only=True)
    assert button.sizeHint().width() == button.sizeHint().height() == 32
    assert button.accessibleName() == "Play (Space)"
    assert button.toolTip() == "Play (Space)"


def test_segmented_control_arrow_keys_change_value(qtbot: QtBot) -> None:
    control = SegmentedControl(quality_options(), accessible_name="Quality")
    qtbot.addWidget(control)
    control.set_value("balanced")
    control.show()
    buttons = control.buttons()
    assert [b.focusPolicy() for b in buttons] == [
        Qt.FocusPolicy.ClickFocus,
        Qt.FocusPolicy.StrongFocus,
        Qt.FocusPolicy.ClickFocus,
    ]
    with qtbot.waitSignal(control.changed) as blocker:
        qtbot.keyClick(buttons[1], Qt.Key.Key_Right)
    assert blocker.args == ["small"]
    assert control.value() == "small"
    qtbot.keyClick(buttons[2], Qt.Key.Key_Right)
    assert control.value() == "small"


def test_tab_strip_switches_with_arrow_keys(qtbot: QtBot) -> None:
    strip = TabStrip(
        [
            TabSpec("main", "Convert", "ArrowRightLeft"),
            TabSpec("queue", "Queue", "ListOrdered", planned=True),
            TabSpec("settings", "Settings", "Settings", planned=True, trailing=True),
        ]
    )
    qtbot.addWidget(strip)
    assert strip.current() == "main"
    with qtbot.waitSignal(strip.current_changed) as blocker:
        qtbot.keyClick(strip.buttons()[0], Qt.Key.Key_Left)
    assert blocker.args == ["settings"]
    assert strip.buttons()[2].accessibleDescription() == "Planned"


def test_check_drop_rules(tmp_path: Path) -> None:
    file = tmp_path / "clip.mp4"
    file.write_bytes(b"")
    assert check_drop([file], busy=False) is None
    assert check_drop([file], busy=True) is DropRefusal.BUSY
    # Several files go to the queue, even while converting.
    assert check_drop([file, file], busy=False) is None
    assert check_drop([file, file], busy=True) is None
    assert check_drop([file, tmp_path], busy=False) is DropRefusal.FOLDER
    assert check_drop([], busy=False) is DropRefusal.SEVERAL_FILES
    assert check_drop([tmp_path], busy=False) is DropRefusal.FOLDER


def _mime(*paths: Path) -> QMimeData:
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path)) for path in paths])
    return mime


def test_drop_zone_accepts_one_file(qtbot: QtBot, tmp_path: Path) -> None:
    zone = make_drop_zone()
    qtbot.addWidget(zone)
    file = tmp_path / "clip.mp4"
    file.write_bytes(b"")
    mime = _mime(file)
    enter = QDragEnterEvent(
        QPointF(5, 5),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(zone, enter)
    # Compare values: mypy would otherwise narrow the property for the rest of the test.
    assert zone.state.value == DropState.OVER.value

    drop = QDropEvent(
        QPointF(5, 5),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    with qtbot.waitSignal(zone.file_dropped) as blocker:
        QApplication.sendEvent(zone, drop)
    assert blocker.args == [file]
    assert zone.state is DropState.IDLE


def _enter(zone: QWidget, mime: QMimeData) -> None:
    enter = QDragEnterEvent(
        QPointF(5, 5),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(zone, enter)


def test_drop_zone_explains_refusal(qtbot: QtBot, tmp_path: Path) -> None:
    zone = make_drop_zone()
    qtbot.addWidget(zone)
    # Events do not own their mime data; keep it alive for the duration of the test.
    mime = _mime(tmp_path / "a.mp4", tmp_path)
    _enter(zone, mime)
    assert zone.state is DropState.BLOCKED
    assert "Drop files, not folders" in zone.blocked_text.text()
    assert zone.title.text() == "Can’t open a file right now"


def test_several_files_go_to_the_queue(qtbot: QtBot, tmp_path: Path) -> None:
    zone = make_drop_zone()
    qtbot.addWidget(zone)
    files = [tmp_path / "a.mp4", tmp_path / "b.mp4"]
    for file in files:
        file.write_bytes(b"")
    mime = _mime(*files)
    _enter(zone, mime)
    assert zone.state is DropState.OVER
    assert zone.title.text() == "Release to add 2 files to the queue"
    drop = QDropEvent(
        QPointF(5, 5),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    with qtbot.waitSignal(zone.files_dropped) as blocker:
        QApplication.sendEvent(zone, drop)
    assert blocker.args == [files]


def test_format_combo_groups_and_keys(qtbot: QtBot) -> None:
    combo = FormatCombo()
    qtbot.addWidget(combo)
    combo.set_groups(demo_format_groups(), "opus")
    assert combo.current_key() == "opus"
    assert combo.keys()[:2] == ["mp4-h264", "mp4-h265"]
    header = combo.model().index(0, 0)
    assert not header.flags() & Qt.ItemFlag.ItemIsSelectable
    assert header.data(KEY_ROLE) is None
    with qtbot.waitSignal(combo.format_changed) as blocker:
        combo.set_current_key("flac")
    assert blocker.args == ["flac"]
    assert "identical to the source" in combo.accessibleDescription()


def test_format_combo_defaults_to_first_option(qtbot: QtBot) -> None:
    combo = FormatCombo()
    qtbot.addWidget(combo)
    combo.set_groups(demo_format_groups(), "missing")
    assert combo.current_key() == "mp4-h264"


def test_progress_bar_announces_in_ten_percent_steps(qapp: QApplication) -> None:
    bar = ProgressBar()
    bar.set_fraction(0.42)
    assert bar.fraction() == pytest.approx(0.42)
    assert bar.value() == 40
    bar.set_fraction(0.499)
    assert bar.value() == 40
    bar.set_indeterminate(True)
    assert bar.is_indeterminate()
    bar.set_fraction(1.0)
    assert not bar.is_indeterminate()
    assert bar.value() == 100


def test_streams_table_hides_title_when_compact(qtbot: QtBot) -> None:
    table = StreamsTable(["#", "Type", "Codec", "Details", "Language", "Title"])
    qtbot.addWidget(table)
    table.set_rows(DEMO_STREAMS)
    assert table.model().rowCount() == 12
    assert not table.isColumnHidden(COLUMN_TITLE)
    table.set_compact(True)
    assert table.isColumnHidden(COLUMN_TITLE)


def test_facts_grid_moves_title_to_own_row_when_narrow(qtbot: QtBot) -> None:
    grid = FactsGrid(["Container", "Duration", "Size", "Bitrate"], "Title")
    qtbot.addWidget(grid)
    grid.set_values(["Matroska / WebM", "2:13", "186.4 MB", "11.2 Mb/s"], "Long title")
    grid.resize(1000, 60)
    grid.show()
    assert not grid.is_narrow()
    grid.resize(560, 120)
    qtbot.waitUntil(grid.is_narrow)
    assert grid.wide.value.toolTip() == "Long title"


def test_step_strip_uses_short_labels_when_narrow(qtbot: QtBot) -> None:
    strip = StepStrip(["Open a file", "Check what’s inside"], ["Open", "Check"])
    qtbot.addWidget(strip)
    strip.set_current(1)
    strip.resize(1400, 40)
    assert not strip.compact()
    strip.resize(150, 40)
    assert strip.compact()
    assert strip.accessibleDescription() == "Step 2 of 2: Check what’s inside"


def test_player_swaps_play_and_mute_labels(qtbot: QtBot) -> None:
    player = Player()
    qtbot.addWidget(player)
    player.set_duration(15_000)
    player.set_position(4_000)
    assert player.time.text() == "0:04 / 0:15"
    player.set_playing(True)
    assert player.play_button.toolTip() == "Pause (Space)"
    player.set_muted(True)
    assert player.mute_button.accessibleName() == "Unmute (M)"
    assert format_clock(133_400) == "2:13"
