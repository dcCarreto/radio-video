"""Updates: find a newer release on GitHub, download its installer and run it.

The installer is only run when its SHA-256 matches the digest GitHub publishes for it.
Network work happens on daemon threads, so a slow connection never holds up the window
or keeps the application from quitting.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import re
import shutil
import sys
import threading
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal, SignalInstance

from radio_video import __version__

logger = logging.getLogger(__name__)

REPOSITORY = "dcCarreto/radio-video"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
DOWNLOAD_PREFIX = f"https://github.com/{REPOSITORY}/releases/download/"
INSTALLER_NAME = "Radio-Video-Setup-{version}.exe"
CHECK_TIMEOUT = 20.0
DOWNLOAD_TIMEOUT = 60.0
CHUNK_SIZE = 1 << 16
PROGRESS_STEP = 1 << 20
PARTIAL_SUFFIX = ".part"

# "v1.2.3" or "1.2.3"; development builds such as "1.2.4.dev3+gabc" compare as 1.2.4.
_RELEASE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
_LEADING = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)")


class UpdateError(Exception):
    """The check or the download did not work; the message says why."""


@dataclass(frozen=True)
class Update:
    """A release newer than the running version, with its Windows installer."""

    version: str
    page_url: str
    installer_url: str
    installer_name: str
    size: int
    sha256: str


def release_version(text: str) -> tuple[int, int, int] | None:
    match = _RELEASE.match(text.strip())
    return (int(match[1]), int(match[2]), int(match[3])) if match else None


def running_version(text: str) -> tuple[int, int, int]:
    match = _LEADING.match(text.strip())
    return (int(match[1]), int(match[2]), int(match[3])) if match else (0, 0, 0)


def update_from_release(data: Mapping[str, object], current: str) -> Update | None:
    """The update a GitHub release offers, or None when it is not newer than ``current``."""
    tag = data.get("tag_name")
    if not isinstance(tag, str) or (version := release_version(tag)) is None:
        raise UpdateError(f"The latest release has an unexpected name: {tag!r}")
    if version <= running_version(current):
        return None
    text = ".".join(str(part) for part in version)
    name = INSTALLER_NAME.format(version=text)
    assets = data.get("assets")
    asset = next(
        (
            item
            for item in (assets if isinstance(assets, list) else [])
            if isinstance(item, dict) and item.get("name") == name
        ),
        None,
    )
    if asset is None:
        raise UpdateError(f"Version {text} has no Windows installer yet")
    url, size, digest = asset.get("browser_download_url"), asset.get("size"), asset.get("digest")
    if not isinstance(url, str) or not isinstance(size, int):
        raise UpdateError(f"The installer for version {text} is not described correctly")
    algorithm, _, value = digest.partition(":") if isinstance(digest, str) else ("", "", "")
    if algorithm != "sha256" or not re.fullmatch(r"[0-9a-fA-F]{64}", value):
        raise UpdateError(f"The installer for version {text} has no checksum to verify it with")
    page = data.get("html_url")
    return Update(
        version=text,
        page_url=page if isinstance(page, str) else f"https://github.com/{REPOSITORY}/releases",
        installer_url=url,
        installer_name=name,
        size=size,
        sha256=value.lower(),
    )


def _request(url: str) -> urllib.request.Request:
    return urllib.request.Request(  # noqa: S310
        url,
        headers={
            "User-Agent": f"Radio-Video/{__version__}",
            "Accept": "application/vnd.github+json",
        },
    )


def fetch_release(url: str = LATEST_RELEASE_URL, timeout: float = CHECK_TIMEOUT) -> object:
    try:
        with urllib.request.urlopen(_request(url), timeout=timeout) as response:  # noqa: S310
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise UpdateError(f"GitHub answered {exc.code} {exc.reason}") from exc
    except (urllib.error.URLError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise UpdateError(f"Could not reach GitHub ({reason})") from exc
    except json.JSONDecodeError as exc:
        raise UpdateError("GitHub sent an answer that could not be read") from exc


def check_for_update(
    current: str = __version__,
    url: str = LATEST_RELEASE_URL,
    fetch: Callable[[str], object] = fetch_release,
) -> Update | None:
    data = fetch(url)
    if not isinstance(data, dict):
        raise UpdateError("GitHub sent an answer that could not be read")
    return update_from_release(data, current)


def download_installer(
    update: Update,
    folder: Path,
    progress: Callable[[int, int], None] = lambda _received, _total: None,
    canceled: Callable[[], bool] = lambda: False,
    timeout: float = DOWNLOAD_TIMEOUT,
) -> Path:
    """Download the installer into ``folder`` and verify it; returns its path."""
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / update.installer_name
    if target.is_file() and _sha256(target) == update.sha256:
        progress(update.size, update.size)
        return target
    partial = target.with_name(target.name + PARTIAL_SUFFIX)
    digest = hashlib.sha256()
    received = 0
    try:
        with (
            urllib.request.urlopen(_request(update.installer_url), timeout=timeout) as response,  # noqa: S310
            partial.open("wb") as out,
        ):
            while chunk := response.read(CHUNK_SIZE):
                if canceled():
                    raise UpdateError("The download was canceled")
                out.write(chunk)
                digest.update(chunk)
                received += len(chunk)
                progress(received, update.size)
    except urllib.error.HTTPError as exc:
        partial.unlink(missing_ok=True)
        raise UpdateError(f"The download failed: {exc.code} {exc.reason}") from exc
    except (urllib.error.URLError, OSError) as exc:
        partial.unlink(missing_ok=True)
        reason = getattr(exc, "reason", exc)
        raise UpdateError(f"The download failed ({reason})") from exc
    except UpdateError:
        partial.unlink(missing_ok=True)
        raise
    if received != update.size or digest.hexdigest() != update.sha256:
        partial.unlink(missing_ok=True)
        raise UpdateError("The downloaded installer did not match its checksum")
    partial.replace(target)
    return target


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def clear_downloads(folder: Path) -> None:
    """Remove installers left from earlier updates."""
    if folder.is_dir():
        shutil.rmtree(folder, ignore_errors=True)


def can_install() -> bool:
    """Only the installed Windows application can update itself with the installer."""
    return sys.platform == "win32" and bool(getattr(sys, "frozen", False))


def installer_arguments(relaunch: bool) -> list[str]:
    """Run the installer with a progress window only; it reuses the installed folder."""
    arguments = ["/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"]
    if relaunch:
        # packaging/radio-video.iss opens Radio/Video again when this is set.
        arguments.append("/RELAUNCH=1")
    return arguments


def launch_installer(installer: Path, relaunch: bool) -> bool:
    started, _pid = QProcess.startDetached(str(installer), installer_arguments(relaunch))
    return bool(started)


class UpdateService(QObject):
    """Checks and downloads on background threads and reports back with signals."""

    # An Update, or None when the running version is the latest.
    checked = Signal(object)
    check_failed = Signal(str)
    # Bytes received and the total.
    progressed = Signal(int, int)
    # The verified installer's Path.
    downloaded = Signal(object)
    download_failed = Signal(str)

    def __init__(
        self,
        folder: Path,
        parent: QObject | None = None,
        *,
        url: str = LATEST_RELEASE_URL,
        current: str = __version__,
        trusted_prefix: str = DOWNLOAD_PREFIX,
    ) -> None:
        super().__init__(parent)
        self.folder = folder
        self.url = url
        self.current = current
        self.trusted_prefix = trusted_prefix
        self._checking = False
        self._downloading = False
        self._cancel = threading.Event()

    @property
    def checking(self) -> bool:
        return self._checking

    @property
    def downloading(self) -> bool:
        return self._downloading

    def check(self) -> bool:
        if self._checking:
            return False
        self._checking = True
        threading.Thread(target=self._check, name="update-check", daemon=True).start()
        return True

    def _check(self) -> None:
        try:
            update = check_for_update(self.current, self.url)
            if update is not None and not update.installer_url.startswith(self.trusted_prefix):
                raise UpdateError("The installer is not hosted by the Radio/Video project")
        except UpdateError as exc:
            self._report(self.check_failed, str(exc))
        except Exception as exc:
            logger.exception("Checking for updates failed")
            self._report(self.check_failed, str(exc))
        else:
            self._report(self.checked, update)
        finally:
            self._checking = False

    def download(self, update: Update) -> bool:
        if self._downloading:
            return False
        self._downloading = True
        self._cancel.clear()
        threading.Thread(
            target=self._download, args=(update,), name="update-download", daemon=True
        ).start()
        return True

    def cancel(self) -> None:
        self._cancel.set()

    def _download(self, update: Update) -> None:
        reported = -PROGRESS_STEP

        def progress(received: int, total: int) -> None:
            nonlocal reported
            # About one report per megabyte keeps the window's event queue quiet.
            if received - reported >= PROGRESS_STEP or received >= total:
                reported = received
                self._report(self.progressed, received, total)

        try:
            path = download_installer(update, self.folder, progress, self._cancel.is_set)
        except UpdateError as exc:
            self._downloading = False
            self._report(self.download_failed, str(exc))
        except Exception as exc:
            logger.exception("Downloading the update failed")
            self._downloading = False
            self._report(self.download_failed, str(exc))
        else:
            self._downloading = False
            self._report(self.downloaded, path)

    @staticmethod
    def _report(signal: SignalInstance, *args: object) -> None:
        # RuntimeError: the window closed while the thread was working.
        with contextlib.suppress(RuntimeError):
            signal.emit(*args)
