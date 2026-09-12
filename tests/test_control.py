"""The control surface: one result per command, and no output of its own."""

from __future__ import annotations

import subprocess
from dataclasses import is_dataclass
from pathlib import Path

from backrec import control, instance, paths, shortcut as shortcut_module
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


# --- Update -------------------------------------------------------------------


def test_update_from_git_without_version_control_points_at_the_archive(tmp_path: Path) -> None:
    repo = _installed_repo(tmp_path)

    result = control.update_from_git(repo)

    assert not result.ok
    assert "Setup.cmd" in " ".join(result.lines)


def test_a_broken_archive_changes_nothing(tmp_path: Path) -> None:
    repo = _installed_repo(tmp_path)
    broken = tmp_path / "kaputt.zip"
    broken.write_bytes(b"kein Archiv")

    result = control.apply_archive(broken, repo, detached=False)

    assert not result.ok
    assert not (repo.with_name(repo.name + ".update")).exists()


def _archive(tmp_path: Path, version: str = "2026.10.1") -> Path:
    import hashlib
    import json
    import zipfile

    from backrec import release

    content = "neu"
    target = tmp_path / f"Backrec-{version}.zip"
    with zipfile.ZipFile(target, "w") as bundle:
        bundle.writestr("Backrec/README.md", content)
        bundle.writestr(
            f"Backrec/{release.MANIFEST_NAME}",
            json.dumps(
                {
                    "tool": "Backrec",
                    "version": version,
                    "files": [
                        {
                            "path": "README.md",
                            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                            "size": len(content),
                        }
                    ],
                }
            ),
        )
    return target


class FakeProcess:
    pid = 4242

    def is_running(self) -> bool:
        return True


def test_updating_a_running_instance_hands_over_to_the_helper_outside_the_folder(
    tmp_path: Path, monkeypatch
) -> None:
    repo = _installed_repo(tmp_path)
    (repo / "scripts" / "win").mkdir(parents=True)
    (repo / "scripts" / "win" / "apply-update.ps1").write_text("# helfer", encoding="utf-8")
    launched: list[list[str]] = []

    monkeypatch.setattr(control.instance, "running_instance", lambda **_k: FakeProcess())
    monkeypatch.setattr(control.subprocess, "Popen", lambda command, **_k: launched.append(command))

    result = control.apply_archive(_archive(tmp_path), repo)

    assert result.ok
    assert launched
    assert launched[0][0] == "powershell.exe"
    assert "-File" in launched[0]
    assert str(repo / "scripts" / "win" / "apply-update.ps1") in launched[0]
    assert str(FakeProcess.pid) in launched[0]


def test_updating_names_both_versions_before_anything_changes(
    tmp_path: Path, monkeypatch
) -> None:
    repo = _installed_repo(tmp_path)
    (repo / "scripts" / "win").mkdir(parents=True)
    (repo / "scripts" / "win" / "apply-update.ps1").write_text("# helfer", encoding="utf-8")

    monkeypatch.setattr(control.instance, "running_instance", lambda **_k: FakeProcess())
    monkeypatch.setattr(control.subprocess, "Popen", lambda command, **_k: None)

    result = control.apply_archive(_archive(tmp_path), repo)

    joined = " ".join(result.lines)
    assert "2026.09.1" in joined
    assert "2026.10.1" in joined


def test_a_missing_helper_leaves_the_previous_state_runnable(
    tmp_path: Path, monkeypatch
) -> None:
    repo = _installed_repo(tmp_path)
    monkeypatch.setattr(control.instance, "running_instance", lambda **_k: FakeProcess())

    result = control.apply_archive(_archive(tmp_path), repo)

    assert not result.ok
    assert "Setup.cmd" in " ".join(result.lines)
    assert (repo / ".venv" / "pyvenv.cfg").is_file()


def test_an_archive_that_is_not_newer_changes_nothing(tmp_path: Path) -> None:
    """The specification asks for both versions and an explicit yes first."""
    repo = _installed_repo(tmp_path)

    result = control.apply_archive(_archive(tmp_path, "2026.08.1"), repo, detached=False)

    joined = " ".join(result.lines)
    assert not result.ok
    assert "2026.09.1" in joined
    assert "2026.08.1" in joined
    assert not repo.with_name(repo.name + ".update").exists()
    assert not (repo / "README.md").exists()


def test_an_older_archive_goes_in_after_an_explicit_yes(tmp_path: Path) -> None:
    repo = _installed_repo(tmp_path)

    result = control.apply_archive(
        _archive(tmp_path, "2026.08.1"), repo, detached=False, allow_older=True
    )

    assert result.ok
    assert (repo / "README.md").read_text(encoding="utf-8") == "neu"


def test_reading_an_archive_unpacks_nothing(tmp_path: Path) -> None:
    """The window asks before the first change, so this may not make one."""
    repo = _installed_repo(tmp_path)

    decision, problem = control.inspect_archive(_archive(tmp_path), repo)

    assert problem == ()
    assert decision is not None
    assert decision.installed_version == "2026.09.1"
    assert decision.info.version == "2026.10.1"
    assert not repo.with_name(repo.name + ".update").exists()


def test_updating_without_a_running_instance_mirrors_right_away(tmp_path: Path) -> None:
    repo = _installed_repo(tmp_path)

    result = control.apply_archive(_archive(tmp_path), repo, detached=False)

    assert result.ok
    assert (repo / "README.md").read_text(encoding="utf-8") == "neu"
    assert not repo.with_name(repo.name + ".update").exists()
    assert "Setup.cmd" in " ".join(result.lines)


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
