import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Keeps console windows from flashing when the GUI starts FFmpeg processes on Windows.
if sys.platform == "win32":
    CREATION_FLAGS = subprocess.CREATE_NO_WINDOW
else:
    CREATION_FLAGS = 0


def kill_process_tree(pid: int) -> None:
    """Forcefully terminate a process and all of its descendants on Windows.

    Package managers such as Chocolatey and Scoop install ``ffmpeg.exe`` as a shim that starts
    the real executable as a child process. Killing only the shim would leave FFmpeg running.
    On other platforms this does nothing; callers still kill the direct child themselves.
    """
    if sys.platform != "win32" or pid <= 0:
        return
    taskkill = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32" / "taskkill.exe"
    try:
        subprocess.run(
            [str(taskkill), "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            timeout=10,
            check=False,
            creationflags=CREATION_FLAGS,
        )
    except (OSError, subprocess.TimeoutExpired):
        logger.warning("Could not terminate process tree of %d", pid, exc_info=True)
