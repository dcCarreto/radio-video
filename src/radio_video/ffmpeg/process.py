import subprocess
import sys

# Keeps console windows from flashing when the GUI starts FFmpeg processes on Windows.
if sys.platform == "win32":
    CREATION_FLAGS = subprocess.CREATE_NO_WINDOW
else:
    CREATION_FLAGS = 0
