"""Gallery page with every component in its states, mirroring the design system sheet."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from radio_video.ui import strings as s
from radio_video.ui.icons import IconName
from radio_video.ui.strings import tr
from radio_video.ui.theme.fonts import TextStyle
from radio_video.ui.widgets.badge import Badge, BadgeTone
from radio_video.ui.widgets.button import Button, ButtonKind, ButtonSize, Expander
from radio_video.ui.widgets.checks import CheckBox, LabeledCheck, RadioButton, Switch
from radio_video.ui.widgets.drop_zone import DropRefusal, DropState, DropZone
from radio_video.ui.widgets.facts_grid import FactsGrid
from radio_video.ui.widgets.format_combo import FormatCombo, FormatGroup, FormatOption
from radio_video.ui.widgets.frames import CodeBlock, FieldBox, Note, PlannedBanner
from radio_video.ui.widgets.labels import kicker, label
from radio_video.ui.widgets.player import Player, Slider
from radio_video.ui.widgets.progress import ProgressBlock, ProgressState
from radio_video.ui.widgets.segmented import SegmentedControl, SegmentOption
from radio_video.ui.widgets.step_strip import StepStrip
from radio_video.ui.widgets.streams_table import StreamRow, StreamsTable
from radio_video.ui.widgets.tab_strip import TabSpec, TabStrip

DEMO_STREAMS = [
    StreamRow(1, "Video", "Film", "h264 (High)", "1920×1080 · 23.976 fps · 10.4 Mb/s", "—", "Main"),
    StreamRow(
        2,
        "Audio",
        "Music",
        "aac (LC)",
        "48 kHz · 5.1 · 384 kb/s",
        "Portuguese",
        "Original mix",
        True,
    ),
    StreamRow(
        3, "Audio", "Music", "aac (LC)", "48 kHz · Stereo · 192 kb/s", "English", "English dub"
    ),
    StreamRow(
        4,
        "Audio",
        "Music",
        "opus",
        "48 kHz · Stereo · 128 kb/s",
        "Portuguese",
        "Director’s commentary",
    ),
    StreamRow(5, "Subtitle", "Captions", "subrip", "Text", "Portuguese", "", True),
    StreamRow(6, "Subtitle", "Captions", "subrip", "Text", "English", ""),
    StreamRow(7, "Subtitle", "Captions", "subrip", "Text", "Spanish", ""),
    StreamRow(8, "Subtitle", "Captions", "subrip", "Text", "French", ""),
    StreamRow(9, "Subtitle", "Captions", "subrip", "Text", "German", ""),
    StreamRow(10, "Subtitle", "Captions", "subrip", "Text", "Italian", ""),
    StreamRow(11, "Subtitle", "Captions", "subrip", "Text", "English", "Hearing impaired (SDH)"),
    StreamRow(12, "Cover art", "Image", "mjpeg", "600×600 · JPEG image", "—", "cover.jpg"),
]

VIDEO_FORMATS = (
    ("mp4-h264", "MP4 (H.264 + AAC)", True),
    ("mp4-h265", "MP4 (H.265 + AAC)", False),
    ("mkv-h264", "MKV (H.264 + AAC)", False),
    ("webm-vp9", "WebM (VP9 + Opus)", False),
)
AUDIO_FORMATS = (
    ("mp3", "MP3"),
    ("m4a-aac", "AAC (M4A)"),
    ("opus", "Opus"),
    ("ogg-vorbis", "Ogg Vorbis"),
    ("flac", "FLAC (lossless)"),
    ("wav", "WAV (lossless)"),
)


def demo_format_groups() -> list[FormatGroup]:
    def option(key: str, name: str, recommended: bool = False) -> FormatOption:
        return FormatOption(key, name, tr(s.FORMAT_DESCRIPTIONS[key]), recommended)

    return [
        FormatGroup(tr(s.FORMAT_GROUP_VIDEO), tuple(option(*f) for f in VIDEO_FORMATS)),
        FormatGroup(tr(s.FORMAT_GROUP_AUDIO_FROM_VIDEO), tuple(option(*f) for f in AUDIO_FORMATS)),
    ]


def quality_options() -> list[SegmentOption]:
    return [
        SegmentOption("high", tr(s.QUALITY_HIGH), tr(s.QUALITY_HIGH_SUB), tr(s.QUALITY_HIGH_HELP)),
        SegmentOption(
            "balanced",
            tr(s.QUALITY_BALANCED),
            tr(s.QUALITY_BALANCED_SUB),
            tr(s.QUALITY_BALANCED_HELP),
        ),
        SegmentOption(
            "small", tr(s.QUALITY_SMALL), tr(s.QUALITY_SMALL_SUB), tr(s.QUALITY_SMALL_HELP)
        ),
    ]


def make_drop_zone() -> DropZone:
    refusals = {
        DropRefusal.SEVERAL_FILES: s.DROP_BLOCKED_SEVERAL,
        DropRefusal.FOLDER: s.DROP_BLOCKED_SEVERAL,
        DropRefusal.BUSY: s.DROP_BLOCKED_CONVERTING,
    }
    return DropZone(
        titles={
            DropState.IDLE: tr(s.DROP_IDLE_TITLE),
            DropState.OVER: tr(s.DROP_OVER_TITLE),
            DropState.BLOCKED: tr(s.DROP_BLOCKED_TITLE),
        },
        idle_hint=tr(s.DROP_IDLE_HINT),
        idle_help=tr(s.DROP_IDLE_HELP),
        over_text=tr(s.DROP_OVER_TEXT),
        open_text=tr(s.ACTION_OPEN),
        open_shortcut=tr(s.SHORTCUT_OPEN),
        refusal_text=lambda refusal: tr(refusals[refusal]),
    )


def _spec(title: str, *widgets: QWidget) -> QWidget:
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    layout.addWidget(kicker(title, tone=None))
    for widget in widgets:
        layout.addWidget(widget)
    return box


def _row(*widgets: QWidget, spacing: int = 10, stretch: bool = True) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    for widget in widgets:
        layout.addWidget(widget)
    if stretch:
        layout.addStretch()
    return row


def _button_states() -> QWidget:
    grid = QWidget()
    layout = QGridLayout(grid)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setHorizontalSpacing(8)
    layout.setVerticalSpacing(8)
    states = ("Rest", "Hover", "Pressed", "Disabled")
    kinds: tuple[tuple[str, ButtonKind, IconName], ...] = (
        ("Primary", ButtonKind.PRIMARY, "ArrowRightLeft"),
        ("Secondary", ButtonKind.SECONDARY, "FolderOpen"),
        ("Subtle", ButtonKind.SUBTLE, "FolderOpen"),
        ("Destructive", ButtonKind.DANGER, "X"),
    )
    for row, (name, kind, icon) in enumerate(kinds):
        layout.addWidget(label(name, TextStyle.CAPTION, "secondary"), row, 0)
        for column, state in enumerate(states, start=1):
            button = Button(state, kind, icon=icon)
            if state == "Hover":
                button.setProperty("demoHover", True)
            elif state == "Pressed":
                button.setDown(True)
            elif state == "Disabled":
                button.setEnabled(False)
            layout.addWidget(button, row, column)
    layout.setColumnStretch(len(states) + 1, 1)
    return grid


def components_page() -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(24, 24, 24, 48)
    layout.setSpacing(28)

    convert = Button(
        tr(s.TAB_CONVERT),
        ButtonKind.PRIMARY,
        icon="ArrowRightLeft",
        shortcut_hint=tr(s.SHORTCUT_CONVERT),
        size=ButtonSize.LARGE,
    )
    convert.setFixedWidth(300)
    layout.addWidget(
        _spec(
            "Buttons: primary, secondary, subtle, destructive",
            _button_states(),
            _row(
                convert,
                Button("Small", icon="Copy", size=ButtonSize.SMALL),
                Button(tr(s.PLAYER_PLAY), ButtonKind.SUBTLE, icon="Play", icon_only=True),
            ),
            label(
                "Labels sit flush left; a wide button pushes its shortcut hint to the right "
                "edge. Only one primary button per screen.",
                TextStyle.CAPTION,
                "secondary",
                wrap=True,
            ),
        )
    )

    badges = [
        Badge("Done", BadgeTone.SUCCESS, "CircleCheck"),
        Badge("Converting", BadgeTone.ACCENT, "LoaderCircle"),
        Badge("Waiting", BadgeTone.NEUTRAL, "Clock"),
        Badge("Failed", BadgeTone.DANGER, "CircleX"),
        Badge("Canceled", BadgeTone.NEUTRAL, "Ban"),
        Badge("File moved", BadgeTone.WARNING, "TriangleAlert"),
        Badge("Converted preview", BadgeTone.ACCENT, "Eye"),
        Badge(tr(s.BADGE_RECOMMENDED), BadgeTone.ACCENT),
        Badge(tr(s.BADGE_DEFAULT)),
        Badge(tr(s.BADGE_PLANNED), BadgeTone.PLANNED),
    ]
    layout.addWidget(_spec("Status badges", _row(*badges, spacing=10)))

    combo = FormatCombo()
    combo.set_groups(demo_format_groups(), "mp4-h264")
    combo.setMaximumWidth(400)
    layout.addWidget(_spec("Format picker", combo))

    quality = SegmentedControl(quality_options(), accessible_name="Quality")
    quality.set_value("balanced")
    quality.setMaximumWidth(400)
    disabled_quality = SegmentedControl(quality_options(), accessible_name="Quality")
    disabled_quality.set_value("balanced")
    disabled_quality.setEnabled(False)
    disabled_quality.setMaximumWidth(400)
    mode = SegmentedControl(
        [SegmentOption("simple", "Simple"), SegmentOption("advanced", "Advanced", planned=True)],
        accessible_name="Mode",
    )
    mode.set_value("simple")
    mode.setMaximumWidth(400)
    lossless = Note(tr(s.QUALITY_LOSSLESS))
    layout.addWidget(
        _spec(
            "Quality selector, mode switch",
            quality,
            label(tr(s.QUALITY_BALANCED_HELP), TextStyle.CAPTION, "secondary"),
            disabled_quality,
            mode,
            lossless,
        )
    )

    folder = FieldBox("C:\\Users\\Ana\\Videos\\Exports")
    folder_row = _row(folder, Button(tr(s.BROWSE)), stretch=False)
    folder_row.setMaximumWidth(400)
    disabled_field = FieldBox("Disabled field", icon=None)
    disabled_field.setEnabled(False)
    disabled_field.setMaximumWidth(400)
    layout.addWidget(_spec("Folder picker, disabled field", folder_row, disabled_field))

    check_on, check_off = CheckBox("Checked"), CheckBox("Unchecked")
    check_on.setChecked(True)
    radio_on, radio_off = RadioButton("Selected"), RadioButton("Option")
    radio_on.setChecked(True)
    switch_on, switch_off = Switch(), Switch()
    switch_on.setChecked(True)
    slider = Slider()
    slider.setRange(0, 100)
    slider.setValue(45)
    slider.setFixedWidth(160)
    layout.addWidget(
        _spec(
            "Checkbox, radio, switch, slider",
            _row(
                check_on, check_off, radio_on, radio_off, switch_on, switch_off, slider, spacing=20
            ),
            LabeledCheck(
                CheckBox("Fast start for web playback"), "Moves the file index to the start."
            ),
        )
    )

    zones = []
    for drop_state, reason in (
        (DropState.IDLE, ""),
        (DropState.OVER, ""),
        (DropState.BLOCKED, tr(s.DROP_BLOCKED_CONVERTING)),
    ):
        zone = make_drop_zone()
        zone.set_state(drop_state, reason)
        zone.setFixedHeight(230)
        zones.append(zone)
    layout.addWidget(_spec("Drop zone: idle, drag-over, unavailable", *zones))

    table = StreamsTable([tr(c) for c in s.STREAM_COLUMNS])
    table.set_rows(DEMO_STREAMS)
    table.setFixedHeight(260)
    layout.addWidget(_spec("Streams list (12 tracks, scrolls with sticky header)", table))

    blocks = []
    for title, detail, fraction, state in (
        ("Determinate", "42% · 3.1× · 0:25 remaining", 0.42, None),
        ("Indeterminate", "Reading the file…", None, None),
        ("Success: Saved clip.mp3 (118.9 KB)", "", 1.0, ProgressState.SUCCESS),
        ("Failed at 66%", "", 0.66, ProgressState.FAILED),
        ("Canceled at 42%", "", 0.42, ProgressState.CANCELED),
    ):
        block = ProgressBlock()
        block.set_header(title, detail)
        if state is ProgressState.SUCCESS:
            block.set_status_icon("CircleCheck", "success")
        elif state is ProgressState.FAILED:
            block.set_status_icon("CircleX", "danger")
        elif state is ProgressState.CANCELED:
            block.set_status_icon("Ban")
        if state is not None:
            block.bar.set_state(state)
        if fraction is None:
            block.bar.set_indeterminate(True)
        else:
            block.bar.set_fraction(fraction)
        blocks.append(block)
    layout.addWidget(_spec("Progress block", *blocks))

    layout.addWidget(
        _spec(
            "Helper text, notes",
            label(
                "Helper text: one line under a control, in plain words.",
                TextStyle.CAPTION,
                "secondary",
            ),
            Note("This is the converted output, not the original file.", tone="accent"),
            Note("Some older devices can’t play H.265.", "TriangleAlert", "warning"),
            Note("Not enough disk space on drive C:.", "CircleX", "danger"),
            CodeBlock("winget install --id Gyan.FFmpeg -e", copy_text="Copy"),
            Expander("Technical details"),
        )
    )

    player = Player()
    player.set_duration(15_000)
    player.set_position(4_000)
    player.setMaximumWidth(560)
    layout.addWidget(_spec("Player controls (playback only)", player))

    tabs = TabStrip(
        [
            TabSpec("main", tr(s.TAB_CONVERT), "ArrowRightLeft"),
            TabSpec("queue", tr(s.TAB_QUEUE), "ListOrdered", planned=True),
            TabSpec("history", tr(s.TAB_HISTORY), "History", planned=True),
            TabSpec("settings", tr(s.TAB_SETTINGS), "Settings", planned=True, trailing=True),
        ]
    )
    steps = StepStrip([tr(x) for x in s.STEPS], [tr(x) for x in s.STEPS_SHORT])
    steps.set_current(2)
    facts = FactsGrid(["Container", "Duration", "Size", "Bitrate"], "Title")
    facts.set_values(
        ["Matroska / WebM", "2:13", "186.4 MB", "11.2 Mb/s"],
        "Lisbon Studio Session: full interview, director’s cut",
    )
    layout.addWidget(
        _spec(
            "Tabs, steps, facts, planned banner",
            tabs,
            steps,
            facts,
            PlannedBanner("Advanced Mode isn’t built yet. This shows how it will work."),
        )
    )
    layout.addStretch()
    page.setMinimumWidth(720)
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    return page
