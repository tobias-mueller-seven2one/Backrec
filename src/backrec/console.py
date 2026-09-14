"""The one place every sentence a colleague reads is written to.

The setup runs in a console because it starts uv and winget and has to collect
what they say. It must not read like one: the people this tool is for are put
off by terminals, and a wall of installer output is exactly the thing that makes
them stop and ask someone.

So every line of the setup, the update and the diagnosis report goes through
this module, and the rules of the suite convention are code here rather than
good intentions (design D19): numbered steps, one symbol and one sentence per
result, one question at a time with a default the Enter key takes, no
implementation vocabulary, no stack trace, and the log path named exactly once
at the end.

`FORBIDDEN_TERMS` is enforced by a test that walks the package's source and
checks every string handed to this class. It is meant to be annoying: it is the
only place in day-to-day development where the audience shows up at all.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Sequence, TextIO

# Implementation vocabulary that must never reach a colleague. Matched on word
# boundaries so that German words which merely contain one of them ("Blockade",
# "Verzeichnis") do not trip the check.
#
# Not on the list, with reason: "log"/"logs", because the wording section 6 of
# the convention prescribes for the log folder uses it, and "Archiv", because the
# guide names the release bundle that way - a word a colleague knows.
FORBIDDEN_TERMS: tuple[str, ...] = (
    "venv",
    "lock",
    "lockfile",
    "stdout",
    "stderr",
    "exit code",
    "exit-code",
    "tray",
    "sentinel",
    "pid",
    "traceback",
    "stacktrace",
    "repository",
    "sync",
    "commit",
    "hash",
    "manifest",
    "json",
    "toml",
    "path",
    "timeout",
    "prozess",
    "zip",
    "cache",
    "script",
    "skript",
    "thread",
    "merge",
    "buffer",
    "stream",
)

_TERM_PATTERNS = tuple(
    (term, re.compile(rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])", re.IGNORECASE))
    for term in FORBIDDEN_TERMS
)

_ANSI = {
    "ok": "\x1b[32m",
    "warn": "\x1b[33m",
    "fail": "\x1b[31m",
    "reset": "\x1b[0m",
}


class Status(Enum):
    """The result of a step; exactly one symbol in the output."""

    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


SYMBOLS: dict[Status, str] = {
    Status.OK: "[OK]",
    Status.WARN: "[!]",
    Status.FAIL: "[X]",
}


@dataclass(frozen=True)
class StepRecord:
    """What the closing summary says about this step."""

    number: int
    name: str
    status: Status
    message: str


def contains_forbidden(text: str) -> tuple[str, ...]:
    """The implementation terms occurring in `text` - empty when it is clean."""
    return tuple(term for term, pattern in _TERM_PATTERNS if pattern.search(text))


def use_utf8(stream: TextIO | None = None) -> None:
    """Switches the output channel to UTF-8 with replacement characters.

    Both `.cmd` files set `chcp 65001` and `PYTHONUTF8=1`, and that is enough -
    but only for a run that comes through them. A call from another console
    inherits the system code page, and there every umlaut is an encoding error.
    This costs one line and takes the output's appearance off the calling route.
    """
    target = stream if stream is not None else sys.stdout
    if target is None or not hasattr(target, "reconfigure"):
        return
    try:
        target.reconfigure(encoding="utf-8", errors="replace")
    except (OSError, ValueError, AttributeError):
        pass


def supports_color(stream: TextIO | None) -> bool:
    """Whether ANSI colour can be used on this stream.

    Windows needs `ENABLE_VIRTUAL_TERMINAL_PROCESSING` switched on before escape
    sequences mean anything; if it cannot be switched on the escape codes would
    be printed literally and every line would look broken. `NO_COLOR` is honoured
    because a redirected setup log should stay readable.
    """
    if stream is None or not hasattr(stream, "isatty") or not stream.isatty():
        return False
    if os.environ.get("NO_COLOR"):
        return False
    if os.name != "nt":
        return True

    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except (AttributeError, OSError, ValueError):
        return False


class Assistant:
    """The output of the setup, the update and the report.

    `interactive=False` answers every question with its default without asking
    it - that is the unattended run, and it writes exactly the same lines as the
    guided one so that a log stays comparable.
    """

    def __init__(
        self,
        total_steps: int = 0,
        stream: TextIO | None = None,
        *,
        interactive: bool = True,
        color: bool | None = None,
        input_fn: Callable[[str], str] | None = None,
    ) -> None:
        self.total_steps = total_steps
        self.stream: TextIO = stream if stream is not None else (sys.stdout or sys.stderr)
        self.interactive = interactive
        self.color = supports_color(self.stream) if color is None else color
        self.input_fn = input_fn or input
        self.steps: list[StepRecord] = []
        self._current: tuple[int, str] | None = None

    # --- Output -------------------------------------------------------------

    def write(self, text: str = "") -> None:
        """Writes one line. A channel that cannot be written ends nothing.

        An encoding error is explicitly not "cannot be written": it hits exactly
        one line, and that line would otherwise vanish without trace - a
        `UnicodeEncodeError` is a `ValueError`, and a line with an umlaut would
        simply not have been there. Hence the second attempt with replacement
        characters: a line with "ue" instead of "ü" is readable, a missing line
        is not.
        """
        try:
            self.stream.write(f"{text}\n")
            self.stream.flush()
            return
        except UnicodeEncodeError:
            pass
        except (OSError, ValueError, AttributeError):
            return

        try:
            self.stream.write(text.encode("ascii", "replace").decode("ascii") + "\n")
            self.stream.flush()
        except (OSError, ValueError, AttributeError):
            pass

    def _symbol(self, status: Status) -> str:
        plain = SYMBOLS[status]
        if not self.color:
            return plain
        return f"{_ANSI[status.value]}{plain}{_ANSI['reset']}"

    def header(self, tool_name: str, version: str, subtitle: str = "") -> None:
        line = f"{tool_name} {version}"
        self.write(line)
        self.write("=" * len(line))
        if subtitle:
            self.write(subtitle)
        self.write()

    def step(self, number: int, name: str) -> None:
        self._current = (number, name)
        self.write(f"Schritt {number} von {self.total_steps}: {name}")

    def _record(self, status: Status, message: str) -> None:
        number, name = self._current or (len(self.steps) + 1, "")
        self.steps.append(StepRecord(number=number, name=name, status=status, message=message))

    def ok(self, message: str) -> None:
        self._record(Status.OK, message)
        self.write(f"    {self._symbol(Status.OK)} {message}")

    def warn(self, message: str) -> None:
        self._record(Status.WARN, message)
        self.write(f"    {self._symbol(Status.WARN)} {message}")

    def fail(self, happened: str, todo: str) -> None:
        """Every error in two statements: what happened, what to do."""
        self._record(Status.FAIL, happened)
        self.write(f"    {self._symbol(Status.FAIL)} Was ist passiert: {happened}")
        self.write(f"        Was tun: {todo}")

    def note(self, message: str) -> None:
        """A line without a result, e.g. a hint during a step."""
        self.write(f"    {message}")

    def blank(self) -> None:
        self.write()

    # --- Questions ----------------------------------------------------------

    def ask(self, question: str, default: str) -> str:
        """Exactly one question with its default in brackets; Enter takes it."""
        if not self.interactive:
            self.write(f"{question} [{default}]  -> {default}")
            return default

        try:
            answer = self.input_fn(f"{question} [{default}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            self.write()
            return default
        return answer or default

    def ask_yes_no(self, question: str, default: bool = True) -> bool:
        marker = "J/n" if default else "j/N"
        answer = self.ask(question, marker)
        if answer == marker:
            return default
        return answer.strip().lower() in ("j", "ja", "y", "yes")

    # --- Closing ------------------------------------------------------------

    def summary(self, log_path: Path | None = None, closing: str = "") -> None:
        """Every step with its symbol, then the log path exactly once."""
        self.blank()
        self.write("Zusammenfassung")
        self.write("---------------")
        for record in self.steps:
            name = record.name or record.message
            self.write(f"  {self._symbol(record.status)} {name}: {record.message}")
        if closing:
            self.blank()
            self.write(closing)
        if log_path is not None:
            self.blank()
            self.write(f"Aufzeichnung dieses Laufs: {log_path}")

    def has_failure(self) -> bool:
        return any(record.status is Status.FAIL for record in self.steps)


def render_lines(records: Sequence[StepRecord]) -> list[str]:
    """The summary as plain lines, without colour - for the report."""
    return [f"{SYMBOLS[record.status]} {record.name}: {record.message}" for record in records]
