from pathlib import Path

from radio_video.ffmpeg.hardware import adapter_for, detect_hardware, probe_encoder
from radio_video.ffmpeg.locator import FFmpegTools
from radio_video.models.hardware import AMF, NVENC

ADAPTERS = ["NVIDIA GeForce RTX 4070 SUPER", "AMD Radeon(TM) Graphics"]


def test_adapter_matches_the_vendor() -> None:
    assert adapter_for(NVENC, ADAPTERS) == "NVIDIA GeForce RTX 4070 SUPER"
    assert adapter_for(AMF, ADAPTERS) == "AMD Radeon(TM) Graphics"
    assert adapter_for(NVENC, ["Intel(R) UHD Graphics 770"]) is None


def test_detection_prefers_nvenc_and_keeps_working_encoders_only() -> None:
    tried: list[str] = []

    def probe(_ffmpeg: Path, encoder: str) -> bool:
        tried.append(encoder)
        return encoder in {"h264_nvenc", "h264_amf", "hevc_amf"}

    encoders = {"libx264", "h264_nvenc", "hevc_nvenc", "h264_amf", "hevc_amf"}
    support = detect_hardware(Path("ffmpeg"), encoders, probe, lambda: ADAPTERS)
    assert support is not None
    assert support.technology == "NVENC"
    assert [encoder.name for encoder in support.encoders] == ["h264_nvenc"]
    assert support.adapter == "NVIDIA GeForce RTX 4070 SUPER"
    assert tried == ["h264_nvenc", "hevc_nvenc"]


def test_listed_encoders_that_fail_are_skipped() -> None:
    def probe(_ffmpeg: Path, encoder: str) -> bool:
        return encoder == "h264_amf"

    encoders = {"h264_nvenc", "hevc_nvenc", "h264_amf", "h264_qsv"}
    support = detect_hardware(Path("ffmpeg"), encoders, probe, lambda: ADAPTERS)
    assert support is not None
    assert support.technology == "AMF"
    assert support.adapter == "AMD Radeon(TM) Graphics"


def test_no_hardware() -> None:
    assert detect_hardware(Path("ffmpeg"), {"libx264"}, lambda *_: True, list) is None
    assert detect_hardware(Path("ffmpeg"), {"h264_nvenc"}, lambda *_: False, list) is None


def test_probe_encoder_runs_a_test_encode(ffmpeg_tools: FFmpegTools) -> None:
    assert probe_encoder(ffmpeg_tools.ffmpeg, "libx264")
    assert not probe_encoder(ffmpeg_tools.ffmpeg, "no_such_encoder")
