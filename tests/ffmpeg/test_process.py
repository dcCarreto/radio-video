from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from radio_video.ffmpeg.process import kill_process_tree

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows process trees")

PARENT = """
import subprocess, sys, time
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


def _wait_until(condition: object, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if callable(condition) and condition():
            return True
        time.sleep(0.1)
    return False


def test_kills_child_processes(tmp_path: Path) -> None:
    pid_file = tmp_path / "child.pid"
    parent = subprocess.Popen([sys.executable, "-c", PARENT, str(pid_file)])
    try:
        assert _wait_until(lambda: pid_file.exists() and pid_file.read_text().strip())
        child_pid = int(pid_file.read_text())
        assert _is_alive(child_pid)

        kill_process_tree(parent.pid)

        parent.wait(timeout=10)
        assert _wait_until(lambda: not _is_alive(child_pid))
    finally:
        if parent.poll() is None:
            parent.kill()


def test_ignores_invalid_pid() -> None:
    kill_process_tree(0)
    kill_process_tree(-1)
