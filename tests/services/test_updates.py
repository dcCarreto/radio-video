"""Updates: reading the latest release, downloading and verifying the installer."""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from radio_video.services.updates import (
    LATEST_RELEASE_URL,
    Update,
    UpdateError,
    UpdateService,
    check_for_update,
    clear_downloads,
    download_installer,
    fetch_release,
    installer_arguments,
    release_version,
    running_version,
    update_from_release,
)

INSTALLER = b"MZ" + bytes(range(256)) * 900
DIGEST = hashlib.sha256(INSTALLER).hexdigest()


def _release(version: str = "0.5.0", **asset: object) -> dict[str, object]:
    name = f"Radio-Video-Setup-{version}.exe"
    return {
        "tag_name": f"v{version}",
        "html_url": f"https://github.com/dcCarreto/radio-video/releases/tag/v{version}",
        "assets": [
            {"name": f"radio_video-{version}-py3-none-any.whl", "size": 10},
            {
                "name": name,
                "size": len(INSTALLER),
                "digest": f"sha256:{DIGEST}",
                "browser_download_url": "https://github.com/dcCarreto/radio-video/releases/"
                f"download/v{version}/{name}",
                **asset,
            },
        ],
    }


class _Server:
    """Serves fixed answers on 127.0.0.1; ``routes`` maps a path to (status, body)."""

    def __init__(self) -> None:
        self.routes: dict[str, tuple[int, bytes]] = {}
        routes = self.routes

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                status, body = routes.get(self.path, (404, b"missing"))
                self.send_response(status)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args: object) -> None:
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def server() -> Iterator[_Server]:
    running = _Server()
    yield running
    running.close()


def _update(url: str) -> Update:
    return Update("0.5.0", "page", url, "Radio-Video-Setup-0.5.0.exe", len(INSTALLER), DIGEST)


def test_versions_are_read_from_tags_and_development_builds() -> None:
    assert release_version("v1.2.3") == (1, 2, 3)
    assert release_version("1.10.0") == (1, 10, 0)
    assert release_version("v1.2.3-rc1") is None
    assert running_version("0.4.1.dev3+g1234abc") == (0, 4, 1)
    assert running_version("0.0.0") == (0, 0, 0)
    assert running_version("unknown") == (0, 0, 0)


def test_a_newer_release_offers_its_installer() -> None:
    update = update_from_release(_release("0.5.0"), "0.4.0")
    assert update is not None
    assert update.version == "0.5.0"
    assert update.installer_name == "Radio-Video-Setup-0.5.0.exe"
    assert update.installer_url.endswith("/v0.5.0/Radio-Video-Setup-0.5.0.exe")
    assert update.sha256 == DIGEST and update.size == len(INSTALLER)
    assert update.page_url.endswith("/tag/v0.5.0")
    # 0.10.0 is newer than 0.9.0, not older.
    assert update_from_release(_release("0.10.0"), "0.9.0") is not None


@pytest.mark.parametrize("current", ["0.5.0", "0.6.0", "0.5.0.dev2+gabc"])
def test_the_same_or_an_older_release_is_no_update(current: str) -> None:
    assert update_from_release(_release("0.5.0"), current) is None


def test_a_development_build_is_offered_the_release_it_comes_before() -> None:
    assert update_from_release(_release("0.5.0"), "0.4.1.dev7+gabc") is not None


@pytest.mark.parametrize(
    ("release", "message"),
    [
        ({"tag_name": "nightly"}, "unexpected name"),
        ({"tag_name": "v0.5.0", "assets": []}, "no Windows installer"),
        (_release(digest=None), "no checksum"),
        (_release(digest="md5:abc"), "no checksum"),
        (_release(size="big"), "not described"),
    ],
)
def test_releases_that_cannot_be_installed_safely_are_refused(
    release: dict[str, object], message: str
) -> None:
    with pytest.raises(UpdateError, match=message):
        update_from_release(release, "0.4.0")


def test_check_reads_the_latest_release() -> None:
    urls: list[str] = []

    def fetch(url: str) -> object:
        urls.append(url)
        return _release("0.5.0")

    update = check_for_update("0.4.0", fetch=fetch)
    assert update is not None and update.version == "0.5.0"
    assert urls == [LATEST_RELEASE_URL]
    with pytest.raises(UpdateError):
        check_for_update("0.4.0", fetch=lambda _url: ["not", "a", "release"])


def test_fetch_reports_http_and_network_errors(server: _Server) -> None:
    server.routes["/latest"] = (200, json.dumps(_release()).encode())
    server.routes["/broken"] = (200, b"{not json")
    assert isinstance(fetch_release(f"{server.url}/latest"), dict)
    with pytest.raises(UpdateError, match="404"):
        fetch_release(f"{server.url}/nothing")
    with pytest.raises(UpdateError, match="could not be read"):
        fetch_release(f"{server.url}/broken")
    with pytest.raises(UpdateError, match="Could not reach GitHub"):
        fetch_release("http://127.0.0.1:9/latest", timeout=2)


def test_the_installer_is_downloaded_and_verified(server: _Server, tmp_path: Path) -> None:
    server.routes["/setup.exe"] = (200, INSTALLER)
    seen: list[tuple[int, int]] = []
    path = download_installer(
        _update(f"{server.url}/setup.exe"), tmp_path, lambda r, t: seen.append((r, t))
    )
    assert path == tmp_path / "Radio-Video-Setup-0.5.0.exe"
    assert path.read_bytes() == INSTALLER
    assert seen[-1] == (len(INSTALLER), len(INSTALLER))
    assert not list(tmp_path.glob("*.part"))
    # Already downloaded and still matching: nothing to fetch again.
    server.routes.clear()
    assert download_installer(_update(f"{server.url}/setup.exe"), tmp_path) == path


def test_a_damaged_download_is_thrown_away(server: _Server, tmp_path: Path) -> None:
    server.routes["/setup.exe"] = (200, INSTALLER[:-1] + b"!")
    with pytest.raises(UpdateError, match="checksum"):
        download_installer(_update(f"{server.url}/setup.exe"), tmp_path)
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(UpdateError, match="404"):
        download_installer(_update(f"{server.url}/gone.exe"), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_a_canceled_download_leaves_nothing_behind(server: _Server, tmp_path: Path) -> None:
    server.routes["/setup.exe"] = (200, INSTALLER)
    with pytest.raises(UpdateError, match="canceled"):
        download_installer(_update(f"{server.url}/setup.exe"), tmp_path, canceled=lambda: True)
    assert list(tmp_path.iterdir()) == []


def test_old_downloads_are_cleared(tmp_path: Path) -> None:
    folder = tmp_path / "updates"
    folder.mkdir()
    (folder / "Radio-Video-Setup-0.4.0.exe").write_bytes(b"x")
    clear_downloads(folder)
    assert not folder.exists()
    clear_downloads(folder)


def test_the_installer_runs_quietly_and_can_reopen_the_app() -> None:
    assert "/SILENT" in installer_arguments(False)
    assert "/RELAUNCH=1" not in installer_arguments(False)
    assert installer_arguments(True)[-1] == "/RELAUNCH=1"


def test_service_checks_and_downloads_in_the_background(
    qtbot: QtBot, server: _Server, tmp_path: Path
) -> None:
    release = _release("0.5.0", browser_download_url=f"{server.url}/setup.exe")
    server.routes["/latest"] = (200, json.dumps(release).encode())
    server.routes["/setup.exe"] = (200, INSTALLER)
    service = UpdateService(
        tmp_path, url=f"{server.url}/latest", current="0.4.0", trusted_prefix=server.url
    )
    with qtbot.waitSignal(service.checked, timeout=10_000) as checked:
        assert service.check()
    update = checked.args[0]
    assert isinstance(update, Update) and update.version == "0.5.0"
    assert not service.checking

    progress: list[int] = []
    service.progressed.connect(lambda received, _total: progress.append(received))
    with qtbot.waitSignal(service.downloaded, timeout=10_000) as downloaded:
        assert service.download(update)
    assert Path(downloaded.args[0]).read_bytes() == INSTALLER
    assert progress[-1] == len(INSTALLER)
    assert not service.downloading


def test_service_reports_failures(qtbot: QtBot, server: _Server, tmp_path: Path) -> None:
    service = UpdateService(tmp_path, url=f"{server.url}/latest", current="0.4.0")
    with qtbot.waitSignal(service.check_failed, timeout=10_000) as failed:
        service.check()
    assert "404" in failed.args[0]

    # Only installers published by the project are accepted.
    server.routes["/latest"] = (200, json.dumps(_release("0.5.0")).encode())
    service.trusted_prefix = "https://example.invalid/"
    with qtbot.waitSignal(service.check_failed, timeout=10_000) as failed:
        service.check()
    assert "not hosted" in failed.args[0]

    with qtbot.waitSignal(service.download_failed, timeout=10_000) as failed:
        service.download(_update(f"{server.url}/gone.exe"))
    assert "404" in failed.args[0]
