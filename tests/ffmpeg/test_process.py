from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from radio_video.ffmpeg.process import ProcessGroup

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Windows Job Objects")

# Waits before spawning its child, so the child is created after the parent joined the group,
# like a package-manager shim starting the real FFmpeg.
PARENT = """
import subprocess, sys, time
time.sleep(0.5)
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
open(sys.argv[1], "w").write(str(child.pid))
child.wait()
"""

TASKLIST = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32" / "tasklist.exe"


def _is_alive(pid: int) -> bool:
    result = subprocess.run(
        [str(TASKLIST), "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
        capture_output=True,
        text=True,
        check=False,
    )
    return f'"{pid}"' in result.stdout


def _wait_until(condition: Callable[[], bool], timeout: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.1)
    return False


def _child_pid(pid_file: Path) -> int:
    assert _wait_until(lambda: pid_file.exists() and bool(pid_file.read_text().strip()))
    return int(pid_file.read_text())


@windows_only
def test_terminate_kills_children_started_after_attach(tmp_path: Path) -> None:
    pid_file = tmp_path / "child.pid"
    parent = subprocess.Popen([sys.executable, "-c", PARENT, str(pid_file)])
    group = ProcessGroup()
    try:
        assert group.attach(parent.pid)
        child_pid = _child_pid(pid_file)
        assert _is_alive(child_pid)

        group.terminate()

        parent.wait(timeout=10)
        assert _wait_until(lambda: not _is_alive(child_pid))
    finally:
        group.close()
        if parent.poll() is None:
            parent.kill()


@windows_only
def test_closing_the_group_kills_survivors(tmp_path: Path) -> None:
    pid_file = tmp_path / "child.pid"
    parent = subprocess.Popen([sys.executable, "-c", PARENT, str(pid_file)])
    group = ProcessGroup()
    try:
        assert group.attach(parent.pid)
        child_pid = _child_pid(pid_file)
        group.close()
        assert _wait_until(lambda: not _is_alive(child_pid))
        parent.wait(timeout=10)
    finally:
        if parent.poll() is None:
            parent.kill()


def test_invalid_pid_is_not_attached() -> None:
    group = ProcessGroup()
    assert not group.attach(0)
    assert not group.attach(-1)
    assert not group.attached
    group.terminate()
    group.close()
