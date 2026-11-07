"""Build the Windows installer.

1. Freeze the application with PyInstaller (packaging/radio-video.spec).
2. Add the GPL FFmpeg build from BtbN/FFmpeg-Builds: the latest build of the chosen release
   series, verified against the SHA-256 digest GitHub publishes for the asset. Its license,
   build configuration and source locations go next to the executables.
3. Download the corresponding FFmpeg source and the build scripts that produced the binaries,
   to publish with the release as the GPL requires.
4. Compile packaging/radio-video.iss with Inno Setup.

Usage: python scripts/build_installer.py --version 1.2.3 [--output dist]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "packaging" / "radio-video.spec"
INNO_SCRIPT = ROOT / "packaging" / "radio-video.iss"

FFMPEG_REPOSITORY = "BtbN/FFmpeg-Builds"
FFMPEG_RELEASE = "latest"
FFMPEG_SERIES = "9.0"
FFMPEG_VARIANT = "win64-gpl-shared"
FFMPEG_SOURCE_REPOSITORY = "FFmpeg/FFmpeg"
DOWNLOAD_ATTEMPTS = 4
DOWNLOAD_RETRY_SECONDS = 60.0
BUNDLED_FOLDER = "ffmpeg"
ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 256)
INNO_LOCATIONS = (
    Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
    Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
)

# "ffmpeg version n9.0.2-45-g1e65c6cd5d-20261102 Copyright" -> "1e65c6cd5d"
_COMMIT = re.compile(r"^ffmpeg version \S*?-g([0-9a-f]{7,40})\b", re.IGNORECASE)
_RELEASE_VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)")


class BuildError(Exception):
    """The installer could not be built."""


@dataclass(frozen=True)
class Asset:
    name: str
    url: str
    digest: str | None


def numeric_version(version: str) -> str:
    """Windows file versions are four numbers: "1.2.3.dev4+gabc" -> "1.2.3.0"."""
    match = _RELEASE_VERSION.match(version)
    if match is None:
        raise BuildError(f"Not a release version: {version!r}")
    return ".".join([*match.groups(), "0"])


def ffmpeg_asset_name(series: str, variant: str) -> str:
    return f"ffmpeg-n{series}-latest-{variant}-{series}.zip"


def select_asset(release: Mapping[str, object], name: str) -> Asset:
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise BuildError("The FFmpeg release lists no assets")
    for asset in assets:
        if isinstance(asset, dict) and asset.get("name") == name:
            digest = asset.get("digest")
            return Asset(
                name=name,
                url=str(asset["browser_download_url"]),
                digest=str(digest) if digest else None,
            )
    raise BuildError(f"FFmpeg build {name} is not in the release")


def parse_commit(version_output: str) -> str:
    match = _COMMIT.match(version_output.strip())
    if match is None:
        raise BuildError("Could not read the FFmpeg commit from its version")
    return match.group(1)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_digest(path: Path, expected: str | None) -> None:
    if not expected:
        raise BuildError(f"No published digest for {path.name}; refusing an unverified download")
    algorithm, _, value = expected.partition(":")
    if algorithm != "sha256" or not value:
        raise BuildError(f"Unsupported digest {expected!r}")
    actual = sha256_file(path)
    if actual != value.lower():
        raise BuildError(f"{path.name} digest mismatch: expected {value}, got {actual}")


def write_ico(images: Sequence[tuple[int, bytes]], path: Path) -> None:
    """Write an .ico file from (size, PNG data) pairs; Windows reads PNG-compressed icons."""
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    directory = b""
    for size, data in images:
        dimension = 0 if size >= 256 else size
        directory += struct.pack("<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    path.write_bytes(header + directory + b"".join(data for _, data in images))


def version_resource(version: str) -> str:
    """PyInstaller version resource, shown in the executable's Properties dialog."""
    numbers = tuple(int(part) for part in numeric_version(version).split("."))
    strings = {
        "CompanyName": "Radio/Video",
        "FileDescription": "Radio/Video",
        "FileVersion": version,
        "InternalName": "radio-video",
        "LegalCopyright": "MIT License",
        "OriginalFilename": "radio-video.exe",
        "ProductName": "Radio/Video",
        "ProductVersion": version,
    }
    table = ", ".join(f"StringStruct({key!r}, {value!r})" for key, value in strings.items())
    return (
        "VSVersionInfo(\n"
        f"  ffi=FixedFileInfo(filevers={numbers}, prodvers={numbers}, mask=0x3f, flags=0x0,\n"
        "    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),\n"
        f"  kids=[StringFileInfo([StringTable('040904B0', [{table}])]),\n"
        "        VarFileInfo([VarStruct('Translation', [1033, 1200])])]\n"
        ")\n"
    )


# Steps with side effects


def _request(url: str) -> urllib.request.Request:
    request = urllib.request.Request(url, headers={"User-Agent": "radio-video-build"})  # noqa: S310
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        request.add_header("Authorization", f"Bearer {token}")
    return request


def github_json(path: str) -> dict[str, object]:
    with urllib.request.urlopen(_request(f"https://api.github.com/{path}"), timeout=60) as response:  # noqa: S310
        data = json.load(response)
    if not isinstance(data, dict):
        raise BuildError(f"Unexpected GitHub response for {path}")
    return data


def download(url: str, destination: Path) -> Path:
    print(f"Downloading {url}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    response = urllib.request.urlopen(_request(url), timeout=600)  # noqa: S310
    with response, destination.open("wb") as out:
        shutil.copyfileobj(response, out)
    return destination


def make_icon(path: Path) -> Path:
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter

    from radio_video.ui.icons import paint_app_icon

    _app = QGuiApplication.instance() or QGuiApplication(["build"])
    images = []
    for size in ICON_SIZES:
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        paint_app_icon(painter, QRectF(0, 0, size, size))
        painter.end()
        # Saved by file name: the format comes from the extension.
        png = path.with_name(f"icon-{size}.png")
        png.parent.mkdir(parents=True, exist_ok=True)
        if not image.save(str(png)):
            raise BuildError(f"Could not render the {size} px icon")
        images.append((size, png.read_bytes()))
        png.unlink()
    write_ico(images, path)
    return path


def freeze(version: str, work: Path) -> Path:
    icon = make_icon(work / "radio-video.ico")
    version_file = work / "version.txt"
    version_file.write_text(version_resource(version), encoding="utf-8")
    environment = {
        **os.environ,
        "RADIO_VIDEO_ICON": str(icon),
        "RADIO_VIDEO_VERSION_FILE": str(version_file),
    }
    subprocess.run(
        [
            sys.executable, "-m", "PyInstaller", str(SPEC), "--noconfirm", "--clean",
            "--distpath", str(work / "dist"), "--workpath", str(work / "pyinstaller"),
        ],
        check=True,
        env=environment,
    )  # fmt: skip
    return work / "dist" / "radio-video"


@dataclass(frozen=True)
class FFmpegBundle:
    version_line: str
    commit: str
    builds_commit: str


def download_latest_ffmpeg(
    work: Path,
    series: str,
    variant: str,
    *,
    attempts: int = DOWNLOAD_ATTEMPTS,
    wait: float = DOWNLOAD_RETRY_SECONDS,
) -> tuple[Path, Asset]:
    """Download the newest build, asking for the release again when an asset vanished.

    The "latest" release is rebuilt every day: its assets are deleted and uploaded again, so
    a link read a moment earlier can answer 404 for a few minutes.
    """
    for attempt in range(1, attempts + 1):
        release = github_json(f"repos/{FFMPEG_REPOSITORY}/releases/tags/{FFMPEG_RELEASE}")
        try:
            asset = select_asset(release, ffmpeg_asset_name(series, variant))
            return download(asset.url, work / asset.name), asset
        except (BuildError, urllib.error.HTTPError) as exc:
            missing = isinstance(exc, BuildError) or exc.code == HTTPStatus.NOT_FOUND
            if not missing or attempt == attempts:
                raise
            print(f"FFmpeg build not available ({exc}); asking again in {wait:g} s")
            time.sleep(wait)
    raise BuildError("FFmpeg could not be downloaded")


def add_ffmpeg(app: Path, work: Path, series: str, variant: str) -> FFmpegBundle:
    archive, asset = download_latest_ffmpeg(work, series, variant)
    verify_digest(archive, asset.digest)

    target = app / BUNDLED_FOLDER
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.namelist():
            parts = Path(member).parts
            if (
                len(parts) == 3
                and parts[1] == "bin"
                and parts[2].lower().endswith((".exe", ".dll"))
            ):
                if parts[2].lower() == "ffplay.exe":
                    continue
                (target / parts[2]).write_bytes(bundle.read(member))
            elif len(parts) == 2 and parts[1].upper().startswith("LICENSE"):
                (target / "LICENSE.txt").write_bytes(bundle.read(member))

    ffmpeg = target / "ffmpeg.exe"
    version_line = _run_text([str(ffmpeg), "-hide_banner", "-version"]).splitlines()[0]
    commit = parse_commit(version_line)
    tag = github_json(f"repos/{FFMPEG_REPOSITORY}/git/ref/tags/{FFMPEG_RELEASE}")
    obj = tag.get("object")
    builds_commit = str(obj.get("sha")) if isinstance(obj, dict) else ""
    (target / "BUILDCONF.txt").write_text(
        version_line + "\n\n" + _run_text([str(ffmpeg), "-hide_banner", "-buildconf"]),
        encoding="utf-8",
    )
    (target / "SOURCE.txt").write_text(
        "This folder contains FFmpeg, licensed under the GNU General Public License version 3\n"
        "(see LICENSE.txt). It is an unmodified build from "
        f"https://github.com/{FFMPEG_REPOSITORY} ({asset.name}).\n\n"
        f"{version_line}\n\n"
        "The corresponding source code is attached to the Radio/Video release that contains\n"
        "this installer, and is also available here:\n"
        f"- FFmpeg: https://github.com/{FFMPEG_SOURCE_REPOSITORY}/tree/{commit}\n"
        f"- Build scripts and the versions of every library they compile: "
        f"https://github.com/{FFMPEG_REPOSITORY}/tree/{builds_commit}\n"
        "The configure options used are in BUILDCONF.txt.\n",
        encoding="utf-8",
    )
    return FFmpegBundle(version_line, commit, builds_commit)


def _run_text(command: Sequence[str]) -> str:
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


def download_sources(bundle: FFmpegBundle, output: Path) -> list[Path]:
    """The FFmpeg source and the build scripts, to attach to the release."""
    return [
        download(
            f"https://github.com/{FFMPEG_SOURCE_REPOSITORY}/archive/{bundle.commit}.tar.gz",
            output / f"ffmpeg-source-{bundle.commit}.tar.gz",
        ),
        download(
            f"https://github.com/{FFMPEG_REPOSITORY}/archive/{bundle.builds_commit}.tar.gz",
            output / f"ffmpeg-build-scripts-{bundle.builds_commit[:12]}.tar.gz",
        ),
    ]


def find_iscc() -> Path:
    candidates = [Path(os.environ["ISCC"])] if os.environ.get("ISCC") else []
    candidates += [*INNO_LOCATIONS]
    on_path = shutil.which("iscc")
    if on_path:
        candidates.append(Path(on_path))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise BuildError("Inno Setup 6 (ISCC.exe) was not found; install it or set ISCC")


def compile_installer(version: str, app: Path, work: Path, output: Path) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            str(find_iscc()),
            f"/DAppVersion={version}",
            f"/DNumericVersion={numeric_version(version)}",
            f"/DSourceDir={app}",
            f"/DIconFile={work / 'radio-video.ico'}",
            f"/DOutputDir={output}",
            str(INNO_SCRIPT),
        ],
        check=True,
    )
    return output / f"Radio-Video-Setup-{version}.exe"


def write_version_module(version: str) -> None:
    """Make the frozen application report the release version."""
    path = ROOT / "src" / "radio_video" / "_version.py"
    path.write_text(f'__version__ = version = "{version}"\n', encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--version", required=True, help="Release version, such as 1.2.3")
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--work", type=Path, default=ROOT / "build" / "installer")
    parser.add_argument("--ffmpeg-series", default=FFMPEG_SERIES)
    parser.add_argument("--ffmpeg-variant", default=FFMPEG_VARIANT)
    parser.add_argument("--skip-ffmpeg", action="store_true", help="Leave FFmpeg out (testing)")
    parser.add_argument("--skip-installer", action="store_true", help="Only freeze the application")
    args = parser.parse_args(argv)

    try:
        numeric_version(args.version)
        args.work.mkdir(parents=True, exist_ok=True)
        write_version_module(args.version)
        app = freeze(args.version, args.work)
        if not args.skip_ffmpeg:
            bundle = add_ffmpeg(app, args.work, args.ffmpeg_series, args.ffmpeg_variant)
            print(f"Bundled {bundle.version_line}")
            for path in download_sources(bundle, args.output):
                print(f"Source: {path}")
        if not args.skip_installer:
            installer = compile_installer(args.version, app, args.work, args.output)
            print(f"Installer: {installer}")
    except (BuildError, subprocess.CalledProcessError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
