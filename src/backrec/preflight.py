"""What has to hold before the window exists at all.

Five checks in a fixed order, and the first failure ends the start (design D5).
The order is not cosmetic: without settings there is no folder to check, and
without a folder there is nothing to record into.

Splitting the chain into small functions that each return a `Problem` or None
makes every cause reachable from a test without having to produce it on the
machine - an unwritable cloud folder is not something a test suite can arrange.

Creating the two folders happens here and nowhere else. The retired module level
made them while the module was being imported (`main.pyw:37-38`), which is why a
bad path used to mean a program that simply did not start: no window, no
message, no trace.

ffmpeg is checked **before** the window, not at STOP as it used to be
(`main.pyw:124-126`). Learning that the mixer is missing after a half-hour
meeting is the most expensive moment there is for that news.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from . import config as config_module, external, instance, paths
from .logging_setup import get_logger

logger = get_logger(__name__)

PROBE_NAME = ".backrec-probe"

SETUP_HINT = "Setup.cmd im Ordner des Werkzeugs doppelklicken."


@dataclass(frozen=True)
class Problem:
    """One reason why no recording may begin, in the two sentences of D19."""

    cause: str
    next_step: str


@dataclass(frozen=True)
class PreflightResult:
    ok: bool
    problem: Problem | None = None
    config: config_module.BackrecConfig | None = None


def probe_writable(directory: Path) -> str | None:
    """Creates and removes a file in `directory`. Returns a cause or None.

    Written rather than asked: on Windows no attribute reliably says whether a
    network share or a cloud folder accepts a write right now, and that is
    exactly the case this check exists for.
    """
    probe = directory / PROBE_NAME
    try:
        probe.write_bytes(b"")
    except OSError as exc:
        return str(exc)
    finally:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass
    return None


def check_config_present(config_path: Path) -> Problem | None:
    if config_path.is_file():
        return None
    return Problem(
        f"Es gibt noch keine Einstellungen. Erwartet werden sie unter {config_path}.",
        SETUP_HINT,
    )


def check_config_readable(
    config_path: Path,
    env: Mapping[str, str] | None = None,
) -> tuple[config_module.BackrecConfig | None, Problem | None]:
    """Reads and checks the settings without creating anything yet.

    `create_dirs=False` on purpose: the folders are made by the next check,
    which can also say why it failed. Creating them here would hide the cause
    inside a message about settings.
    """
    try:
        loaded = config_module.load_config(config_path, env=env, create_dirs=False)
    except config_module.ConfigError as exc:
        logger.error("Einstellungen nicht verwendbar: %s", exc, exc_info=True)
        return None, Problem(str(exc), SETUP_HINT)
    return loaded, None


def check_directory(label: str, directory: Path, consequence: str) -> Problem | None:
    """Creates the folder if need be and writes into it once."""
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.error("Ordner '%s' nicht anlegbar: %s", directory, exc, exc_info=True)
        return Problem(
            f"Der {label} {directory} lässt sich nicht anlegen: {exc.strerror or exc}.",
            f"Den Ordner in den Einstellungen ändern oder ihn erreichbar machen. {consequence}",
        )

    reason = probe_writable(directory)
    if reason is None:
        return None

    logger.error("Ordner '%s' nicht beschreibbar: %s", directory, reason)
    return Problem(
        f"In den {label} {directory} lässt sich nichts schreiben.",
        f"Prüfen, ob der Ordner erreichbar ist. {consequence}",
    )


def check_ffmpeg(state: external.FfmpegState) -> Problem | None:
    """Pure: turns the observed state of ffmpeg into a cause, or None."""
    if state.usable:
        return None

    if state.found_at is None:
        return Problem(
            "Das Programm zum Zusammenmischen fehlt. Ohne es entsteht aus einer "
            "Aufnahme keine fertige Datei.",
            SETUP_HINT,
        )

    return Problem(
        "Das Programm zum Zusammenmischen ist da, lässt sich aber nicht starten.",
        SETUP_HINT,
    )


def run(
    config_path: Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
    ffmpeg_state: external.FfmpegState | None = None,
) -> PreflightResult:
    """The complete chain. Stops at the first cause.

    A stop request left lying around is cleared before anything else: it would
    otherwise end the run that is just beginning, within 150 ms and without a
    visible reason (design D10).
    """
    if instance.stop_requested():
        logger.info("Liegengebliebene Beendigungsanforderung gefunden und entfernt")
        instance.clear_stop_request()

    target = paths.config_path(config_path, env)

    problem = check_config_present(target)
    if problem is not None:
        return PreflightResult(ok=False, problem=problem)

    loaded, problem = check_config_readable(target, env)
    if loaded is None or problem is not None:
        return PreflightResult(ok=False, problem=problem)

    problem = check_directory(
        "Aufnahmeordner",
        loaded.recording_dir,
        "Dorthin werden die Spuren geschrieben.",
    )
    if problem is not None:
        return PreflightResult(ok=False, problem=problem, config=loaded)

    problem = check_directory(
        "Zielordner",
        loaded.target_dir,
        "Dorthin kommt die fertige Aufnahme für das nächste Werkzeug.",
    )
    if problem is not None:
        return PreflightResult(ok=False, problem=problem, config=loaded)

    state = ffmpeg_state if ffmpeg_state is not None else external.inspect()
    problem = check_ffmpeg(state)
    if problem is not None:
        return PreflightResult(ok=False, problem=problem, config=loaded)

    logger.info("Startprüfung bestanden: %s, %s", loaded.recording_dir, loaded.target_dir)
    return PreflightResult(ok=True, config=loaded)


def show_error(problem: Problem) -> None:
    """The one channel a windowless start still has: a dialog of its own.

    `tkinter.messagebox` and deliberately not a CustomTkinter dialog - the
    message has to appear even when the cause lies in the user interface
    itself, and that rules out building one out of it first.
    """
    logger.error("Start abgebrochen: %s | %s", problem.cause, problem.next_step)
    try:
        import tkinter
        from tkinter import messagebox

        root = tkinter.Tk()
        root.withdraw()
        messagebox.showerror(
            f"{paths.TOOL_NAME} kann nicht starten",
            f"Was ist passiert:\n{problem.cause}\n\nWas tun:\n{problem.next_step}",
        )
        root.destroy()
    except Exception:  # noqa: BLE001 - a machine without a display must still log
        logger.error("Fehlerdialog liess sich nicht anzeigen", exc_info=True)
