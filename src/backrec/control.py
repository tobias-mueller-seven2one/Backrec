"""The control surface: every command once, as a function with one result.

Command line and window menu are two faces of the same functions (design D9).
Every decision comes back as a dataclass; `cli.py` turns it into console text
and a return value, `app.py` into a dialog or a status line. No decision logic
in the presentation, no output in the core - which is why the window menu needs
no procedure of its own and can never drift away from the command of the same
name.
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
    update as update_module,
    wizard,
)
from .console import Assistant
from .logging_setup import close_files, configure_logging, get_logger

logger = get_logger(__name__)

SETUP_STEPS = 7

START_READY_TIMEOUT_SECONDS = 30.0
START_POLL_SECONDS = 0.5

# The 30 s of design D10: long enough for threads to end, a mix to run and a
# copy of a long recording to be verified.
STOP_TIMEOUT_SECONDS = 30.0
STOP_POLL_SECONDS = 0.5
STOP_PROGRESS_SECONDS = 5.0

UV_VERSION = "0.11.21"
UV_INSTALL_SCRIPT = f"https://astral.sh/uv/{UV_VERSION}/install.ps1"

# Deliberately without `--reinstall-package backrec`, even though a plain sync
# does not notice changed sources of this package. Reinstalling cannot happen
# from here: this process runs *inside* the environment that would have to be
# replaced, and Windows does not release a running program file. The two places
# that can do it stand outside and do: `scripts\win\bootstrap-uv.ps1` before
# every setup, and the update helper, which calls Setup.cmd and therefore the
# bootstrap again.
SYNC_COMMAND: tuple[str, ...] = ("uv", "sync", "--locked", "--no-dev", "--no-editable")

# Set by Setup.cmd once the bootstrap has built the environment. Without the
# hint step 2 would build it a second time within the same minute.
ENV_BOOTSTRAPPED = "BACKREC_ENV_READY"

# The three uninstall sentences. They appear verbatim here and in the "Entfernen"
# section of the guide, and a test keeps them identical. The same text in two
# places is deliberate: neither place is reachable from the other - whoever has
# the window does not have the guide open, and whoever reads the guide has no
# window yet.
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
    updated_from: str | None = None
    shortcut_installed: bool = False
    checks: tuple[doctor.Check, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class StartResult:
    started: bool
    already_running: bool = False
    pid: int | None = None
    problem: preflight.Problem | None = None
    message: str = ""


@dataclass(frozen=True)
class StopResult:
    stopped: bool
    was_running: bool
    forced: bool = False
    message: str = ""


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


def launcher(repo: Path | None = None) -> Path:
    """The windowless interpreter the shortcut and `start` both use."""
    return shortcut_module.launcher(repo)


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


def _configure(assistant: Assistant, unattended: bool, config_path: Path, repo: Path) -> bool:
    """Step 3: take over existing settings, migrate an old file, or ask."""
    if config_path.is_file():
        assistant.ok(f"Die Einstellungen gibt es schon ({config_path}) -- unverändert übernommen")
        return True

    migration = config_module.migrate_legacy(target=config_path, repo=repo)
    if migration.migrated:
        assistant.ok(
            f"Frühere Einstellungen aus {migration.source} übernommen nach {migration.target}"
        )
        assistant.note(f"Übernommen wurden: {', '.join(migration.keys)}.")
        assistant.note(
            f"Die alte Datei {migration.source} bleibt liegen, wirkt aber nicht mehr."
        )
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


def _external_dependencies(assistant: Assistant) -> bool:
    """Step 4: the program that mixes both takes into one file."""
    result = external.ensure()
    if result.ok:
        assistant.ok(result.message)
        return True

    assistant.fail(result.message, result.next_step)
    return False


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
    it. The update helper does demand it: otherwise the tool would shut down for
    the new version and never come back.
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


def _closing_note(everything_ok: bool) -> str:
    if not everything_ok:
        return "Noch nicht fertig. Ein zweiter Lauf nach dem Beheben zerstört nichts."
    return (
        "Fertig. Das Symbol liegt auf dem Desktop. Im Fenster öffnet das Zahnrad "
        "oben rechts das Menü mit Diagnose, Aktualisieren und Auskunft."
    )


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

    previous = read_installed_version()
    updating = previous is not None and previous != version
    if updating:
        ui.note(f"Es ist eine neue Fassung da: von {previous} auf {version}.")
        if instance.running_instance(repo=root) is not None:
            ui.note("Die laufende Anwendung wird vorher beendet.")
            stop(root)

    ui.step(1, "Hilfsprogramme")
    if not _ensure_uv(ui):
        ui.summary(paths.log_path())
        return SetupResult(ok=False, code=2, version=version)

    ui.step(2, "Arbeitsumgebung")
    if not _ensure_environment(ui, root):
        ui.summary(paths.log_path())
        return SetupResult(ok=False, code=2, version=version)

    if updating:
        removed = _remove_stale_files(root)
        if removed:
            ui.note(f"{removed} nicht mehr benötigte Datei(en) entfernt.")

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
    # point would never get one, and the next update would have no yardstick
    # for the files that went away.
    write_installed_version(version)
    update_module.store_manifest_from_repo(root)

    everything_ok = externals_ready and doctor_ok
    if not everything_ok:
        ui.warn("Noch nicht startklar -- die offenen Punkte stehen oben")
    elif offer_start:
        _offer_start(ui, root, target, unattended=unattended, start_after=start_after)

    ui.summary(paths.log_path(), _closing_note(everything_ok))

    return SetupResult(
        ok=everything_ok,
        code=0 if everything_ok else 1,
        version=version,
        updated_from=previous if updating else None,
        shortcut_installed=shortcut_installed,
        checks=tuple(checks),
    )


def _remove_stale_files(repo: Path) -> int:
    """Remove files of the previous version that the new one no longer has."""
    previous = update_module.read_installed_manifest()
    current_manifest = repo / release_module.MANIFEST_NAME
    if not previous or not current_manifest.is_file():
        logger.info("Kein Vergleichsmassstab vorhanden -- Aufraeumen entfaellt")
        return 0

    try:
        current = release_module.manifest_entries(
            json.loads(current_manifest.read_text(encoding="utf-8"))
        )
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return 0

    removed = update_module.remove_stale(repo, update_module.stale_files(previous, current))
    update_module.write_installed_manifest(current, paths.tool_version(repo))
    return len(removed)


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

    executable = launcher(root)
    if not executable.is_file():
        problem = preflight.Problem(
            "Die Arbeitsumgebung des Werkzeugs fehlt.",
            "Setup.cmd in diesem Ordner doppelklicken.",
        )
        return StartResult(started=False, problem=problem, message=problem.cause)

    checked = preflight.run(target)
    if not checked.ok:
        return StartResult(
            started=False,
            problem=checked.problem,
            message=checked.problem.cause if checked.problem else "",
        )

    instance.clear_stop_request()

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS

    try:
        subprocess.Popen(
            [str(executable), "-m", "backrec"],
            cwd=str(root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=creationflags,
        )
    except OSError as exc:
        logger.error("Start fehlgeschlagen: %s", exc)
        return StartResult(started=False, message="Backrec ließ sich nicht starten.")

    deadline = time.monotonic() + START_READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        found = instance.running_instance(repo=root)
        if found is not None:
            logger.info("Gestartet (Anwendung %d)", found.pid)
            return StartResult(started=True, pid=found.pid, message="Backrec läuft.")
        time.sleep(START_POLL_SECONDS)

    logger.warning("Start angestossen, aber kein Zustandsdatensatz erschienen")
    return StartResult(
        started=False,
        message="Der Start wurde angestoßen, Backrec hat sich aber nicht gemeldet.",
    )


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
    """
    root = repo or paths.repo_root()
    running = instance.running_instance(repo=root)

    if running is None:
        instance.clear_record()
        instance.clear_stop_request()
        return StopResult(stopped=True, was_running=False, message="Es läuft nichts.")

    instance.request_stop()
    logger.info("Beenden angefordert (Anwendung %d, Frist %.0fs)", running.pid, timeout_seconds)

    deadline = time.monotonic() + timeout_seconds
    last_progress = time.monotonic()
    forced = False

    while time.monotonic() < deadline:
        if not running.is_running():
            break
        now = time.monotonic()
        if on_progress is not None and now - last_progress >= STOP_PROGRESS_SECONDS:
            on_progress(deadline - now)
            last_progress = now
        time.sleep(STOP_POLL_SECONDS)

    if running.is_running():
        forced = True
        logger.warning("Frist abgelaufen -- die Anwendung wird beendet")
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
        )

    instance.clear_record()
    instance.clear_recording()
    return StopResult(
        stopped=True,
        was_running=True,
        forced=forced,
        message="Beendet." if not forced else "Beendet, nach Ablauf der Frist.",
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
    )


def run_doctor(
    config_path: Path | None = None,
    repo: Path | None = None,
    *,
    report: bool = False,
    open_report: bool = False,
) -> DoctorReport:
    """The diagnosis as one result, for the command line and for the menu."""
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


# --- Update, uninstall, release -----------------------------------------------


def apply_archive(
    archive: Path,
    repo: Path | None = None,
    *,
    detached: bool = True,
) -> CommandResult:
    """Check an archive, stage it alongside and apply it.

    While the tool is running a helper outside the folder takes over mirroring
    and restart: a process cannot replace the folder its own code came from.
    """
    root = repo or paths.repo_root()

    try:
        decision = update_module.plan(archive, repo=root)
        staging = update_module.stage(decision.info, repo=root)
    except update_module.UpdateError as exc:
        return CommandResult(ok=False, code=1, lines=(str(exc),))

    running = instance.running_instance(repo=root)

    if running is not None and detached:
        helper = root / "scripts" / "win" / "apply-update.ps1"
        if not helper.is_file():
            logger.error("Helfer fuer das Aktualisieren fehlt: %s", helper)
            return CommandResult(
                ok=False,
                code=1,
                lines=(
                    "Was ist passiert: Im Ordner des Werkzeugs fehlt eine Datei, "
                    "die zum Aktualisieren gebraucht wird.",
                    "Was tun: Die neue Fassung über den Ordner entpacken und "
                    "Setup.cmd doppelklicken.",
                ),
            )

        command = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(helper),
            "-RepoPath",
            str(root),
            "-StagingPath",
            str(staging),
            "-WaitForPid",
            str(running.pid),
            "-LogDir",
            str(paths.logs_dir()),
            "-ManifestPath",
            str(paths.installed_manifest_path()),
        ]
        try:
            subprocess.Popen(command, close_fds=True)
        except OSError as exc:
            logger.error("Helfer fuer das Aktualisieren nicht startbar: %s", exc)
            return CommandResult(
                ok=False,
                code=1,
                lines=(
                    "Was ist passiert: Das Aktualisieren ließ sich nicht anstoßen.",
                    "Was tun: Die neue Fassung über den Ordner entpacken und "
                    "Setup.cmd doppelklicken.",
                ),
            )

        return CommandResult(
            ok=True,
            lines=(
                f"Von {decision.installed_version} auf {decision.info.version}.",
                "Backrec beendet sich jetzt und meldet sich gleich wieder.",
            ),
        )

    copied, removed = update_module.mirror(staging, decision.info, root)
    shutil.rmtree(staging, ignore_errors=True)
    return CommandResult(
        ok=True,
        lines=(
            f"Von {decision.installed_version} auf {decision.info.version}.",
            f"{copied} Datei(en) übernommen, {len(removed)} entfernt.",
            "Setup.cmd doppelklicken, damit die Arbeitsumgebung nachgezogen wird.",
        ),
    )


def update_from_git(repo: Path | None = None) -> CommandResult:
    """Developer path: only with an existing working copy."""
    root = repo or paths.repo_root()

    if not (root / ".git").exists():
        return CommandResult(
            ok=False,
            code=1,
            lines=(
                "Dieser Ordner wird nicht über eine Versionsverwaltung gepflegt.",
                "Neues Archiv über den Ordner entpacken und Setup.cmd erneut doppelklicken.",
            ),
        )

    dirty = _run(["git", "status", "--porcelain"], cwd=root)
    if dirty.returncode != 0:
        return CommandResult(ok=False, code=1, lines=("Der Stand ließ sich nicht prüfen.",))
    if dirty.stdout.strip():
        return CommandResult(
            ok=False,
            code=1,
            lines=(
                "Es gibt lokale Änderungen -- es wird nichts erzwungen.",
                "Die Änderungen sichern oder verwerfen und erneut versuchen.",
            ),
        )

    pull = _run(["git", "pull", "--ff-only"], cwd=root)
    if pull.returncode != 0:
        return CommandResult(
            ok=False,
            code=1,
            lines=(
                "Der Stand lässt sich nicht ohne Zusammenführen nachziehen.",
                (pull.stderr or pull.stdout).strip()[:400],
            ),
        )

    synced = _run(list(SYNC_COMMAND), cwd=root)
    if synced.returncode != 0:
        return CommandResult(
            ok=False, code=1, lines=("Die Arbeitsumgebung ließ sich nicht nachziehen.",)
        )

    checks = doctor.run(repo=root)
    return CommandResult(
        ok=not doctor.has_failure(checks),
        code=doctor.exit_code(checks),
        lines=tuple(doctor.render_text(checks)),
    )


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

    lines.extend(shortcut_module.remove(desktop).lines)

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
    """The tool details - for the menu entry and for the command line.

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
    )
