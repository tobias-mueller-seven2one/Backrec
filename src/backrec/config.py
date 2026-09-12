"""Where Backrec writes its recordings, and where the result goes afterwards.

Loads and checks `%LOCALAPPDATA%\\MemoSuite\\Backrec\\config.toml`. TOML rather
than `.env`, because `tomllib` ships with Python 3.11 and allows comments: the
template can explain why the recording folder deliberately sits outside a cloud
folder - knowledge that used to live in source comments only (design D3).

Four layers cover each other, weakest first: code defaults, file, environment
variables with the prefix `BACKREC_`, command line options. The two existing
variables `BACKREC_RECORDING_DIR` and `BACKREC_TARGET_DIR` keep exactly the
effect they have today, but they now sit **above** the file rather than above a
default - and which layer a value came from is something the diagnosis can say.

No folder is created while a module is imported. The old module level made both
of them on import (`main.pyw:37-38`), which is why a bad path used to mean a
program that simply did not start.
"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from . import paths

LAYER_CODE = "Vorgabe"
LAYER_FILE = "Einstellungsdatei"
LAYER_ENV = "Umgebungsvariable"
LAYER_CLI = "Kommandozeile"

REQUIRED_KEYS = ("recording_dir", "target_dir")
PATH_KEYS = REQUIRED_KEYS
KNOWN_KEYS = (*REQUIRED_KEYS, "log_level")

DEFAULT_LOG_LEVEL = "INFO"

# An unresolved variable must not silently become part of a folder name. Both
# spellings, because `os.path.expandvars` leaves either untouched when the name
# is not set.
_WINDOWS_VARIABLE = re.compile(r"%([A-Za-z_][A-Za-z0-9_]*)%")
_UNIX_VARIABLE = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?")


class ConfigError(RuntimeError):
    """The configuration is missing, invalid or incomplete."""


@dataclass(frozen=True)
class BackrecConfig:
    recording_dir: Path
    target_dir: Path
    log_level: str = DEFAULT_LOG_LEVEL
    source_path: Path | None = None
    origins: dict[str, str] = field(default_factory=dict)

    def origin_of(self, key: str) -> str:
        return self.origins.get(key, LAYER_CODE)


def read_toml(path: Path) -> dict[str, Any]:
    """Reads a TOML file and reports a syntax error with file and cause."""
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except FileNotFoundError as exc:
        raise ConfigError(f"Einstellungsdatei nicht gefunden: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(
            f"Die Einstellungsdatei {path} ist nicht lesbar: {exc}. "
            "Nächster Schritt: die Zeile korrigieren oder die Datei löschen und "
            "Setup.cmd erneut ausführen."
        ) from exc
    except OSError as exc:
        raise ConfigError(f"Einstellungsdatei {path} konnte nicht gelesen werden: {exc}") from exc


def env_overrides(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Values from environment variables with the prefix `BACKREC_`.

    `BACKREC_CONFIG` and `BACKREC_HOME` pick the file resp. the folder and are
    therefore not values inside it.
    """
    environ = os.environ if env is None else env
    values: dict[str, Any] = {}

    for name, raw in environ.items():
        if not name.startswith(paths.ENV_PREFIX):
            continue
        if name in (paths.ENV_CONFIG, paths.ENV_HOME):
            continue
        key = name[len(paths.ENV_PREFIX) :].lower()
        if key not in KNOWN_KEYS or not str(raw).strip():
            continue
        values[key] = raw

    return values


def merge_layers(*layers: Mapping[str, Any] | None) -> dict[str, Any]:
    """Lays the layers over each other; later ones win, None is ignored."""
    merged: dict[str, Any] = {}
    for layer in layers:
        if not layer:
            continue
        merged.update({key: value for key, value in layer.items() if value is not None})
    return merged


def layered(
    from_file: Mapping[str, Any] | None = None,
    from_env: Mapping[str, Any] | None = None,
    from_cli: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    """The effective values plus the layer each of them came from."""
    origins: dict[str, str] = {}
    values: dict[str, Any] = {"log_level": DEFAULT_LOG_LEVEL}
    origins["log_level"] = LAYER_CODE

    for layer, name in ((from_file, LAYER_FILE), (from_env, LAYER_ENV), (from_cli, LAYER_CLI)):
        for key, value in (layer or {}).items():
            if value is None:
                continue
            values[key] = value
            origins[key] = name

    return values, origins


def expand_checked(key: str, value: Any, config_path: Path) -> Path:
    """Expands a configured path value and insists on an absolute result.

    `%USERPROFILE%` in the old `.env` had no effect at all: nothing expanded it
    and the literal text landed in a `Path` (`main.pyw:35-36`). Expanding it and
    then checking is what turns that silent mistake into a message.
    """
    text = str(value).strip()
    if not text:
        raise ConfigError(f"'{key}' in {config_path} ist leer.")

    expanded = os.path.expandvars(text)

    for pattern in (_WINDOWS_VARIABLE, _UNIX_VARIABLE):
        match = pattern.search(expanded)
        if match:
            raise ConfigError(
                f"'{key}' in {config_path} nennt '{match.group(1)}' -- diesen Namen kennt "
                "dieser Rechner nicht."
            )

    candidate = Path(os.path.expanduser(expanded))
    if not candidate.is_absolute():
        raise ConfigError(
            f"'{key}' in {config_path} ist ein Pfad ohne Laufwerk: {candidate}. "
            "Es muss ein vollständiger Pfad sein."
        )
    return candidate


def missing_required_keys(raw: Mapping[str, Any]) -> tuple[str, ...]:
    """Mandatory values that are missing or empty."""
    return tuple(key for key in REQUIRED_KEYS if not str(raw.get(key) or "").strip())


def unknown_keys(raw: Mapping[str, Any]) -> tuple[str, ...]:
    """Keys the tool does not know - reported, never removed."""
    return tuple(sorted(key for key in raw if key not in KNOWN_KEYS))


def missing_keys(raw: Mapping[str, Any], template: Mapping[str, Any]) -> tuple[str, ...]:
    """Keys the template carries and the local file does not."""
    return tuple(sorted(key for key in template if key not in raw))


def build_config(
    raw: Mapping[str, Any],
    config_path: Path,
    *,
    origins: Mapping[str, str] | None = None,
    create_dirs: bool = False,
) -> BackrecConfig:
    """Checks the merged values and builds a configuration out of them.

    `create_dirs` stays False by default: the diagnosis is strictly reading, and
    a missing folder is one of its findings. The checked start sequence asks for
    True, because that is where creating belongs (design D5).
    """
    missing = missing_required_keys(raw)
    if missing:
        raise ConfigError(
            f"In {config_path} fehlt: {', '.join(missing)}. "
            "Nächster Schritt: Setup.cmd ausführen, es fragt die Ordner ab."
        )

    recording_dir = expand_checked("recording_dir", raw["recording_dir"], config_path)
    target_dir = expand_checked("target_dir", raw["target_dir"], config_path)

    if create_dirs:
        for directory in (recording_dir, target_dir):
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise ConfigError(f"Ordner '{directory}' konnte nicht angelegt werden: {exc}") from exc

    return BackrecConfig(
        recording_dir=recording_dir,
        target_dir=target_dir,
        log_level=str(raw.get("log_level") or DEFAULT_LOG_LEVEL),
        source_path=config_path,
        origins=dict(origins or {}),
    )


def load_config(
    path: Path,
    *,
    env: Mapping[str, str] | None = None,
    overrides: Mapping[str, Any] | None = None,
    create_dirs: bool = False,
) -> BackrecConfig:
    """Reads `path`, lays environment and command line over it, and checks."""
    if not path.is_file():
        raise ConfigError(
            f"Einstellungsdatei nicht gefunden: {path}. "
            "Nächster Schritt: Setup.cmd doppelklicken, es legt sie an."
        )

    values, origins = layered(read_toml(path), env_overrides(env), overrides)
    return build_config(values, path, origins=origins, create_dirs=create_dirs)


# --- The one-time migration of the old `.env` ---------------------------------

# The old names and what they became. The `.env` is only read: it is never
# deleted and never changed, because a tool that removes somebody else's files
# while setting itself up is hard to trust - and as long as it lies there, there
# is a way back (design D3).
LEGACY_KEYS: dict[str, str] = {
    "BACKREC_RECORDING_DIR": "recording_dir",
    "BACKREC_TARGET_DIR": "target_dir",
}


@dataclass(frozen=True)
class MigrationResult:
    migrated: bool
    source: Path | None = None
    target: Path | None = None
    values: dict[str, str] = field(default_factory=dict)
    keys: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    reason: str = ""


def read_legacy_env(source: Path) -> dict[str, str]:
    """The usable values of an old `.env`, as configuration keys."""
    try:
        text = source.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return {}

    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, _, raw = stripped.partition("=")
        key = LEGACY_KEYS.get(name.strip().upper())
        cleaned = raw.strip().strip('"').strip("'")
        if key and cleaned:
            values[key] = cleaned
    return values


def migrate_legacy(
    source: Path | None = None,
    target: Path | None = None,
    repo: Path | None = None,
) -> MigrationResult:
    """Takes the values of an old `.env` over into the new file, once."""
    legacy = source or paths.legacy_config_path(repo)
    destination = target or paths.config_path()

    if destination.is_file():
        return MigrationResult(
            migrated=False, source=legacy, target=destination, reason="vorhanden"
        )

    if not legacy.is_file():
        return MigrationResult(
            migrated=False, source=legacy, target=destination, reason="keine alte Datei"
        )

    values = read_legacy_env(legacy)
    missing = missing_required_keys(values)
    if missing:
        return MigrationResult(
            migrated=False,
            source=legacy,
            target=destination,
            values=values,
            missing=missing,
            reason="unvollständig",
        )

    from .wizard import write_config

    write_config(destination, values, repo=repo)
    return MigrationResult(
        migrated=True,
        source=legacy,
        target=destination,
        values=values,
        keys=tuple(sorted(values)),
        reason="übernommen",
    )
