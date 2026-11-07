from __future__ import annotations

from dataclasses import replace

from radio_video.models.advanced import (
    AdvancedChoices,
    Deinterlace,
    RateControl,
    TrackRule,
    audio_codecs,
    can_copy_video,
    kept_tracks,
    resolve,
    smaller_heights,
    toggle_track,
    track_rule,
)
from radio_video.models.media import StreamType
from radio_video.models.presets import Quality, format_by_key
from radio_video.ui.demo import DEMO_MEDIA

MP4 = format_by_key("mp4-h264")
MKV = format_by_key("mkv-h264")
WEBM = format_by_key("webm-vp9")
MP3 = format_by_key("mp3")
ALL_ENCODERS = {"libx264", "aac", "libopus", "flac", "libvorbis", "libvpx-vp9", "libmp3lame"}


def test_no_choices_is_the_simple_recipe() -> None:
    for fmt in (MP4, MKV, WEBM, MP3):
        recipe = resolve(fmt, Quality.BALANCED, DEMO_MEDIA)
        base = fmt.settings(Quality.BALANCED)
        assert recipe.streams == fmt.plan(DEMO_MEDIA)
        assert recipe.settings.audio == base.audio
        if base.video is not None:
            assert recipe.settings.video == replace(base.video, deinterlace="auto")
        assert recipe.settings.fast_start
        assert recipe.settings.preserve_metadata
        assert not recipe.settings.normalize_loudness


def test_crf_preset_and_picture_choices() -> None:
    choices = AdvancedChoices(
        crf=20, preset="slow", height=720, frame_rate=25.0, aspect="4:3", pixel_format="yuv444p"
    )
    video = resolve(MP4, Quality.BALANCED, DEMO_MEDIA, choices).settings.video
    assert video is not None
    assert (video.crf, video.preset, video.height, video.frame_rate) == (20, "slow", 720, 25.0)
    assert (video.aspect, video.pixel_format) == ("4:3", "yuv444p")


def test_choices_that_dont_fit_are_ignored() -> None:
    # 2160 would upscale; VP9 has no x264 presets; yuv444p isn't offered for VP9.
    choices = AdvancedChoices(height=2160, preset="slow", pixel_format="yuv444p", crf=99)
    video = resolve(WEBM, Quality.BALANCED, DEMO_MEDIA, choices).settings.video
    assert video is not None
    assert (video.height, video.preset, video.pixel_format, video.crf) == (
        None,
        None,
        "yuv420p",
        63,
    )
    assert smaller_heights(DEMO_MEDIA) == (720, 576, 480, 360)


def test_target_bitrate_replaces_constant_quality() -> None:
    choices = AdvancedChoices(rate_control=RateControl.BITRATE, video_bitrate=8_000_000)
    video = resolve(MP4, Quality.BALANCED, DEMO_MEDIA, choices).settings.video
    assert video is not None
    assert (video.crf, video.bitrate) == (None, 8_000_000)


def test_stream_copy_only_when_the_container_holds_the_codec() -> None:
    copy = AdvancedChoices(copy_video=True)
    video = resolve(MP4, Quality.BALANCED, DEMO_MEDIA, copy).settings.video
    assert video is not None and video.is_copy
    assert can_copy_video(MKV, DEMO_MEDIA)
    # WebM can't hold H.264: the video is converted as usual.
    assert not can_copy_video(WEBM, DEMO_MEDIA)
    webm = resolve(WEBM, Quality.BALANCED, DEMO_MEDIA, copy).settings.video
    assert webm is not None and webm.codec == "libvpx-vp9"


def test_audio_copy_and_codec_choices() -> None:
    assert audio_codecs(MKV, ALL_ENCODERS) == ("aac", "libopus", "flac")
    assert audio_codecs(MP4, ALL_ENCODERS) == ("aac",)
    assert audio_codecs(MP3, ALL_ENCODERS) == ("libmp3lame",)
    copy = resolve(MKV, Quality.BALANCED, DEMO_MEDIA, AdvancedChoices(audio_codec="copy"))
    assert copy.settings.audio is not None and copy.settings.audio.is_copy
    # MP3 can only copy MP3 audio; the AAC source is converted.
    mp3 = resolve(MP3, Quality.BALANCED, DEMO_MEDIA, AdvancedChoices(audio_codec="copy"))
    assert mp3.settings.audio is not None and mp3.settings.audio.codec == "libmp3lame"
    opus = resolve(
        MKV,
        Quality.BALANCED,
        DEMO_MEDIA,
        AdvancedChoices(audio_codec="libopus", audio_bitrate=96_000, sample_rate=44_100),
    ).settings.audio
    assert opus is not None
    # Opus only encodes 48 kHz here, so 44.1 kHz is dropped.
    assert (opus.codec, opus.bitrate, opus.sample_rate) == ("libopus", 96_000, None)


def test_copied_audio_is_never_downmixed_or_normalized() -> None:
    mp4_audio = format_by_key("m4a-aac")
    choices = AdvancedChoices(audio_codec="copy", normalize_loudness=True)
    recipe = resolve(mp4_audio, Quality.BALANCED, DEMO_MEDIA, choices)
    assert recipe.settings.audio is not None and recipe.settings.audio.is_copy
    assert not recipe.streams.downmix_to_stereo
    assert not recipe.settings.normalize_loudness


def test_track_rules_follow_the_container() -> None:
    by_index = {s.index: s for s in DEMO_MEDIA.streams}
    cover = by_index[11]
    assert track_rule(MP4, cover) is TrackRule.KEEP
    assert track_rule(WEBM, cover) is TrackRule.NOT_SUPPORTED
    assert track_rule(MP3, by_index[0]) is TrackRule.NOT_SUPPORTED
    assert track_rule(MP3, by_index[1]) is TrackRule.ONE_OF
    assert track_rule(MP4, by_index[0]) is TrackRule.ONE_OF


def test_toggling_tracks() -> None:
    choices = toggle_track(MP4, DEMO_MEDIA, AdvancedChoices(), 2, keep=False)
    recipe = resolve(MP4, Quality.BALANCED, DEMO_MEDIA, choices)
    assert 2 not in recipe.streams.audio
    # Back to the format's own set: the choice is forgotten.
    assert toggle_track(MP4, DEMO_MEDIA, choices, 2, keep=True).tracks is None
    # An audio-only format keeps one audio track: picking another replaces it.
    mp3 = toggle_track(MP3, DEMO_MEDIA, AdvancedChoices(), 3, keep=True)
    assert resolve(MP3, Quality.BALANCED, DEMO_MEDIA, mp3).streams.audio == (3,)


def test_leaving_out_the_video_keeps_an_audio_only_file() -> None:
    choices = toggle_track(MP4, DEMO_MEDIA, AdvancedChoices(), 0, keep=False)
    recipe = resolve(MP4, Quality.BALANCED, DEMO_MEDIA, choices)
    assert recipe.settings.video is None
    assert recipe.streams.video is None and recipe.streams.audio


def test_leaving_out_everything_falls_back_to_the_format() -> None:
    nothing = AdvancedChoices(tracks=frozenset())
    assert resolve(MP4, Quality.BALANCED, DEMO_MEDIA, nothing).streams == MP4.plan(DEMO_MEDIA)


def test_unsupported_tracks_are_never_kept() -> None:
    every = AdvancedChoices(tracks=frozenset(s.index for s in DEMO_MEDIA.streams))
    kept = kept_tracks(WEBM, DEMO_MEDIA, every)
    assert 11 not in kept
    mp3 = kept_tracks(MP3, DEMO_MEDIA, every)
    kinds = {s.type for s in DEMO_MEDIA.streams if s.index in mp3 and not s.is_attached_picture}
    assert kinds == {StreamType.AUDIO}
    assert 11 in mp3


def test_output_options() -> None:
    choices = AdvancedChoices(
        deinterlace=Deinterlace.OFF, fast_start=False, keep_metadata=False, normalize_loudness=True
    )
    settings = resolve(MP4, Quality.BALANCED, DEMO_MEDIA, choices).settings
    assert settings.video is not None and settings.video.deinterlace is None
    assert not settings.fast_start and not settings.preserve_metadata
    assert settings.normalize_loudness


def test_quality_and_format_changes_reset_what_they_govern() -> None:
    choices = AdvancedChoices(
        crf=19, audio_bitrate=96_000, height=720, copy_video=True, tracks=frozenset({0})
    )
    after_quality = choices.for_quality()
    assert (after_quality.crf, after_quality.audio_bitrate, after_quality.height) == (
        None,
        None,
        720,
    )
    after_format = choices.for_format()
    assert not after_format.copy_video and after_format.tracks is None
    assert after_format.height == 720
    assert AdvancedChoices().is_default and not choices.is_default
