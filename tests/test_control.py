"""The control surface: one result per command, and no output of its own."""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import is_dataclass
from pathlib import Path

from backrec import control, instance, merge, paths, shortcut as shortcut_module
from backrec.wizard import write_config


def _result(returncode: int = 0, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def _installed_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "Backrec"
    (repo / ".venv" / "Scripts").mkdir(parents=True)
    (repo / ".venv" / "pyvenv.cfg").write_text("version = 3.11.9\n", encoding="utf-8")
    (repo / ".venv" / "Scripts" / "pythonw.exe").write_bytes(b"MZ")
    (repo / paths.VERSION_FILE_NAME).write_text("2026.09.1\n", encoding="utf-8")
    return repo


# --- Shape --------------------------------------------------------------------


def test_every_command_hands_back_a_dataclass(tmp_path: Path) -> None:
    repo = _installed_repo(tmp_path)

    assert is_dataclass(control.status(repo))
    assert is_dataclass(control.stop(repo))
    assert is_dataclass(control.start(repo))
    assert is_dataclass(control.build_release(repo, tmp_path / "out"))
    assert is_dataclass(control.run_doctor(repo=repo))


def test_no_command_writes_to_the_console(tmp_path: Path, capsys) -> None:
    """Decisions here, presentation elsewhere (design D9)."""
    repo = _installed_repo(tmp_path)

    control.status(repo)
    control.stop(repo)
    control.about_lines(repo)

    captured = capsys.readouterr()
    assert captured.out == ""


# --- Plain causes -------------------------------------------------------------


def test_a_missing_command_is_named_as_such() -> None:
    reason = control.short_reason(_result(1, stderr="'winget' is not recognized"))

    assert "Kommando" in reason


def test_a_network_problem_is_named_as_such() -> None:
    reason = control.short_reason(_result(1, stderr="unable to connect to host"))

    assert "Internet" in reason


def test_a_refusal_by_windows_is_named_as_such() -> None:
    reason = control.short_reason(_result(1, stderr="Access is denied"))

    assert "Windows" in reason


def test_an_unknown_failure_points_at_the_log() -> None:
    reason = control.short_reason(_result(1, stderr="etwas ganz anderes"))

    assert "Aufzeichnung" in reason


# --- Start --------------------------------------------------------------------


def test_start_without_an_environment_names_the_setup(tmp_path: Path) -> None:
    repo = tmp_path / "Backrec"
    repo.mkdir()

    result = control.start(repo)

    assert not result.started
    assert result.problem is not None
    assert "Setup.cmd" in result.problem.next_step


def test_start_without_settings_never_launches_anything(tmp_path: Path, monkeypatch) -> None:
    repo = _installed_repo(tmp_path)
    launched: list[list[str]] = []
    monkeypatch.setattr(
        control.subprocess, "Popen", lambda command, **_kwargs: launched.append(command)
    )

    result = control.start(repo)

    assert not result.started
    assert launched == []


def test_start_uses_the_interpreter_of_the_environment_by_absolute_path(
    tmp_path: Path, repo: Path, config_values: dict[str, str], monkeypatch
) -> None:
    installed = _installed_repo(tmp_path)
    write_config(paths.config_path(), config_values, repo=repo)
    launched: list[list[str]] = []

    class FakePopen:
        def __init__(self, command, **_kwargs) -> None:
            launched.append(command)

    monkeypatch.setattr(control.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(control, "START_READY_TIMEOUT_SECONDS", 0.0)
    monkeypatch.setattr(control.preflight, "run", lambda *_a, **_k: control.preflight.PreflightResult(ok=True))

    control.start(installed)

    assert launched
    assert launched[0][0] == str(installed / ".venv" / "Scripts" / "pythonw.exe")
    assert launched[0][1:] == ["-m", "backrec"]


def test_starting_opens_the_window_and_not_a_process_without_one(tmp_path: Path) -> None:
    """Step 7, Start.cmd and the icon take one and the same route (H4).

    Backrec has no tray icon and therefore no arrow of the hidden icons to point
    at: here the window itself is what the colleague sees after "Jetzt starten?",
    so the start has to be the one the icon performs, module and all.
    """
    installed = _installed_repo(tmp_path)
    spec = shortcut_module.build_spec(installed)

    command = control.start_command(installed)

    assert command == [spec.target, *spec.arguments.split()]
    assert command[1:] == ["-m", "backrec"], "das Modul, das das Fenster öffnet"


def test_the_closing_line_points_at_the_desktop_and_the_window(tmp_path: Path) -> None:
    """No tray, no arrow: the sentence about the hidden icons would mislead."""
    closing = control._closing_note(True)

    assert "Symbol liegt auf dem Desktop" in closing
    assert "Pfeil" not in closing
    assert "Uhr" not in closing


def test_a_second_start_reports_the_running_instance(tmp_path: Path, monkeypatch) -> None:
    installed = _installed_repo(tmp_path)
    record = instance.write_record(repo=installed)

    result = control.start(installed)

    assert result.already_running
    assert result.pid == record.pid
    assert not result.started


# --- Stop ---------------------------------------------------------------------


def test_stop_without_a_running_instance_ends_without_error(tmp_path: Path) -> None:
    repo = _installed_repo(tmp_path)

    result = control.stop(repo)

    assert result.stopped
    assert not result.was_running
    assert "nichts" in result.message


def test_stop_clears_a_left_over_request(tmp_path: Path) -> None:
    repo = _installed_repo(tmp_path)
    instance.request_stop()

    control.stop(repo)

    assert not instance.stop_requested()


# --- The deadline that follows the closing sequence ---------------------------


class Clock:
    """A stand-in for `time` inside `control` - the deadline is under test.

    Every `sleep` moves the clock by what it was asked to wait for, so a
    simulated five minutes cost no real time at all.
    """

    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class FakeProcess:
    def __init__(self, clock: Clock, ends_at: float | None) -> None:
        self.pid = 4242
        self._clock = clock
        self.ends_at = ends_at

    def is_running(self) -> bool:
        return self.ends_at is None or self._clock.now < self.ends_at


def _stopping(
    monkeypatch,
    *,
    ends_at: float | None = None,
    beats_until: float | None = None,
) -> tuple[Clock, FakeProcess, list[object]]:
    """A stop against a stand-in process, on a clock nobody has to wait for.

    `beats_until` is how long the application keeps reporting work; the beat
    changes once per simulated second, which is what `FINISHING_BEAT_SECONDS`
    asks of it.
    """
    clock = Clock()
    process = FakeProcess(clock, ends_at)
    terminated: list[object] = []

    monkeypatch.setattr(control, "time", clock)
    monkeypatch.setattr(control.instance, "running_instance", lambda **_kwargs: process)
    monkeypatch.setattr(control.instance, "request_stop", lambda: None)
    monkeypatch.setattr(control.instance, "clear_stop_request", lambda: None)
    monkeypatch.setattr(control.instance, "clear_record", lambda: None)
    monkeypatch.setattr(control.instance, "clear_recording", lambda: None)
    monkeypatch.setattr(control.instance, "clear_finishing", lambda: None)

    def beat() -> int | None:
        if beats_until is None or clock.now > beats_until:
            return None
        return int(clock.now / instance.FINISHING_BEAT_SECONDS)

    monkeypatch.setattr(control.instance, "finishing_beat", beat)

    def terminate(target, **_kwargs) -> list[int]:
        terminated.append(target)
        target.ends_at = clock.now
        return [target.pid]

    monkeypatch.setattr(control.instance, "terminate_tree", terminate)
    return clock, process, terminated


def test_a_closing_sequence_longer_than_the_base_deadline_is_not_cut_off(
    tmp_path: Path, monkeypatch
) -> None:
    """The whole point (design D1).

    Two minutes of mixing and copying used to run into a thirty-second deadline.
    As long as the application keeps reporting work, the wait goes on.
    """
    repo = _installed_repo(tmp_path)
    clock, _process, terminated = _stopping(monkeypatch, ends_at=100.0, beats_until=99.0)

    result = control.stop(repo)

    assert terminated == [], "kein hartes Beenden"
    assert not result.forced
    assert result.stopped
    assert clock.now >= 100.0, "es wurde tatsaechlich ueber die Grundfrist hinaus gewartet"


def test_a_stop_without_a_closing_sequence_waits_no_longer_than_before(
    tmp_path: Path, monkeypatch
) -> None:
    """Without a beat there is no extension - the base deadline is untouched."""
    repo = _installed_repo(tmp_path)
    clock, _process, terminated = _stopping(monkeypatch, ends_at=None, beats_until=None)

    result = control.stop(repo)

    assert clock.now == control.STOP_TIMEOUT_SECONDS
    assert result.forced
    assert len(terminated) == 1


def test_a_stop_of_an_application_that_ends_at_once_terminates_nothing(
    tmp_path: Path, monkeypatch
) -> None:
    repo = _installed_repo(tmp_path)
    clock, _process, terminated = _stopping(monkeypatch, ends_at=0.0)

    result = control.stop(repo)

    assert clock.now == 0.0
    assert terminated == []
    assert not result.forced


def test_a_single_beat_never_shortens_the_base_deadline(tmp_path: Path, monkeypatch) -> None:
    """The grace is shorter than the base deadline and must not replace it."""
    repo = _installed_repo(tmp_path)
    clock, _process, _terminated = _stopping(monkeypatch, ends_at=None, beats_until=1.0)

    control.stop(repo)

    assert clock.now == control.STOP_TIMEOUT_SECONDS


def test_a_beat_that_never_stops_ends_at_the_ceiling(tmp_path: Path, monkeypatch) -> None:
    """A hanging process must not block for ever (design D4)."""
    repo = _installed_repo(tmp_path)
    clock, _process, terminated = _stopping(monkeypatch, ends_at=None, beats_until=1_000_000.0)

    result = control.stop(repo)

    assert clock.now == control.STOP_LIMIT_SECONDS
    assert result.forced
    assert len(terminated) == 1


def test_the_ceiling_covers_mixing_the_recorder_threads_and_a_copy() -> None:
    """The two numbers used to be maintained in two modules without a link.

    That, not the value itself, was the fault: the comment above the deadline
    claimed the cover, and nothing ever checked the sum (design D6).
    """
    recorder_threads = 2 * 5.0
    copy_reserve = 60.0

    assert (
        control.STOP_LIMIT_SECONDS
        > merge.MERGE_TIMEOUT_SECONDS + recorder_threads + copy_reserve
    )
    assert control.STOP_LIMIT_SECONDS > control.STOP_TIMEOUT_SECONDS
    assert control.STOP_GRACE_SECONDS < control.STOP_TIMEOUT_SECONDS


# --- What a forced stop says --------------------------------------------------


class Collected(logging.Handler):
    """The package's own logger does not propagate once it is configured.

    Hanging a handler on it directly is the only way to read what it wrote that
    does not depend on whichever test ran before this one.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def test_a_forced_stop_names_the_folder_the_raw_takes_stay_in(
    tmp_path: Path, repo: Path, config_values: dict[str, str], monkeypatch
) -> None:
    """Without this nobody ever learns that a recording was cut off."""
    installed = _installed_repo(tmp_path)
    write_config(paths.config_path(), config_values, repo=repo)
    recording_dir = Path(config_values["recording_dir"])
    recording_dir.mkdir(parents=True, exist_ok=True)
    takes = [recording_dir / "mic_2026.wav", recording_dir / "system_2026.wav"]
    for take in takes:
        take.write_bytes(b"Rohspur")

    _stopping(monkeypatch, ends_at=None, beats_until=1_000_000.0)
    collected = Collected()
    package_logger = logging.getLogger("backrec")
    package_logger.addHandler(collected)
    try:
        result = control.stop(installed)
    finally:
        package_logger.removeHandler(collected)

    assert result.forced
    assert result.raw_takes == str(recording_dir)
    assert str(recording_dir) in result.message
    assert "abgeschnitten" in result.message
    assert any(str(recording_dir) in message for message in collected.messages)
    assert all(take.is_file() for take in takes), "die Rohspuren bleiben unangetastet"


def test_a_forced_stop_without_a_closing_sequence_still_points_at_the_folder(
    tmp_path: Path, repo: Path, config_values: dict[str, str], monkeypatch
) -> None:
    """A process hanging mid-recording leaves two half-written takes there too."""
    installed = _installed_repo(tmp_path)
    write_config(paths.config_path(), config_values, repo=repo)
    _stopping(monkeypatch, ends_at=None, beats_until=None)

    result = control.stop(installed)

    assert result.forced
    assert result.raw_takes == config_values["recording_dir"]
    assert "abgeschnitten" not in result.message
    assert config_values["recording_dir"] in result.message


def test_a_forced_stop_reports_even_without_readable_settings(
    tmp_path: Path, monkeypatch
) -> None:
    """A stop that failed over the settings file would be the worst cure."""
    installed = _installed_repo(tmp_path)
    _stopping(monkeypatch, ends_at=None, beats_until=None)

    result = control.stop(installed)

    assert result.forced
    assert result.raw_takes is None
    assert "Frist" in result.message


# --- Status -------------------------------------------------------------------


def test_status_without_a_running_instance_says_so(tmp_path: Path) -> None:
    repo = _installed_repo(tmp_path)

    report = control.status(repo)

    assert not report.running
    assert report.pid is None
    assert report.repo_path == repo


def test_status_reads_pid_start_and_folders_from_the_record(tmp_path: Path) -> None:
    repo = _installed_repo(tmp_path)
    record = instance.write_record(repo=repo)

    report = control.status(repo)

    assert report.running
    assert report.pid == record.pid
    assert report.started == record.started
    assert report.config_path == paths.config_path()
    assert report.logs_path == paths.logs_dir()


def test_status_reads_a_running_recording_from_the_file_system(tmp_path: Path) -> None:
    repo = _installed_repo(tmp_path)
    instance.write_record(repo=repo)
    instance.mark_recording()

    assert control.status(repo).recording

    instance.clear_recording()
    assert not control.status(repo).recording


# --- Uninstall ----------------------------------------------------------------


def test_uninstall_keeps_settings_and_names_what_stays(tmp_path: Path, monkeypatch) -> None:
    repo = _installed_repo(tmp_path)
    paths.tool_home().mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(control, "_runs_from", lambda _repo: False)

    result = control.uninstall(repo, desktop=tmp_path / "Desktop")

    joined = " ".join(result.lines)
    assert result.ok
    assert not (repo / ".venv").exists()
    assert paths.tool_home().is_dir()
    assert str(paths.tool_home()) in joined
    assert "Aufnahmen" in joined
    assert str(paths.suite_handshake_path()) in joined


def test_uninstall_never_touches_its_own_environment(tmp_path: Path, monkeypatch) -> None:
    """Half-deleting it is worse than leaving it (a finding from AutoMemo)."""
    repo = _installed_repo(tmp_path)
    monkeypatch.setattr(control, "_runs_from", lambda _repo: True)

    result = control.uninstall(repo, desktop=tmp_path / "Desktop")

    assert (repo / ".venv" / "pyvenv.cfg").is_file()
    assert "verschwindet mit dem Ordner" in " ".join(result.lines)


def test_uninstall_with_purge_removes_the_tool_home(tmp_path: Path, monkeypatch) -> None:
    repo = _installed_repo(tmp_path)
    paths.tool_home().mkdir(parents=True, exist_ok=True)
    (paths.tool_home() / "config.toml").write_text("x", encoding="utf-8")
    monkeypatch.setattr(control, "_runs_from", lambda _repo: False)

    control.uninstall(repo, purge=True, desktop=tmp_path / "Desktop")

    assert not paths.tool_home().exists()


def test_uninstall_removes_the_desktop_icon(tmp_path: Path, monkeypatch) -> None:
    repo = _installed_repo(tmp_path)
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    (desktop / shortcut_module.SHORTCUT_NAME).write_text("lnk", encoding="utf-8")
    monkeypatch.setattr(control, "_runs_from", lambda _repo: False)

    control.uninstall(repo, desktop=desktop)

    assert not (desktop / shortcut_module.SHORTCUT_NAME).exists()


def test_the_uninstall_never_says_the_application_keeps_running(
    tmp_path: Path, monkeypatch
) -> None:
    """It stops the application first - the note of the icon command contradicts that."""
    repo = _installed_repo(tmp_path)
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    (desktop / shortcut_module.SHORTCUT_NAME).write_text("lnk", encoding="utf-8")
    monkeypatch.setattr(control, "_runs_from", lambda _repo: False)

    result = control.uninstall(repo, desktop=desktop)

    assert shortcut_module.RUNNING_UNTOUCHED_NOTE not in result.lines


# --- A second installation ----------------------------------------------------


def _record_of_another_installation(other: Path) -> None:
    import json
    import os

    import psutil

    target = paths.pid_record_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "create_time": psutil.Process().create_time(),
                "started": "",
                "repo": str(other),
            }
        ),
        encoding="utf-8",
    )


def test_a_second_installation_is_named_and_blocks_nothing(tmp_path: Path) -> None:
    """Two unpacked copies are two installations - neither may block the other.

    Left unsaid, the two look like one that misbehaves: a window on screen that
    this folder knows nothing about.
    """
    repo = _installed_repo(tmp_path)
    other = tmp_path / "zweite-installation"
    _record_of_another_installation(other)

    report = control.status(repo)

    assert report.running is False
    assert report.foreign_folder == str(other)
    assert control.foreign_installation(repo) == str(other)


def test_no_second_installation_means_no_note(tmp_path: Path) -> None:
    repo = _installed_repo(tmp_path)
    instance.clear_record()

    assert control.status(repo).foreign_folder is None


# --- About --------------------------------------------------------------------


def test_about_names_version_folder_settings_guide_and_removal(tmp_path: Path) -> None:
    repo = _installed_repo(tmp_path)

    lines = control.about_lines(repo)
    joined = "\n".join(lines)

    assert "2026.09.1" in joined
    assert str(repo) in joined
    assert str(paths.config_path()) in joined
    assert paths.GUIDE_FILE_NAME in joined
    for sentence in control.UNINSTALL_SENTENCES:
        assert sentence in joined


def test_about_says_what_survives_the_deleted_folder(tmp_path: Path) -> None:
    """Three sentences that end at the folder leave the rest unsaid."""
    repo = _installed_repo(tmp_path)

    joined = "\n".join(control.about_lines(repo))

    assert str(paths.tool_home()) in joined
    assert "getrennt löschen" in joined


def test_the_removal_sentences_are_the_ones_from_the_guide() -> None:
    """The same text in two places that cannot reach each other."""
    guide = paths.guide_path().read_bytes()[3:].decode("utf-8")

    for sentence in control.UNINSTALL_SENTENCES:
        assert sentence in guide


# --- Installed version --------------------------------------------------------


def test_the_installed_version_round_trips() -> None:
    control.write_installed_version("2026.10.3")

    assert control.read_installed_version() == "2026.10.3"


def test_an_unreadable_record_of_the_installed_version_counts_as_absent() -> None:
    target = paths.installed_record_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{kaputt", encoding="utf-8")

    assert control.read_installed_version() is None


# --- Opening folders (H1) -----------------------------------------------------


# A command line that starts Explorer, and the switch that selects a file in it.
# The registry path `...\CurrentVersion\Explorer\Shell Folders` is no call and is
# not matched: there the word is followed by a backslash, never by a quote.
_EXPLORER_CALL = re.compile(r"""["']explorer(\.exe)?["']|/select""", re.IGNORECASE)


def test_no_folder_is_opened_through_an_explorer_command() -> None:
    """Convention section 5, revision of 12.09.2026.

    Handed an argument list, Python puts quotes around the whole argument as soon
    as the path carries a space; Explorer then sees `"/select,C:\\...lnk"`, knows
    no such switch and opens "Dokumente" instead of the wanted folder. Backrec
    never builds such a command line -- `os.startfile` takes a path and needs no
    switch -- and this test is what keeps that route from being left.
    """
    sources = sorted(Path(control.__file__).parent.glob("*.py"))
    offenders = [path.name for path in sources if _EXPLORER_CALL.search(path.read_text(encoding="utf-8"))]

    assert offenders == [], "Ordner werden mit os.startfile geöffnet, nie über eine Explorer-Kommandozeile"


# --- The diagnosis the status line asks for -----------------------------------


def test_the_report_is_written_and_opened(tmp_path: Path, monkeypatch) -> None:
    """The route a click on the status line takes, without an editor on the machine."""
    repo = _installed_repo(tmp_path)
    opened: list[str] = []
    monkeypatch.setattr(control.doctor.os, "startfile", opened.append, raising=False)

    result = control.run_doctor(repo=repo, report=True, open_report=True)

    assert result.report_path is not None
    assert result.report_path.is_file()
    assert result.report_path.parent == paths.reports_dir()
    assert opened == [str(result.report_path)]


def test_a_diagnosis_without_a_report_writes_no_file(tmp_path: Path, monkeypatch) -> None:
    """Only the route through the window asks for one (design D21)."""
    repo = _installed_repo(tmp_path)
    opened: list[str] = []
    monkeypatch.setattr(control.doctor.os, "startfile", opened.append, raising=False)

    result = control.run_doctor(repo=repo)

    assert result.report_path is None
    assert opened == []


def test_a_report_that_cannot_be_opened_is_still_written(tmp_path: Path, monkeypatch) -> None:
    """No editor is no reason to lose the file a colleague is meant to send on."""

    def refuse(_target: str) -> None:
        raise OSError("kein Editor")

    repo = _installed_repo(tmp_path)
    monkeypatch.setattr(control.doctor.os, "startfile", refuse, raising=False)

    result = control.run_doctor(repo=repo, report=True, open_report=True)

    assert result.report_path is not None
    assert result.report_path.is_file()

