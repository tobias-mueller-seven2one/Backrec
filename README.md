# Backrec

A tiny Windows desktop app for recording **microphone** and **system audio** at the same time, then merging both into a single WAV file.

Built with `customtkinter`, `sounddevice`, `soundcard` and `ffmpeg`.

![status](https://img.shields.io/badge/status-mini--project-blue)
![license](https://img.shields.io/badge/license-MIT-green)

## Features

- One-click **REC / STOP** with a minimal always-on-top window
- Records the default communication microphone and the default speaker (WASAPI loopback) simultaneously
- Live level indicators and per-source mute toggle (click the dot/label)
- Automatically follows Windows default device changes while recording
- Merges mic + system audio into one WAV via `ffmpeg` (falls back to saving both raw files if the merge fails)
- Raw per-source recordings are kept locally; only the merged (or raw) result is copied to your configured output folder

## Requirements

- Windows 10/11
- Python 3.10+
- [ffmpeg](https://ffmpeg.org/download.html) available on your `PATH`

## Getting started

### Option 1: Start script (Windows)

Double-click [Start_Recorder.bat](Start_Recorder.bat). On first run it creates a virtual environment (`.venv`), installs dependencies from [requirements.txt](requirements.txt), and launches Backrec.

### Option 2: Manual setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pythonw main.pyw
```

## Configuration

Backrec writes files to two folders, configurable via environment variables. The easiest way to set them is via a local `.env` file (not committed to git):

```powershell
copy .env.example .env
notepad .env
```

| Variable | Purpose | Default |
| --- | --- | --- |
| `BACKREC_RECORDING_DIR` | Where raw/merged recordings are written during/after recording | `%USERPROFILE%\Backrec\Recording` |
| `BACKREC_TARGET_DIR` | Where the final merged (or raw fallback) file is copied to | `%USERPROFILE%\Backrec\Output` |

Alternatively, set them as regular environment variables before starting the app, e.g. in PowerShell:

```powershell
$env:BACKREC_RECORDING_DIR = "D:\Recordings\Raw"
$env:BACKREC_TARGET_DIR = "D:\Recordings\Output"
pythonw main.pyw
```

## How it works

- Microphone capture uses `sounddevice` (PortAudio) against the current default communications device.
- System audio capture uses `soundcard`'s WASAPI loopback against the current default playback device.
- Both are recorded into separate WAV files, then combined using `ffmpeg`'s `amix` filter (`duration=longest`, `normalize=0`) so neither source is clipped.
- Device changes (e.g. switching headsets) are detected while recording and the affected stream is reopened automatically.

## Project status

Backrec is a small personal utility, shared as-is in case it's useful to others. It's intentionally minimal — no installer, no auto-update, no telemetry.

## Contributing

Issues and pull requests are welcome, but please keep in mind this is a mini project maintained on a best-effort basis.

## License

Licensed under the [MIT License](LICENSE).
