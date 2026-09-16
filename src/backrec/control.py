"""The control surface: every command once, as a function with one result.

Command line and window are two faces of the same functions (design D9). Every
decision comes back as a dataclass; `cli.py` turns it into console text and a
return value, `app.py` into a dialog or a status line. No decision logic in the
presentation, no output in the core - which is why the window needs no procedure
of its own and can never drift away from the command of the same name.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, TextIO

from . import (
    config as config_module,
    doctor,
    external,
    instance,
    paths,
    preflight,
    release as release_module,
    shortcut as shortcut_module,
    wizard,
)
from .console import Assistant
from .logging_setup import close_files, configure_logging, get_logger

logger = get_logger(__name__)

# Everything this module runs to answer a question is also reachable from the
# window, which owns no console. Without the flag Windows hands each of those a
# console of its own (see `merge.NO_WINDOW`).
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

SETUP_STEPS = 7

START_READY_TIMEOUT_SECONDS = 30.0
START_POLL_SECONDS = 0.5

# Three deadlines, not one. The 30 s of design D10 were promised to cover
# threads ending, a mix running and a long recording being copied - a sum that
# was never added up: mixing alone may take `merge.MERGE_TIMEOUT_SECONDS`, four
# times as long as the deadline above it. So the base deadline stays what it is
# and now means only what it can mean - the wait for an application that reports
# nothing. An application that keeps reporting work extends it beat by beat, and
# the ceiling ends the wait whatever happens (design D1, D4).
STOP_TIMEOUT_SECONDS = 30.0
STOP_GRACE_SECONDS = 10.0
STOP_LIMIT_SECONDS = 300.0
STOP_POLL_SECONDS = 0.5
STOP_PROGRESS_SECONDS = 5.0

UV_VERSION = "0.11.21"
UV_INSTALL_SCRIPT = f"https://astral.sh/uv/{UV_VERSION}/install.ps1"

# Deliberately without `--reinstall-package backrec`, even though a plain sync
# does not notice changed sources of this package. Reinstalling cannot happen
# from here: this process runs *inside* the environment that would have to be
# replaced, and Windows does not release a running program file. The one place
# that can do it stands outside and does: `scripts\win\bootstrap-uv.ps1`, which
# runs before every setup.
SYNC_COMMAND: tuple[str, ...] = ("uv", "sync", "--locked", "--no-dev", "--no-editable")

# Set by Setup.cmd once the bootstrap has built the environment. Without the
# hint step 2 would build it a second time within the same minute.
ENV_BOOTSTRAPPED = "BACKREC_ENV_READY"

# The three uninstall sentences. They appear verbatim here and in the "Entfernen"
# section of the guide, and a test keeps them identical. The same text in two
# places is deliberate: neither place is reachable from the other - whoever has
# the window does not have the guide open, and whoever reads the guide has no
# window yet.
# Both ways to change a setting, named in the closing summary of every run.
# Both, because they suit two different people: one runs Setup.cmd again and
# answers questions, the other opens the file and reads the comments.
SETTINGS_CHANGE_HINT = "Ändern: Setup.cmd erneut ausführen oder die Datei im Editor öffnen."

UNINSTALL_SENTENCES: tuple[str, str, str] = (
    "Schließe das Fenster.",
    "Lösche das Symbol vom Desktop.",
    "Lösche danach den Ordner, in den du das Archiv entpackt hast.",
)


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    code: int = 0
    lines: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SetupResult:
    ok: bool
    code: int
    version: str = ""
    shortcut_installed: bool = False
    checks: tuple[doctor.Check, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class StartResult:
    started: bool
    already_running: bool = False
    pid: int | None = None
    problem: preflight.Problem | None = None
    message: str = ""
    foreign_folder: str | None = None


@dataclass(frozen=True)
class StopResult:
    stopped: bool
    was_running: bool
    forced: bool = False
    message: str = ""
    raw_takes: str | None = None


@dataclass(frozen=True)
class StatusReport:
    running: bool
    pid: int | None
    started: str
    version: str
    recording: bool
    shortcut_installed: bool
    config_path: Path
    logs_path: Path
    state_path: Path
    repo_path: Path
    foreign_folder: str | None = None


@dataclass(frozen=True)
class DoctorReport:
    checks: tuple[doctor.Check, ...]
    code: int
    report_path: Path | None = None


# --- Helpers ------------------------------------------------------------------


def _run(
    command: list[str],
    cwd: Path | None = None,
    timeout: float = 1800,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return subprocess.CompletedProcess(args=command, returncode=1, stdout="", stderr=str(exc))


def short_reason(result: subprocess.CompletedProcess[str]) -> str:
    """One plain sentence derived from what a failed command left behind.

    The raw output is the opposite of what the assistant rules ask for: English,
    technical, several lines. It goes into the log; what comes out here is the
    single sentence the reader's next move depends on.
    """
    detail = (result.stderr or result.stdout or "").strip().lower()
    if not detail:
        return "das nötige Kommando gibt es auf diesem Rechner nicht"

    causes = (
        (
            ("not recognized", "nicht gefunden", "winerror 2", "not found"),
            "das nötige Kommando gibt es auf diesem Rechner nicht",
        ),
        (
            ("no such host", "unable to connect", "timed out", "getaddrinfo", "ssl", "proxy",
             "certificate", "network"),
            "der Rechner kam nicht ins Internet",
        ),
        (
            ("denied", "verweigert", "forbidden", "not permitted", "elevation"),
            "Windows hat es nicht zugelassen",
        ),
    )
    for needles, reason in causes:
        if any(needle in detail for needle in needles):
            return reason

    return "es hat nicht geklappt; die Einzelheiten stehen in der Aufzeichnung"


def foreign_installation(repo: Path | None = None) -> str | None:
    """The folder of a second, unpacked copy that is running right now.

    Its record never blocks this start - but it is the answer to the question
    that follows, which is why a window is on screen that this folder knows
    nothing about. Left unsaid, the two copies look like one that misbehaves.
    """
    root = repo or paths.repo_root()
    return instance.foreign_repo(instance.read_record(), root)


def launcher(repo: Path | None = None) -> Path:
    """The windowless interpreter the shortcut and `start` both use."""
    return shortcut_module.launcher(repo)


def start_command(repo: Path | None = None) -> list[str]:
    """The command line that opens the window - the one the icon carries too.

    Kept in one place so the three ways in cannot drift apart: whatever the
    desktop icon starts, `Start.cmd` and step 7 of the setup start as well.
    Backrec has no tray icon, so the window *is* the proof that the start
    worked; a route that only launched a loop without one would satisfy every
    check on processes and leave the colleague looking at nothing.
    """
    root = repo or paths.repo_root()
    return [str(launcher(root)), *shortcut_module.LAUNCH_ARGUMENTS.split()]


def read_installed_version(path: Path | None = None) -> str | None:
    """The version that was last set up successfully."""
    target = path or paths.installed_record_path()
    if not target.is_file():
        return None
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None
    value = raw.get("version") if isinstance(raw, dict) else None
    return str(value) if value else None


def write_installed_version(version: str, path: Path | None = None) -> Path:
    target = path or paths.installed_record_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {"version": version, "at": datetime.now().isoformat(timespec="seconds")}, indent=2
        ),
        encoding="utf-8",
    )
    return target


# --- Setup --------------------------------------------------------------------


def _store_python_placeholder() -> str | None:
    """The Microsoft Store stand-in for Python, if it is on the search path."""
    found = shutil.which("python")
    if found and "windowsapps" in found.lower():
        return found
    return None


def _ensure_uv(assistant: Assistant) -> bool:
    """Step 1: the helper that provides environment and language runtime."""
    if _store_python_placeholder():
        assistant.note(
            "Im Suchpfad liegt nur ein Platzhalter aus dem Microsoft Store. "
            "Das ist kein Problem: die Einrichtung bringt ihre eigene Fassung mit."
        )

    if shutil.which("uv"):
        assistant.ok("Das Hilfsprogramm für die Einrichtung ist vorhanden")
        return True

    assistant.note("Das Hilfsprogramm für die Einrichtung fehlt und wird jetzt geholt.")
    winget = _run(
        [
            "winget",
            "install",
            "--id",
            "astral-sh.uv",
            "-e",
            "--scope",
            "user",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ]
    )
    if winget.returncode == 0 and shutil.which("uv"):
        assistant.ok("Das Hilfsprogramm wurde über die Windows-Paketverwaltung eingerichtet")
        return True

    logger.warning(
        "winget-Weg fehlgeschlagen: %s", (winget.stderr or winget.stdout or "").strip()[:500]
    )
    fallback = _run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            f"irm {UV_INSTALL_SCRIPT} | iex",
        ]
    )
    if fallback.returncode == 0 and shutil.which("uv"):
        assistant.ok("Das Hilfsprogramm wurde über den zweiten Weg eingerichtet")
        return True

    logger.error(
        "Zweiter Weg fehlgeschlagen: %s", (fallback.stderr or fallback.stdout or "").strip()[:500]
    )
    assistant.fail(
        "Das Hilfsprogramm für die Einrichtung ließ sich auf beiden Wegen nicht holen.",
        "Internetverbindung prüfen und Setup.cmd erneut doppelklicken. "
        "Bleibt es dabei, den Bericht der Diagnose an Tobias schicken.",
    )
    # Both ways named separately: "neither worked" leaves open whether the
    # internet, the permissions or the machine were at fault - and what the
    # reader does next depends on exactly that.
    assistant.note(f"Über die Windows-Paketverwaltung: {short_reason(winget)}.")
    assistant.note(f"Über den zweiten Weg: {short_reason(fallback)}.")
    return False


def _stop_running_application(assistant: Assistant, repo: Path) -> None:
    """Unconditional stop before anything touches the environment (design D5).

    Hygiene of the setup, no routine of its own: whoever replaces the
    environment must not leave anything running out of it. The one place that
    replaces it stands outside - `scripts\\win\\bootstrap-uv.ps1` runs
    before every setup and replaces the package inside `.venv` with
    `--reinstall-package backrec`; an application that took its code from there
    keeps running on code that no longer exists on disk, and nothing on screen
    says so. No version is read and none is compared - a run on an unchanged
    version replaces the same files as any other.

    The side effect is deliberate: a colleague who double-clicks `Setup.cmd`
    next to an open window always loses that window, and step 7 offers the
    start again.
    """
    if instance.running_instance(repo=repo) is None:
        return

    assistant.note("Die laufende Anwendung wird vorher beendet.")
    outcome = stop(repo)
    if not outcome.stopped:
        assistant.warn(outcome.message)
        return

    # A forced stop counted as success here and said nothing - on exactly the
    # route that made this case routine: `Setup.cmd` next to a running
    # recording. The colleague this concerns is the one who would otherwise
    # never learn that his recording was cut off, nor where its takes are
    # (design D8). Not a reason to abort: the application is gone, the
    # environment can be replaced, and stopping here would help nobody.
    if outcome.forced:
        assistant.warn(outcome.message)


def _discard_broken_environment(repo: Path) -> bool:
    """Removes a half-deleted environment.

    An uninstall that ran from inside the environment cannot remove it entirely:
    Windows does not release the running program file. What stays is a folder
    without `pyvenv.cfg` that a rebuild silently leaves alone - and every start
    afterwards fails for a reason nobody connects to the uninstall.
    """
    venv = repo / ".venv"
    if not venv.is_dir() or (venv / "pyvenv.cfg").is_file():
        return False

    logger.warning("Unvollstaendige Arbeitsumgebung gefunden -- wird neu aufgebaut: %s", venv)
    shutil.rmtree(venv, ignore_errors=True)
    return True


def _environment_is_complete(repo: Path) -> bool:
    return (repo / ".venv" / "pyvenv.cfg").is_file() and launcher(repo).is_file()


def _package_is_stale(repo: Path) -> bool:
    """Whether a source file is newer than what the environment installed.

    Modification times, not versions: a fix between two releases carries the
    same number and would otherwise look exactly like the installed state.
    """
    marker = repo / ".venv" / "pyvenv.cfg"
    if not marker.is_file():
        return False

    try:
        installed_at = marker.stat().st_mtime
        newest = max(
            path.stat().st_mtime for path in (repo / "src" / "backrec").glob("*.py")
        )
    except (OSError, ValueError):
        return False
    return newest > installed_at


def _sync_blocked_by_itself(detail: str) -> bool:
    """Whether the environment could not be replaced because we run out of it.

    Windows does not release a running program file, so a sync started through
    the environment's own entry point fails on exactly that file. Worth telling
    apart: the plain message sends the reader to their internet connection, and
    the actual fix is the route that stands outside the environment.
    """
    lowered = detail.lower()
    denied = any(
        marker in lowered
        for marker in ("os error 5", "zugriff verweigert", "access is denied", "permission denied")
    )
    return denied and ".venv" in lowered


def _ensure_environment(assistant: Assistant, repo: Path) -> bool:
    """Step 2: the environment built from the locked list.

    On a double click the bootstrap has just built it - it has to, since this
    command already runs inside it. Building a second time within the same
    minute only costs time, so the step then reports it as done.
    """
    if _discard_broken_environment(repo):
        assistant.note("Eine unvollständige Arbeitsumgebung wurde gefunden und wird neu aufgebaut.")
    elif os.environ.get(ENV_BOOTSTRAPPED) and _environment_is_complete(repo):
        assistant.ok("Die Arbeitsumgebung ist aufgebaut")
        return True

    result = _run(list(SYNC_COMMAND), cwd=repo)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        logger.error("Aufbau der Arbeitsumgebung fehlgeschlagen: %s", detail[:2000])
        if _sync_blocked_by_itself(detail):
            assistant.fail(
                "Die Arbeitsumgebung lässt sich von hier aus nicht nachziehen, "
                "weil dieser Vorgang aus ihr heraus läuft.",
                "Setup.cmd in diesem Ordner doppelklicken -- dieser Weg steht daneben "
                "und kommt deshalb daran.",
            )
            return False
        assistant.fail(
            "Die Arbeitsumgebung ließ sich nicht aufbauen.",
            "Internetverbindung prüfen und Setup.cmd erneut doppelklicken; "
            "bleibt es dabei, den Bericht der Diagnose an Tobias schicken.",
        )
        return False

    if _package_is_stale(repo):
        logger.warning(
            "Quellen sind neuer als die eingerichtete Umgebung in %s -- "
            "Setup.cmd laufen lassen, damit der Bootstrap sie neu einrichtet",
            repo / ".venv",
        )
        assistant.warn(
            "Die Arbeitsumgebung steht, ist aber nicht ganz aktuell -- "
            "Setup.cmd doppelklicken zieht sie nach"
        )
        return True

    assistant.ok("Die Arbeitsumgebung ist aufgebaut")
    return True


def _complete_settings(assistant: Assistant, config_path: Path, repo: Path) -> None:
    """Add settings that are new in the template to an existing file.

    Never a reason to abort: the tool runs on its code defaults for every key it
    does not find, so a file that could not be extended is a worse file, not a
    broken one.
    """
    try:
        added = wizard.complete_from_template(config_path, repo=repo)
    except (OSError, config_module.ConfigError) as exc:
        logger.warning("Einstellungen nicht ergaenzbar: %s", exc)
        return

    if added:
        assistant.note(wizard.completion_message(len(added)))


def _review_settings(
    assistant: Assistant, unattended: bool, config_path: Path, repo: Path
) -> None:
    """Show what is set and offer to change it.

    Never a reason to abort, for the same reason as `_complete_settings`: the
    settings that are there keep working, whether or not anyone looked at them.
    """
    if unattended:
        return

    try:
        result = wizard.review(assistant, config_path, repo=repo)
    except OSError as exc:
        logger.warning("Einstellungen nicht aenderbar: %s", exc)
        assistant.note("Die Einstellungen ließen sich nicht ändern -- sie bleiben, wie sie waren.")
        return

    if result.changed:
        assistant.note(wizard.change_message(len(result.changed)))


def _settle_settings(assistant: Assistant, unattended: bool, config_path: Path, repo: Path) -> bool:
    """Existing settings, a migrated `.env`, or the wizard - in that order."""
    if config_path.is_file():
        assistant.ok(f"Die Einstellungen gibt es schon ({config_path})")
        _complete_settings(assistant, config_path, repo)
        _review_settings(assistant, unattended, config_path, repo)
        return True

    migration = config_module.migrate_legacy(target=config_path, repo=repo)
    if migration.migrated:
        assistant.ok(
            f"Frühere Einstellungen aus {migration.source} übernommen nach {migration.target}"
        )
        assistant.note(f"Übernommen wurden: {', '.join(migration.keys)}.")
        assistant.note(f"Die alte Datei {migration.source} bleibt liegen, wirkt aber nicht mehr.")
        _complete_settings(assistant, config_path, repo)
        return True

    if migration.missing:
        assistant.note(
            "In den früheren Einstellungen fehlten Angaben "
            f"({', '.join(migration.missing)}) -- sie werden jetzt abgefragt."
        )

    try:
        result = wizard.run(assistant, target=config_path, unattended=unattended, repo=repo)
    except OSError as exc:
        logger.error("Einstellungen konnten nicht geschrieben werden: %s", exc)
        assistant.fail(
            "Die Einstellungen ließen sich nicht speichern.",
            "Prüfen, ob genug Platz auf der Festplatte ist, und Setup.cmd erneut doppelklicken.",
        )
        return False

    assistant.ok(f"Einstellungen angelegt: {result.config_path}")
    return True


def _configure(assistant: Assistant, unattended: bool, config_path: Path, repo: Path) -> bool:
    """Step 3: settle the settings, then make sure both folders exist.

    Creating them belongs here and not only to the wizard. Two of the three ways
    into this step - settings that were already there, and a migrated `.env` -
    never pass through the wizard, and the check two steps later would then
    report both folders as missing on a machine where nothing is wrong. The
    start creates them too (design D5); doing it here as well is what makes the
    check meaningful.
    """
    if not _settle_settings(assistant, unattended, config_path, repo):
        return False

    try:
        settled = config_module.load_config(config_path, create_dirs=True)
    except config_module.ConfigError as exc:
        logger.error("Eingestellte Ordner nicht verwendbar: %s", exc, exc_info=True)
        assistant.fail(
            "Die eingestellten Ordner lassen sich nicht anlegen.",
            "Die Einstellungen prüfen oder einen anderen Ordner wählen, "
            "danach Setup.cmd erneut doppelklicken.",
        )
        return False

    assistant.note(f"Aufnahmeordner: {settled.recording_dir}")
    assistant.note(f"Zielordner: {settled.target_dir}")
    return True


def _external_dependencies(assistant: Assistant) -> bool:
    """Step 4: the program that mixes both takes into one file."""
    result = external.ensure()
    if result.ok:
        assistant.ok(result.message)
        return True

    assistant.fail(result.message, result.next_step)
    return False


def clear_stale_shortcuts(
    repo: Path,
    desktop: Path | None = None,
    report: Callable[[str], None] | None = None,
) -> int:
    """Remove leftover icons of this folder from the desktop.

    Before every enquiry about the state, not after: a leftover under a name
    this tool never carried - Tobias' desktop held one pointing at the retired
    `Start_Recorder.bat` - would otherwise simply stay and go on greeting a
    double click with a notice instead of the window.
    """
    try:
        removed = shortcut_module.remove_stale(desktop, repo)
    except OSError as exc:
        logger.warning("Veraltete Verknuepfungen nicht pruefbar: %s", exc)
        return 0

    if removed and report is not None:
        report(shortcut_module.stale_message(len(removed)))
    return len(removed)


def guided_shortcut(
    assistant: Assistant,
    unattended: bool,
    repo: Path,
    *,
    desktop: Path | None = None,
) -> bool:
    """Step 6: the desktop icon, created by the setup itself (design D14).

    The neighbouring tools ask for a manual drag here because their target is
    the startup folder. Backrec's target is the desktop, which establishes no
    logon persistence - so the colleague is spared the one step of the whole
    procedure that does not work without an explanation.
    """
    clear_stale_shortcuts(repo, desktop, assistant.note)
    existing = shortcut_module.status(repo, desktop)
    if existing.installed:
        assistant.ok("Das Symbol liegt schon auf dem Desktop")
        return True

    if not unattended and not assistant.ask_yes_no(
        "Soll ein Symbol auf dem Desktop angelegt werden?", default=True
    ):
        assistant.ok(
            "Kein Symbol angelegt -- mit dem Kommando shortcut lässt es sich jederzeit nachholen"
        )
        return False

    result = shortcut_module.create(repo, desktop)
    if not result.ok:
        # A warning, never an abort: everything else is set up, and a missing
        # icon costs a double click on Start.cmd, not the tool.
        assistant.warn(" ".join(result.lines))
        return False

    for line in result.lines:
        assistant.note(line)
    assistant.ok("Das Symbol liegt auf dem Desktop")
    return True


def _offer_start(
    assistant: Assistant,
    repo: Path,
    config_path: Path,
    *,
    unattended: bool,
    start_after: bool,
) -> None:
    """Step 7: start, offer to start, or leave it.

    An unattended run asks nothing and starts nothing unless the caller demands
    it - a script that wants a window at the end says so.
    """
    if unattended and not start_after:
        assistant.ok("Alles bereit")
        return

    if not unattended and not assistant.ask_yes_no("Jetzt starten?", default=True):
        assistant.ok("Du kannst es später über das Symbol auf dem Desktop starten")
        return

    outcome = start(repo, config_path)
    if outcome.started or outcome.already_running:
        assistant.ok("Backrec läuft")
        return
    assistant.warn(outcome.message or "Der Start hat nicht geklappt")


def _closing_note(everything_ok: bool, config_path: Path | None = None) -> str:
    """The last block of a run: the state, then where the settings are.

    Both ways to change them are named, even after a run that ended with open
    points: whoever reads this has the file in front of them exactly once, and
    the question "and how do I change that folder now" comes right here.
    """
    if everything_ok:
        head = (
            "Fertig. Das Symbol liegt auf dem Desktop. Im Fenster öffnet ein Klick "
            "auf die Statuszeile die Diagnose."
        )
    else:
        head = "Noch nicht fertig. Ein zweiter Lauf nach dem Beheben zerstört nichts."

    if config_path is None:
        return head
    return "\n".join((head, "", f"Deine Einstellungen: {config_path}", SETTINGS_CHANGE_HINT))


def setup(
    assistant: Assistant | None = None,
    *,
    unattended: bool = False,
    repo: Path | None = None,
    config_path: Path | None = None,
    offer_start: bool = True,
    start_after: bool = False,
    desktop: Path | None = None,
) -> SetupResult:
    """The complete setup in seven steps. Idempotent by construction."""
    root = repo or paths.repo_root()
    target = paths.config_path(config_path)
    version = paths.tool_version(root)
    ui = assistant or Assistant(total_steps=SETUP_STEPS, interactive=not unattended)
    ui.total_steps = SETUP_STEPS

    # During the setup the technical lines go into the log only: none of them
    # belongs between two steps of the assistant.
    configure_logging(paths.log_path(), "INFO", force=True, console=False)

    ui.header(paths.TOOL_NAME, version, "Einrichten -- das dauert ein paar Minuten.")

    ui.step(1, "Hilfsprogramme")
    if not _ensure_uv(ui):
        ui.summary(paths.log_path())
        return SetupResult(ok=False, code=2, version=version)

    ui.step(2, "Arbeitsumgebung")
    _stop_running_application(ui, root)
    if not _ensure_environment(ui, root):
        ui.summary(paths.log_path())
        return SetupResult(ok=False, code=2, version=version)

    ui.step(3, "Einstellungen")
    if not _configure(ui, unattended, target, root):
        ui.summary(paths.log_path())
        return SetupResult(ok=False, code=2, version=version)

    ui.step(4, "Zusatzprogramme")
    externals_ready = _external_dependencies(ui)

    ui.step(5, "Prüfung")
    checks = doctor.run(target, root)
    for line in doctor.render_text(checks):
        ui.write(line)
    doctor_ok = not doctor.has_failure(checks)
    if doctor_ok:
        ui.ok("Die Prüfung hat nichts Blockierendes gefunden")
    else:
        ui.warn("Die Prüfung hat offene Punkte gefunden -- sie stehen oben")

    ui.step(6, "Symbol auf dem Desktop")
    shortcut_installed = guided_shortcut(ui, unattended, root, desktop=desktop)

    ui.step(7, "Loslegen")

    # Recorded as soon as helper, environment and settings are in place, and
    # deliberately not only after a completely clean run: the record states
    # which version is installed, and that holds whether or not ffmpeg happens
    # to answer right now. Tied to the check result, a colleague with an open
    # point would never get one.
    write_installed_version(version)

    everything_ok = externals_ready and doctor_ok
    if not everything_ok:
        ui.warn("Noch nicht startklar -- die offenen Punkte stehen oben")

    # An open point holds the offer back, but never a start that was demanded.
    # A single warning - a cloud folder offline, a report too many - would
    # otherwise leave a caller who asked for a window with none and no idea why.
    # The start runs its own check and says so if it cannot.
    if offer_start and (everything_ok or start_after):
        _offer_start(ui, root, target, unattended=unattended, start_after=start_after)

    ui.summary(paths.log_path(), _closing_note(everything_ok, target))

    return SetupResult(
        ok=everything_ok,
        code=0 if everything_ok else 1,
        version=version,
        shortcut_installed=shortcut_installed,
        checks=tuple(checks),
    )


# --- Start, stop, status ------------------------------------------------------


def start(repo: Path | None = None, config_path: Path | None = None) -> StartResult:
    """Checked, detached, windowless start (design D9).

    The interpreter is taken from the built environment by its absolute path.
    The retired `Start_Recorder.bat` went through the search path, so which
    interpreter it hit depended on the order of `PATH`.
    """
    root = repo or paths.repo_root()
    target = paths.config_path(config_path)

    running = instance.running_instance(repo=root)
    if running is not None:
        logger.info("Start abgewiesen: Anwendung %d laeuft bereits", running.pid)
        return StartResult(
            started=False,
            already_running=True,
            pid=running.pid,
            message="Backrec läuft bereits. Das Fenster ist offen, vielleicht hinter einem anderen.",
        )

    foreign = foreign_installation(root)
    if foreign is not None:
        logger.info("Aus einem anderen Ordner laeuft bereits eine Fassung: %s", foreign)

    executable = launcher(root)
    if not executable.is_file():
        problem = preflight.Problem(
            "Die Arbeitsumgebung des Werkzeugs fehlt.",
            "Setup.cmd in diesem Ordner doppelklicken.",
        )
        return StartResult(
            started=False, problem=problem, message=problem.cause, foreign_folder=foreign
        )

    checked = preflight.run(target)
    if not checked.ok:
        return StartResult(
            started=False,
            problem=checked.problem,
            message=checked.problem.cause if checked.problem else "",
            foreign_folder=foreign,
        )

    instance.clear_stop_request()

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS

    try:
        subprocess.Popen(
            start_command(root),
            cwd=str(root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=creationflags,
        )
    except OSError as exc:
        logger.error("Start fehlgeschlagen: %s", exc)
        return StartResult(
            started=False,
            message="Backrec ließ sich nicht starten.",
            foreign_folder=foreign,
        )

    deadline = time.monotonic() + START_READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        found = instance.running_instance(repo=root)
        if found is not None:
            logger.info("Gestartet (Anwendung %d)", found.pid)
            return StartResult(
                started=True,
                pid=found.pid,
                message="Backrec läuft.",
                foreign_folder=foreign,
            )
        time.sleep(START_POLL_SECONDS)

    logger.warning("Start angestossen, aber kein Zustandsdatensatz erschienen")
    return StartResult(
        started=False,
        message="Der Start wurde angestoßen, Backrec hat sich aber nicht gemeldet.",
        foreign_folder=foreign,
    )


def _recording_folder(config_path: Path | None = None) -> str | None:
    """The folder the raw takes stay in, named when a stop had to be forced.

    Never a reason to fail: a stop that ended because the settings file could
    not be read would be the worst possible cure. Without the folder the forced
    termination is still reported - only without the one detail that says where
    to look (design D7).
    """
    try:
        settled = config_module.load_config(paths.config_path(config_path))
    except (config_module.ConfigError, OSError):
        logger.warning("Aufnahmeordner nicht ermittelbar -- die Meldung nennt ihn nicht")
        return None

    return str(settled.recording_dir)


def _forced_message(finishing: bool, raw_takes: str | None) -> str:
    """What a forced termination says to whoever asked for the stop.

    The tone differs by what was observed, the folder does not. An application
    that hung without ever starting its closing sequence can just as well have
    hung in the middle of a recording, and then two half-written takes lie in
    exactly the same place.
    """
    head = (
        "Beendet, nach Ablauf der Frist -- die Nachbereitung der Aufnahme wurde abgeschnitten."
        if finishing
        else "Beendet, nach Ablauf der Frist."
    )
    if raw_takes is None:
        return head

    whereabouts = (
        f"Die Rohspuren liegen in {raw_takes}."
        if finishing
        else f"Falls eine Aufnahme lief, liegen ihre Rohspuren in {raw_takes}."
    )
    return f"{head} {whereabouts}"


def stop(
    repo: Path | None = None,
    *,
    timeout_seconds: float = STOP_TIMEOUT_SECONDS,
    on_progress: Callable[[float], None] | None = None,
) -> StopResult:
    """Stop through the request file, forcefully once the deadline passes.

    Success is measured on the processes, not on the request that was written.
    Removing the record while the application is still running would make it
    untraceable, and the next start would consider it stopped.

    The deadline follows the application rather than a fixed number: every beat
    of `instance.finishing_beat` that differs from the one seen before pushes it
    out by `STOP_GRACE_SECONDS`, up to `STOP_LIMIT_SECONDS`. It is never pulled
    in below the base deadline, and without a single beat it is the base
    deadline - which is what keeps a stop with nothing to finish exactly as fast
    as it was (design D1).
    """
    root = repo or paths.repo_root()
    running = instance.running_instance(repo=root)

    if running is None:
        instance.clear_record()
        instance.clear_stop_request()
        instance.clear_finishing()
        return StopResult(stopped=True, was_running=False, message="Es läuft nichts.")

    instance.request_stop()
    logger.info("Beenden angefordert (Anwendung %d, Frist %.0fs)", running.pid, timeout_seconds)

    started = time.monotonic()
    limit = started + STOP_LIMIT_SECONDS
    deadline = min(started + timeout_seconds, limit)
    last_progress = started
    last_beat = instance.finishing_beat()
    finishing = False

    while time.monotonic() < deadline:
        if not running.is_running():
            break

        now = time.monotonic()
        beat = instance.finishing_beat()
        if beat is not None and beat != last_beat:
            # A beat that stands still is no beat: a file left behind by a crash
            # never extends anything, which is what makes the sign self-healing.
            finishing = True
            deadline = min(max(deadline, now + STOP_GRACE_SECONDS), limit)
        last_beat = beat

        if on_progress is not None and now - last_progress >= STOP_PROGRESS_SECONDS:
            on_progress(deadline - now)
            last_progress = now
        time.sleep(STOP_POLL_SECONDS)

    forced = False
    raw_takes: str | None = None

    if running.is_running():
        forced = True
        raw_takes = _recording_folder()
        where = raw_takes or "dem eingestellten Aufnahmeordner"
        if finishing:
            logger.error(
                "Frist abgelaufen -- die Anwendung wird hart beendet und eine laufende "
                "Nachbereitung dabei abgeschnitten. Die Rohspuren der Aufnahme liegen in %s",
                where,
            )
        else:
            logger.error(
                "Frist abgelaufen -- die Anwendung wird hart beendet. Rohspuren einer "
                "begonnenen Aufnahme liegen in %s",
                where,
            )
        instance.terminate_tree(running)

    instance.clear_stop_request()

    if running.is_running():
        logger.error("Die Anwendung %d laeuft weiter -- der Vermerk bleibt stehen", running.pid)
        return StopResult(
            stopped=False,
            was_running=True,
            forced=True,
            message=(
                "Backrec läuft weiter -- es ließ sich nicht beenden. "
                "Den Rechner neu starten und es noch einmal versuchen."
            ),
            raw_takes=raw_takes,
        )

    instance.clear_record()
    instance.clear_recording()
    instance.clear_finishing()
    return StopResult(
        stopped=True,
        was_running=True,
        forced=forced,
        message="Beendet." if not forced else _forced_message(finishing, raw_takes),
        raw_takes=raw_takes,
    )


def status(repo: Path | None = None, config_path: Path | None = None) -> StatusReport:
    """Status report, read from the record and the file system. Changes nothing."""
    root = repo or paths.repo_root()
    record = instance.read_record()
    running = instance.live_process(record, root)

    return StatusReport(
        running=running is not None,
        pid=running.pid if running is not None else None,
        started=record.started if record is not None else "",
        version=paths.tool_version(root),
        recording=running is not None and instance.is_recording(),
        shortcut_installed=shortcut_module.status(root).installed,
        config_path=paths.config_path(config_path),
        logs_path=paths.logs_dir(),
        state_path=paths.state_dir(),
        repo_path=root,
        foreign_folder=instance.foreign_repo(record, root),
    )


def run_doctor(
    config_path: Path | None = None,
    repo: Path | None = None,
    *,
    report: bool = False,
    open_report: bool = False,
) -> DoctorReport:
    """The diagnosis as one result, for the command line and for the window."""
    root = repo or paths.repo_root()
    checks = doctor.run(config_path, root)

    written: Path | None = None
    if report:
        written = doctor.write_report(checks, config_path=config_path, repo=root)
        if open_report:
            doctor.open_in_editor(written)

    return DoctorReport(checks=tuple(checks), code=doctor.exit_code(checks), report_path=written)


def open_logs() -> CommandResult:
    """Shows the log folder in the file manager."""
    directory = paths.logs_dir()
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("Aufzeichnungsordner nicht anlegbar: %s", exc)
        return CommandResult(
            ok=False, code=1, lines=(f"{directory} ist nicht erreichbar.",)
        )

    try:
        os.startfile(str(directory))  # noqa: S606 - exactly what the function is for
    except (OSError, AttributeError) as exc:
        # Never fatal: the path itself is the answer, and the window that asked
        # for it must not end because a file manager did not appear.
        logger.warning("Aufzeichnungsordner liess sich nicht oeffnen: %s", exc)
        return CommandResult(ok=False, code=1, lines=(f"Ordner: {directory}",))

    return CommandResult(ok=True, lines=(f"Ordner: {directory}",))


def follow_logs(stream: TextIO | None = None) -> CommandResult:
    """Shows new log lines until interrupted."""
    out = stream if stream is not None else sys.stdout
    log_path = paths.log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.touch(exist_ok=True)

    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        handle.seek(0, os.SEEK_END)
        try:
            while True:
                line = handle.readline()
                if line:
                    out.write(line)
                    out.flush()
                else:
                    time.sleep(0.5)
        except KeyboardInterrupt:
            return CommandResult(ok=True, lines=("Beendet.",))


# --- Uninstall and release ----------------------------------------------------


def _runs_from(repo: Path) -> bool:
    """Whether this very process was started out of the folder's environment."""
    try:
        return Path(sys.prefix).resolve() == (repo / ".venv").resolve()
    except OSError:
        return False


def _remove_tree(target: Path, label: str) -> str:
    """Deletes a folder and says honestly whether it worked.

    `ignore_errors=True` without a check afterwards would report "removed" while
    everything is still there - the most dishonest message an uninstall can give.
    """
    shutil.rmtree(target, ignore_errors=True)
    if not target.exists():
        return f"{label} wurde entfernt."

    return (
        f"{label} konnte nicht vollständig entfernt werden, weil sie gerade benutzt wird: "
        f"{target}. Diesen Ordner nach dem Schließen dieses Fensters von Hand löschen."
    )


def uninstall(
    repo: Path | None = None,
    *,
    purge: bool = False,
    desktop: Path | None = None,
) -> CommandResult:
    """Removes the installation, never the recordings."""
    root = repo or paths.repo_root()
    lines: list[str] = []

    stopped = stop(root)
    if stopped.was_running and stopped.stopped:
        lines.append("Die laufende Anwendung wurde beendet.")
    elif stopped.was_running:
        # Going on would be dishonest: a running application holds its own files
        # open and the removal would fail item by item with the same cause.
        return CommandResult(ok=False, code=1, lines=(stopped.message,))

    # Without the filter the output contradicts itself within two lines: the
    # removal of the icon ends on "a running application keeps running", and
    # right above it stands the sentence that this one was just stopped. That
    # note belongs to the icon command on its own, not here.
    lines.extend(
        line
        for line in shortcut_module.remove(desktop).lines
        if line != shortcut_module.RUNNING_UNTOUCHED_NOTE
    )

    venv = root / ".venv"
    if not venv.is_dir():
        lines.append("Es gab keine Arbeitsumgebung zu entfernen.")
    elif _runs_from(root):
        # Half-deleting it is worse than leaving it: Windows does not release
        # the running program file, and what stays is a folder without
        # `pyvenv.cfg` that every later start trips over.
        lines.append(
            "Die Arbeitsumgebung bleibt stehen, weil dieser Vorgang aus ihr heraus läuft. "
            "Sie verschwindet mit dem Ordner."
        )
    else:
        lines.append(_remove_tree(venv, "Die Arbeitsumgebung"))

    if purge:
        tool_home = paths.tool_home()
        if tool_home.is_dir():
            # Close the log files first: an open file prevents the folder from
            # being deleted, and a silent failure would be the worst message of
            # all here.
            configure_logging(None, force=True)
            close_files()
            lines.append(_remove_tree(tool_home, "Einstellungen, Aufzeichnungen und Zustand"))
    else:
        lines.append(
            f"Erhalten geblieben: {paths.tool_home()} -- mit --purge wird auch das entfernt, "
            "oder den Ordner im Dateimanager löschen."
        )

    # For every "left untouched" the way to get rid of it after all: a list of
    # what remains without saying how leaves open exactly the question somebody
    # who is uninstalling right now has.
    lines.append(
        "Nicht angetastet: deine Aufnahmen im Aufnahme- und im Zielordner -- sie liegen dort, "
        "wo du sie beim Einrichten angegeben hast, und lassen sich im Dateimanager löschen."
    )
    lines.append(
        "Nicht angetastet: getrennt eingerichtete Programme wie ffmpeg und das Hilfsprogramm "
        "der Einrichtung -- sie stehen in den Windows-Einstellungen unter Apps."
    )
    lines.append(
        f"Nicht angetastet: die gemeinsame Datei der Reihe unter {paths.suite_handshake_path()} -- "
        "sie hilft den Nachbarwerkzeugen beim Einrichten und lässt sich im Dateimanager löschen."
    )
    return CommandResult(ok=True, lines=tuple(lines))


def build_release(repo: Path | None = None, output_dir: Path | None = None) -> CommandResult:
    """Developer path: builds the archive for distribution."""
    try:
        result = release_module.build(repo, output_dir)
    except release_module.ReleaseError as exc:
        return CommandResult(ok=False, code=1, lines=(str(exc),))

    return CommandResult(
        ok=True,
        lines=(
            f"Archiv gebaut: {result.archive}",
            f"Fassung {result.version}, {len(result.entries)} Datei(en).",
        ),
    )


def about_lines(repo: Path | None = None, config_path: Path | None = None) -> tuple[str, ...]:
    """The tool details, as the `about` command reports them.

    The path of the guide is in here because a colleague who has been starting
    the tool from its desktop icon for months no longer has the unpacked folder
    in his head - and that text is the one that describes all four ways
    (design D20, D22).
    """
    root = repo or paths.repo_root()
    return (
        f"{paths.TOOL_NAME} {paths.tool_version(root)}",
        "",
        f"Ordner: {root}",
        f"Einstellungen: {paths.config_path(config_path)}",
        f"Anleitung: {paths.guide_path(root)}",
        "",
        "Entfernen:",
        *UNINSTALL_SENTENCES,
        # The three sentences above are the guide's, word for word, and they end
        # at the folder. What they cannot say without growing a fourth line is
        # that anything personal survives it - and this is the one place that
        # has room for the sentence.
        f"Deine Einstellungen, Aufzeichnungen und der Zustand bleiben unter "
        f"{paths.tool_home()} liegen und lassen sich dort getrennt löschen.",
    )
