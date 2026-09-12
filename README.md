# Backrec

> Setting Backrec up on a colleague's machine? Everything you need is in
> [LIES-MICH-ZUERST.txt](LIES-MICH-ZUERST.txt) — a short German guide that takes
> you from the release archive to the running window without a command line.
> This README is the developer documentation and does not repeat it.

A tiny Windows desktop app for recording **microphone** and **system audio** at the same time, then merging both into a single WAV file.

Built with `customtkinter`, `sounddevice`, `soundcard` and `ffmpeg`.

![status](https://img.shields.io/badge/status-mini--project-blue)
![license](https://img.shields.io/badge/license-MIT-green)

## Features

- One-click **REC / STOP** with a minimal always-on-top window
- A gear button in the window opens a menu: update, diagnose, open logs, about
- Records the default communication microphone and the default speaker (WASAPI loopback) simultaneously
- Live level indicators and per-source mute toggle (click the dot/label)
- Automatically follows Windows default device changes while recording
- Merges mic + system audio into one WAV via `ffmpeg`
- Exactly one merged file reaches the configured target folder; the raw per-source takes always stay in the recording folder

## Requirements

- Windows 11 (Windows 10 is untested)
- Python **3.11** — up from the 3.10 this README used to promise. `tomllib` ships
  with 3.11, and the whole suite is pinned to it. `uv` fetches a matching
  interpreter on its own, so the bump only affects anyone deliberately working
  without it.
- `ffmpeg` — the setup fetches it through `winget install Gyan.FFmpeg -e --scope user`.
  Third-party installers trigger a SmartScreen warning; choose *Weitere
  Informationen* and then *Trotzdem ausführen*. If `winget` is unavailable,
  install it manually from <https://www.gyan.dev/ffmpeg/builds/> and run
  `Setup.cmd` again.

## Getting started

Double-click `Setup.cmd`. It bootstraps `uv`, builds the environment from
`uv.lock`, migrates an existing `.env`, asks for the folders, fetches `ffmpeg`,
runs the diagnosis, offers a desktop shortcut and offers to start.

Afterwards, double-click the desktop icon — or `Start.cmd`.

The manual route still works:

```powershell
uv sync --locked
.venv\Scripts\pythonw.exe -m backrec
```

`pythonw main.pyw` opens the same window; the file is three lines that call the
package.

## Commands

All commands run through `python -m backrec <command>` or the generated
`.venv\Scripts\backrec.exe`.

| Command | What it does | Exit code |
| --- | --- | --- |
| `setup [--unattended] [--start]` | The seven-step setup. Idempotent. | 0, else 1 or 2 |
| `start` | Detached, windowless start via `pythonw.exe -m backrec` | 0, 1, **3** if already running |
| `stop` | Writes a stop request, waits 30 s, then kills the tree | 0, else 1 |
| `status` | Running, pid, start time, recording, folders, shortcut | 0 |
| `doctor [--json] [--report]` | Read-only self check | 0, 1 on any failure |
| `shortcut [--status] [--remove]` | The desktop icon | 0, else 1 |
| `uninstall [--purge]` | Removes shortcut and environment, keeps recordings | 0, else 1 |
| `update [<zip>] [--git]` | Applies a release archive, or pulls | 0, else 1 |
| `logs [--follow]` | Opens the log folder, or tails the log | 0, else 1 |
| `release [--output <dir>]` | Builds the distribution archive | 0, else 1 |
| `about` | Version, folders, path of the guide, how to remove | 0 |

`stop`, `update`, `doctor`, `uninstall` and `release` exist only as commands and
— for the first four — as entries in the window's gear menu. There is
deliberately no `Stop.cmd` or `Update.cmd`: every file in the root folder is a
question a colleague might ask.

## Configuration

Settings live in `%LOCALAPPDATA%\MemoSuite\Backrec\config.toml`, outside the
repository, so an update that overwrites the folder loses nothing.
`MEMOSUITE_HOME` moves the whole suite directory, `BACKREC_CONFIG` redirects the
file alone.

```toml
recording_dir = 'D:\Aufnahmen\Recording'
target_dir    = 'D:\Aufnahmen\Input'
```

Four layers, weakest first: code defaults → `config.toml` → `BACKREC_*`
environment variables → command line options. `doctor` names the layer each
effective value came from. `%VAR%`, `$VAR` and `~` are expanded and the result
must be absolute — in the retired `.env` a `%USERPROFILE%` never expanded at all
and landed in a path verbatim.

`config.example.toml` is the commented template and carries placeholders only.
A `.env` left in the repository is migrated once on setup, then stays where it
is and is reported by `doctor` as no longer effective.

## Recording results

A finished recording produces **exactly one** merged WAV in `target_dir`, named
after the recording's timestamp, with a counter appended if that name is taken.
The copy is verified against the original by size before success is reported.

If the merge fails — `ffmpeg` missing, `ffmpeg` erroring, an unusable output, a
take missing or too small — **nothing** reaches `target_dir`. Both raw takes stay
in `recording_dir`, the window names the cause and their whereabouts, and the
full detail is in the log. This replaces the former behaviour of copying both
raw takes into the target folder: the tool downstream reads every file it finds
there and would transcribe the same conversation twice, once from each side.

`ffmpeg` is therefore checked **before** the window opens, not at STOP. Learning
that the mixer is missing after a half-hour meeting is the most expensive
possible moment for that news.

## How it works

- Microphone capture uses `sounddevice` (PortAudio) against the current default communications device.
- System audio capture uses `soundcard`'s WASAPI loopback against the current default playback device.
- Both are recorded into separate WAV files, then combined using `ffmpeg`'s `amix` filter (`duration=longest`, `normalize=0`) so neither source is clipped.
- Device changes (e.g. switching headsets) are detected while recording and the affected stream is reopened automatically.
- Exactly one instance runs per installation, tracked by a record in
  `%LOCALAPPDATA%\MemoSuite\Backrec\state\` that carries pid, process creation
  time and folder. A second start raises the existing window and exits 3.
- Closing the window during a recording runs the full closing sequence first, so
  nothing is lost. `stop` does the same through a request file, because console
  signals never reach a `pythonw` process.

## Release and update

`backrec release` builds `Backrec-<version>.zip` into
`%LOCALAPPDATA%\MemoSuite\releases\`. The file selection is an allow list over
`git ls-files`; `.venv`, `logs`, `.env`, `config.toml`, `*.lnk` and
`openspec/changes/` never get in. Four checks abort the build hard: the lock file
must match `pyproject.toml`, no packed file may contain a user path or something
that looks like an access key, and `LIES-MICH-ZUERST.txt` must obey all of its
rules (encoding, line count, line length, vocabulary, the eight sections in
order).

The archive carries `Backrec\` as its single top level plus a
`release-manifest.json` listing every file with its SHA-256.

Two update routes, both without Git:

- **A** — extract the new archive over the folder, double-click `Setup.cmd`. The
  setup notices the version change, stops a running instance, syncs, removes
  files the new release no longer has, runs the diagnosis and offers to start.
- **B** — the gear menu entry *Aktualisieren…*. The archive is staged next to the
  folder, every file checked against its checksum, and a detached PowerShell 5.1
  helper outside the folder mirrors the files in and restarts. The folder keeps
  its name, so the desktop shortcut stays valid, and `.venv` stays where it is.

`update --git` is the developer route: `git pull --ff-only`, sync, diagnosis. It
refuses without a `.git` folder and points at the archive route.

## Working with the neighbouring tools

Optional. Backrec writes its result into `target_dir`; if that folder is the
input folder of AMD-Transcription, a finished recording becomes text on its own.
`setup` can note the chosen base folder in
`%LOCALAPPDATA%\MemoSuite\suite.toml`, which the neighbouring tools use as a
suggestion when they are set up. Nothing reads that file at runtime — every tool
of the suite stands alone.

## Tests

```powershell
uv run pytest
```

The operating layer and every pure function are covered. The recording core is
not: it needs real audio devices.

## Project status

Backrec is a small personal utility, shared as-is in case it's useful to others. It's intentionally minimal — no installer, no auto-update, no telemetry.

## Contributing

Issues and pull requests are welcome, but please keep in mind this is a mini project maintained on a best-effort basis.

## License

Licensed under the [MIT License](LICENSE).
