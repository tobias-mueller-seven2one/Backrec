"""The icon on the desktop - Backrec's way in.

Backrec is the one interactive tool of the suite: it is started when a
conversation begins, not when Windows logs in. That is why the setup may create
this shortcut **itself** while the neighbouring tools insist on a manual drag
(design D14). Their target is the startup folder, which is logon persistence and
exactly the behaviour endpoint protection reacts to; the desktop is not, and a
program is allowed to put an icon there. It saves the colleague the one step of
the whole procedure that does not work without an explanation.

The link is built and read back through `WScript.Shell`. Read back rather than
derived, because a `.lnk` is one save away from pointing anywhere, and only
Windows knows what is really inside one.

The desktop folder comes from the registry, with `%USERPROFILE%\\Desktop` as the
fallback: only the registry follows a redirected or roaming profile, and on
those machines the fallback would silently create the icon where nobody sees it.

Writer and reader are parameters so the whole decision logic - does one exist,
does it belong here, does its target still exist - is testable without COM and
without a real desktop.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import paths
from .logging_setup import get_logger

logger = get_logger(__name__)

SHORTCUT_NAME = f"{paths.TOOL_NAME}.lnk"
SHORTCUT_DESCRIPTION = "Backrec: nimmt Mikrofon und Systemton eines Gesprächs auf"

LAUNCH_ARGUMENTS = "-m backrec"

# Only the registry knows a redirected desktop.
_SHELL_FOLDERS_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"

# An icon of its own if the folder carries one; otherwise the shortcut keeps the
# icon of its target. No file is generated for it - a binary in a public
# repository wants a reason, and "nicer" is not one.
ICON_CANDIDATES: tuple[str, ...] = ("Backrec.ico", "assets/Backrec.ico")

FIXED_PATH_NOTE = (
    "Die Verknüpfung enthält feste Pfade auf diesen Ordner. Wird er verschoben oder "
    "umbenannt, muss sie neu aufgebaut werden."
)

MISSING_ENVIRONMENT_NOTE = (
    "Das Werkzeug ist noch nicht eingerichtet, deshalb gibt es nichts, worauf die "
    "Verknüpfung zeigen könnte."
)

RUNNING_UNTOUCHED_NOTE = (
    "Eine laufende Anwendung läuft weiter; beenden lässt sie sich über das Fenster-X."
)


@dataclass(frozen=True)
class ShortcutSpec:
    """What the link will contain. Pure, therefore testable anywhere."""

    target: str
    arguments: str
    workdir: str
    description: str
    icon: str = ""


@dataclass(frozen=True)
class ShortcutStatus:
    """What a look at the desktop found."""

    path: Path
    exists: bool
    readable: bool = False
    belongs_here: bool = False
    target_exists: bool = False
    contents: dict[str, str] = field(default_factory=dict)
    notes: tuple[str, ...] = ()

    @property
    def installed(self) -> bool:
        """Present, readable, ours, and pointing at something that is there."""
        return self.exists and self.readable and self.belongs_here and self.target_exists


@dataclass(frozen=True)
class ShortcutResult:
    ok: bool
    code: int = 0
    path: Path | None = None
    lines: tuple[str, ...] = ()


ShortcutWriter = Callable[[Path, ShortcutSpec], "str | None"]
ShortcutReader = Callable[[Path], "dict[str, str] | None"]


# --- Locations ----------------------------------------------------------------


def desktop_folder() -> Path:
    """The user's desktop, following a redirected profile.

    Never raises: whoever has a damaged profile should still get *a* folder that
    can be named in a message instead of an exception nobody can act on.
    """
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _SHELL_FOLDERS_KEY) as key:
            value, _ = winreg.QueryValueEx(key, "Desktop")
            if value:
                return Path(os.path.expandvars(str(value)))
    except (ImportError, OSError) as exc:
        logger.debug("Desktop-Ordner nicht aus der Registry lesbar: %s", exc)

    profile = os.environ.get("USERPROFILE")
    base = Path(profile) if profile else Path.home()
    return base / "Desktop"


def launcher(repo: Path | None = None) -> Path:
    """The windowless interpreter of the built environment.

    The same one `Start.cmd` uses. Deliberately not a generated `backrec.exe`:
    that file is recreated by every build, and a shortcut pointing at it would
    have to be rebuilt along with it (design D9).
    """
    return (repo or paths.repo_root()) / ".venv" / "Scripts" / "pythonw.exe"


def icon_location(repo: Path | None = None) -> str:
    root = repo or paths.repo_root()
    for candidate in ICON_CANDIDATES:
        found = root / candidate
        if found.is_file():
            return str(found)
    return ""


def shortcut_path(desktop: Path | None = None) -> Path:
    return (desktop or desktop_folder()) / SHORTCUT_NAME


def build_spec(repo: Path | None = None) -> ShortcutSpec:
    root = repo or paths.repo_root()
    return ShortcutSpec(
        target=str(launcher(root)),
        arguments=LAUNCH_ARGUMENTS,
        workdir=str(root),
        description=SHORTCUT_DESCRIPTION,
        icon=icon_location(root),
    )


# --- COM ----------------------------------------------------------------------


def write_link(link: Path, spec: ShortcutSpec) -> str | None:
    """Creates or replaces a `.lnk`. Returns a cause or None.

    COM is initialised for this thread explicitly: the command line may already
    have used it for the device query, and the rule of the recording core -
    initialise per thread - holds here as well.
    """
    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        return f"Windows-Anbindung nicht verfügbar: {exc}"

    link.parent.mkdir(parents=True, exist_ok=True)

    def save() -> None:
        # In a function of its own so that both COM references are gone before
        # `CoUninitialize` runs. Released afterwards, Windows complains about a
        # released IUnknown on every single call.
        shell = win32com.client.Dispatch("WScript.Shell")
        entry = shell.CreateShortCut(str(link))
        entry.TargetPath = spec.target
        entry.Arguments = spec.arguments
        entry.WorkingDirectory = spec.workdir
        entry.Description = spec.description
        if spec.icon:
            entry.IconLocation = spec.icon
        entry.Save()

    pythoncom.CoInitialize()
    try:
        save()
    except Exception as exc:  # noqa: BLE001 - COM reports everything as its own error type
        logger.error("Verknuepfung '%s' nicht schreibbar", link, exc_info=True)
        return str(exc)
    finally:
        pythoncom.CoUninitialize()

    return None


def read_link(link: Path) -> dict[str, str] | None:
    """Reads target, arguments and working directory back, or None.

    `CreateShortCut` on an existing path only reads it; without `.Save()`
    nothing is written, so this route is safe for a read-only query too.
    """
    if not link.is_file():
        return None

    try:
        import pythoncom
        import win32com.client
    except ImportError:
        return None

    def load() -> dict[str, str]:
        # See `write_link`: both references have to be gone before
        # `CoUninitialize`.
        shell = win32com.client.Dispatch("WScript.Shell")
        entry = shell.CreateShortCut(str(link))
        return {
            "target": str(entry.TargetPath or ""),
            "arguments": str(entry.Arguments or ""),
            "workdir": str(entry.WorkingDirectory or ""),
        }

    pythoncom.CoInitialize()
    try:
        return load()
    except Exception:  # noqa: BLE001 - an unreadable link is a finding, not a crash
        logger.warning("Verknuepfung '%s' nicht lesbar", link, exc_info=True)
        return None
    finally:
        pythoncom.CoUninitialize()


# --- Decisions ----------------------------------------------------------------


def points_at_repo(contents: dict[str, str] | None, repo: Path) -> bool:
    """Whether a read-back link belongs to this installation."""
    if not contents:
        return False

    expected = os.path.normcase(str(repo))
    workdir = contents.get("workdir") or ""
    if workdir and os.path.normcase(workdir) == expected:
        return True

    target = contents.get("target") or ""
    return bool(target) and os.path.normcase(target).startswith(expected + os.sep)


def status(
    repo: Path | None = None,
    desktop: Path | None = None,
    reader: ShortcutReader | None = None,
) -> ShortcutStatus:
    """What is on the desktop right now. Reads, changes nothing.

    The reader is resolved here rather than in the signature: bound as a default
    it would freeze the function at import time, and a caller replacing the COM
    route would then be quietly ignored.
    """
    root = repo or paths.repo_root()
    read = reader or read_link
    link = shortcut_path(desktop)

    if not link.is_file():
        return ShortcutStatus(
            path=link,
            exists=False,
            notes=(f"Auf dem Desktop {link.parent} liegt keine Verknüpfung.",),
        )

    contents = read(link)
    if contents is None:
        return ShortcutStatus(
            path=link,
            exists=True,
            readable=False,
            notes=(f"Die Verknüpfung {link} ist vorhanden, lässt sich aber nicht lesen.",),
        )

    belongs = points_at_repo(contents, root)
    target = contents.get("target") or ""
    target_exists = bool(target) and Path(target).is_file()

    notes = [
        f"Verknüpfung: {link}",
        f"Startet: {target}",
        f"Argumente: {contents.get('arguments', '')}",
        f"Arbeitsordner: {contents.get('workdir', '')}",
    ]
    if not belongs:
        notes.append(f"Diese Verknüpfung gehört zu einer anderen Installation, nicht zu {root}.")
    elif not target_exists:
        notes.append("Das Ziel der Verknüpfung gibt es nicht mehr -- sie muss neu aufgebaut werden.")

    return ShortcutStatus(
        path=link,
        exists=True,
        readable=True,
        belongs_here=belongs,
        target_exists=target_exists,
        contents=contents,
        notes=tuple(notes),
    )


def create(
    repo: Path | None = None,
    desktop: Path | None = None,
    writer: ShortcutWriter | None = None,
) -> ShortcutResult:
    """Builds the shortcut. An existing one is replaced without failing."""
    root = repo or paths.repo_root()
    write = writer or write_link
    spec = build_spec(root)

    if not Path(spec.target).is_file():
        return ShortcutResult(
            ok=False,
            code=1,
            path=None,
            lines=(MISSING_ENVIRONMENT_NOTE, "Setup.cmd in diesem Ordner doppelklicken."),
        )

    link = shortcut_path(desktop)
    error = write(link, spec)
    if error is not None:
        return ShortcutResult(
            ok=False,
            code=1,
            path=link,
            lines=(f"Die Verknüpfung {link} ließ sich nicht anlegen: {error}",),
        )

    logger.info("Verknuepfung aufgebaut: %s", link)
    return ShortcutResult(
        ok=True,
        path=link,
        lines=(
            f"Verknüpfung angelegt: {link}",
            f"Name: {link.stem}",
            FIXED_PATH_NOTE,
        ),
    )


def remove(desktop: Path | None = None) -> ShortcutResult:
    """Deletes the shortcut and nothing else."""
    link = shortcut_path(desktop)

    if not link.is_file():
        return ShortcutResult(
            ok=True,
            path=link,
            lines=(f"Auf dem Desktop {link.parent} lag keine Verknüpfung.",),
        )

    try:
        link.unlink()
    except OSError as exc:
        logger.error("Verknuepfung '%s' nicht entfernbar: %s", link, exc)
        return ShortcutResult(
            ok=False,
            code=1,
            path=link,
            lines=(f"Die Verknüpfung {link} ließ sich nicht entfernen: {exc.strerror or exc}",),
        )

    logger.info("Verknuepfung entfernt: %s", link)
    return ShortcutResult(
        ok=True,
        path=link,
        lines=(f"Verknüpfung entfernt: {link}", RUNNING_UNTOUCHED_NOTE),
    )
