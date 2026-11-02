"""Radio/Video: desktop audio and video converter."""

try:
    from radio_video._version import __version__
except ImportError:
    __version__ = "0.0.0"

APP_NAME = "Radio/Video"

__all__ = ["APP_NAME", "__version__"]
