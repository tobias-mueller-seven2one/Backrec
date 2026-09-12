"""The self check: why is Backrec not doing what it should, and what now.

Strictly read-only (design D12). No folder is created, no setting completed, no
process started, nothing tidied up - a check that changes things is one people
stop running while a meeting is going on, and that is exactly when it is needed.
The one write it does make is the report it was asked for, and the probe file it
removes again.

Observing and evaluating are separate, and `evaluate` is a pure function: an
empty disk, a missing playback device and an environment that does not match the
locked list are all situations no test suite can arrange on a real machine, but
every one of them can be handed to `evaluate` as a fact.

The audio devices are only **named**, never opened. Opening one would be the
more meaningful check and is not a read: it seizes a device that may be carrying
a conversation at that very moment.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Sequence

from . import config as config_module, external, instance, paths, shortcut as shortcut_module
from .logging_setup import get_logger

logger = get_logger(__name__)

# Roughly a hundred minutes of recording. A number inside a requirement, not a
# requirement itself - the first weeks of use may move it.
SPACE_RESERVE_BYTES = 2 * 1024 * 1024 * 1024
MEGABYTES_PER_MINUTE = 20

REPORT_LIMIT = 20
REPORT_PREFIX = "diagnose-"

LOCK_CHECK_TIMEOUT_SECONDS = 120
PROBE_NAME = ".backrec-doctor-probe"

CATEGORY_RUNTIME = "Laufzeit"
CATEGORY_CONFIG = "Einstellungen"
CATEGORY_EXTERNAL = "Zusatzprogramme"
CATEGORY_DEVICES = "Audiogeräte"
CATEGORY_DIRECTORIES = "Ordner und Speicherplatz"
CATEGORY_SHORTCUT = "Verknüpfung"
CATEGORY_STATE = "Zustand"


class Level(Enum):
    PASS = "bestanden"
    WARN = "Warnung"
    FAIL = "Fehler"


SYMBOLS: dict[Level, str] = {Level.PASS: "[OK]", Level.WARN: "[!]", Level.FAIL: "[X]"}


@dataclass(frozen=True)
class Check:
    """One finding. `key` is the stable identifier the machine-readable form uses."""

    key: str
    category: str
    name: str
    level: Level
    cause: str
    next_step: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "id": self.key,
            "category": self.category,
            "name": self.name,
            "level": self.level.name.lower(),
            "cause": self.cause,
            "next_step": self.next_step,
        }


@dataclass(frozen=True)
class DirectoryFact:
    key: str
    path: Path
    exists: bool
    writable: bool
    free_bytes: int | None = None
    in_cloud: bool = False


@dataclass
class Observations:
    """Everything the check knows about this machine. Facts only."""

    installed_version: str = paths.UNKNOWN_VERSION
    repo_path: Path | None = None
    repo_recognised: bool = True
    uv_path: str | None = None
    python_version: str = ""
    required_python: str = ""
    venv_present: bool = False
    venv_matches_lock: bool | None = None

    config_path: Path | None = None
    config_exists: bool = False
    config_error: str | None = None
    unknown_keys: tuple[str, ...] = ()
    missing_keys: tuple[str, ...] = ()
    missing_required: tuple[str, ...] = ()
    origins: dict[str, str] = field(default_factory=dict)

    ffmpeg: external.FfmpegState | None = None

    device_detection: bool = True
    microphone: str | None = None
    speaker: str | None = None

    directories: tuple[DirectoryFact, ...] = ()

    shortcut: shortcut_module.ShortcutStatus | None = None
    shortcut_stale: tuple[Path, ...] = ()

    logs_dir: Path | None = None
    logs_exists: bool = True
    logs_writable: bool = True
    orphan_record: bool = False
    stop_request: bool = False
    legacy_env: Path | None = None
    stale_folders: tuple[Path, ...] = ()
    report_count: int = 0


# --- Evaluation (pure) --------------------------------------------------------


def _runtime_checks(facts: Observations) -> list[Check]:
    known_version = facts.installed_version != paths.UNKNOWN_VERSION
    checks = [
        Check(
            "runtime.version",
            CATEGORY_RUNTIME,
            "Eingerichtete Fassung",
            Level.PASS if known_version else Level.WARN,
            f"Fassung {facts.installed_version}",
            "" if known_version else "Setup.cmd erneut doppelklicken.",
        ),
        Check(
            "runtime.folder",
            CATEGORY_RUNTIME,
            "Ordner des Werkzeugs",
            Level.PASS if facts.repo_recognised else Level.WARN,
            str(facts.repo_path or "unbekannt")
            if facts.repo_recognised
            else f"{facts.repo_path} sieht nicht wie der Ordner des Werkzeugs aus",
            ""
            if facts.repo_recognised
            else "Das Archiv noch einmal vollständig entpacken und Setup.cmd doppelklicken.",
        ),
        Check(
            "runtime.uv",
            CATEGORY_RUNTIME,
            "Hilfsprogramm für die Einrichtung",
            Level.PASS if facts.uv_path else Level.FAIL,
            f"gefunden unter {facts.uv_path}" if facts.uv_path else "nicht gefunden",
            "" if facts.uv_path else "Setup.cmd doppelklicken, es beschafft das Hilfsprogramm.",
        ),
    ]

    matches = bool(facts.required_python) and facts.python_version.startswith(facts.required_python)
    checks.append(
        Check(
            "runtime.python",
            CATEGORY_RUNTIME,
            "Fassung der Programmiersprache",
            Level.PASS if matches else Level.FAIL,
            f"vorhanden {facts.python_version or 'unbekannt'}, "
            f"verlangt {facts.required_python or 'unbekannt'}",
            "" if matches else "Setup.cmd doppelklicken, es richtet die verlangte Fassung ein.",
        )
    )

    if not facts.venv_present:
        checks.append(
            Check(
                "runtime.environment",
                CATEGORY_RUNTIME,
                "Arbeitsumgebung",
                Level.FAIL,
                "die Arbeitsumgebung des Werkzeugs fehlt",
                "Setup.cmd doppelklicken.",
            )
        )
    elif facts.venv_matches_lock is False:
        checks.append(
            Check(
                "runtime.environment",
                CATEGORY_RUNTIME,
                "Arbeitsumgebung",
                Level.FAIL,
                "die Arbeitsumgebung passt nicht zu dieser Fassung des Werkzeugs",
                "Setup.cmd doppelklicken, es zieht sie nach.",
            )
        )
    elif facts.venv_matches_lock is None:
        checks.append(
            Check(
                "runtime.environment",
                CATEGORY_RUNTIME,
                "Arbeitsumgebung",
                Level.WARN,
                "vorhanden; ob sie zur festgeschriebenen Liste passt, ließ sich nicht feststellen",
                "Setup.cmd doppelklicken, es zieht sie nach.",
            )
        )
    else:
        checks.append(
            Check(
                "runtime.environment",
                CATEGORY_RUNTIME,
                "Arbeitsumgebung",
                Level.PASS,
                "vorhanden und passend",
            )
        )

    return checks


def _config_checks(facts: Observations) -> list[Check]:
    location = str(facts.config_path) if facts.config_path else "unbekannt"

    if not facts.config_exists:
        return [
            Check(
                "config.file",
                CATEGORY_CONFIG,
                "Einstellungen",
                Level.FAIL,
                f"es gibt noch keine Einstellungen ({location})",
                "Setup.cmd doppelklicken, es legt sie an.",
            )
        ]

    if facts.config_error:
        return [
            Check(
                "config.file",
                CATEGORY_CONFIG,
                "Einstellungen",
                Level.FAIL,
                facts.config_error,
                "Setup.cmd doppelklicken oder die Zeile in der Datei korrigieren.",
            )
        ]

    checks = [
        Check("config.file", CATEGORY_CONFIG, "Einstellungen", Level.PASS, f"gelesen aus {location}")
    ]

    if facts.missing_required:
        checks.append(
            Check(
                "config.required",
                CATEGORY_CONFIG,
                "Pflichtangaben",
                Level.FAIL,
                f"es fehlen: {', '.join(facts.missing_required)}",
                "Setup.cmd doppelklicken, es fragt die Ordner ab.",
            )
        )
    else:
        checks.append(
            Check("config.required", CATEGORY_CONFIG, "Pflichtangaben", Level.PASS, "alle vorhanden")
        )

    if facts.unknown_keys:
        checks.append(
            Check(
                "config.unknown",
                CATEGORY_CONFIG,
                "Unbekannte Angaben",
                Level.WARN,
                f"unbekannt: {', '.join(facts.unknown_keys)}",
                "Die Angabe entfernen oder Tobias fragen; geändert wird hier nichts.",
            )
        )

    if facts.missing_keys:
        checks.append(
            Check(
                "config.template",
                CATEGORY_CONFIG,
                "Neue Angaben in der Vorlage",
                Level.WARN,
                f"in der Vorlage neu, hier nicht vorhanden: {', '.join(facts.missing_keys)}",
                "Setup.cmd doppelklicken ergänzt sie.",
            )
        )

    if facts.origins:
        named = ", ".join(f"{key} aus {layer}" for key, layer in sorted(facts.origins.items()))
        checks.append(
            Check("config.origins", CATEGORY_CONFIG, "Herkunft der Werte", Level.PASS, named)
        )

    return checks


def _external_checks(facts: Observations) -> list[Check]:
    state = facts.ffmpeg
    if state is None:
        return []

    if state.usable:
        return [
            Check(
                "external.ffmpeg",
                CATEGORY_EXTERNAL,
                "Programm zum Zusammenmischen",
                Level.PASS,
                f"gefunden unter {state.found_at}, Fassung {state.version or 'unbekannt'}",
            )
        ]

    if state.found_at is None:
        return [
            Check(
                "external.ffmpeg",
                CATEGORY_EXTERNAL,
                "Programm zum Zusammenmischen",
                Level.FAIL,
                "es ist auf diesem Rechner nicht auffindbar",
                "Setup.cmd doppelklicken; die Einrichtung beschafft es.",
            )
        ]

    return [
        Check(
            "external.ffmpeg",
            CATEGORY_EXTERNAL,
            "Programm zum Zusammenmischen",
            Level.FAIL,
            f"unter {state.found_at} vorhanden, der Aufruf scheitert",
            "Setup.cmd doppelklicken; bleibt es dabei, das Programm neu einrichten.",
        )
    ]


def _device_checks(facts: Observations) -> list[Check]:
    """A missing detection is its own finding, never "no device" (design D12)."""
    if not facts.device_detection:
        return [
            Check(
                "devices.detection",
                CATEGORY_DEVICES,
                "Geräteerkennung",
                Level.FAIL,
                "die Erkennung der Standardgeräte ist auf diesem Rechner nicht verfügbar",
                "Setup.cmd doppelklicken, es baut die Arbeitsumgebung neu auf.",
            )
        ]

    return [
        Check(
            "devices.microphone",
            CATEGORY_DEVICES,
            "Standard-Aufnahmegerät",
            Level.PASS if facts.microphone else Level.FAIL,
            facts.microphone or "es ist kein Standard-Aufnahmegerät eingerichtet",
            ""
            if facts.microphone
            else "In den Windows-Einstellungen unter Sound ein Mikrofon als Standard wählen.",
        ),
        Check(
            "devices.speaker",
            CATEGORY_DEVICES,
            "Standard-Wiedergabegerät",
            Level.PASS if facts.speaker else Level.FAIL,
            facts.speaker or "es ist kein Standard-Wiedergabegerät eingerichtet",
            ""
            if facts.speaker
            else "In den Windows-Einstellungen unter Sound eine Wiedergabe als Standard wählen; "
            "die Aufnahme des Systemtons setzt darauf auf.",
        ),
    ]


def _gigabytes(value: int) -> str:
    return f"{value / (1024 * 1024 * 1024):.1f} GB"


def _directory_checks(facts: Observations) -> list[Check]:
    checks: list[Check] = []

    for directory in facts.directories:
        if not directory.exists:
            checks.append(
                Check(
                    f"directory.{directory.key}",
                    CATEGORY_DIRECTORIES,
                    f"Ordner {directory.key}",
                    Level.FAIL,
                    f"{directory.path} gibt es nicht",
                    "Setup.cmd doppelklicken; der Start legt ihn sonst selbst an. "
                    "Das nächste Werkzeug der Reihe liest aus dem Zielordner.",
                )
            )
            continue

        if not directory.writable:
            checks.append(
                Check(
                    f"directory.{directory.key}",
                    CATEGORY_DIRECTORIES,
                    f"Ordner {directory.key}",
                    Level.FAIL,
                    f"in {directory.path} lässt sich nichts schreiben",
                    "Prüfen, ob der Ordner erreichbar ist (etwa die Cloud gerade offline).",
                )
            )
            continue

        checks.append(
            Check(
                f"directory.{directory.key}",
                CATEGORY_DIRECTORIES,
                f"Ordner {directory.key}",
                Level.PASS,
                str(directory.path),
            )
        )

        if directory.free_bytes is not None:
            enough = directory.free_bytes >= SPACE_RESERVE_BYTES
            checks.append(
                Check(
                    f"space.{directory.key}",
                    CATEGORY_DIRECTORIES,
                    f"Freier Platz für {directory.key}",
                    Level.PASS if enough else Level.WARN,
                    f"{_gigabytes(directory.free_bytes)} frei"
                    + (
                        ""
                        if enough
                        else f", das ist weniger als die Reserve von "
                        f"{_gigabytes(SPACE_RESERVE_BYTES)}"
                    ),
                    ""
                    if enough
                    else f"Platz schaffen. Eine Aufnahme braucht rund "
                    f"{MEGABYTES_PER_MINUTE} MB je Minute.",
                )
            )

        if directory.in_cloud:
            checks.append(
                Check(
                    f"cloud.{directory.key}",
                    CATEGORY_DIRECTORIES,
                    f"Ordner {directory.key} in der Cloud",
                    Level.WARN,
                    f"{directory.path} liegt in einem Ordner, der laufend hochgeladen wird",
                    "Einen Ordner außerhalb wählen; während der Aufnahme entstehen dort "
                    f"rund {MEGABYTES_PER_MINUTE} MB je Minute.",
                )
            )

    return checks


def _stale_shortcut_check(facts: Observations) -> Check:
    """Leftover icons of this folder that no longer start anything.

    Reported separately from the icon itself, because both can be true at once:
    a working icon next to one from an earlier version, which is the state that
    makes a double click print a notice instead of opening the window.
    """
    names = ", ".join(entry.name for entry in facts.shortcut_stale)
    return Check(
        "shortcut.stale",
        CATEGORY_SHORTCUT,
        "Veraltete Verknüpfungen",
        Level.FAIL,
        f"{names}: {shortcut_module.STALE_ENTRY_CAUSE}",
        "Setup.cmd doppelklicken entfernt sie.",
    )


def _shortcut_checks(facts: Observations) -> list[Check]:
    checks = _entry_checks(facts)
    if facts.shortcut_stale:
        checks.append(_stale_shortcut_check(facts))
    return checks


def _entry_checks(facts: Observations) -> list[Check]:
    state = facts.shortcut
    if state is None:
        return []

    if not state.exists:
        return [
            Check(
                "shortcut.entry",
                CATEGORY_SHORTCUT,
                "Verknüpfung auf dem Desktop",
                Level.WARN,
                "es liegt keine Verknüpfung auf dem Desktop",
                "Setup.cmd doppelklicken; es legt sie auf Wunsch an.",
            )
        ]

    if not state.readable:
        return [
            Check(
                "shortcut.entry",
                CATEGORY_SHORTCUT,
                "Verknüpfung auf dem Desktop",
                Level.WARN,
                f"{state.path} ist vorhanden, lässt sich aber nicht lesen",
                "Die Verknüpfung löschen und Setup.cmd erneut doppelklicken.",
            )
        ]

    if not state.belongs_here:
        return [
            Check(
                "shortcut.entry",
                CATEGORY_SHORTCUT,
                "Verknüpfung auf dem Desktop",
                Level.WARN,
                f"{state.path} gehört zu einer anderen Installation",
                "Setup.cmd in diesem Ordner doppelklicken, um sie neu aufzubauen.",
            )
        ]

    if not state.target_exists:
        return [
            Check(
                "shortcut.entry",
                CATEGORY_SHORTCUT,
                "Verknüpfung auf dem Desktop",
                Level.FAIL,
                f"{state.path} zeigt auf ein Ziel, das es nicht mehr gibt",
                "Setup.cmd doppelklicken, um sie neu aufzubauen.",
            )
        ]

    if not state.target_current:
        return [
            Check(
                "shortcut.entry",
                CATEGORY_SHORTCUT,
                "Verknüpfung auf dem Desktop",
                Level.WARN,
                f"{state.path} nimmt noch den abgelösten Startweg",
                "Setup.cmd doppelklicken, um sie neu aufzubauen.",
            )
        ]

    return [
        Check(
            "shortcut.entry",
            CATEGORY_SHORTCUT,
            "Verknüpfung auf dem Desktop",
            Level.PASS,
            str(state.path),
        )
    ]


def _logs_check(facts: Observations) -> Check:
    """A folder that is not there yet is not a fault.

    The log folder is made by the first line of every run. Before that first run
    it is simply absent, and reporting that as an error would make a fresh
    installation look broken at the one moment somebody is watching closely.
    """
    if not facts.logs_exists:
        return Check(
            "state.logs",
            CATEGORY_STATE,
            "Ordner der Aufzeichnungen",
            Level.WARN,
            f"{facts.logs_dir} gibt es noch nicht",
            "Nichts. Der erste Start legt ihn an.",
        )

    return Check(
        "state.logs",
        CATEGORY_STATE,
        "Ordner der Aufzeichnungen",
        Level.PASS if facts.logs_writable else Level.FAIL,
        str(facts.logs_dir)
        if facts.logs_writable
        else f"{facts.logs_dir} lässt sich nicht beschreiben",
        "" if facts.logs_writable else "Prüfen, ob der Ordner erreichbar ist.",
    )


def _state_checks(facts: Observations) -> list[Check]:
    checks = [
        _logs_check(facts),
        Check(
            "state.record",
            CATEGORY_STATE,
            "Vermerk der laufenden Anwendung",
            Level.WARN if facts.orphan_record else Level.PASS,
            "ein Vermerk zeigt auf eine Anwendung, die nicht mehr läuft"
            if facts.orphan_record
            else "in Ordnung",
            "Nichts. Der nächste Start übernimmt den Vermerk selbst."
            if facts.orphan_record
            else "",
        ),
        Check(
            "state.stop_request",
            CATEGORY_STATE,
            "Liegengebliebene Beendigungsanforderung",
            Level.WARN if facts.stop_request else Level.PASS,
            "eine Anforderung zum Beenden liegt noch da" if facts.stop_request else "keine",
            "Nichts. Der nächste Start entfernt sie selbst." if facts.stop_request else "",
        ),
    ]

    if facts.legacy_env is not None:
        checks.append(
            Check(
                "state.legacy",
                CATEGORY_STATE,
                "Frühere Einstellungsdatei im Ordner",
                Level.WARN,
                f"{facts.legacy_env} ist vorhanden, wirkt aber nicht mehr",
                "Sie wurde beim Einrichten übernommen und kann gelöscht werden.",
            )
        )

    if facts.stale_folders:
        checks.append(
            Check(
                "state.stale_folders",
                CATEGORY_STATE,
                "Ordner einer abgelösten Fassung",
                Level.WARN,
                ", ".join(str(folder) for folder in facts.stale_folders),
                "Diesen Ordner im Dateimanager löschen; die Diagnose fasst ihn nicht an.",
            )
        )

    if facts.report_count > REPORT_LIMIT:
        checks.append(
            Check(
                "state.reports",
                CATEGORY_STATE,
                "Angesammelte Berichte",
                Level.WARN,
                f"{facts.report_count} Berichte im Ordner der Aufzeichnungen",
                "Die älteren im Dateimanager löschen; die Diagnose räumt nicht selbst auf.",
            )
        )

    return checks


def evaluate(facts: Observations) -> list[Check]:
    """Turn observations into findings. Pure, so every situation is testable."""
    checks: list[Check] = []
    for builder in (
        _runtime_checks,
        _config_checks,
        _external_checks,
        _device_checks,
        _directory_checks,
        _shortcut_checks,
        _state_checks,
    ):
        # One failing group must not cost the others: a report is only worth
        # sending if it is complete.
        try:
            checks.extend(builder(facts))
        except Exception:  # noqa: BLE001 - see comment
            logger.exception("Pruefgruppe fehlgeschlagen")
            checks.append(
                Check(
                    "meta.incomplete",
                    "Weitere Prüfungen",
                    "Unvollständige Prüfung",
                    Level.WARN,
                    "Ein Teil der Prüfungen ließ sich nicht durchführen.",
                    "Diesen Bericht an Tobias schicken.",
                )
            )
    return checks


def exit_code(checks: Sequence[Check]) -> int:
    """0 as long as nothing reports 'Fehler'. A warning changes nothing."""
    return 1 if any(check.level is Level.FAIL for check in checks) else 0


def has_failure(checks: Sequence[Check]) -> bool:
    return exit_code(checks) != 0


def failures(checks: Sequence[Check]) -> list[Check]:
    return [check for check in checks if check.level is Level.FAIL]


def render_text(checks: Sequence[Check]) -> list[str]:
    """The findings as lines, grouped by category."""
    lines: list[str] = []
    current = ""
    for check in checks:
        if check.category != current:
            current = check.category
            lines.append("")
            lines.append(current)
            lines.append("-" * len(current))
        lines.append(f"  {SYMBOLS[check.level]} {check.name}: {check.cause}")
        if check.next_step:
            lines.append(f"      Was tun: {check.next_step}")
    return lines


def as_json(checks: Sequence[Check], repo: Path | None = None) -> dict[str, Any]:
    root = repo or paths.repo_root()
    return {
        "tool": paths.TOOL_NAME,
        "version": paths.tool_version(root),
        "generated": datetime.now().isoformat(timespec="seconds"),
        "result": "fail" if exit_code(checks) else "pass",
        "checks": [check.as_dict() for check in checks],
    }


def json_text(checks: Sequence[Check], repo: Path | None = None) -> str:
    return json.dumps(as_json(checks, repo), indent=2, ensure_ascii=False)


# --- Observation (with I/O) ---------------------------------------------------


def is_writable(directory: Path) -> bool:
    """Whether a file can be created in `directory` - without leaving one behind.

    The only write this check makes outside its report, and it is unavoidable:
    on Windows no attribute reliably says whether a share or a cloud folder
    accepts a write right now. The folder itself is never created.
    """
    if not directory.is_dir():
        return False

    probe = directory / PROBE_NAME
    try:
        probe.write_bytes(b"")
    except OSError:
        return False
    finally:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass
    return True


def free_bytes(directory: Path) -> int | None:
    try:
        return shutil.disk_usage(directory).free
    except OSError:
        return None


def in_cloud_folder(directory: Path, env: dict[str, str] | None = None) -> bool:
    """Whether `directory` lies below the folder that is synchronised away."""
    environ = env if env is not None else dict(os.environ)
    root = environ.get(paths.CLOUD_VARIABLE, "").strip()
    if not root:
        return False

    try:
        prefix = os.path.normcase(str(Path(root).resolve()))
        candidate = os.path.normcase(str(directory.resolve()))
    except OSError:
        return False
    return candidate == prefix or candidate.startswith(prefix + os.sep)


def required_python(root: Path) -> str:
    try:
        return (root / ".python-version").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def environment_python(root: Path) -> str:
    """The version of the built environment, read from its own marker file.

    Read out of `pyvenv.cfg` rather than taken from the running interpreter:
    the check may well run from somewhere else, and the question is what the
    shortcut will start, not what is executing right now.
    """
    marker = root / ".venv" / "pyvenv.cfg"
    try:
        for line in marker.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "version" or name.strip() == "version_info":
                return value.strip()
    except OSError:
        return ""
    return ""


def environment_matches_lock(root: Path) -> bool | None:
    """Whether the locked list still matches the project. None if unanswerable.

    `uv lock --check` and not `uv sync --dry-run`: the latter returns 0 even
    when it would install packages, and reports a difference as soon as someone
    built with development tools - a false alarm either way.
    """
    if shutil.which("uv") is None:
        return None

    try:
        result = subprocess.run(
            ["uv", "lock", "--check"],
            cwd=str(root),
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=LOCK_CHECK_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("Abgleich mit der festgeschriebenen Liste nicht moeglich: %s", exc)
        return None
    return result.returncode == 0


def stale_update_folders(root: Path) -> tuple[Path, ...]:
    """Leftovers of an update: a staging folder or a superseded copy."""
    found: list[Path] = []
    try:
        for sibling in root.parent.iterdir():
            if not sibling.is_dir() or sibling == root:
                continue
            if sibling.name.startswith(f"{root.name}.old-") or sibling.name == f"{root.name}.update":
                found.append(sibling)
    except OSError as exc:
        logger.debug("Nachbarordner nicht lesbar: %s", exc)
    return tuple(sorted(found))


def count_reports(directory: Path) -> int:
    try:
        return sum(1 for _entry in directory.glob(f"{REPORT_PREFIX}*.txt"))
    except OSError:
        return 0


def _observe_config(facts: Observations, target: Path) -> config_module.BackrecConfig | None:
    if not facts.config_exists:
        return None

    try:
        raw = config_module.read_toml(target)
    except config_module.ConfigError as exc:
        facts.config_error = str(exc)
        return None

    facts.unknown_keys = config_module.unknown_keys(raw)
    facts.missing_required = config_module.missing_required_keys(raw)

    try:
        template = config_module.read_toml(paths.example_config_path())
    except config_module.ConfigError:
        template = {}
    facts.missing_keys = config_module.missing_keys(raw, template)

    try:
        # create_dirs=False: the diagnosis reads, and a missing folder is one of
        # its findings rather than something to fix on the side.
        loaded = config_module.load_config(target, create_dirs=False)
    except config_module.ConfigError as exc:
        if not facts.missing_required:
            facts.config_error = str(exc)
        return None

    facts.origins = dict(loaded.origins)
    return loaded


def _observe_directories(facts: Observations, loaded: config_module.BackrecConfig | None) -> None:
    if loaded is None:
        return

    facts.directories = tuple(
        DirectoryFact(
            key=key,
            path=path,
            exists=path.is_dir(),
            writable=is_writable(path),
            free_bytes=free_bytes(path) if path.is_dir() else None,
            in_cloud=in_cloud_folder(path),
        )
        for key, path in (
            ("Aufnahme", loaded.recording_dir),
            ("Ziel", loaded.target_dir),
        )
    )


def _observe_devices(facts: Observations) -> None:
    """Names the default devices without opening a stream (design D12)."""
    try:
        from .devices import (
            PYCAW_AVAILABLE,
            get_default_comm_device_name,
            get_default_speaker_device_name,
        )
    except Exception:  # noqa: BLE001 - a missing audio stack is a finding of its own
        logger.warning("Geraeteerkennung nicht importierbar", exc_info=True)
        facts.device_detection = False
        return

    facts.device_detection = PYCAW_AVAILABLE
    if not PYCAW_AVAILABLE:
        return

    import comtypes

    comtypes.CoInitialize()
    try:
        facts.microphone = get_default_comm_device_name()
        facts.speaker = get_default_speaker_device_name()
    finally:
        comtypes.CoUninitialize()


def _observe_state(facts: Observations, root: Path) -> None:
    record = instance.read_record()
    facts.orphan_record = record is not None and instance.live_process(record, root) is None
    facts.stop_request = instance.stop_requested()

    legacy = paths.legacy_config_path(root)
    facts.legacy_env = legacy if legacy.is_file() else None

    try:
        # Reads every `.lnk` on the desktop, one COM call per file. Affordable
        # here -- the diagnosis runs on demand, never in a cycle of the window.
        facts.shortcut_stale = tuple(shortcut_module.stale_entries(repo=root))
    except OSError as exc:
        logger.debug("Veraltete Verknuepfungen nicht lesbar: %s", exc)

    facts.stale_folders = stale_update_folders(root)
    facts.report_count = count_reports(paths.reports_dir())
    facts.logs_exists = paths.logs_dir().is_dir()
    facts.logs_writable = facts.logs_exists and is_writable(paths.logs_dir())


def observe(
    config_path: Path | None = None,
    repo: Path | None = None,
    *,
    with_devices: bool = True,
) -> Observations:
    """Gather every fact. Each failure is caught, none is fatal."""
    root = repo or paths.repo_root()
    target = paths.config_path(config_path)

    facts = Observations(
        installed_version=paths.tool_version(root),
        repo_path=root,
        repo_recognised=paths.has_repo_marker(root),
        uv_path=shutil.which("uv"),
        python_version=environment_python(root) or platform.python_version(),
        required_python=required_python(root),
        venv_present=(root / ".venv" / "Scripts" / "pythonw.exe").is_file(),
        config_path=target,
        config_exists=target.is_file(),
        logs_dir=paths.logs_dir(),
        ffmpeg=external.inspect(),
        shortcut=shortcut_module.status(root),
    )
    facts.venv_matches_lock = environment_matches_lock(root) if facts.venv_present else False

    loaded = _observe_config(facts, target)
    _observe_directories(facts, loaded)
    if with_devices:
        _observe_devices(facts)
    _observe_state(facts, root)
    return facts


def run(
    config_path: Path | None = None,
    repo: Path | None = None,
    *,
    with_devices: bool = True,
) -> list[Check]:
    """Observe and evaluate in one step."""
    return evaluate(observe(config_path, repo, with_devices=with_devices))


# --- Report -------------------------------------------------------------------


def report_lines(
    checks: Sequence[Check],
    config_path: Path | None = None,
    repo: Path | None = None,
) -> list[str]:
    """Header, findings, locations.

    The header is this verbose on purpose: it answers the three questions that
    would otherwise come back as replies to the message the report was attached
    to (design D21).
    """
    root = repo or paths.repo_root()
    heading = f"{paths.TOOL_NAME} {paths.tool_version(root)} -- Diagnose"

    lines = [
        heading,
        "=" * len(heading),
        f"Erstellt am: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
        f"Ordner des Werkzeugs: {root}",
        f"Einstellungen: {paths.config_path(config_path)}",
        f"Windows: {platform.platform()}",
        "",
        "Diese Datei darfst du an Tobias schicken. Sie enthält nichts aus deinen",
        "Aufnahmen und keine Zugangsdaten. Die genannten Ordner enthalten deinen",
        "Windows-Benutzernamen.",
    ]
    lines.extend(render_text(checks))
    lines.extend(
        [
            "",
            "Orte",
            "----",
            f"  Aufzeichnungen: {paths.logs_dir()}",
            f"  Zustand: {paths.state_dir()}",
        ]
    )
    return lines


def write_report(
    checks: Sequence[Check],
    directory: Path | None = None,
    config_path: Path | None = None,
    repo: Path | None = None,
) -> Path:
    """Write the report as a text file and return its path.

    Nothing is pruned here, unlike the neighbouring tool: the diagnosis of this
    tool tidies nothing up, it only warns once the reports pile up. Deleting a
    report would be a change, and a check that changes things is one people stop
    running.
    """
    target_dir = directory or paths.reports_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    target = target_dir / f"{REPORT_PREFIX}{stamp}.txt"

    # CRLF and a byte order mark, because the report is opened in the default
    # editor. `newline=""` is not optional: without it Python turns every "\n"
    # into "\r\n" a second time and every line becomes a blank-line sandwich.
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        handle.write("\r\n".join(report_lines(checks, config_path, repo)) + "\r\n")

    logger.info("Diagnosebericht geschrieben: %s", target)
    return target


def open_in_editor(path: Path) -> bool:
    """Open the report in the default editor. Says whether that worked."""
    try:
        os.startfile(str(path))  # noqa: S606 - exactly what the function is for
        return True
    except (OSError, AttributeError) as exc:
        logger.warning("Bericht '%s' liess sich nicht oeffnen: %s", path, exc)
        return False
