# PyInstaller specification for the Windows build. Run through scripts/build_installer.py,
# which sets RADIO_VIDEO_ICON and RADIO_VIDEO_VERSION_FILE.
# ruff: noqa
import os
from pathlib import Path

ROOT = Path(SPECPATH).parent
SOURCE = ROOT / "src"

analysis = Analysis(
    [str(SOURCE / "radio_video" / "__main__.py")],
    pathex=[str(SOURCE)],
    datas=[
        (str(SOURCE / "radio_video" / "ui" / "icons" / "lucide"), "radio_video/ui/icons/lucide"),
    ],
    # Qt modules the application does not use, kept out to save space.
    excludes=[
        "tkinter",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.Qt3DCore",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtPdf",
    ],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="radio-video",
    console=False,
    icon=os.environ.get("RADIO_VIDEO_ICON"),
    version=os.environ.get("RADIO_VIDEO_VERSION_FILE"),
    upx=False,
)
collection = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    name="radio-video",
    upx=False,
)
