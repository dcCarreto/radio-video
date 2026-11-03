from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtMultimedia import QMediaPlayer
from pytestqt.qtbot import QtBot

from radio_video.ffmpeg import FFmpegTools, probe
from radio_video.models.presets import OUTPUT_FORMATS, Quality
from radio_video.services.preview import PreviewKind
from radio_video.ui.preview_dialog import PreviewDialog

pytestmark = pytest.mark.ffmpeg

TIMEOUT_MS = 60000
MP4 = next(fmt for fmt in OUTPUT_FORMATS if fmt.key == "mp4-h264")
LOADED = {
    QMediaPlayer.MediaStatus.LoadedMedia,
    QMediaPlayer.MediaStatus.BufferingMedia,
    QMediaPlayer.MediaStatus.BufferedMedia,
    QMediaPlayer.MediaStatus.EndOfMedia,
}


def test_dialog_generates_and_plays_converted_preview(
    qtbot: QtBot, ffmpeg_tools: FFmpegTools, sample_video: Path
) -> None:
    media = probe(sample_video, ffmpeg_tools.ffprobe)
    # CI runners have no audio device; Qt Multimedia can hang stopping audio playback there.
    dialog = PreviewDialog(
        ffmpeg_tools.ffmpeg, media, MP4, Quality.SMALL, PreviewKind.SHORT, autoplay=False
    )
    qtbot.addWidget(dialog)
    estimates: list[int] = []
    dialog.size_estimated.connect(estimates.append)

    with qtbot.waitSignal(dialog.generator.ready, timeout=TIMEOUT_MS) as blocker:
        assert dialog.start()
    sample = blocker.args[0]

    source = dialog.player.player.source().toLocalFile()
    assert Path(source) == sample.path
    assert Path(source) != sample_video
    assert "MP4 (H.264 + AAC), Small file" in dialog.settings_label.text()
    assert "not the original" in dialog.status_label.text()
    assert dialog.range_label.text() == "Converted the whole file (0:03)"
    assert estimates == [sample.size]
    qtbot.waitUntil(lambda: dialog.player.player.mediaStatus() in LOADED, timeout=TIMEOUT_MS)

    dialog.reject()
    assert not sample.path.parent.exists()
