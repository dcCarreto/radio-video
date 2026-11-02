VIDEO_EXTENSIONS = (
    "3gp", "avi", "flv", "m2ts", "m4v", "mkv", "mov", "mp4", "mpeg", "mpg",
    "mts", "mxf", "ogv", "ts", "vob", "webm", "wmv",
)  # fmt: skip

AUDIO_EXTENSIONS = (
    "aac", "ac3", "aif", "aiff", "alac", "amr", "ape", "dts", "flac", "m4a",
    "mka", "mp2", "mp3", "oga", "ogg", "opus", "wav", "wma", "wv",
)  # fmt: skip


def _patterns(extensions: tuple[str, ...]) -> str:
    return " ".join(f"*.{ext}" for ext in extensions)


def open_file_filter() -> str:
    """Filter string for QFileDialog. FFprobe decides what is actually readable."""
    return ";;".join(
        [
            f"Media files ({_patterns(VIDEO_EXTENSIONS + AUDIO_EXTENSIONS)})",
            f"Video files ({_patterns(VIDEO_EXTENSIONS)})",
            f"Audio files ({_patterns(AUDIO_EXTENSIONS)})",
            "All files (*)",
        ]
    )
