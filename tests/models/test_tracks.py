from pathlib import Path

from radio_video.models.media import MediaInfo, StreamInfo, StreamType
from radio_video.models.presets import format_by_key
from radio_video.models.tracks import TrackPolicy, main_audio, plan_streams

VIDEO = StreamInfo(index=0, type=StreamType.VIDEO, codec_name="h264")
SURROUND = StreamInfo(index=1, type=StreamType.AUDIO, channels=6, is_default=True)
STEREO = StreamInfo(index=2, type=StreamType.AUDIO, channels=2)
SRT = StreamInfo(index=3, type=StreamType.SUBTITLE, codec_name="subrip")
PGS = StreamInfo(index=4, type=StreamType.SUBTITLE, codec_name="hdmv_pgs_subtitle")
COVER = StreamInfo(index=5, type=StreamType.VIDEO, codec_name="mjpeg", is_attached_picture=True)

MEDIA = MediaInfo(
    path=Path("in.mkv"),
    format_name="matroska",
    streams=(VIDEO, SURROUND, STEREO, SRT, PGS, COVER),
)


def test_mp4_keeps_all_audio_text_subtitles_and_cover() -> None:
    plan = format_by_key("mp4-h264").plan(MEDIA)
    assert plan.video == 0
    assert plan.audio == (1, 2)
    assert plan.subtitles == (3,)
    assert plan.subtitle_codec == "mov_text"
    assert plan.cover_art == 5
    assert not plan.downmix_to_stereo


def test_mkv_copies_every_subtitle() -> None:
    plan = format_by_key("mkv-h264").plan(MEDIA)
    assert plan.subtitles == (3, 4)
    assert plan.subtitle_codec == "copy"


def test_webm_leaves_out_cover_art() -> None:
    plan = format_by_key("webm-vp9").plan(MEDIA)
    assert plan.cover_art is None
    assert plan.subtitle_codec == "webvtt"


def test_lossy_audio_keeps_main_track_and_downmixes_surround() -> None:
    plan = format_by_key("mp3").plan(MEDIA)
    assert plan.video is None
    assert plan.audio == (1,)
    assert plan.subtitles == ()
    assert plan.cover_art == 5
    assert plan.downmix_to_stereo


def test_lossless_audio_keeps_surround() -> None:
    plan = format_by_key("flac").plan(MEDIA)
    assert plan.audio == (1,)
    assert not plan.downmix_to_stereo


def test_stereo_source_is_not_remixed() -> None:
    media = MediaInfo(path=Path("in.wav"), format_name="wav", streams=(STEREO,))
    assert not format_by_key("opus").plan(media).downmix_to_stereo


def test_main_audio_prefers_the_default_track() -> None:
    media = MediaInfo(path=Path("in.mkv"), format_name="matroska", streams=(STEREO, SURROUND))
    assert main_audio(media) is SURROUND
    no_default = MediaInfo(
        path=Path("in.mkv"),
        format_name="matroska",
        streams=(STEREO, StreamInfo(index=3, type=StreamType.AUDIO)),
    )
    assert main_audio(no_default) is STEREO


def test_no_subtitles_when_none_are_convertible() -> None:
    media = MediaInfo(path=Path("in.mkv"), format_name="matroska", streams=(VIDEO, PGS))
    plan = plan_streams(media, TrackPolicy(subtitle_codec="mov_text"), include_video=True)
    assert plan.subtitles == ()
    assert plan.subtitle_codec is None
