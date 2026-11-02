from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Slot
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from radio_video.utils.formatting import format_duration


class PreviewPlayer(QWidget):
    """Playback-only player for converted preview files."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)

        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumSize(320, 180)
        self.player.setVideoOutput(self.video_widget)
        self.audio_only_label = QLabel("Audio preview")
        self.audio_only_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.audio_only_label.hide()

        self.play_button = QPushButton()
        self.play_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_button.setToolTip("Play")
        self.play_button.setEnabled(False)

        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.setEnabled(False)
        self.time_label = QLabel(self._time_text(0, 0))

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setMaximumWidth(100)
        self.volume_slider.setToolTip("Volume")
        self.audio_output.setVolume(0.8)

        controls = QHBoxLayout()
        controls.addWidget(self.play_button)
        controls.addWidget(self.position_slider, stretch=1)
        controls.addWidget(self.time_label)
        controls.addWidget(self.volume_slider)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.video_widget, stretch=1)
        layout.addWidget(self.audio_only_label, stretch=1)
        layout.addLayout(controls)

        self.play_button.clicked.connect(self.toggle_playback)
        self.position_slider.sliderMoved.connect(self.player.setPosition)
        self.volume_slider.valueChanged.connect(lambda v: self.audio_output.setVolume(v / 100))
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.playbackStateChanged.connect(self._on_state_changed)
        self.player.hasVideoChanged.connect(self._on_has_video_changed)

    def load(self, path: Path) -> None:
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.play_button.setEnabled(True)
        self.position_slider.setEnabled(True)

    def unload(self) -> None:
        """Stop playback and release the file so it can be deleted."""
        self.player.stop()
        self.player.setSource(QUrl())
        self.play_button.setEnabled(False)
        self.position_slider.setEnabled(False)
        self.position_slider.setRange(0, 0)
        self.time_label.setText(self._time_text(0, 0))

    @Slot()
    def toggle_playback(self) -> None:
        if self.player.playbackState() is QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    @staticmethod
    def _time_text(position_ms: int, duration_ms: int) -> str:
        return f"{format_duration(position_ms / 1000)} / {format_duration(duration_ms / 1000)}"

    @Slot(int)
    def _on_duration_changed(self, duration: int) -> None:
        self.position_slider.setRange(0, duration)
        self.time_label.setText(self._time_text(self.player.position(), duration))

    @Slot(int)
    def _on_position_changed(self, position: int) -> None:
        if not self.position_slider.isSliderDown():
            self.position_slider.setValue(position)
        self.time_label.setText(self._time_text(position, self.player.duration()))

    @Slot(QMediaPlayer.PlaybackState)
    def _on_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        playing = state is QMediaPlayer.PlaybackState.PlayingState
        icon = (
            QStyle.StandardPixmap.SP_MediaPause if playing else QStyle.StandardPixmap.SP_MediaPlay
        )
        self.play_button.setIcon(self.style().standardIcon(icon))
        self.play_button.setToolTip("Pause" if playing else "Play")

    @Slot(bool)
    def _on_has_video_changed(self, has_video: bool) -> None:
        self.video_widget.setVisible(has_video)
        self.audio_only_label.setVisible(not has_video)
