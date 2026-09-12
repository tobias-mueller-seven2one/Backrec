"""Building the archive Backrec is handed over in.

The colleagues' machines have no Git and no checkout. What ships is a ZIP that
Tobias builds, with exactly one folder as its top level so that "Extract all"
yields a clean folder instead of two dozen files in Downloads.

The file selection is an **allow list over `git ls-files`** plus the two files
the build itself produces (design D18). An exclusion list only ever knows what
someone thought of; everything versioned is by definition reviewed content, and
nothing that grew locally can slip in behind it.

Four checks run before packing, and every one of them aborts hard rather than
warning:

  * the locked list must match the project definition, or a colleague ends up
    with a resolution nobody tested,
  * no file may carry a user path - the repository is public, and an archive
    with the developer's name in it is an incident, not an annoyance,
  * no file may look like it carries an access key,
  * the getting-started guide must exist and obey every one of its rules.

The last one is the one that matters most in practice. A guide nobody checks
decays: somebody adds a line with a path, somebody saves without a byte order
mark, somebody writes a technical term. An archive with a broken guide ships
exactly the problem the guide exists to solve - and a release cannot be recalled
once it sits in a chat channel.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import subprocess
import zipfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable, Sequence

from . import paths
from .console import contains_forbidden
from .logging_setup import get_logger

logger = get_logger(__name__)

MANIFEST_NAME = paths.INSTALLED_MANIFEST_NAME

LOCK_CHECK_TIMEOUT_SECONDS = 180
LIST_FILES_TIMEOUT_SECONDS = 120

# Folders that never belong in the archive. Two groups: what the setup itself
# produces, and what only describes the developer's machine.
EXCLUDED_DIRS: tuple[str, ...] = (
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "logs",
    "state",
    ".claude",
)

# Path prefixes, checked as whole path segments. The planning artefacts are
# versioned and are of no use to anybody who only unpacks the archive.
EXCLUDED_PREFIXES: tuple[str, ...] = ("openspec/changes",)

EXCLUDED_PATTERNS: tuple[str, ...] = (
    "*.pyc",
    "*.lnk",
    "*.wav",
    "*.zip",
    # One pattern rather than two names: a filled-in settings file carries
    # whatever name the person who filled it in chose.
    "config*.json",
    "config.toml",
    ".env",
    MANIFEST_NAME,
)

# Patterns that give a machine away. Assembled instead of spelled out, and that
# is no quirk: this module is read by its own check, so a spelled-out pattern
# would be a hit in itself and the build would abort on the file that checks it.
_HOME_NEEDLE = "C:" + "\\\\" + "Users" + "\\\\"
_CLOUD_NEEDLE = "One" + "Drive" + " - "
_COMPANY_NEEDLE = "Seven" + "2one"

USER_PATH_PATTERNS: tuple[str, ...] = (
    _HOME_NEEDLE,
    re.escape(_CLOUD_NEEDLE),
    re.escape(_COMPANY_NEEDLE),
)

# Credentials that have no business in a shipped archive. The key pattern
# demands a continuation, because "sk-" occurs in ordinary prose, and a check
# that aborts without cause on every second run gets worked around before long.
SECRET_PATTERNS: tuple[str, ...] = (
    r"(?<![A-Za-z0-9])" + "sk" + r"-[A-Za-z0-9_\-]{8,}",
    "ANTHROPIC" + "_API_KEY",
    "CLAUDE_CODE" + "_OAUTH_TOKEN",
)

# Suffixes that are read as text. Everything else is packed unread.
TEXT_SUFFIXES: tuple[str, ...] = (
    ".py",
    ".pyw",
    ".toml",
    ".md",
    ".txt",
    ".cmd",
    ".bat",
    ".ps1",
    ".json",
    ".yaml",
    ".yml",
    ".cfg",
)

GUIDE_MAX_LINES = 40
GUIDE_MAX_LINE_LENGTH = 80

# The eight sections in their fixed order (design D22). The first and the last
# are header and closing line and are recognised by their content.
GUIDE_SECTIONS: tuple[str, ...] = (
    paths.TOOL_NAME,
    "Was du brauchst",
    "So richtest du es ein",
    "Im Alltag",
    "Wenn etwas rot ist",
    "Aktualisieren",
    "Entfernen",
    "Tobias",
)

GUIDE_FORBIDDEN_MARKUP: tuple[str, ...] = ("```", "**", "](", "|", "<!--")
GUIDE_FORBIDDEN_COMMANDS: tuple[str, ...] = ("uv ", "npm ", "git ", "--", "python ", "powershell")

# The only two file names the guide may mention: `Setup.cmd` is the handle
# itself, `README.md` is demanded as the closing line by the convention. Any
# further name would be a path a colleague has to go looking for.
GUIDE_ALLOWED_FILE_NAMES: tuple[str, ...] = ("Setup.cmd", "README.md")

# What looks like a path: a separator with something on both sides, a drive
# letter, or an environment name in percent signs.
_GUIDE_PATH_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"[A-Za-z0-9_.\-]\\[A-Za-z0-9_.\-]", "ein Pfad"),
    (r"(?<![A-Za-z])[A-Za-z]:[\\/]", "ein Laufwerksbuchstabe"),
    (r"%[A-Za-z_][A-Za-z0-9_]*%", "eine Umgebungsangabe"),
)

_GUIDE_FILE_NAME_PATTERN = re.compile(
    r"\b[A-Za-z0-9_\-]+\.(?:cmd|bat|ps1|py|pyw|toml|json|md|txt|exe|lnk|zip|cfg|log)\b"
)


class ReleaseError(RuntimeError):
    """The build aborts. The message names the file and the rule."""


@dataclass(frozen=True)
class ManifestEntry:
    path: str
    sha256: str
    size: int


@dataclass(frozen=True)
class ReleaseResult:
    archive: Path
    version: str
    entries: tuple[ManifestEntry, ...] = field(default_factory=tuple)


# --- File selection -----------------------------------------------------------


def is_excluded(relative: Path) -> bool:
    """Whether a path relative to the tool folder stays out of the archive."""
    if any(part in EXCLUDED_DIRS for part in relative.parts):
        return True

    posix = relative.as_posix()
    if any(posix == prefix or posix.startswith(f"{prefix}/") for prefix in EXCLUDED_PREFIXES):
        return True

    return any(fnmatch.fnmatch(relative.name, pattern) for pattern in EXCLUDED_PATTERNS)


def tracked_files(root: Path) -> list[Path] | None:
    """The versioned files, or None where there is no version control."""
    if not (root / ".git").exists():
        return None

    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=str(root),
            capture_output=True,
            timeout=LIST_FILES_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("Versionierte Dateien nicht abrufbar -- es wird gelaufen: %s", exc)
        return None

    if result.returncode != 0:
        logger.warning(
            "Versionierte Dateien nicht abrufbar -- es wird gelaufen: %s",
            result.stderr.decode("utf-8", errors="replace").strip()[:400],
        )
        return None

    # `-z` and bytes: a file name with an umlaut would otherwise arrive as an
    # escape sequence and never match a file on disk.
    names = result.stdout.decode("utf-8", errors="replace").split("\0")
    return [Path(name) for name in names if name]


def collect_files(root: Path) -> list[Path]:
    """Everything to be packed, relative to the folder, in a stable order.

    Walking the folder stays as the fallback for a build from an unpacked
    archive, where there is no version control to ask. The exclusion list
    applies in both cases, because the planning artefacts are versioned too.
    """
    found = tracked_files(root)

    if found is None:
        found = []
        for current, directories, files in os.walk(root):
            current_path = Path(current)
            directories[:] = [name for name in directories if name not in EXCLUDED_DIRS]
            found.extend((current_path / name).relative_to(root) for name in files)

    selected = [
        relative for relative in found if not is_excluded(relative) and (root / relative).is_file()
    ]
    return sorted(selected, key=lambda item: item.as_posix())


# --- Checks -------------------------------------------------------------------


def check_lockfile(root: Path) -> None:
    """The locked list has to match the project definition."""
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
        raise ReleaseError(f"Die festgeschriebene Liste liess sich nicht pruefen: {exc}") from exc

    if result.returncode != 0:
        raise ReleaseError(
            "Die festgeschriebene Liste passt nicht zur Projektdefinition: "
            f"{(result.stderr or result.stdout).strip()[:500]}"
        )


def read_checkable_text(path: Path) -> str | None:
    """The content as text; None only when it cannot be read at all.

    A silent skip on non-UTF-8 would be the most dangerous line in this file: of
    all files, one saved in the local character set because a user name carries
    an umlaut would go unchecked - and that is exactly where the user path is.
    """
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
        except OSError as exc:
            logger.warning("Datei '%s' nicht lesbar -- sie wird nicht geprueft: %s", path, exc)
            return None

    logger.warning("Datei '%s' in keinem erwarteten Zeichensatz -- mit Ersatzzeichen geprueft", path)
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.warning("Datei '%s' nicht lesbar -- sie wird nicht geprueft: %s", path, exc)
        return None


def user_path_hits(text: str, username: str | None = None) -> list[str]:
    """Occurrences that give a specific machine away."""
    patterns = list(USER_PATH_PATTERNS)
    name = username if username is not None else os.environ.get("USERNAME", "")
    if name:
        patterns.append(re.escape(name))

    hits: list[str] = []
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            hits.append(match.group(0))
    return hits


def secret_hits(text: str) -> list[str]:
    """Occurrences that look like an access key."""
    hits: list[str] = []
    for pattern in SECRET_PATTERNS:
        match = re.search(pattern, text)
        if match:
            hits.append(match.group(0))
    return hits


def check_user_paths(root: Path, files: Sequence[Path], username: str | None = None) -> None:
    for relative in files:
        if relative.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = read_checkable_text(root / relative)
        if text is None:
            continue
        hits = user_path_hits(text, username)
        if hits:
            raise ReleaseError(
                f"{relative.as_posix()} enthaelt einen Nutzerpfad: {', '.join(sorted(set(hits)))}"
            )


def check_secrets(root: Path, files: Sequence[Path]) -> None:
    """Abort when a file to be packed looks like it carries a key.

    Hard, not a warning: an archive gets distributed, and a distributed key
    cannot be recalled. The message names the file and never the finding - that
    would only move the key into the build output.
    """
    for relative in files:
        if relative.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = read_checkable_text(root / relative)
        if text is None:
            continue
        if secret_hits(text):
            raise ReleaseError(
                f"{relative.as_posix()} sieht aus, als enthielte sie einen Zugangsschluessel. "
                "Der Bau bricht ab; die Datei gehoert nicht in ein Archiv."
            )


def _check_guide_line_paths(name: str, number: int, line: str) -> None:
    """Enforce the rule that the guide carries no path.

    A path in the guide is the most common way it decays: it is right on the
    machine of whoever wrote it in and on no second one.
    """
    for pattern, what in _GUIDE_PATH_PATTERNS:
        if re.search(pattern, line):
            raise ReleaseError(f"{name}, Zeile {number}: {what} hat hier nichts zu suchen")

    for found in _GUIDE_FILE_NAME_PATTERN.findall(line):
        if found not in GUIDE_ALLOWED_FILE_NAMES:
            raise ReleaseError(
                f"{name}, Zeile {number}: der Dateiname '{found}' ist hier nicht erlaubt "
                f"(erlaubt: {', '.join(GUIDE_ALLOWED_FILE_NAMES)})"
            )


def guide_lines(path: Path) -> list[str]:
    """The guide's lines, after checking name, encoding and line endings."""
    if path.name != paths.GUIDE_FILE_NAME:
        raise ReleaseError(
            f"Die Einstiegsanleitung muss genau '{paths.GUIDE_FILE_NAME}' heissen "
            f"(gefunden: {path.name})"
        )

    if not path.is_file():
        raise ReleaseError(f"Die Einstiegsanleitung fehlt: {path}")

    raw = path.read_bytes()

    if not raw.startswith(b"\xef\xbb\xbf"):
        raise ReleaseError(
            f"{path.name}: Bytereihenfolge-Kennung fehlt -- der Editor zeigt Umlaute sonst falsch"
        )

    body = raw[3:]
    if b"\r\n" not in body:
        raise ReleaseError(f"{path.name}: keine Windows-Zeilenenden gefunden")
    if re.search(rb"(?<!\r)\n", body):
        raise ReleaseError(f"{path.name}: mindestens eine Zeile endet ohne Windows-Zeilenende")

    lines = body.decode("utf-8").split("\r\n")
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def check_guide(path: Path) -> None:
    """Check the getting-started guide against every one of its rules."""
    lines = guide_lines(path)

    if len(lines) > GUIDE_MAX_LINES:
        raise ReleaseError(f"{path.name}: {len(lines)} Zeilen, erlaubt sind {GUIDE_MAX_LINES}")

    for number, line in enumerate(lines, start=1):
        if len(line) > GUIDE_MAX_LINE_LENGTH:
            raise ReleaseError(
                f"{path.name}, Zeile {number}: {len(line)} Zeichen, "
                f"erlaubt sind {GUIDE_MAX_LINE_LENGTH}"
            )
        for marker in GUIDE_FORBIDDEN_MARKUP:
            if marker in line:
                raise ReleaseError(f"{path.name}, Zeile {number}: Auszeichnungssyntax '{marker}'")
        lowered = line.lower()
        for marker in GUIDE_FORBIDDEN_COMMANDS:
            if marker in lowered:
                raise ReleaseError(
                    f"{path.name}, Zeile {number}: sieht aus wie ein Kommando ('{marker.strip()}')"
                )
        found = contains_forbidden(line)
        if found:
            raise ReleaseError(f"{path.name}, Zeile {number}: Fachbegriff '{found[0]}'")
        _check_guide_line_paths(path.name, number, line)

    position = 0
    for section in GUIDE_SECTIONS:
        for index in range(position, len(lines)):
            if section.lower() in lines[index].lower():
                position = index + 1
                break
        else:
            raise ReleaseError(
                f"{path.name}: Abschnitt '{section}' fehlt oder steht an falscher Stelle"
            )


# --- Manifest and archive -----------------------------------------------------


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(root: Path, files: Iterable[Path], version: str) -> dict[str, object]:
    entries = [
        {
            "path": relative.as_posix(),
            "sha256": file_digest(root / relative),
            "size": (root / relative).stat().st_size,
        }
        for relative in files
    ]
    return {
        "tool": paths.TOOL_NAME,
        "version": version,
        "created": date.today().isoformat(),
        "files": entries,
    }


def manifest_entries(manifest: dict[str, object]) -> tuple[ManifestEntry, ...]:
    raw = manifest.get("files")
    if not isinstance(raw, list):
        return ()
    return tuple(
        ManifestEntry(path=str(item["path"]), sha256=str(item["sha256"]), size=int(item["size"]))
        for item in raw
        if isinstance(item, dict) and {"path", "sha256", "size"} <= set(item)
    )


def build(
    root: Path | None = None,
    output_dir: Path | None = None,
    *,
    skip_lock_check: bool = False,
) -> ReleaseResult:
    """Build the archive and return its path."""
    source = root or paths.repo_root()
    version = paths.tool_version(source)
    if paths.parse_version(version) is None:
        raise ReleaseError(f"Die Fassung '{version}' hat nicht die Form JJJJ.MM.N")

    if not skip_lock_check:
        check_lockfile(source)

    check_guide(paths.guide_path(source))

    files = collect_files(source)
    check_user_paths(source, files)
    check_secrets(source, files)

    manifest = build_manifest(source, files, version)
    manifest_text = json.dumps(manifest, indent=2, ensure_ascii=False)

    target_dir = output_dir or paths.releases_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    archive = target_dir / f"{paths.TOOL_NAME}-{version}.zip"

    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for relative in files:
            bundle.write(source / relative, f"{paths.TOOL_NAME}/{relative.as_posix()}")
        bundle.writestr(f"{paths.TOOL_NAME}/{MANIFEST_NAME}", manifest_text)

    logger.info("Archiv gebaut: %s", archive)
    return ReleaseResult(archive=archive, version=version, entries=manifest_entries(manifest))
