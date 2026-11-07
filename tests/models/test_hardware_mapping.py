from radio_video.models.conversion import AudioOptions, ConversionSettings, VideoOptions
from radio_video.models.hardware import AMF, NVENC, QUICK_SYNC, HardwareSupport, accelerate
from radio_video.models.presets import Quality, format_by_key

NVIDIA = HardwareSupport(NVENC, NVENC.encoders, "NVIDIA GeForce RTX 4070 SUPER")


def test_h264_moves_to_nvenc_with_a_matching_quality() -> None:
    settings = accelerate(format_by_key("mp4-h264").settings(Quality.BALANCED), NVIDIA)
    video = settings.video
    assert video is not None
    assert video.codec == "h264_nvenc"
    assert video.crf == 21  # CRF 23 looks like NVENC CQ 21
    assert video.preset == "p4"
    assert video.bitrate == 0
    assert video.pixel_format == "nv12"
    assert settings.audio == format_by_key("mp4-h264").settings(Quality.BALANCED).audio


def test_h265_keeps_its_quality_level_on_nvenc() -> None:
    video = accelerate(format_by_key("mp4-h265").settings(Quality.HIGH), NVIDIA).video
    assert video is not None
    assert (video.codec, video.crf) == ("hevc_nvenc", 22)


def test_amf_and_quick_sync_presets() -> None:
    h264 = format_by_key("mkv-h264").settings(Quality.SMALL)
    amf = accelerate(h264, HardwareSupport(AMF, AMF.encoders)).video
    qsv = accelerate(h264, HardwareSupport(QUICK_SYNC, QUICK_SYNC.encoders)).video
    assert amf is not None and qsv is not None
    assert (amf.codec, amf.crf, amf.preset, amf.bitrate) == ("h264_amf", 26, None, None)
    assert (qsv.codec, qsv.crf, qsv.preset) == ("h264_qsv", 28, "medium")


def test_only_working_encoders_are_used() -> None:
    h264_only = HardwareSupport(NVENC, NVENC.encoders[:1])
    settings = format_by_key("mp4-h265").settings(Quality.BALANCED)
    assert accelerate(settings, h264_only) == settings


def test_other_settings_stay_in_software() -> None:
    for key in ("webm-vp9", "mp3", "flac"):
        settings = format_by_key(key).settings(Quality.BALANCED)
        assert accelerate(settings, NVIDIA) == settings
    assert accelerate(format_by_key("mp4-h264").settings(Quality.HIGH), None).video is not None
    ten_bit = ConversionSettings(
        VideoOptions(codec="libx265", crf=26, pixel_format="yuv420p10le"), AudioOptions("aac")
    )
    assert accelerate(ten_bit, NVIDIA) == ten_bit
    copy = ConversionSettings(VideoOptions(codec="copy"), AudioOptions(codec="aac"))
    assert accelerate(copy, NVIDIA) == copy


def test_target_bitrate_moves_to_the_graphics_card() -> None:
    bitrate_only = ConversionSettings(
        VideoOptions(codec="libx264", bitrate=2_000_000, preset="slow"), AudioOptions("aac")
    )
    video = accelerate(bitrate_only, NVIDIA).video
    assert video is not None
    assert (video.codec, video.crf, video.bitrate) == ("h264_nvenc", None, 2_000_000)
    assert (video.preset, video.pixel_format) == ("p4", "nv12")
