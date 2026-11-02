# Radio/Video

Radio/Video is a free and open-source desktop application for converting audio and video files
between formats. It uses [FFmpeg](https://ffmpeg.org/) for all media processing and provides a
Qt-based interface with two modes: a Simple Mode for quick conversions and an Advanced Mode for
full control over encoding parameters.

> **Status:** early development. The application is not usable yet. See
> [Current Features](#current-features) for what exists today.

## Goals

- Make common conversions possible without knowing anything about codecs.
- Expose the full set of relevant encoding options to users who want them, showing only the
  options that apply to the selected format and codec.
- Show previews that are produced with the actual conversion settings, never the original file.
- Keep the interface responsive during long conversions, with accurate progress and reliable
  cancellation.
- Preserve metadata, subtitles and multiple audio tracks whenever the target format allows it.
- Stay maintainable: modular architecture, automated tests and clear licensing.

## Current Features

- Project structure, packaging and development tooling.
- Continuous integration: linting, type checking, tests on Windows, dependency audit and package
  build on every pull request.
- Automated semantic versioning and GitHub releases when changes reach `main`.
- FFmpeg and FFprobe discovery through environment variables or `PATH`.
- Media analysis with FFprobe: container, duration, size, bitrate, tags, and per-stream codec,
  resolution, frame rate, pixel format, sample rate, channels, language and title.
- Main window: open a file from the menu, the Open button or by drag and drop, and view its media
  information. Analysis runs in the background so the window stays responsive. When FFmpeg is
  missing, the window explains how to install it.

## Planned Features

- Conversion engine with progress reporting and cancellation.
- Simple Mode: output format, quality preset, destination folder, estimated output.
- Advanced Mode: video and audio codecs, bitrate, CRF, resolution, aspect ratio, frame rate,
  pixel format, sample rate, channels, filters, track selection and container options.
- Preview player with short (10–20 s) and full previews generated from the real settings.
- Batch conversion, conversion queue and conversion history.
- Audio extraction and stream copy when re-encoding is not needed.
- Hardware acceleration detection (NVENC, Quick Sync, AMF).
- Estimated output size, error reporting and cleanup of temporary files.
- Windows installer.

## Technology Stack

| Area | Technology |
|---|---|
| Language | Python 3.11+ |
| User interface | PySide6 (Qt 6) |
| Media processing | FFmpeg |
| Media analysis | FFprobe |
| Preview playback | Qt Multimedia (FFmpeg backend) |
| Testing | pytest, pytest-qt |
| Linting and typing | Ruff, mypy |

## System Requirements

- Windows 10 or 11 (64-bit). Other platforms may work but are not tested yet.
- Python 3.11 or newer (for running from source).
- FFmpeg and FFprobe available on `PATH`, or their full paths set in the `RADIO_VIDEO_FFMPEG`
  and `RADIO_VIDEO_FFPROBE` environment variables.

FFmpeg is not bundled. On Windows it can be installed with:

```powershell
winget install --id Gyan.FFmpeg -e
```

## Development Setup

```powershell
git clone https://github.com/dcCarreto/radio-video.git
cd radio-video
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Running the Application

From the activated virtual environment:

```powershell
radio-video            # installed entry point
python -m radio_video  # equivalent
```

Pass `--debug` for verbose logging. The application can currently open and analyze media files;
conversion is not available yet.

## Building

```powershell
python -m build
```

This produces a source distribution and a wheel in `dist/`. A Windows installer is planned.

## Project Structure

```
radio-video/
├── .github/                 CI, release workflow, Dependabot, PR template
├── docs/                    Development documentation
├── scripts/                 Release tooling
├── src/radio_video/
│   ├── app.py               Application entry point
│   ├── ffmpeg/              FFmpeg and FFprobe integration
│   ├── models/              Data models
│   ├── services/            Background work for the user interface
│   ├── ui/                  Qt windows and widgets
│   └── utils/               Shared helpers
└── tests/                   Automated tests, mirroring the package layout
```

## Testing

```powershell
pytest                 # run the test suite
ruff check .           # lint
ruff format --check .  # formatting
mypy                   # type checking
```

Tests that need FFmpeg are marked `ffmpeg` and are skipped when FFmpeg is not installed.

## Contributing

The branch model, commit conventions and pull request process are described in
[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Future Updates

A cumulative history of changes merged into `dev`, newest first.

### 2026-11-02

- **#5 feat: add main window with media information view**: first runnable version of the
  application. Files can be opened from the menu, a button or by drag and drop; FFprobe runs in the
  background and the window shows the container summary and every stream. Adds the `radio-video`
  entry point.
- **#3 feat: add FFprobe media analysis**: locates FFmpeg and FFprobe (environment variables,
  bundled directories, `PATH`) and reads container and stream metadata into typed models, with
  clear errors for missing, unreadable or non-media files.
- **#1 chore: set up project structure, tooling and CI**: Python packaging with Git-tag
  versioning, Ruff, mypy and pytest configuration, CI checks on pull requests (branch policy,
  lint, Windows tests with FFmpeg, dependency audit, package build), automated semantic-version
  releases on `main`, and the README, development guide and third-party license documentation.

## License

Radio/Video is released under the [MIT License](LICENSE).

Third-party components, including Qt, PySide6 and FFmpeg, are distributed under their own licenses.
See [THIRD-PARTY-LICENSES.md](THIRD-PARTY-LICENSES.md).
