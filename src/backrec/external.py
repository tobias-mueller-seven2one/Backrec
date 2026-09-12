"""ffmpeg: finding it, running it, and fetching it without administrator rights.

Two findings, never one (design D12): "not in the search path" and "found but
the call fails" have different causes and different next steps, and a check
that folds them together sends the reader to the wrong place.

Fetched through `winget --scope user` (design D13). Not shipped inside the
repository: a public MIT repository with a bundled GPL binary is a licensing
statement nobody wants to make. Not through a Python package either, which
would tie the version of the mixer to a wheel.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable

from .logging_setup import get_logger

logger = get_logger(__name__)

FFMPEG_NAME = "ffmpeg"
VERSION_TIMEOUT_SECONDS = 5
INSTALL_TIMEOUT_SECONDS = 900

WINGET_PACKAGE = "Gyan.FFmpeg"
MANUAL_DOWNLOAD_URL = "https://www.gyan.dev/ffmpeg/builds/"

_VERSION_PATTERN = re.compile(r"ffmpeg version (\S+)")

Runner = Callable[[list[str], float], "subprocess.CompletedProcess[str]"]


@dataclass(frozen=True)
class FfmpegState:
    """What is known about ffmpeg on this machine."""

    found_at: str | None
    runs: bool
    version: str = ""
    detail: str = ""

    @property
    def usable(self) -> bool:
        return self.found_at is not None and self.runs


@dataclass(frozen=True)
class DependencyResult:
    ok: bool
    message: str
    next_step: str = ""


def run_command(command: list[str], timeout: float = INSTALL_TIMEOUT_SECONDS) -> subprocess.CompletedProcess[str]:
    """Runs an external command. Never raises."""
    try:
        return subprocess.run(
            command,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return subprocess.CompletedProcess(args=command, returncode=1, stdout="", stderr=str(exc))


def which(name: str = FFMPEG_NAME) -> str | None:
    return shutil.which(name)


def inspect(
    *,
    which_fn: Callable[[str], str | None] = which,
    runner: Runner = run_command,
) -> FfmpegState:
    """Looks for ffmpeg and, if it is there, actually calls it."""
    found = which_fn(FFMPEG_NAME)
    if found is None:
        return FfmpegState(found_at=None, runs=False, detail="nicht im Suchpfad gefunden")

    result = runner([found, "-version"], VERSION_TIMEOUT_SECONDS)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()[:300]
        logger.warning("ffmpeg gefunden (%s), der Aufruf scheitert: %s", found, detail)
        return FfmpegState(found_at=found, runs=False, detail=detail or "der Aufruf scheitert")

    match = _VERSION_PATTERN.search(result.stdout or "")
    return FfmpegState(found_at=found, runs=True, version=match.group(1) if match else "")


def install(runner: Runner = run_command) -> subprocess.CompletedProcess[str]:
    """Fetches ffmpeg into the user profile, without administrator rights."""
    logger.info("ffmpeg fehlt -- Beschaffung ueber winget wird versucht")
    return runner(
        [
            "winget",
            "install",
            "--id",
            WINGET_PACKAGE,
            "-e",
            "--scope",
            "user",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ],
        INSTALL_TIMEOUT_SECONDS,
    )


def ensure(
    *,
    which_fn: Callable[[str], str | None] = which,
    runner: Runner = run_command,
) -> DependencyResult:
    """Makes sure a usable ffmpeg is there, and says what happened.

    An ffmpeg that is already there is never installed again. After a fresh
    installation the check runs a second time, because a successful install does
    not necessarily reach the search path of the running session - in that case
    the message says that a new window or a new sign-in is needed.
    """
    state = inspect(which_fn=which_fn, runner=runner)
    if state.usable:
        return DependencyResult(
            ok=True,
            message=f"Das Programm zum Zusammenmischen ist vorhanden (Fassung {state.version or 'unbekannt'})",
        )

    if state.found_at is not None:
        return DependencyResult(
            ok=False,
            message="Das Programm zum Zusammenmischen ist da, lässt sich aber nicht starten.",
            next_step=(
                f"Es von {MANUAL_DOWNLOAD_URL} neu herunterladen und einrichten, danach Setup.cmd "
                "erneut doppelklicken. Fremde Installationsprogramme lösen dabei eine "
                "Sicherheitswarnung von Windows aus; dort auf Weitere Informationen und "
                "dann auf Trotzdem ausführen klicken."
            ),
        )

    result = install(runner)
    after = inspect(which_fn=which_fn, runner=runner)
    if after.usable:
        return DependencyResult(
            ok=True,
            message=f"Das Programm zum Zusammenmischen wurde eingerichtet (Fassung {after.version or 'unbekannt'})",
        )

    if result.returncode == 0:
        # Installed, but this session does not see it yet: winget extends the
        # search path of new windows, not of the one that is already open.
        return DependencyResult(
            ok=False,
            message="Das Programm zum Zusammenmischen wurde eingerichtet, ist aber noch nicht erreichbar.",
            next_step="Dieses Fenster schließen und Setup.cmd noch einmal doppelklicken.",
        )

    detail = (result.stderr or result.stdout or "").strip()
    logger.error("Beschaffung von ffmpeg fehlgeschlagen: %s", detail[:1000])
    return DependencyResult(
        ok=False,
        message=(
            "Das Programm zum Zusammenmischen fehlt. Ohne es entsteht aus einer Aufnahme "
            "keine fertige Datei."
        ),
        next_step=(
            f"Es von {MANUAL_DOWNLOAD_URL} herunterladen und einrichten, danach Setup.cmd "
            "erneut doppelklicken. Fremde Installationsprogramme lösen dabei eine "
            "Sicherheitswarnung von Windows aus; dort auf Weitere Informationen und dann "
            "auf Trotzdem ausführen klicken."
        ),
    )


def is_available() -> bool:
    """Short answer for the checked start sequence."""
    return inspect().usable
