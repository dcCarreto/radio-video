# Third-Party Licenses

Radio/Video is released under the [MIT License](LICENSE). The MIT License applies only to the
Radio/Video source code. Third-party components keep their own licenses, and nothing in this
project's license overrides or relaxes their terms.

This document lists the third-party software Radio/Video depends on, how it is used, and the
obligations that apply when Radio/Video is distributed.

## Runtime Dependencies

### Qt 6 and PySide6

| | |
|---|---|
| Project | [Qt for Python (PySide6)](https://doc.qt.io/qtforpython-6/) |
| License used | GNU Lesser General Public License v3 (LGPLv3) |
| Also available under | GPLv2, GPLv3, Qt commercial license |
| How it is used | Imported Python packages (`PySide6-Essentials`, `PySide6-Addons`), dynamically linked Qt libraries |

Obligations when distributing binaries that include Qt or PySide6:

- Ship the LGPLv3 license text and the copyright notices of Qt and PySide6.
- Link Qt dynamically. Users must be able to replace the bundled Qt and PySide6 libraries with
  their own builds.
- Make the corresponding source code of the Qt and PySide6 versions in use available, or state
  where it can be obtained.
- Do not modify Qt libraries without publishing those modifications under LGPLv3.

Qt modules licensed only under GPL or commercial terms (for example Qt Charts, Qt Data
Visualization, Qt Virtual Keyboard) are not used. Any new Qt module must be checked against
<https://doc.qt.io/qt-6/licensing.html> before use.

### Qt Multimedia FFmpeg backend

The preview player uses Qt Multimedia (`QtMultimedia`, `QtMultimediaWidgets`, LGPLv3). On Windows, the PySide6 wheels include Qt's
FFmpeg-based media backend together with shared FFmpeg libraries (`avcodec`, `avformat`,
`avutil`, `swresample`, `swscale`) built by The Qt Company under the LGPL. These libraries are
covered by the same LGPL obligations as Qt itself.

### Lucide icons

| | |
|---|---|
| Project | [Lucide](https://lucide.dev/) 0.460.0 (`lucide-static`) |
| License | ISC License; portions from Feather under the MIT License |
| How it is used | SVG files bundled in `src/radio_video/ui/icons/lucide/`, recoloured at runtime |

Only the icons the interface uses are bundled. The ISC license text ships next to them in
`src/radio_video/ui/icons/lucide/LICENSE` and must accompany any redistribution.

## External Tools

### FFmpeg and FFprobe

| | |
|---|---|
| Project | [FFmpeg](https://ffmpeg.org/) |
| License | GPLv3 for the build bundled with the installer; any FFmpeg a user installs keeps its own license |
| How it is used | Separate executables started as child processes |
| Bundled build | Latest GPL shared build of FFmpeg 9.0 from [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds), unmodified |

Radio/Video does not link against FFmpeg. It runs the `ffmpeg` and `ffprobe` executables as
independent processes, communicating only through command-line arguments and standard streams.

The Windows installer redistributes a GPL build of FFmpeg (with x264, x265 and other GPL
libraries) in the `ffmpeg` folder next to the application. Bundling a GPL program alongside
MIT code is allowed because FFmpeg runs as a separate program; the GPL applies to that FFmpeg
build, not to Radio/Video. Each release meets the GPL obligations for it:

- The license text ships as `ffmpeg\LICENSE.txt`.
- The exact version and `configure` options ship as `ffmpeg\BUILDCONF.txt`.
- The corresponding source is attached to every GitHub release that contains an installer:
  the FFmpeg source at the exact commit of the bundled build, and the BtbN/FFmpeg-Builds scripts
  at the commit that produced it, which pin the version and source location of every library
  compiled into it. `ffmpeg\SOURCE.txt` points to both.
- The binaries are not modified.

Builds configured with `--enable-nonfree` (for example with `libfdk_aac`) must never be
redistributed; `scripts/build_installer.py` only uses BtbN's `gpl` variants.

When Radio/Video runs from source or from the wheel, FFmpeg is not bundled. Users install it
separately (see the README) and the license of that build applies to it.

### Codec patents

Some formats Radio/Video can produce through FFmpeg, such as H.264/AVC, H.265/HEVC and AAC, may be
covered by patents in some countries. Software licenses do not grant patent rights. Users and
distributors are responsible for any patent licensing that applies to them. Royalty-free
alternatives such as AV1, VP9, Opus, Vorbis and FLAC are available.

## Development-Only Dependencies

These tools are used to develop, test and build Radio/Video. They are not included in
distributed application packages.

| Package | License |
|---|---|
| [pytest](https://pytest.org/) | MIT |
| [pytest-qt](https://github.com/pytest-dev/pytest-qt) | MIT |
| [Ruff](https://github.com/astral-sh/ruff) | MIT |
| [mypy](https://mypy-lang.org/) | MIT |
| [build](https://github.com/pypa/build) | MIT |
| [setuptools](https://github.com/pypa/setuptools) | MIT |
| [setuptools-scm](https://github.com/pypa/setuptools-scm) | MIT |
| [pip-audit](https://github.com/pypa/pip-audit) (CI only) | Apache-2.0 |

### Build tools for the Windows installer

| Tool | License | Notes |
|---|---|---|
| [PyInstaller](https://pyinstaller.org/) | GPLv2 with a bootloader exception | The exception allows distributing the bootloader it adds to the executable under any license. |
| [Inno Setup](https://jrsoftware.org/isinfo.php) | Inno Setup License (free, permissive) | Generates the installer and uninstaller; no Inno Setup license terms apply to the installed application. |
