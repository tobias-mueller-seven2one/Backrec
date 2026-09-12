"""Updating from a release archive: check, stage alongside, mirror.

A checked order, because every step has to be able to fail before the first
intervention: does the archive belong to this tool, which version does it carry,
does every file match its checksum. Only then is anything replaced. Whatever
fails before that leaves the existing state unchanged and runnable.

**Mirrored, not swapped.** The design of this change (D17) described renaming
the folder aside and the new one into its place; the suite convention (section 9)
has since settled on mirroring for all five tools, and the reasons apply to
Backrec unchanged: the folder path is baked into the desktop shortcut, a folder
that keeps its name survives the update without rework, and no rename can trip
over a handle somebody else still holds. The built environment stays where it is
and is brought up to date with the new locked list afterwards - rebuilding it
would download hundreds of megabytes for a change that usually is not there.

The mirroring itself is done during operation by a helper **outside** the folder
(`scripts\\win\\apply-update.ps1`): a process cannot replace the folder its own
code was loaded from and keep running. The functions here are the same procedure
for the case that nothing is running - and the place where it is testable.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import paths
from .logging_setup import get_logger
from .release import MANIFEST_NAME, ManifestEntry, manifest_entries

logger = get_logger(__name__)

STAGING_SUFFIX = ".update"


class UpdateError(RuntimeError):
    """The operation aborts before anything has been changed."""


@dataclass(frozen=True)
class ArchiveInfo:
    archive: Path
    tool: str
    version: str
    top_level: str
    entries: tuple[ManifestEntry, ...]


@dataclass(frozen=True)
class UpdatePlan:
    info: ArchiveInfo
    installed_version: str
    newer: bool
    same: bool

    @property
    def needs_confirmation_for_age(self) -> bool:
        """An equal or older version is confirmed once before anything happens."""
        return not self.newer


def _read_manifest(bundle: zipfile.ZipFile, archive: Path) -> tuple[str, dict[str, Any]]:
    """Find the accompanying list and the top level of the archive."""
    for name in bundle.namelist():
        parts = name.split("/")
        if len(parts) == 2 and parts[1] == MANIFEST_NAME:
            try:
                return parts[0], json.loads(bundle.read(name).decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                logger.error("Angaben in '%s' unlesbar: %s", archive, exc)
                raise UpdateError(
                    f"{archive.name} ist beschädigt -- die Datei mit den Angaben zur Fassung "
                    "lässt sich nicht lesen."
                ) from exc

    raise UpdateError(
        f"{archive.name} enthält keine Angaben zur Fassung und ist damit kein Archiv "
        "dieses Werkzeugs."
    )


def inspect(archive: Path) -> ArchiveInfo:
    """Read the archive without changing anything."""
    if not archive.is_file():
        raise UpdateError(f"Die Datei {archive} gibt es nicht.")

    try:
        with zipfile.ZipFile(archive) as bundle:
            top_level, manifest = _read_manifest(bundle, archive)
    except zipfile.BadZipFile as exc:
        raise UpdateError(f"{archive.name} ist beschädigt oder kein Archiv.") from exc

    tool = str(manifest.get("tool", ""))
    if tool != paths.TOOL_NAME:
        raise UpdateError(
            f"{archive.name} gehört zum Werkzeug '{tool or 'unbekannt'}', "
            f"erwartet war '{paths.TOOL_NAME}'."
        )

    version = str(manifest.get("version", ""))
    if paths.parse_version(version) is None:
        raise UpdateError(f"{archive.name} nennt keine gültige Fassung ('{version}').")

    return ArchiveInfo(
        archive=archive,
        tool=tool,
        version=version,
        top_level=top_level,
        entries=manifest_entries(manifest),
    )


def plan(archive: Path, installed_version: str | None = None, repo: Path | None = None) -> UpdatePlan:
    """Check the archive and compare its version with the installed one."""
    info = inspect(archive)
    current = (
        installed_version if installed_version is not None else paths.tool_version(repo or paths.repo_root())
    )
    return UpdatePlan(
        info=info,
        installed_version=current,
        newer=paths.is_newer(info.version, current),
        same=info.version == current,
    )


def staging_dir(repo: Path | None = None) -> Path:
    root = repo or paths.repo_root()
    return root.with_name(root.name + STAGING_SUFFIX)


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stage(info: ArchiveInfo, target: Path | None = None, repo: Path | None = None) -> Path:
    """Extract next to the folder and check every file against its checksum.

    On any failure the neighbouring folder is removed again and nothing about
    the running state has changed.
    """
    destination = target or staging_dir(repo)
    if destination.exists():
        shutil.rmtree(destination, ignore_errors=True)
    destination.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(info.archive) as bundle:
            prefix = f"{info.top_level}/"
            for name in bundle.namelist():
                if not name.startswith(prefix) or name.endswith("/"):
                    continue
                relative = Path(name[len(prefix) :])
                # An entry leading out of the target folder would mean a crafted
                # archive. Here it ends as a failure rather than as an
                # overwritten file somewhere in the profile.
                if relative.is_absolute() or ".." in relative.parts:
                    raise UpdateError(
                        f"{info.archive.name} enthält einen unzulässigen Eintrag: {name}"
                    )
                out_path = destination / relative
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(bundle.read(name))

        for entry in info.entries:
            candidate = destination / Path(entry.path)
            if not candidate.is_file():
                raise UpdateError(f"Im Archiv fehlt die Datei {entry.path}.")
            if _digest(candidate) != entry.sha256:
                raise UpdateError(f"Die Datei {entry.path} im Archiv ist beschädigt.")
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise

    logger.info("Archiv geprueft und nach '%s' entpackt", destination)
    return destination


def read_installed_manifest(path: Path | None = None) -> tuple[ManifestEntry, ...]:
    """The accompanying list of the state most recently set up.

    Kept in the state folder, because extracting an archive over the folder
    overwrites the copy inside it and would destroy the yardstick the comparison
    needs (design D17).
    """
    target = path or paths.installed_manifest_path()
    if not target.is_file():
        return ()
    try:
        return manifest_entries(json.loads(target.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        logger.warning("Angaben zur eingerichteten Fassung '%s' nicht lesbar: %s", target, exc)
        return ()


def write_installed_manifest(
    entries: tuple[ManifestEntry, ...],
    version: str,
    path: Path | None = None,
) -> Path:
    target = path or paths.installed_manifest_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "tool": paths.TOOL_NAME,
                "version": version,
                "files": [
                    {"path": entry.path, "sha256": entry.sha256, "size": entry.size}
                    for entry in entries
                ],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return target


def store_manifest_from_repo(repo: Path | None = None) -> Path | None:
    """Remember the accompanying list of the state that was just set up."""
    source = (repo or paths.repo_root()) / MANIFEST_NAME
    if not source.is_file():
        return None
    try:
        target = paths.installed_manifest_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return target
    except OSError as exc:
        logger.warning("Angaben zur eingerichteten Fassung nicht sicherbar: %s", exc)
        return None


def stale_files(
    previous: tuple[ManifestEntry, ...],
    current: tuple[ManifestEntry, ...],
) -> tuple[str, ...]:
    """Files of the old state that no longer exist in the new one."""
    new_paths = {entry.path for entry in current}
    return tuple(sorted(entry.path for entry in previous if entry.path not in new_paths))


def remove_stale(repo: Path, stale: tuple[str, ...]) -> tuple[str, ...]:
    """Delete the files of the previous state. Only what stood in that list.

    `.venv`, the log folder, a shortcut and the settings never appear in an
    accompanying list, so they can never turn up here either - which is what
    makes deleting by list safe at all.
    """
    removed: list[str] = []
    for relative in stale:
        target = repo / Path(relative)
        try:
            if target.is_file():
                target.unlink()
                removed.append(relative)
        except OSError as exc:
            logger.warning("Altdatei '%s' liess sich nicht entfernen: %s", target, exc)
    return tuple(removed)


def mirror(
    staging: Path,
    info: ArchiveInfo,
    repo: Path | None = None,
    previous: tuple[ManifestEntry, ...] | None = None,
) -> tuple[int, tuple[str, ...]]:
    """Mirror the checked files into the folder and clear away what is stale."""
    root = repo or paths.repo_root()
    copied = 0

    for entry in info.entries:
        source = staging / Path(entry.path)
        destination = root / Path(entry.path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied += 1

    # The accompanying list does not list itself, so mirroring by list alone
    # leaves the previous release's copy lying in the folder. The next setup
    # then measures the files that were just installed against a list that
    # predates them, takes them for leftovers and deletes them - every file new
    # in the release, right after it arrived.
    source_manifest = staging / MANIFEST_NAME
    if source_manifest.is_file():
        shutil.copy2(source_manifest, root / MANIFEST_NAME)

    known = previous if previous is not None else read_installed_manifest()
    removed = remove_stale(root, stale_files(known, info.entries))

    write_installed_manifest(info.entries, info.version)
    logger.info("%d Datei(en) gespiegelt, %d Altdatei(en) entfernt", copied, len(removed))
    return copied, removed
