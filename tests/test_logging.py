"""The log file, its rotation, and the two failure modes it has to survive."""

from __future__ import annotations

import io
import logging
from pathlib import Path

from backrec import logging_setup, merge, paths


def test_the_file_is_written_with_a_full_time_stamp(tmp_path):
    target = tmp_path / "logs" / "backrec.log"
    logging_setup.configure_logging(target, force=True)

    logging_setup.get_logger("probe").info("eine Zeile")

    text = target.read_text(encoding="utf-8")
    assert "eine Zeile" in text
    assert text[:4].isdigit(), text


def test_the_bootstrap_uses_the_place_from_paths(tmp_path, monkeypatch):
    monkeypatch.setenv(paths.ENV_SUITE_HOME, str(tmp_path / "MemoSuite"))

    written = logging_setup.bootstrap()

    assert written == paths.log_path()
    assert written.is_file()


def test_it_rotates_instead_of_growing_without_end(tmp_path, monkeypatch):
    target = tmp_path / "logs" / "backrec.log"
    monkeypatch.setattr(logging_setup, "MAX_LOG_BYTES", 2048)
    logging_setup.configure_logging(target, force=True)

    logger = logging_setup.get_logger("probe")
    for index in range(200):
        logger.info("Zeile %d mit genug Text, damit die Datei die Grenze erreicht", index)

    assert target.is_file()
    assert (tmp_path / "logs" / "backrec.log.1").is_file()
    assert not (tmp_path / "logs" / "backrec.log.4").is_file()


def test_a_log_that_cannot_be_written_does_not_reach_the_caller(tmp_path, monkeypatch):
    """A log directory that refuses writes is no reason to prevent a recording."""
    blocked = tmp_path / "gesperrt" / "backrec.log"
    monkeypatch.setattr(
        logging_setup,
        "RotatingFileHandler",
        _raising_handler,
    )
    reported: list[str] = []
    monkeypatch.setattr(
        logging_setup, "_report_unwritable_log", lambda path, exc: reported.append(str(path))
    )

    logging_setup.configure_logging(blocked, force=True)
    logging_setup.get_logger("probe").info("verschwindet, aber ohne Ausnahme")

    assert reported == [str(blocked)]


def test_without_a_terminal_no_console_handler_is_attached(tmp_path, monkeypatch):
    """Under pythonw there is no console; a handler there would fail on every line."""
    monkeypatch.setattr("sys.stderr", io.StringIO())

    logging_setup.configure_logging(tmp_path / "backrec.log", force=True)

    handlers = logging.getLogger(logging_setup.ROOT_LOGGER_NAME).handlers
    assert not any(type(handler) is logging.StreamHandler for handler in handlers)
    assert logging_setup.is_terminal(io.StringIO()) is False
    assert logging_setup.is_terminal(None) is False


def test_a_missing_stderr_is_survivable(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.stderr", None)

    logging_setup.configure_logging(tmp_path / "backrec.log", force=True)
    logging_setup.get_logger("probe").warning("ohne Konsole")

    assert (tmp_path / "backrec.log").is_file()


def test_the_notice_of_last_resort_lands_in_a_file(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.stderr", None)
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))

    logging_setup._report_unwritable_log(tmp_path / "logs" / "backrec.log", OSError("kein Zugriff"))

    assert (tmp_path / "backrec-notzeile.txt").read_text(encoding="utf-8").strip()


def test_the_moved_log_calls_keep_their_traceback(tmp_path, monkeypatch):
    """Task 3.3: the roughly sixty existing calls now land in the file.

    Checked against the merge, because it is the one place that logs with
    `exc_info=True` and can be triggered without a real recording: ffmpeg under
    a name that does not exist behaves exactly like a missing ffmpeg.
    """
    target = tmp_path / "logs" / "backrec.log"
    logging_setup.configure_logging(target, force=True)
    monkeypatch.setattr(merge, "FFMPEG_EXE", "ffmpeg-gibt-es-nicht")

    ok, reason = merge.merge_audio_files(
        Path(tmp_path / "mic.wav"), Path(tmp_path / "system.wav"), Path(tmp_path / "out.wav")
    )

    text = target.read_text(encoding="utf-8")
    assert not ok
    assert reason == "ffmpeg nicht gefunden"
    assert "[MERGE] ffmpeg nicht gefunden" in text
    assert "Traceback (most recent call last)" in text


class _raising_handler:  # noqa: N801 - stands in for RotatingFileHandler
    def __init__(self, *args, **kwargs):
        raise OSError("kein Zugriff")
