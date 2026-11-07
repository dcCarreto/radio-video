# Radio/Video

Radio/Video is a free and open-source desktop application for converting audio and video files
between formats. It uses [FFmpeg](https://ffmpeg.org/) for all media processing and provides a
Qt-based interface. Simple Mode covers common conversions with presets; Advanced Mode gives full
control over encoding parameters, tracks and filters.

> **Status:** early development. Media analysis, Simple and Advanced Mode conversion and previews
> work; see
> [Current Features](#current-features) for details and [Planned Features](#planned-features)
> for what is still missing.

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
- Windows installer with FFmpeg included: installs for the current user without administrator
  rights (or for all users), with a Start menu shortcut and an uninstaller. Releases also carry
  the source of the bundled FFmpeg build.
- FFmpeg and FFprobe discovery through environment variables, the copy bundled with the
  installed application, or `PATH`.
- Media analysis with FFprobe: container, duration, size, bitrate, tags, and per-stream codec,
  resolution, frame rate, pixel format, sample rate, channels, language and title.
- Main window in a light or dark theme that follows Windows, with a step strip (Open, Check,
  Choose, Preview, Convert) and a status bar showing the conversion engine:
  - Start screen: drop a file or open it with the button or Ctrl+O. Reading the file runs in the
    background. Several files go to the queue; folders, and a single file dropped during a
    conversion, are refused with the reason.
  - When FFmpeg is missing, a one-time setup page shows the winget command (with Copy), the
    environment variables for a custom location and a Check Again button.
  - A loaded file shows a plain-language summary ("1 video track, 3 audio tracks (Portuguese,
    English)…"), container facts and every track with codec, details, language, title and the
    default flag.
  - Play opens the loaded file in the built-in player as it is, without converting anything,
    and stays available during a conversion. The original and converted previews link to each
    other for a quick comparison.
  - Keyboard: Ctrl+O, Ctrl+Enter (convert), Ctrl+P and Ctrl+Shift+P (previews),
    Ctrl+Shift+Space (play the original), Ctrl+Shift+Enter (add to the queue), Esc (cancel),
    Ctrl+1–4 (tabs), F1 (About); a visible focus ring for keyboard use.
  - Conversion progress also shows on the taskbar button, and a notification reports the result
    when the window is in the background.
- Conversion engine: runs FFmpeg asynchronously with progress (percentage, speed, time remaining)
  and cancellation. Output is written to a temporary `.part` file next to the destination and
  moved into place only on success, so failed or canceled conversions leave nothing behind.
  Supports video and audio codec settings, resolution, frame rate, pixel format, audio bitrate or
  variable-bitrate quality, sample rate and channels, stream copy, audio extraction, track
  selection, time ranges and metadata preservation.
- Simple Mode in the main window:
  - Output formats: MP4 (H.264 or H.265 with AAC), MKV (H.264 + AAC), WebM (VP9 + Opus), MP3,
    AAC (M4A), Opus, Ogg Vorbis, FLAC and WAV. Only formats whose encoders are present in the
    installed FFmpeg are offered, and video formats only for sources that contain video.
  - Quality presets (High, Balanced, Small file); lossless formats always keep full quality.
    Audio bitrates: MP3 320/192/128 kb/s, AAC (M4A) 256/160/96 kb/s, Opus 160/96/64 kb/s;
    Ogg Vorbis uses variable bitrate.
  - Tracks: video formats keep every audio track. MP4 and WebM convert text subtitles to MP4
    text and WebVTT (image-based subtitles are left out); MKV copies all subtitles. Cover art is
    kept in MP4, MKV, MP3, AAC (M4A) and FLAC. Audio formats extract the default audio track;
    lossy ones mix surround sound down to stereo.
  - Destination folder, remembered between sessions (Videos or Music the first time). Output names
    never overwrite existing files: a number is added, as in "clip (1).mp4".
  - "You'll get" card: output name and what goes into it (video, audio tracks, subtitles, cover
    art, what is left out), with an honest size estimate: calculated when the bitrate fixes it,
    measured after a preview with the same settings, otherwise "Depends on the content".
  - Hardware encoding: MP4 and MKV video (H.264 and H.265) is encoded on the graphics card when
    one is supported (NVIDIA NVENC, AMD AMF or Intel Quick Sync), about 2 times faster for H.264
    and 5 times faster for H.265 on an RTX 4070 SUPER, at the same picture quality with somewhat
    larger files. Each encoder is checked with a test encode at startup, in the background; on
    by default and switchable in Settings. If the graphics card encoder fails, the error offers
    to convert again with software encoding. WebM (VP9) uses fast multithreaded software
    encoding.
  - Progress with percentage, speed and remaining time; cancel; Show in Folder after success.
  - Failures are explained in plain language (what happened, what to do) with the most likely fix
    as a button and the technical details one click away.
  - Settings and opening other files are locked while a conversion runs, and closing the window
    asks for confirmation.
- Advanced Mode (Ctrl+M switches mode), each setting explained with its recommended value and
  a live output summary; Simple choices carry over:
  - Video: stream copy (offered only when the container can hold the source codec), software or
    graphics card encoder, constant quality (CRF) or target bitrate, preset, resolution (never
    upscaled), aspect ratio, frame rate and pixel format (including 10-bit for H.265 and VP9).
  - Audio: codec (only those the container can hold, or a copy of the original), bitrate,
    sample rate and channels, applied to every kept audio track.
  - Tracks: keep or leave out each track; tracks the format can't hold are disabled with the
    reason, and audio-only formats keep one audio track.
  - Output and filters: container (MP4 or MKV for the same codecs), deinterlacing (automatic
    for frames marked as interlaced, off or always), fast start for web playback, metadata
    and chapters, and loudness normalization (EBU R128).
  - Back in Simple Mode, "Quality: Custom (set in Advanced)" shows with a Reset to Balanced
    button. Choosing a quality resets the quality levels; switching formats resets the
    codec-specific choices and tracks.
- Queue: convert many files one after another, each with its own format, quality and Advanced
  choices.
  - Add files with **Add Files…**, by dropping several files on the window (also during a
    conversion), or with **Add to Queue** (Ctrl+Shift+Enter) on the Convert tab, which keeps
    every setting of the open file. Files are read in the background; unreadable ones are
    listed with the reason.
  - Each row shows the target format, a status badge, live progress or the result (time taken,
    the reason for a failure, where it was canceled) and the size: estimated while waiting
    when the bitrate fixes it, measured when done.
  - Start Queue / Stop Queue, Pause after the current file, Move Up/Down (Alt+Up/Down),
    Retry, Remove (Delete) and Clear Finished. The footer shows "File 2 of 6", overall
    progress and the counts per status; the tab shows how many files are left.
  - Only one conversion runs at a time: Convert is unavailable while the queue runs, and the
    queue can start once a conversion on the Convert tab finishes. Progress shows in the status bar and on the
    taskbar, a notification reports when the queue finishes, and quitting asks first.
- History: the latest 100 conversions from the Convert tab and the queue, newest first, kept in
  a file on this computer only. Each row shows when, the source and output names, the format
  and quality ("· Custom" after Advanced changes), the result (Saved, Failed, Canceled, or
  File moved when the output is no longer there), size and time taken. Saved files can be
  opened or shown in their folder; failures open the explanation and technical details.
  Clear History… asks first and never touches the converted files.
- Settings, saved as they change:
  - Conversion engine: shows the FFmpeg in use and where it came from. Browse… chooses
    ffmpeg.exe or ffprobe.exe (each is run first, and one that isn't FFmpeg is refused; the
    other program in the same folder comes along). The choice applies at once when FFmpeg was
    missing, otherwise from the next start; Find Automatically goes back. Check Again repeats
    the graphics card check.
  - Defaults for newly opened files: save to the same folder as the original or to a chosen
    folder, the format for video files and for audio files, and the quality.
  - Performance: hardware acceleration on or off, naming the detected graphics card.
  - Temporary files: the folder previews are made in.
  - Appearance: follow Windows, light or dark, applied at once.
  - Updates: Update automatically (on by default) checks the latest GitHub release when the app
    starts, downloads the new installer in the background and verifies it against the SHA-256
    published with the release. It then offers Restart and Update, which installs and opens
    the app again; otherwise the update installs when the app closes. Check Now and Help →
    Check for Updates… check at any time, and What's New opens the release page. Copies not
    set up with the installer open the download page instead.
- Converted preview window:
  - **Preview 15 s** converts a 15-second sample, starting a third of the way into the file, with
    the exact settings. Files of 15 seconds or less are converted entirely. **Full Preview**
    converts the whole file without saving it.
  - The window always says it shows the converted output, never the original: a "Converted
    preview" badge stays on the picture. Audio previews show the track as it sounds in the
    output.
  - Files with several audio tracks or with subtitles get an audio track menu and a subtitles
    menu (off by default); text subtitles are drawn over the picture.
  - Playback-only controls (play/pause, seek, mute, volume) with Space/K, Left/Right, M and Esc;
    Ctrl+Enter converts the full file with the same settings.
  - A side panel shows the part previewed, the preview size, the estimated full size (measured
    from the preview, or calculated from the bitrate) and the settings used.
  - If the settings change while the window is open, it offers to update the preview. Failures
    say where reading stopped when the source is damaged. Preview files are deleted when the
    window closes.

## Planned Features

- Code-signed installer.
- Keeping the queue between sessions.

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
- The installer includes FFmpeg. When running from source, FFmpeg and FFprobe must be on
  `PATH`, or their full paths set in the `RADIO_VIDEO_FFMPEG` and `RADIO_VIDEO_FFPROBE`
  environment variables. On Windows FFmpeg can be installed with:

```powershell
winget install --id Gyan.FFmpeg -e
```

FFmpeg is looked up in this order: the environment variables, the copy bundled with the
installed application, then `PATH`.

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

Pass `--debug` for verbose logging. `--ui-gallery` opens a gallery of the design foundations,
components and every screen state with demo data; add `--capture DIR` to save them as PNG files.

Open a file, choose a format, quality and destination folder in the **Convert** panel, and press
**Convert**.

## Building

```powershell
python -m build
```

This produces a source distribution and a wheel in `dist/`.

### Windows installer

The installer is built with [PyInstaller](https://pyinstaller.org/) and
[Inno Setup 6](https://jrsoftware.org/isinfo.php) (`ISCC.exe` on `PATH`, in its default folder,
or set in the `ISCC` environment variable):

```powershell
python -m pip install -e ".[installer]"
python scripts/build_installer.py --version 1.2.3
```

The script freezes the application, adds the latest GPL build of FFmpeg 9.0 from
[BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds) (verified against the SHA-256 digest
GitHub publishes for it), downloads the corresponding FFmpeg source and build scripts, and writes
`dist/Radio-Video-Setup-1.2.3.exe` together with the source archives. `--skip-installer` stops
after freezing; `--skip-ffmpeg` leaves FFmpeg out. CI builds and smoke-tests the installer on
every pull request.

## Installing a Release

Each [GitHub release](https://github.com/dcCarreto/radio-video/releases) includes:

- `Radio-Video-Setup-<version>.exe`: the Windows installer (64-bit Windows 10 or 11), with FFmpeg
  included. It installs for the current user without administrator rights, or for all users,
  and adds a Start menu shortcut and an uninstaller. From 0.5.0, installed copies update
  themselves from later releases (Settings → Updates).
- The FFmpeg source and build scripts that correspond to the bundled FFmpeg.
- A wheel and a source distribution, for installing with pip (Python 3.11 or newer, FFmpeg
  installed separately):

```powershell
python -m pip install radio_video-<version>-py3-none-any.whl
radio-video
```

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

### 2026-11-07

- **#59 feat: update automatically from GitHub releases**: installed copies check for a new
  version at startup, download the installer in the background, verify its SHA-256 and offer
  Restart and Update (or install when the app closes). Settings → Updates turns this off and
  has Check Now; Help → Check for Updates… checks at any time.
- **#57 feat: make every setting work**: Settings now chooses the FFmpeg to use (checked before
  it is accepted), where converted files are saved, the format and quality new files start
  with, the folder for previews and the theme. Changes are saved as they are made.
- **#53 feat: choose the audio track and subtitles in the player**: files with several audio
  tracks or with subtitles get menus in the preview window's player to switch the audio track
  and turn subtitles on, with each track named by its language and title. Text subtitles are
  shown over the picture.
- **#51 feat: keep a history of conversions**: the History tab lists the latest 100 conversions
  from the Convert tab and the queue, stored only on this computer, with the result, size and
  time taken. Saved files can be opened or shown in their folder, failures show what happened,
  and files moved since show as such. Clear History asks first and keeps the converted files.
- **#49 feat: convert many files with the queue**: the Queue tab converts files one after
  another, each with its own format, quality and Advanced choices. Add files with Add Files…,
  by dropping several files on the window, or with Add to Queue on the Convert tab; start,
  stop, pause after the current file, reorder, retry and remove them, with live progress, a
  notification when the queue finishes and a confirmation before quitting.
- **#47 fix: retry the FFmpeg download when the daily build is being replaced**: the installer
  build reads the FFmpeg release again and retries when the daily rebuild briefly removes the
  file it was about to download, instead of failing.
- **#45 feat: make Advanced Mode work**: every setting on the Video, Audio, Tracks and Output
  and filters tabs now changes the conversion and the previews: stream copy, software or
  graphics card encoder, constant quality or target bitrate, preset, resolution, aspect ratio,
  frame rate, pixel format, audio codec or copy, bitrate, sample rate, channels, per-track
  choice, MP4/MKV switch, deinterlacing, fast start, metadata and loudness normalization. Only
  options that fit the format and the file are offered. Simple Mode shows when Advanced choices
  are in effect and can reset them; MP4 files now start playing on the web before they finish
  downloading.
- **#43 feat: play the opened file as it is, without converting**: a Play button next to Open
  (Ctrl+Shift+Space) opens the loaded file in the built-in player straight away, showing its size
  and every track, with nothing converted or written. It stays available during a conversion,
  offers a converted preview when the player can't open the file, and the original and converted
  previews link to each other for a quick comparison.

### 2026-11-03

- **#39 feat: encode video on the graphics card when available**: MP4 and MKV conversions
  and previews use NVIDIA NVENC, AMD AMF or Intel Quick Sync when a test encode at startup shows
  the encoder works, about 2 times faster for H.264 and 5 times faster for H.265 on an RTX 4070
  SUPER at the same picture quality. The Settings switch for hardware acceleration now works
  and names the detected graphics card, and a graphics card failure offers to convert again
  with software encoding.
- **#38 fix: make WebM (VP9) conversions about 8 times faster**: VP9 encoding uses
  multithreaded rows and a faster speed setting, going from about 0.2 to 1.5 times real time at
  1080p with practically the same quality.
- **#33 feat: ship a Windows installer with FFmpeg**: each release now includes
  `Radio-Video-Setup-<version>.exe`, which installs without administrator rights and bundles a
  GPL build of FFmpeg 9.0 (verified against its published SHA-256 digest); the matching FFmpeg
  source and build scripts are attached to the release, and CI builds and smoke-tests the
  installer on every pull request.
- **#32 feat(ui): add the planned Advanced Mode, Queue, History and Settings screens**: preview
  versions of the upcoming screens, marked as planned, so their layout can be reviewed before
  they work.
- **#31 feat(ui): add the converted preview window**: previews open in their own window with a
  video canvas, player controls, the measured size and a notice when the settings change.
- **#30 feat(ui): rebuild the main window on the new design**: start screen, file view with the
  tracks table and source details, the Convert panel with format, quality, output name and size
  estimate, progress, results, error dialogs with next steps, and a quit confirmation; the
  window follows the Windows colour scheme and works by keyboard alone.
- **#29 feat(ui): add UI state machine, view models and error messages**: the screen flow,
  texts and FFmpeg error classification are kept separate from the widgets and covered by tests.
- **#28 feat: keep every audio track, subtitles and cover art where the format allows**:
  conversions keep all audio tracks, convert subtitles to the output format and keep cover art;
  new bitrates for M4A and Opus, quality-based Vorbis, and the partial output is written as
  `name.ext.part`.

### 2026-11-02

- **#26 feat(ui): add design system widgets**: the building blocks of the redesigned
  interface, painted from the theme tokens: buttons with shortcut hints, badges, segmented
  controls, tab and step strips, the drop zone with its one-file rules, the grouped format
  picker, progress bars that announce progress every 10%, notes, the facts grid, the tracks
  table, player controls, check boxes and switches.
- **#24 feat(ui): add design tokens, theme manager, icons and UI gallery**: foundation of the
  redesigned interface: light and dark colour tokens checked for WCAG AA contrast, a theme that
  follows the Windows colour scheme, the type scale, bundled Lucide icons, a keyboard focus ring
  and a `--ui-gallery` debug window for comparing screens with the design.
- **#22 fix: make release publishing resilient to transient API failures**: publishing skips
  releases that already exist, replaces leftover drafts, retries failures and accepts releases
  GitHub published despite an error; release notes leave out repository bookkeeping.
- **#21 ci: add job timeouts and stack dumps for stalled tests**: CI jobs fail within 20 minutes
  instead of hanging, and stalled tests print the stack of every thread.
- **#19 ci: bump actions/checkout from 4 to 7** and **#18 ci: bump actions/setup-python from 5
  to 7**: GitHub Actions dependency updates.
- **v0.1.0 released** from #17.
- **#15 chore: depend on PySide6 Essentials and Addons only**: installs only the Qt modules the
  application uses, dropping Qt WebEngine and Qt PDF (about 130 MB) from the installation.
- **#11 feat: add preview player with short and full previews**: previews converted with the
  selected settings, either a 15-second sample or the whole file, played in a playback-only
  player and deleted when closed. A short preview also measures the output size for
  quality-based formats.
- **#12 fix: use a Windows Job Object to stop FFmpeg and its children**: canceling immediately
  after a conversion starts no longer leaves FFmpeg running when it is installed as a
  package-manager shim, and FFmpeg can no longer outlive the application.
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
