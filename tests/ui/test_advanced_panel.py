"""Advanced Mode end to end: controls change the choices, conversions use them."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from pytestqt.qtbot import QtBot

from radio_video.ffmpeg import FFmpegTools
from radio_video.models.advanced import AdvancedChoices, EncoderChoice, RateControl
from radio_video.models.conversion import ConversionJob
from radio_video.models.hardware import NVENC, HardwareSupport
from radio_video.models.presets import OUTPUT_FORMATS, Quality
from radio_video.ui.demo import DEMO_MEDIA
from radio_video.ui.pages.advanced_panel import AdvancedPanel
from radio_video.ui.state import Mode
from radio_video.ui.windows.main_window import Engine, MainWindow

ALL_ENCODERS = frozenset(e for fmt in OUTPUT_FORMATS for e in fmt.encoders)
NVIDIA = HardwareSupport(NVENC, NVENC.encoders, "NVIDIA GeForce RTX 4070 SUPER")


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> Iterator[MainWindow]:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    engine = Engine(FFmpegTools(tmp_path / "ffmpeg.exe", tmp_path / "ffprobe.exe"), ALL_ENCODERS)
    main = MainWindow(engine, settings=settings)
    qtbot.addWidget(main)
    source = tmp_path / DEMO_MEDIA.path.name
    source.write_bytes(b"")
    main.load_media(replace(DEMO_MEDIA, path=source), folder=tmp_path)
    main.machine.set_mode(Mode.ADVANCED)
    yield main
    main.machine._state = main.machine.state.__class__()


def _panel(window: MainWindow) -> AdvancedPanel:
    return window.convert_page.file.panel.advanced


def _jobs(window: MainWindow) -> list[ConversionJob]:
    jobs: list[ConversionJob] = []
    assert window.runner is not None
    window.runner.start = jobs.append  # type: ignore[method-assign,assignment]
    return jobs


def test_crf_and_preset_reach_the_conversion(window: MainWindow) -> None:
    panel = _panel(window)
    window.engine.hardware = None
    panel.crf.setValue(19)
    panel.preset.set_current_key("slow")
    assert window.machine.state.advanced == AdvancedChoices(crf=19, preset="slow")
    summary = window.convert_page.file.panel.summary_text.text()
    assert summary.startswith("MP4 · H.264 x264 CRF 19 slow")
    jobs = _jobs(window)
    window.start_conversion()
    video = jobs[-1].settings.video
    assert video is not None and (video.crf, video.preset) == (19, "slow")


def test_target_bitrate_shows_its_field_and_a_calculated_size(window: MainWindow) -> None:
    panel = _panel(window)
    assert panel.crf_field.isVisibleTo(panel)
    panel.method.set_value(RateControl.BITRATE.value)
    assert window.machine.state.advanced.rate_control is RateControl.BITRATE
    assert panel.video_bitrate_field.isVisibleTo(panel)
    assert not panel.crf_field.isVisibleTo(panel)
    panel.video_bitrate.set_current_key("8000000")
    assert window.machine.state.advanced.video_bitrate == 8_000_000
    # Bitrates fix the size: 8 Mb/s video and three 192 kb/s audio tracks for 2:13.
    estimate = window.convert_page.file.panel.output
    assert estimate.estimate_how.text() == "Calculated from the bitrate and length."
    # (8 000 000 + 3 × 192 000) b/s × 133 s / 8 = 142 576 000 bytes, shown as 136 MB
    assert estimate.estimate_value.text() == "≈ 136 MB"


def test_stream_copy_disables_the_encoding_fields(window: MainWindow) -> None:
    panel = _panel(window)
    panel.copy_video.setChecked(True)
    assert window.machine.state.advanced.copy_video
    assert not panel.crf.isEnabled()
    assert not panel.resolution.isEnabled()
    jobs = _jobs(window)
    window.start_conversion()
    video = jobs[-1].settings.video
    assert video is not None and video.is_copy


def test_stream_copy_is_unavailable_when_the_container_cant_hold_it(window: MainWindow) -> None:
    window.machine.set_format("webm-vp9", lossless=False)
    panel = _panel(window)
    assert not panel.copy_video.isEnabled()
    help_label = panel.copy_field.help
    assert help_label is not None
    assert "WebM can’t hold H.264 video as it is" in help_label.text()  # type: ignore[attr-defined]


def test_tracks_tab_leaves_tracks_out(window: MainWindow) -> None:
    panel = _panel(window)
    panel.track_checks[2].setChecked(False)
    assert window.machine.state.advanced.tracks is not None
    assert panel.track_outputs[2].text() == "Left out"
    assert panel.tracks_help.text().endswith("11 of 12 kept.")
    jobs = _jobs(window)
    window.start_conversion()
    assert jobs[-1].streams is not None and 2 not in jobs[-1].streams.audio


def test_tracks_the_format_cant_hold_are_disabled(window: MainWindow) -> None:
    window.machine.set_format("webm-vp9", lossless=False)
    panel = _panel(window)
    assert not panel.track_checks[11].isEnabled()
    assert panel.track_outputs[11].text() == "WebM can’t store this track"


def test_container_switch_changes_the_format(window: MainWindow) -> None:
    panel = _panel(window)
    assert panel.container.keys() == ["mp4-h264", "mkv-h264"]
    panel.container.set_current_key("mkv-h264")
    assert window.machine.state.format_key == "mkv-h264"
    codecs = panel.audio_codec.keys()
    assert "copy" in codecs


def test_output_options(window: MainWindow) -> None:
    panel = _panel(window)
    panel.loudness.setChecked(True)
    panel.fast_start.setChecked(False)
    panel.deinterlace.set_current_key("off")
    choices = window.machine.state.advanced
    assert choices.normalize_loudness and not choices.fast_start
    jobs = _jobs(window)
    window.start_conversion()
    settings = jobs[-1].settings
    assert settings.normalize_loudness and not settings.fast_start
    assert settings.video is not None and settings.video.deinterlace is None


def test_encoder_choice_overrides_the_settings_switch(window: MainWindow) -> None:
    window.engine.hardware = NVIDIA
    window.machine.set_advanced(AdvancedChoices(crf=22))
    panel = _panel(window)
    assert panel.encoder.keys() == ["software", "hardware"]
    assert panel.encoder.current_key() == "hardware"
    panel.encoder.set_current_key("software")
    assert window.machine.state.advanced.encoder is EncoderChoice.SOFTWARE
    jobs = _jobs(window)
    window.start_conversion()
    video = jobs[-1].settings.video
    assert video is not None and video.codec == "libx264"


def test_simple_mode_shows_custom_and_resets(window: MainWindow) -> None:
    window.machine.set_advanced(AdvancedChoices(height=720))
    window.machine.set_mode(Mode.SIMPLE)
    simple = window.convert_page.file.panel
    assert simple.custom_note.isVisibleTo(simple)
    simple.reset_button.click()
    assert window.machine.state.advanced.is_default
    assert window.machine.state.quality is Quality.BALANCED
    assert not simple.custom_note.isVisibleTo(simple)


def test_quality_change_keeps_picture_choices(window: MainWindow) -> None:
    window.machine.set_advanced(AdvancedChoices(crf=19, height=720))
    window.machine.set_quality(Quality.HIGH)
    assert window.machine.state.advanced == AdvancedChoices(height=720)


def test_everything_is_locked_while_converting(window: MainWindow) -> None:
    window.machine.conversion_requested()
    window.machine.conversion_started()
    panel = _panel(window)
    for widget in (panel.crf, panel.copy_video, panel.audio_codec, panel.loudness):
        assert not widget.isEnabled()
    assert not panel.track_checks[1].isEnabled()
