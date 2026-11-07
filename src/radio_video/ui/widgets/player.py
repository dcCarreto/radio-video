"""Playback-only controls: play/pause, time, seek, track choice, mute and volume."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, Signal, SignalInstance
from PySide6.QtGui import QAction, QActionGroup, QMouseEvent, QPaintEvent
from PySide6.QtWidgets import QHBoxLayout, QMenu, QSizePolicy, QSlider, QWidget

from radio_video.ui import theme
from radio_video.ui.theme.fonts import TextStyle
from radio_video.ui.widgets.button import Button, ButtonKind
from radio_video.ui.widgets.labels import label
from radio_video.ui.widgets.painting import antialiased, fill_rounded, follow_theme

TRACK = 4
HANDLE = 18


def format_clock(milliseconds: int) -> str:
    seconds = max(0, round(milliseconds / 1000))
    return f"{seconds // 60}:{seconds % 60:02d}"


class Slider(QSlider):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setFixedHeight(20)
        self.setProperty("focusRadius", 10)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        follow_theme(self)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(120, 20)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(40, 20)

    def _fraction(self) -> float:
        span = self.maximum() - self.minimum()
        return (self.value() - self.minimum()) / span if span > 0 else 0.0

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        p = theme.palette()
        if not self.isEnabled():
            painter.setOpacity(0.5)
        usable = self.width() - HANDLE
        center_x = HANDLE / 2 + usable * self._fraction()
        track = QRectF(0, (self.height() - TRACK) / 2, self.width(), TRACK)
        fill_rounded(painter, track, TRACK / 2, p.border)
        fill_rounded(painter, QRectF(track.left(), track.top(), center_x, TRACK), TRACK / 2, p.sel)
        handle = QRectF(center_x - HANDLE / 2, (self.height() - HANDLE) / 2, HANDLE, HANDLE)
        fill_rounded(painter, handle, HANDLE / 2, p.raised, p.border_ctl)
        dot = handle.adjusted(5, 5, -5, -5)
        fill_rounded(painter, dot, dot.width() / 2, p.sel)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        # Jump to the clicked position instead of paging.
        if event.button() == Qt.MouseButton.LeftButton:
            usable = max(self.width() - HANDLE, 1)
            fraction = min(max((event.position().x() - HANDLE / 2) / usable, 0.0), 1.0)
            self.setValue(round(self.minimum() + fraction * (self.maximum() - self.minimum())))
            self.sliderMoved.emit(self.value())
        super().mousePressEvent(event)


class TrackMenu:
    """A button that opens a menu of tracks, with the current one checked."""

    def __init__(self, button: Button, chosen: SignalInstance) -> None:
        self.button = button
        self.menu = QMenu(button)
        self.group = QActionGroup(self.menu)
        self.group.setExclusive(True)
        self._chosen = chosen
        self.button.clicked.connect(self.open)
        self.button.hide()

    def set_tracks(self, labels: list[tuple[int, str]], active: int, *, visible: bool) -> None:
        self.menu.clear()
        for action in self.group.actions():
            self.group.removeAction(action)
        for index, text in labels:
            action = QAction(text, self.menu)
            action.setCheckable(True)
            action.setChecked(index == active)
            action.triggered.connect(lambda _checked=False, i=index: self._chosen.emit(i))
            self.group.addAction(action)
            self.menu.addAction(action)
        self.button.setVisible(visible)

    def set_active(self, active: int, indices: list[int]) -> None:
        for index, action in zip(indices, self.group.actions(), strict=False):
            action.setChecked(index == active)

    def open(self) -> None:
        below = self.button.mapToGlobal(QPoint(0, self.button.height()))
        self.menu.popup(below)


class Player(QWidget):
    play_toggled = Signal()
    seek_requested = Signal(int)
    mute_toggled = Signal()
    volume_changed = Signal(int)
    # Track numbers as the media player counts them; -1 turns subtitles off.
    audio_track_chosen = Signal(int)
    subtitle_track_chosen = Signal(int)

    def __init__(
        self,
        *,
        play_tip: str = "Play (Space)",
        pause_tip: str = "Pause (Space)",
        seek_tip: str = "Seek (Left/Right arrow)",
        mute_tip: str = "Mute (M)",
        unmute_tip: str = "Unmute (M)",
        volume_tip: str = "Volume",
        audio_tip: str = "Audio track",
        subtitles_tip: str = "Subtitles",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tips = {"play": play_tip, "pause": pause_tip, "mute": mute_tip, "unmute": unmute_tip}
        self._duration = 0
        self.play_button = Button(play_tip, ButtonKind.SUBTLE, icon="Play", icon_only=True)
        self.time = label("0:00 / 0:00", TextStyle.MONO_SMALL, "secondary")
        self.time.setMinimumWidth(84)
        self.seek = Slider()
        self.seek.setToolTip(seek_tip)
        self.seek.setAccessibleName(seek_tip)
        self.audio_menu = TrackMenu(
            Button(audio_tip, ButtonKind.SUBTLE, icon="Music", icon_only=True),
            self.audio_track_chosen,
        )
        self.subtitle_menu = TrackMenu(
            Button(subtitles_tip, ButtonKind.SUBTLE, icon="Captions", icon_only=True),
            self.subtitle_track_chosen,
        )
        self.mute_button = Button(mute_tip, ButtonKind.SUBTLE, icon="Volume2", icon_only=True)
        self.volume = Slider()
        self.volume.setRange(0, 100)
        self.volume.setValue(80)
        self.volume.setFixedWidth(80)
        self.volume.setToolTip(volume_tip)
        self.volume.setAccessibleName(volume_tip)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self.play_button)
        layout.addWidget(self.time)
        layout.addWidget(self.seek, 1)
        layout.addWidget(self.audio_menu.button)
        layout.addWidget(self.subtitle_menu.button)
        layout.addWidget(self.mute_button)
        layout.addWidget(self.volume)

        self.play_button.clicked.connect(self.play_toggled)
        self.mute_button.clicked.connect(self.mute_toggled)
        self.seek.sliderMoved.connect(self.seek_requested)
        self.volume.valueChanged.connect(self.volume_changed)

    def set_playing(self, playing: bool) -> None:
        tip = self._tips["pause" if playing else "play"]
        self.play_button.set_icon_name("Pause" if playing else "Play")
        self.play_button.setToolTip(tip)
        self.play_button.setAccessibleName(tip)

    def set_muted(self, muted: bool) -> None:
        tip = self._tips["unmute" if muted else "mute"]
        self.mute_button.set_icon_name("VolumeX" if muted else "Volume2")
        self.mute_button.setToolTip(tip)
        self.mute_button.setAccessibleName(tip)

    def set_duration(self, milliseconds: int) -> None:
        self._duration = max(milliseconds, 0)
        self.seek.setRange(0, self._duration)
        self._update_time(self.seek.value())

    def set_position(self, milliseconds: int) -> None:
        if not self.seek.isSliderDown():
            self.seek.setValue(milliseconds)
        self._update_time(milliseconds)

    def _update_time(self, position: int) -> None:
        self.time.setText(f"{format_clock(position)} / {format_clock(self._duration)}")
