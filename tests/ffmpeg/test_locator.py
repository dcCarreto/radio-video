import sys
from pathlib import Path

import pytest

from radio_video.ffmpeg.locator import (
    FFMPEG_ENV,
    FFPROBE_ENV,
    FFmpegNotFoundError,
    locate_tools,
)

EXT = ".exe" if sys.platform == "win32" else ""


def _make_tools(directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    ffmpeg = directory / f"ffmpeg{EXT}"
    ffprobe = directory / f"ffprobe{EXT}"
    for path in (ffmpeg, ffprobe):
        path.write_bytes(b"")
        path.chmod(0o755)
    return ffmpeg, ffprobe


def test_environment_override_takes_precedence(tmp_path: Path) -> None:
    env_ffmpeg, env_ffprobe = _make_tools(tmp_path / "env")
    _make_tools(tmp_path / "bundled")
    tools = locate_tools(
        search_dirs=[tmp_path / "bundled"],
        environ={FFMPEG_ENV: str(env_ffmpeg), FFPROBE_ENV: str(env_ffprobe), "PATH": ""},
    )
    assert tools.ffmpeg == env_ffmpeg.resolve()
    assert tools.ffprobe == env_ffprobe.resolve()


def test_invalid_environment_override_raises(tmp_path: Path) -> None:
    with pytest.raises(FFmpegNotFoundError) as info:
        locate_tools(environ={FFMPEG_ENV: str(tmp_path / "missing.exe"), "PATH": ""})
    assert info.value.env_var == FFMPEG_ENV
    assert FFMPEG_ENV in str(info.value)


def test_search_dirs_before_path(tmp_path: Path) -> None:
    bundled_ffmpeg, bundled_ffprobe = _make_tools(tmp_path / "bundled")
    _make_tools(tmp_path / "onpath")
    tools = locate_tools(
        search_dirs=[tmp_path / "bundled"],
        environ={"PATH": str(tmp_path / "onpath")},
    )
    assert tools.ffmpeg == bundled_ffmpeg.resolve()
    assert tools.ffprobe == bundled_ffprobe.resolve()


def test_falls_back_to_path(tmp_path: Path) -> None:
    ffmpeg, ffprobe = _make_tools(tmp_path / "onpath")
    tools = locate_tools(environ={"PATH": str(tmp_path / "onpath"), "PATHEXT": ".EXE"})
    assert tools.ffmpeg == ffmpeg.resolve()
    assert tools.ffprobe == ffprobe.resolve()


def test_missing_tools_raise(tmp_path: Path) -> None:
    with pytest.raises(FFmpegNotFoundError) as info:
        locate_tools(environ={"PATH": str(tmp_path)})
    assert info.value.program == "ffmpeg"


def test_bundled_ffmpeg_is_found_next_to_the_frozen_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ffmpeg, ffprobe = _make_tools(tmp_path / "app" / "ffmpeg")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "app" / "radio-video.exe"))
    tools = locate_tools(environ={"PATH": ""})
    assert tools.ffmpeg == ffmpeg.resolve()
    assert tools.ffprobe == ffprobe.resolve()


def test_no_bundled_folder_when_running_from_source() -> None:
    from radio_video.ffmpeg.locator import bundled_dirs

    assert getattr(sys, "frozen", False) or bundled_dirs() == ()
