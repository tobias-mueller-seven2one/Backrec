"""The command line: the control surface's results turned into text and exit codes.

It exists for Tobias, for scripts and for troubleshooting. It does not appear in
the guide for colleagues - there are two files to double-click there, and after
that the icon on the desktop and the gear in the window.

Everything written here goes through `Assistant`, never through a bare print.
That is not tidiness: the rules of design D19 - two sentences per error, no
implementation vocabulary, no stack trace - are enforced by a test that looks at
what is handed to that class, and a `print` would walk straight past it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

from . import control, doctor, paths, shortcut as shortcut_module
from .console import Assistant, use_utf8
from .logging_setup import bootstrap, get_logger

logger = get_logger(__name__)

# A second start gets its own value so a script can tell it from a real failure
# (design D6).
EXIT_ALREADY_RUNNING = 3
EXIT_INTERRUPTED = 130


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="backrec",
        description="Nimmt Mikrofon und Systemton eines Gesprächs auf und mischt beides.",
    )
    parser.add_argument(
        "--config", type=Path, default=None, help="Andere Einstellungsdatei verwenden"
    )
    subparsers = parser.add_subparsers(dest="command")

    setup_parser = subparsers.add_parser("setup", help="Einrichten (Exit 0, sonst 1 oder 2)")
    setup_parser.add_argument("--unattended", action="store_true", help="Ohne Rückfragen")
    setup_parser.add_argument("--start", action="store_true", help="Am Ende ohne Rückfrage starten")

    subparsers.add_parser("start", help="Fensterlos starten (Exit 0, 1, oder 3 wenn es schon läuft)")
    subparsers.add_parser("stop", help="Beenden (Exit 0, sonst 1)")
    subparsers.add_parser("status", help="Auskunft (Exit 0)")

    doctor_parser = subparsers.add_parser("doctor", help="Prüfung (Exit 0, 1 bei einem Fehler)")
    doctor_parser.add_argument("--json", action="store_true", help="Maschinenlesbar")
    doctor_parser.add_argument("--report", action="store_true", help="Bericht als Textdatei")

    shortcut_parser = subparsers.add_parser(
        "shortcut", help="Symbol auf dem Desktop (Exit 0, sonst 1)"
    )
    shortcut_group = shortcut_parser.add_mutually_exclusive_group()
    shortcut_group.add_argument("--status", action="store_true", help="Nur berichten")
    shortcut_group.add_argument("--remove", action="store_true", help="Symbol entfernen")

    uninstall_parser = subparsers.add_parser("uninstall", help="Entfernen (Exit 0, sonst 1)")
    uninstall_parser.add_argument(
        "--purge", action="store_true", help="Auch Einstellungen, Aufzeichnungen und Zustand"
    )

    update_parser = subparsers.add_parser("update", help="Aktualisieren (Exit 0, sonst 1)")
    update_parser.add_argument(
        "archive", nargs="?", type=Path, default=None, help="Pfad zum Archiv"
    )
    update_parser.add_argument(
        "--git", action="store_true", help="Entwicklerweg über die Versionsverwaltung"
    )
    update_parser.add_argument(
        "--force",
        action="store_true",
        help="Auch eine gleiche oder ältere Fassung einspielen",
    )

    logs_parser = subparsers.add_parser("logs", help="Aufzeichnungen (Exit 0, sonst 1)")
    logs_parser.add_argument("--follow", action="store_true", help="Neue Zeilen anzeigen")

    release_parser = subparsers.add_parser("release", help="Archiv bauen (Exit 0, sonst 1)")
    release_parser.add_argument("--output", type=Path, default=None, help="Zielordner")

    subparsers.add_parser("about", help="Angaben zum Werkzeug (Exit 0)")

    return parser


def _ui() -> Assistant:
    return Assistant(total_steps=0)


def _emit(ui: Assistant, lines: Iterable[str]) -> None:
    for line in lines:
        ui.note(line)


def _command_setup(args: argparse.Namespace) -> int:
    assistant = Assistant(total_steps=control.SETUP_STEPS, interactive=not args.unattended)
    result = control.setup(
        assistant,
        unattended=args.unattended,
        config_path=args.config,
        start_after=args.start,
    )
    return result.code


FOREIGN_NOTE = (
    "Aus einem anderen Ordner läuft bereits eine Fassung von Backrec: {folder}. "
    "Sie bleibt unberührt."
)


def _command_start(args: argparse.Namespace) -> int:
    ui = _ui()
    result = control.start(config_path=args.config)

    # Never a reason to refuse: two unpacked copies are two installations. But
    # it is the answer to the question that follows, why a window is on screen
    # that this folder knows nothing about.
    if result.foreign_folder:
        ui.note(FOREIGN_NOTE.format(folder=result.foreign_folder))

    if result.already_running:
        ui.ok(result.message)
        return EXIT_ALREADY_RUNNING
    if result.started:
        ui.ok(result.message)
        return 0

    if result.problem is not None:
        ui.fail(result.problem.cause, result.problem.next_step)
    else:
        ui.fail(result.message, "Die Prüfung ausführen und ihren Bericht an Tobias schicken.")
    return 1


def _command_stop(args: argparse.Namespace) -> int:
    ui = _ui()
    result = control.stop(
        on_progress=lambda remaining: ui.note(f"Warte noch bis zu {int(remaining)} Sekunden ...")
    )

    if result.stopped:
        ui.ok(result.message)
        return 0

    ui.fail(result.message, "Den Rechner neu starten und es noch einmal versuchen.")
    return 1


def _command_status(args: argparse.Namespace) -> int:
    ui = _ui()
    report = control.status(config_path=args.config)

    if report.running:
        ui.note(f"Backrec läuft seit {report.started} (Anwendung {report.pid}).")
        ui.note(f"Aufnahme läuft: {'ja' if report.recording else 'nein'}")
    else:
        ui.note("Backrec läuft nicht. Nächster Schritt: das Symbol auf dem Desktop anklicken.")

    if report.foreign_folder:
        ui.note(FOREIGN_NOTE.format(folder=report.foreign_folder))

    ui.note(f"Fassung: {report.version}")
    ui.note(f"Symbol auf dem Desktop: {'vorhanden' if report.shortcut_installed else 'keines'}")
    ui.note(f"Einstellungen: {report.config_path}")
    ui.note(f"Aufzeichnungen: {report.logs_path}")
    ui.note(f"Zustand: {report.state_path}")
    ui.note(f"Ordner: {report.repo_path}")
    return 0


def _command_doctor(args: argparse.Namespace) -> int:
    result = control.run_doctor(args.config, report=args.report)

    if args.json:
        # The one place that deliberately writes past the output layer: this is
        # not a sentence for a reader but a value for a script, and a symbol in
        # front of it would break every parser.
        sys.stdout.write(doctor.json_text(list(result.checks)) + "\n")
    else:
        ui = _ui()
        for line in doctor.render_text(list(result.checks)):
            ui.write(line)
        if result.report_path is not None:
            ui.blank()
            ui.note(f"Bericht: {result.report_path}")

    return result.code


def _command_shortcut(args: argparse.Namespace) -> int:
    ui = _ui()

    if args.remove:
        result = shortcut_module.remove()
        _emit(ui, result.lines)
        return result.code

    if args.status:
        result = shortcut_module.status()
        _emit(ui, result.notes)
        return 0

    # Rebuilding is the moment to sweep up: an icon of a retired start route
    # carries any name at all, and the new one would land next to it.
    control.clear_stale_shortcuts(paths.repo_root(), report=ui.note)

    built = shortcut_module.create()
    if built.ok:
        _emit(ui, built.lines)
        return 0

    ui.fail(built.lines[0], built.lines[1] if len(built.lines) > 1 else "Setup.cmd doppelklicken.")
    return built.code


def _command_uninstall(args: argparse.Namespace) -> int:
    ui = _ui()
    result = control.uninstall(purge=args.purge)
    _emit(ui, result.lines)
    return result.code


def _command_update(args: argparse.Namespace) -> int:
    ui = _ui()

    if args.git:
        result = control.update_from_git()
        _emit(ui, result.lines)
        return result.code

    if args.archive is None:
        ui.note("Es gibt zwei Wege, eine neue Fassung einzuspielen:")
        ui.note("  1. Das neue Archiv über den Ordner entpacken und Setup.cmd doppelklicken.")
        ui.note("  2. Im Zahnrad-Menü des Fensters den Eintrag 'Aktualisieren...' wählen.")
        return 0

    result = control.apply_archive(args.archive, detached=False, allow_older=args.force)
    _emit(ui, result.lines)
    return result.code


def _command_logs(args: argparse.Namespace) -> int:
    ui = _ui()
    result = control.follow_logs() if args.follow else control.open_logs()
    _emit(ui, result.lines)
    return result.code


def _command_release(args: argparse.Namespace) -> int:
    ui = _ui()
    result = control.build_release(output_dir=args.output)

    if result.ok:
        _emit(ui, result.lines)
        return 0

    ui.fail(result.lines[0] if result.lines else "Der Bau ist fehlgeschlagen.", "Die genannte Stelle korrigieren und es erneut versuchen.")
    return result.code


def _command_about(args: argparse.Namespace) -> int:
    ui = _ui()
    _emit(ui, control.about_lines(config_path=args.config))
    return 0


_COMMANDS = {
    "setup": _command_setup,
    "start": _command_start,
    "stop": _command_stop,
    "status": _command_status,
    "doctor": _command_doctor,
    "shortcut": _command_shortcut,
    "uninstall": _command_uninstall,
    "update": _command_update,
    "logs": _command_logs,
    "release": _command_release,
    "about": _command_about,
}


def main(argv: list[str] | None = None) -> int:
    """`python -m backrec <Kommando>`. Without a command: the window.

    The bare call opens the window, because that is what the desktop shortcut
    does - it passes `-m backrec` and nothing else.
    """
    args = build_parser().parse_args(argv)

    # The file log is in place before anything is read: a fault in the settings,
    # of all things, would otherwise be the one that lands nowhere.
    bootstrap()
    # Before the first line: the output carries umlauts, and whether the console
    # accepts them would otherwise depend on how this was invoked.
    use_utf8()

    if args.command is None:
        from .app import main as open_window

        return open_window()

    logger.info("Kommando '%s'", args.command)

    try:
        return _COMMANDS[args.command](args)
    except KeyboardInterrupt:
        logger.info("Abgebrochen")
        return EXIT_INTERRUPTED


if __name__ == "__main__":
    sys.exit(main())
