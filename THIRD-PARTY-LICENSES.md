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
| How it is used | Imported Python package, dynamically linked Qt libraries |

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

The preview player is planned on Qt Multimedia. On Windows, the PySide6 wheels include Qt's
FFmpeg-based media backend together with shared FFmpeg libraries (`avcodec`, `avformat`,
`avutil`, `swresample`, `swscale`) built by The Qt Company under the LGPL. These libraries are
covered by the same LGPL obligations as Qt itself.

## External Tools

### FFmpeg and FFprobe

| | |
|---|---|
| Project | [FFmpeg](https://ffmpeg.org/) |
| License | LGPLv2.1+ or GPLv2+/GPLv3+, depending on the build configuration |
| How it is used | Separate executables started as child processes |

Radio/Video does not link against FFmpeg. It runs the `ffmpeg` and `ffprobe` executables as
independent processes, communicating only through command-line arguments and standard streams.

Radio/Video does not currently redistribute FFmpeg. Users install it separately (see the README).
The license of the FFmpeg build a user installs applies to that build. For example, the
`full_build` packages from gyan.dev are configured with `--enable-gpl --enable-version3` and are
therefore licensed under GPLv3.

Before any Radio/Video release bundles FFmpeg binaries, the following must be decided and
documented here:

- Whether to ship an LGPL build (no `--enable-gpl`, no `--enable-nonfree`) or a GPL build.
  Bundling a GPL build is possible alongside MIT code because FFmpeg runs as a separate program,
  but the GPL obligations for that binary still apply: the license text, the exact
  `configure` options, and the corresponding source code must be provided.
- Builds configured with `--enable-nonfree` (for example with `libfdk_aac`) must never be
  redistributed.
- The exact version, build configuration and source location of the bundled build.

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
