"""Hardware video encoders and how software settings map onto them."""

from __future__ import annotations

from dataclasses import dataclass, replace

from radio_video.models.conversion import ConversionSettings

# Every hardware encoder accepts NV12, the same 8-bit 4:2:0 picture as yuv420p; Quick Sync
# accepts nothing else.
HARDWARE_PIXEL_FORMAT = "nv12"
SOFTWARE_PIXEL_FORMAT = "yuv420p"


@dataclass(frozen=True)
class HardwareEncoder:
    name: str
    replaces: str
    preset: str | None
    # Added to the software CRF: hardware H.264 encoders need a lower value for the same
    # picture quality (measured with SSIM on a 1080p clip).
    quality_offset: int = 0
    # NVENC only keeps a constant quality when the bitrate cap is removed.
    unlimited_bitrate: bool = False


@dataclass(frozen=True)
class HardwareFamily:
    technology: str
    vendors: tuple[str, ...]
    encoders: tuple[HardwareEncoder, ...]


NVENC = HardwareFamily(
    "NVENC",
    ("NVIDIA",),
    (
        HardwareEncoder("h264_nvenc", "libx264", "p4", -2, unlimited_bitrate=True),
        HardwareEncoder("hevc_nvenc", "libx265", "p4", unlimited_bitrate=True),
    ),
)
AMF = HardwareFamily(
    "AMF",
    ("AMD", "Radeon"),
    (
        HardwareEncoder("h264_amf", "libx264", None, -2),
        HardwareEncoder("hevc_amf", "libx265", None, -3),
    ),
)
QUICK_SYNC = HardwareFamily(
    "Quick Sync",
    ("Intel",),
    (
        HardwareEncoder("h264_qsv", "libx264", "medium"),
        HardwareEncoder("hevc_qsv", "libx265", "medium"),
    ),
)
# In order of preference: a dedicated NVIDIA card is usually faster than integrated graphics.
FAMILIES = (NVENC, AMF, QUICK_SYNC)


@dataclass(frozen=True)
class HardwareSupport:
    """Hardware encoders that passed a test encode on this computer."""

    family: HardwareFamily
    encoders: tuple[HardwareEncoder, ...]
    adapter: str | None = None

    @property
    def technology(self) -> str:
        return self.family.technology

    def encoder_for(self, codec: str) -> HardwareEncoder | None:
        return next((encoder for encoder in self.encoders if encoder.replaces == codec), None)


def accelerate(settings: ConversionSettings, support: HardwareSupport | None) -> ConversionSettings:
    """``settings`` with the video encoded on the graphics card, when it can be.

    Constant quality moves the CRF to the encoder's quality level; a target bitrate is kept.
    Only 8-bit 4:2:0 pictures move: other pixel formats stay in software. Everything else,
    including audio and filters, is unchanged.
    """
    video = settings.video
    if support is None or video is None or video.is_copy:
        return settings
    if video.crf is None and not video.bitrate:
        return settings
    if video.pixel_format not in (None, SOFTWARE_PIXEL_FORMAT):
        return settings
    encoder = support.encoder_for(video.codec)
    if encoder is None:
        return settings
    crf: int | None = None
    bitrate = video.bitrate
    if video.crf is not None:
        crf = max(1, video.crf + encoder.quality_offset)
        bitrate = 0 if encoder.unlimited_bitrate else video.bitrate
    hardware = replace(
        video,
        codec=encoder.name,
        crf=crf,
        preset=encoder.preset,
        bitrate=bitrate,
        pixel_format=HARDWARE_PIXEL_FORMAT,
    )
    return replace(settings, video=hardware)
