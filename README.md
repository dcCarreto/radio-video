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
- Conversion engine: runs FFmpeg asynchronously with progress (percentage, speed, time remaining)
  and cancellation. Output is written to a temporary file and moved into place only on success, so
  failed or canceled conversions leave nothing behind. Supports video and audio codec settings,
  resolution, frame rate, pixel format, audio bitrate, sample rate and channels, stream copy, audio
  extraction, time ranges and metadata preservation.
- Simple Mode in the main window:
  - Output formats: MP4 (H.264 or H.265 with AAC), MKV (H.264 + AAC), WebM (VP9 + Opus), MP3,
    AAC (M4A), Opus, Ogg Vorbis, FLAC and WAV. Only formats whose encoders are present in the
    installed FFmpeg are offered, and video formats only for sources that contain video.
  - Quality presets (High, Balanced, Small file); lossless formats always keep full quality.
  - Destination folder selection. Output names never overwrite existing files.
  - Output summary: file name, output streams and estimated size when it is predictable
    (bitrate-based and uncompressed audio).
  - Progress with percentage, speed and remaining time; cancel; Show in Folder after success.
  - Opening other files is blocked while a conversion runs, and closing the window asks for
    confirmation.
- Preview player:
  - **Short preview** converts a 15-second sample, starting a third of the way into the file, with
    the selected format and quality. Files of 15 seconds or less are converted entirely.
  - **Full preview** converts the whole file to a temporary location.
  - Previews are always the converted output, never the original file. They play in a
    playback-only player (play/pause, seek, volume) and are deleted when the preview is closed.
  - A short preview measures the real output size and extrapolates it to the full file, which
    gives a size estimate for quality-based formats.

## Planned Features

- Advanced Mode: video and audio codecs, bitrate, CRF, resolution, aspect ratio, frame rate,
  pixel format, sample rate, channels, filters, track selection and container options.
- Batch conversion, conversion queue and conversion history.
- Stream copy when re-encoding is not needed.
- Hardware acceleration detection (NVENC, Quick Sync, AMF).
- Preservation of subtitles and multiple audio tracks.
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

Pass `--debug` for verbose logging.

Open a file, choose a format, quality and destination folder in the **Convert** panel, and press
**Convert**.

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

- **#9 feat: add simple conversion mode**: Convert panel in the main window with output formats
  (MP4, MKV, WebM, MP3, AAC, Opus, Vorbis, FLAC, WAV), quality presets, destination folder,
  output summary, size estimate where predictable, progress, cancel and Show in Folder. Formats are
  offered according to the encoders in the installed FFmpeg, and existing files are never
  overwritten.
- **#7 feat: add conversion engine with progress and cancellation**: validated conversion
  settings, FFmpeg command construction, progress parsing and an asynchronous runner. Output is
  written to a temporary file and moved into place only on success; cancel terminates the whole
  FFmpeg process tree, including package-manager shims, and removes partial output.
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
