"""ffmpeg: found, callable, fetched - and the three of them kept apart."""

from __future__ import annotations

import subprocess

from backrec import external


def _result(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


VERSION_OUTPUT = "ffmpeg version 7.1.1-full_build-www.gyan.dev Copyright (c) 2000-2025"


def test_inspect_reports_not_found_without_hits() -> None:
    state = external.inspect(which_fn=lambda _name: None, runner=lambda _cmd, _timeout: _result())

    assert state.found_at is None
    assert not state.usable
    assert "Suchpfad" in state.detail


def test_inspect_separates_found_from_callable() -> None:
    state = external.inspect(
        which_fn=lambda _name: r"C:\tools\ffmpeg.exe",
        runner=lambda _cmd, _timeout: _result(returncode=1, stderr="not a valid application"),
    )

    assert state.found_at is not None
    assert not state.runs
    assert not state.usable


def test_inspect_names_the_version_on_success() -> None:
    state = external.inspect(
        which_fn=lambda _name: r"C:\tools\ffmpeg.exe",
        runner=lambda _cmd, _timeout: _result(stdout=VERSION_OUTPUT),
    )

    assert state.usable
    assert state.version.startswith("7.1.1")


def test_ensure_never_installs_an_existing_ffmpeg() -> None:
    calls: list[list[str]] = []

    def runner(command: list[str], _timeout: float) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return _result(stdout=VERSION_OUTPUT)

    result = external.ensure(which_fn=lambda _name: r"C:\tools\ffmpeg.exe", runner=runner)

    assert result.ok
    assert "7.1.1" in result.message
    assert all("winget" not in command[0] for command in calls)


def test_ensure_installs_when_missing_and_reports_the_new_version() -> None:
    seen: list[list[str]] = []
    found: list[str | None] = [None]

    def which_fn(_name: str) -> str | None:
        return found[0]

    def runner(command: list[str], _timeout: float) -> subprocess.CompletedProcess[str]:
        seen.append(command)
        if command[0] == "winget":
            found[0] = r"C:\tools\ffmpeg.exe"
            return _result()
        return _result(stdout=VERSION_OUTPUT)

    result = external.ensure(which_fn=which_fn, runner=runner)

    assert result.ok
    assert seen[0][0] == "winget"


def test_ensure_says_a_new_window_is_needed_when_the_path_lags() -> None:
    def runner(command: list[str], _timeout: float) -> subprocess.CompletedProcess[str]:
        return _result()

    result = external.ensure(which_fn=lambda _name: None, runner=runner)

    assert not result.ok
    assert "noch einmal" in result.next_step


def test_ensure_falls_back_to_instructions_with_a_security_hint() -> None:
    def runner(command: list[str], _timeout: float) -> subprocess.CompletedProcess[str]:
        return _result(returncode=1, stderr="no applicable installer")

    result = external.ensure(which_fn=lambda _name: None, runner=runner)

    assert not result.ok
    assert external.MANUAL_DOWNLOAD_URL in result.next_step
    assert "Sicherheitswarnung" in result.next_step


def test_run_command_never_raises_on_a_missing_program() -> None:
    result = external.run_command(["definitiv-nicht-vorhanden-xyz"], timeout=5)

    assert result.returncode == 1
