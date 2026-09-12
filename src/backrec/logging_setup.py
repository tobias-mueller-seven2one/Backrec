"""The log file, set up before anything else reads a configuration.

Backrec runs windowless: under `pythonw` `sys.stderr` is None, every `print`
is a no-op, and the roughly sixty log calls of the recording core - several of
them with a full traceback - spoke into nothing. Routing them into a rotating
file is the whole point of this module, and not one of those calls had to
change for it.

`bootstrap()` sets the file up **before** the configuration is read, so that a
broken configuration - the most common start failure there is - lands in a file
as well. That is possible because the log location comes from `paths.py` and no
longer from the configuration.

No second `error.log`, unlike the unattended tools of the suite (design D4):
they need one because nobody watches them. Backrec has a window that shows its
errors; a second file would be one more place nobody reads.
"""

from __future__ import annotations

import logging
import sys
import tempfile
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import paths

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
# With a date, unlike the retired `datefmt="%H:%M:%S"`: in a file that survives
# midnight a bare clock time is unusable.
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
MAX_LOG_BYTES = 2 * 1024 * 1024
LOG_BACKUP_COUNT = 3

ROOT_LOGGER_NAME = "backrec"

_is_configured = False


def get_logger(name: str) -> logging.Logger:
    """The logger of a module, e.g. `get_logger(__name__)`."""
    short = name.removeprefix(f"{ROOT_LOGGER_NAME}.")
    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{short}")


def _report_unwritable_log(log_path: Path, exc: OSError) -> None:
    """Says that the log cannot be written - even without a console.

    The one failure no log can catch is that there is no log. Under `pythonw`
    `sys.stderr` is None and a message there disappears - of all messages the
    one explaining why nothing is traceable afterwards. Hence three ways in
    increasing desperation.
    """
    text = f"Die Aufzeichnung '{log_path}' lässt sich nicht schreiben: {exc}"

    if sys.stderr is not None:
        print(f"WARNUNG: {text}", file=sys.stderr)
        return

    try:
        fallback = Path(tempfile.gettempdir()) / "backrec-notzeile.txt"
        with fallback.open("a", encoding="utf-8") as handle:
            handle.write(f"{datetime.now().isoformat(timespec='seconds')} {text}\n")
        return
    except OSError:
        pass

    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, text, paths.TOOL_NAME, 0x30)
    except (AttributeError, OSError):
        pass


def _rotating_handler(log_path: Path, formatter: logging.Formatter) -> logging.Handler | None:
    """A rotating file handler, or None if the file cannot be created."""
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_path, maxBytes=MAX_LOG_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
        )
    except OSError as exc:
        _report_unwritable_log(log_path, exc)
        return None

    handler.setFormatter(formatter)
    return handler


def is_terminal(stream: object) -> bool:
    """Whether `stream` is a real console.

    The convention asks for the console handler only with a terminal attached.
    A redirected channel - a helper's pipe, a collected subprocess output -
    would otherwise get every technical line twice.
    """
    try:
        return bool(stream.isatty())  # type: ignore[attr-defined]
    except (AttributeError, OSError, ValueError):
        return False


def configure_logging(
    log_path: Path | None,
    level: str = "INFO",
    *,
    force: bool = False,
    console: bool = True,
) -> None:
    """Configures the root logger (file plus optional console).

    Idempotent: a second call without `force=True` does nothing, so entry point
    and window can both ask for it safely. A log file that cannot be created is
    not a reason to refuse a recording, so the run continues without it.
    """
    global _is_configured
    if _is_configured and not force:
        return

    logger = logging.getLogger(ROOT_LOGGER_NAME)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT)

    if log_path is not None:
        file_handler = _rotating_handler(log_path, formatter)
        if file_handler is not None:
            logger.addHandler(file_handler)

    stream = sys.stderr if console else None
    if stream is not None and is_terminal(stream):
        stream_handler = logging.StreamHandler(stream)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    if not logger.handlers:
        logger.addHandler(logging.NullHandler())

    logging.captureWarnings(True)
    logging.getLogger("py.warnings").setLevel(logging.WARNING)

    _is_configured = True


def bootstrap(level: str = "INFO") -> Path:
    """Sets the file log up before the configuration is read.

    Returns the path of the log file so that an aborted start can name it in
    its visible message.
    """
    target = paths.log_path()
    configure_logging(target, level)
    return target


def close_files() -> None:
    """Releases the open log files.

    Needed by the uninstall: Windows deletes no folder that still holds an open
    file, and `shutil.rmtree(..., ignore_errors=True)` would swallow that and
    report success.
    """
    global _is_configured

    logger = logging.getLogger(ROOT_LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    _is_configured = False


def reset_for_tests() -> None:
    """Forgets the configured handlers so a test can configure anew."""
    close_files()
