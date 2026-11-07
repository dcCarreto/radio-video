import hashlib
import struct
import urllib.error
from email.message import Message
from pathlib import Path

import pytest

import build_installer
from build_installer import (
    Asset,
    BuildError,
    download_latest_ffmpeg,
    ffmpeg_asset_name,
    numeric_version,
    parse_commit,
    select_asset,
    verify_digest,
    version_resource,
    write_ico,
)


@pytest.mark.parametrize(
    ("version", "expected"),
    [("1.2.3", "1.2.3.0"), ("0.1.1.dev7+gffd6e03", "0.1.1.0"), ("10.0.12", "10.0.12.0")],
)
def test_numeric_version(version: str, expected: str) -> None:
    assert numeric_version(version) == expected


def test_numeric_version_rejects_garbage() -> None:
    with pytest.raises(BuildError):
        numeric_version("latest")


def test_asset_selection() -> None:
    name = ffmpeg_asset_name("9.0", "win64-gpl-shared")
    assert name == "ffmpeg-n9.0-latest-win64-gpl-shared-9.0.zip"
    release = {
        "assets": [
            {"name": "other.zip", "browser_download_url": "https://x/other.zip"},
            {"name": name, "browser_download_url": "https://x/f.zip", "digest": "sha256:ab"},
        ]
    }
    assert select_asset(release, name) == Asset(name, "https://x/f.zip", "sha256:ab")
    with pytest.raises(BuildError, match="not in the release"):
        select_asset(release, "missing.zip")


def test_parse_commit() -> None:
    line = "ffmpeg version n9.0.2-45-g1e65c6cd5d-20261102 Copyright (c) 2000-2026"
    assert parse_commit(line) == "1e65c6cd5d"
    with pytest.raises(BuildError):
        parse_commit("ffmpeg version 7.1-full_build-www.gyan.dev")


def test_verify_digest(tmp_path: Path) -> None:
    path = tmp_path / "f.zip"
    path.write_bytes(b"data")
    digest = hashlib.sha256(b"data").hexdigest()
    verify_digest(path, f"sha256:{digest}")
    with pytest.raises(BuildError, match="mismatch"):
        verify_digest(path, "sha256:" + "0" * 64)
    with pytest.raises(BuildError, match="unverified"):
        verify_digest(path, None)


def test_write_ico_directory(tmp_path: Path) -> None:
    path = tmp_path / "a.ico"
    write_ico([(16, b"PNG16"), (256, b"PNG256")], path)
    data = path.read_bytes()
    reserved, kind, count = struct.unpack_from("<HHH", data)
    assert (reserved, kind, count) == (0, 1, 2)
    width, _, _, _, planes, bits, size, offset = struct.unpack_from("<BBBBHHII", data, 6)
    assert (width, planes, bits, size, offset) == (16, 1, 32, 5, 6 + 32)
    width, *_ = struct.unpack_from("<BBBBHHII", data, 22)
    assert width == 0  # 256 px is stored as 0
    assert data[offset : offset + 5] == b"PNG16"


def test_version_resource_has_numbers_and_strings() -> None:
    text = version_resource("1.2.3")
    assert "filevers=(1, 2, 3, 0)" in text
    assert "StringStruct('ProductVersion', '1.2.3')" in text
    assert "StringStruct('OriginalFilename', 'radio-video.exe')" in text


def _release(url: str) -> dict[str, object]:
    name = ffmpeg_asset_name("9.0", "win64-gpl-shared")
    return {"assets": [{"name": name, "browser_download_url": url, "digest": "sha256:00"}]}


def test_ffmpeg_download_asks_again_after_a_404(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    releases = iter([_release("https://x/old.zip"), _release("https://x/new.zip")])
    monkeypatch.setattr(build_installer, "github_json", lambda path: next(releases))
    tried: list[str] = []

    def fake_download(url: str, destination: Path) -> Path:
        tried.append(url)
        if url.endswith("old.zip"):
            raise urllib.error.HTTPError(url, 404, "Not Found", Message(), None)
        return destination

    monkeypatch.setattr(build_installer, "download", fake_download)
    archive, asset = download_latest_ffmpeg(tmp_path, "9.0", "win64-gpl-shared", wait=0)
    assert tried == ["https://x/old.zip", "https://x/new.zip"]
    assert asset.url == "https://x/new.zip"
    assert archive.parent == tmp_path


def test_ffmpeg_download_gives_up_on_other_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(build_installer, "github_json", lambda path: _release("https://x/a.zip"))

    def forbidden(url: str, destination: Path) -> Path:
        raise urllib.error.HTTPError(url, 403, "Forbidden", Message(), None)

    monkeypatch.setattr(build_installer, "download", forbidden)
    with pytest.raises(urllib.error.HTTPError):
        download_latest_ffmpeg(tmp_path, "9.0", "win64-gpl-shared", wait=0)
