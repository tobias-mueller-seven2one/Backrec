"""Who is running, recorded so that a second start can tell and a stop can find it.

A bare process id is not an identity. After a crash the number may belong to
something else entirely, and terminating it would be someone else's very bad
day; `os.kill(pid, 0)` is a liveness probe everywhere except Windows, where it
terminates. The creation time is what makes the record checkable, and psutil is
in the dependencies for exactly that one value (design D6).

The repository path is recorded alongside, because two unpacked copies on one
machine are two installations: neither may claim the other's record, and
neither may be blocked by it. A record failing any of those checks is taken
over - a lock file with an exclusive handle would be more direct, but on
Windows a crashed process leaves a state only a reboot clears.

The stop request is a file rather than a signal (design D10): Windows console
events never reach a `pythonw` process, and a hard termination in the middle of
a recording runs past every `finally` there is.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil

from . import paths
from .logging_setup import get_logger

logger = get_logger(__name__)

# psutil reports the creation time with sub-second resolution and it round-trips
# through JSON exactly. The tolerance guards against clock adjustments, not
# against precision.
CREATE_TIME_TOLERANCE_SECONDS = 1.0

WINDOW_TITLE = "Backrec"


@dataclass(frozen=True)
class InstanceRecord:
    """The content of `state\\backrec.pid`."""

    pid: int
    create_time: float
    started: str
    repo: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "pid": self.pid,
            "create_time": self.create_time,
            "started": self.started,
            "repo": self.repo,
        }


def write_record(path: Path | None = None, repo: Path | None = None) -> InstanceRecord:
    """Records the calling process. Creates the state folder."""
    target = path or paths.pid_record_path()
    process = psutil.Process()

    record = InstanceRecord(
        pid=process.pid,
        create_time=process.create_time(),
        started=datetime.now().isoformat(timespec="seconds"),
        repo=str(repo or paths.repo_root()),
    )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record.as_dict(), indent=2), encoding="utf-8")
    logger.info("Zustandsdatensatz geschrieben: %s (Anwendung %d)", target, record.pid)
    return record


def read_record(path: Path | None = None) -> InstanceRecord | None:
    """The record, or None if none is readable."""
    target = path or paths.pid_record_path()
    if not target.is_file():
        return None

    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        logger.warning("Zustandsdatensatz '%s' nicht lesbar, gilt als verwaist: %s", target, exc)
        return None

    if not isinstance(raw, dict) or "pid" not in raw:
        logger.warning("Zustandsdatensatz '%s' nennt keine Anwendung, gilt als verwaist", target)
        return None

    try:
        pid = int(raw["pid"])
    except (TypeError, ValueError):
        logger.warning("Zustandsdatensatz '%s' nennt keine gueltige Anwendung", target)
        return None

    return InstanceRecord(
        pid=pid,
        create_time=float(raw.get("create_time") or 0.0),
        started=str(raw.get("started") or ""),
        repo=str(raw.get("repo") or ""),
    )


def clear_record(path: Path | None = None) -> None:
    """Removes the record. Harmless without an existing file."""
    (path or paths.pid_record_path()).unlink(missing_ok=True)


def belongs_to_repo(record: InstanceRecord, repo: Path | None = None) -> bool:
    """Whether the record belongs to this installation."""
    expected = str(repo or paths.repo_root())
    return os.path.normcase(record.repo) == os.path.normcase(expected)


def live_process(
    record: InstanceRecord | None,
    repo: Path | None = None,
) -> psutil.Process | None:
    """The running process of the record, or None if it is orphaned.

    All three conditions count: the process lives, its creation time matches
    (otherwise the id has been reused) and it belongs to this installation.
    """
    if record is None:
        return None

    if not belongs_to_repo(record, repo):
        logger.info("Zustandsdatensatz gehoert zu einer anderen Installation: %s", record.repo)
        return None

    try:
        process = psutil.Process(record.pid)
    except (psutil.NoSuchProcess, ValueError):
        return None

    if not record.create_time:
        # Without a creation time the number is not an identity: after a crash
        # it can belong to anything, and that anything may neither be
        # terminated nor reported as a running instance.
        logger.warning(
            "Zustandsdatensatz nennt keine Erzeugungszeit -- er gilt als verwaist (Anwendung %d)",
            record.pid,
        )
        return None

    try:
        actual = process.create_time()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None

    if abs(actual - record.create_time) > CREATE_TIME_TOLERANCE_SECONDS:
        logger.warning(
            "Anwendung %d existiert, wurde aber zu einer anderen Zeit gestartet -- "
            "der Zustandsdatensatz ist verwaist",
            record.pid,
        )
        return None

    return process


def running_instance(
    path: Path | None = None,
    repo: Path | None = None,
) -> psutil.Process | None:
    """The running instance of this installation, or None."""
    return live_process(read_record(path), repo)


def foreign_repo(record: InstanceRecord | None, repo: Path | None = None) -> str | None:
    """The folder of another installation that is running right now, or None.

    `live_process` alone is not enough: it reports a foreign record as "not
    running", and the next start would overwrite it without a word.
    """
    root = repo or paths.repo_root()
    if record is None or belongs_to_repo(record, root):
        return None
    if live_process(record, Path(record.repo)) is None:
        return None
    return record.repo or None


# --- Stop request -------------------------------------------------------------


def request_stop(path: Path | None = None) -> Path:
    """Asks the running instance to finish at its next turn of the loop."""
    target = path or paths.stop_request_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(datetime.now().isoformat(timespec="seconds"), encoding="utf-8")
    return target


def stop_requested(path: Path | None = None) -> bool:
    return (path or paths.stop_request_path()).is_file()


def clear_stop_request(path: Path | None = None) -> None:
    """Left behind, the file would end the next start immediately (design D10)."""
    (path or paths.stop_request_path()).unlink(missing_ok=True)


# --- Whether a recording is running -------------------------------------------


def mark_recording(path: Path | None = None) -> Path:
    """Notes that a recording has begun, so `status` can see it from outside."""
    target = path or paths.recording_marker_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(datetime.now().isoformat(timespec="seconds"), encoding="utf-8")
    return target


def clear_recording(path: Path | None = None) -> None:
    (path or paths.recording_marker_path()).unlink(missing_ok=True)


def is_recording(path: Path | None = None) -> bool:
    return (path or paths.recording_marker_path()).is_file()


# --- Whether the closing sequence is still working ----------------------------

FINISHING_BEAT_SECONDS = 1.0


def mark_finishing(beat: int, path: Path | None = None) -> Path:
    """Writes one beat of the closing sequence's sign of life.

    The content is a counter, not a timestamp (design D2): the reader only ever
    asks whether the value differs from the one it saw last, and that question
    needs no clock at all - neither a synchronised one nor a file system whose
    modification times are precise enough to tell two beats apart.
    """
    target = path or paths.finishing_marker_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(str(int(beat)), encoding="utf-8")
    return target


def finishing_beat(path: Path | None = None) -> int | None:
    """The beat currently written, or None if there is none to read.

    A missing, empty, unreadable or nonsensical file all mean the same thing to
    the caller - no sign of life - and none of them may raise: the stop that
    reads this must never fail because of the file it is only consulting.
    """
    target = path or paths.finishing_marker_path()
    try:
        raw = target.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None

    try:
        return int(raw)
    except ValueError:
        return None


def is_finishing(path: Path | None = None) -> bool:
    return finishing_beat(path) is not None


def clear_finishing(path: Path | None = None) -> None:
    (path or paths.finishing_marker_path()).unlink(missing_ok=True)


class FinishingBeacon:
    """Beats for as long as the closing sequence works, in a thread of its own.

    A thread is necessary, not convenient: mixing is a single blocking
    `subprocess.run` of up to two minutes, and the closing sequence has no point
    inside it at which it could write anything (design D3). Both that call and
    the verified copy release the GIL for the duration of their I/O, so this
    thread keeps running while they do.

    Every write failure is logged and swallowed. The beacon describes the work;
    it must never be the reason the work stops.
    """

    def __init__(
        self,
        *,
        interval_seconds: float = FINISHING_BEAT_SECONDS,
        path: Path | None = None,
    ) -> None:
        self._interval = interval_seconds
        self._path = path
        self._done = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return

        self._done.clear()
        self._write(0)
        self._thread = threading.Thread(target=self._run, name="finishing-beacon", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._done.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=max(self._interval * 2, 1.0))
        clear_finishing(self._path)

    def __enter__(self) -> "FinishingBeacon":
        self.start()
        return self

    def __exit__(self, *_exception: object) -> None:
        self.stop()

    def _run(self) -> None:
        beat = 0
        while not self._done.wait(self._interval):
            beat += 1
            self._write(beat)

    def _write(self, beat: int) -> None:
        try:
            mark_finishing(beat, self._path)
        except OSError as exc:
            logger.warning("Lebenszeichen der Nachbereitung nicht schreibbar: %s", exc)


def terminate_tree(process: psutil.Process, grace_seconds: float = 10.0) -> list[int]:
    """Ends a process and everything it started.

    Children are collected before the first signal: once the parent is gone
    they are re-parented and the connection is lost. Leaves first, so that no
    parent tries to clean up while its children are still being ended.
    """
    try:
        family = process.children(recursive=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        family = []

    ordered = list(reversed(family)) + [process]
    stopped: list[int] = []

    for member in ordered:
        try:
            member.terminate()
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied as exc:
            logger.warning("Anwendung %d laesst sich nicht beenden: %s", member.pid, exc)

    gone, alive = psutil.wait_procs(ordered, timeout=grace_seconds)
    stopped.extend(item.pid for item in gone)

    for survivor in alive:
        logger.warning("Anwendung %d reagiert nicht -- wird hart beendet", survivor.pid)
        try:
            survivor.kill()
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied as exc:
            logger.error("Anwendung %d laesst sich nicht hart beenden: %s", survivor.pid, exc)

    killed, _ = psutil.wait_procs(alive, timeout=grace_seconds)
    stopped.extend(item.pid for item in killed)
    return stopped


# --- Bringing the existing window to the front --------------------------------


def window_handles_of(pid: int) -> list[int]:
    """The top-level window handles that belong to `pid`.

    Searched by process id rather than by window title: a title is something
    anyone can carry, and the record already knows exactly which process is
    meant. Returns an empty list when the Windows API is unavailable - on a
    machine without pywin32 a second start still reports and still exits 3.
    """
    try:
        import win32gui
        import win32process
    except ImportError:
        logger.debug("Fenstersuche nicht verfuegbar (pywin32 fehlt)")
        return []

    found: list[int] = []

    def _collect(handle: int, _argument: object) -> bool:
        try:
            if not win32gui.IsWindowVisible(handle):
                return True
            _thread_id, owner = win32process.GetWindowThreadProcessId(handle)
        except Exception:  # noqa: BLE001 - a window may vanish mid-enumeration
            return True
        if owner == pid:
            found.append(handle)
        return True

    try:
        win32gui.EnumWindows(_collect, None)
    except Exception:  # noqa: BLE001 - EnumWindows reports a stopped callback as an error
        logger.debug("Fenstersuche abgebrochen", exc_info=True)

    return found


def raise_window(pid: int) -> bool:
    """Brings the window of `pid` to the front. Says whether that worked.

    Three steps, and success is measured on the first two. `SetForegroundWindow`
    is refused whenever the calling process is not the foreground one - which is
    the normal case here, because the caller is a shortcut that has just been
    double-clicked (design D6). Measured on that call alone the answer would
    almost always be "no", and a dialog would appear in front of a window that
    is demonstrably visible: the window is always-on-top, so restoring it and
    bringing it to the top of its band is what the user actually sees happen.

    Only when not even that works - no window found, or every call refused - is
    the answer no, and the second start says so in a message instead.
    """
    handles = window_handles_of(pid)
    if not handles:
        return False

    try:
        import win32con
        import win32gui
    except ImportError:
        return False

    for handle in handles:
        try:
            if win32gui.IsIconic(handle):
                win32gui.ShowWindow(handle, win32con.SW_RESTORE)
            win32gui.BringWindowToTop(handle)
        except Exception as exc:  # noqa: BLE001 - a window may vanish mid-call
            logger.info("Fenster %d liess sich nicht hervorholen: %s", handle, exc)
            continue

        try:
            win32gui.SetForegroundWindow(handle)
        except Exception as exc:  # noqa: BLE001 - see docstring
            logger.info(
                "Windows hat den Wechsel in den Vordergrund abgelehnt (%s) -- "
                "das Fenster steht trotzdem oben",
                exc,
            )

        logger.info("Bestehendes Fenster der Anwendung %d nach vorn geholt", pid)
        return True

    return False
