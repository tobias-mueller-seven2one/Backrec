"""The root folder is the first surface a colleague sees.

Every file he can double-click there is a question he might ask, so there are
exactly two that start something and two that only open an editor (design D16).
`Start_Recorder.bat` is the one leftover, and it is allowed to exist precisely
because it starts nothing any more (design D11).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backrec import paths

ROOT = paths.repo_root()

# What a double click acts on. Everything else at the top level is a developer
# file that Explorer opens in an editor at worst.
CLICKABLE_SUFFIXES = (".cmd", ".bat", ".ps1", ".exe", ".vbs", ".lnk")

STARTS_SOMETHING = ("Setup.cmd", "Start.cmd")
OPENS_AN_EDITOR = (paths.VERSION_FILE_NAME, paths.GUIDE_FILE_NAME)
THE_LEFTOVER = "Start_Recorder.bat"

# Batch constructs that would be procedure rather than a wrapper.
LOGIC_MARKERS = ("for ", "set /p", "setlocal enabledelayedexpansion", "call ")

MAX_WRAPPER_LINES = 35


def text_of(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8-sig")


def test_only_two_files_at_the_top_level_start_something() -> None:
    clickable = sorted(
        entry.name
        for entry in ROOT.iterdir()
        if entry.is_file() and entry.suffix.lower() in CLICKABLE_SUFFIXES
    )

    assert clickable == sorted([*STARTS_SOMETHING, THE_LEFTOVER])


def test_the_two_text_files_are_there_and_start_nothing() -> None:
    for name in OPENS_AN_EDITOR:
        assert (ROOT / name).is_file()
        assert (ROOT / name).suffix.lower() not in CLICKABLE_SUFFIXES


@pytest.mark.parametrize("name", ["Stop.cmd", "Update.cmd", "Doctor.cmd", "Uninstall.cmd"])
def test_no_further_double_click_file_was_added(name: str) -> None:
    """Stop and update are commands and menu entries, not files (design D16)."""
    assert not (ROOT / name).exists()


@pytest.mark.parametrize("name", STARTS_SOMETHING)
def test_a_wrapper_acts_on_its_own_folder(name: str) -> None:
    assert 'cd /d "%~dp0"' in text_of(name)


@pytest.mark.parametrize("name", STARTS_SOMETHING)
def test_a_wrapper_speaks_the_right_character_set(name: str) -> None:
    content = text_of(name)

    assert "chcp 65001" in content
    assert "PYTHONUTF8=1" in content


@pytest.mark.parametrize("name", [*STARTS_SOMETHING, THE_LEFTOVER])
def test_a_wrapper_carries_no_procedure_of_its_own(name: str) -> None:
    content = text_of(name).lower()

    assert len(content.splitlines()) <= MAX_WRAPPER_LINES
    for marker in LOGIC_MARKERS:
        assert marker not in content


@pytest.mark.parametrize("name", [*STARTS_SOMETHING, THE_LEFTOVER])
def test_a_wrapper_has_windows_line_endings(name: str) -> None:
    """cmd.exe stumbles over a batch file with the other kind."""
    raw = (ROOT / name).read_bytes()

    assert b"\r\n" in raw


def test_the_setup_wrapper_calls_the_bootstrap_before_the_environment_exists() -> None:
    content = text_of("Setup.cmd")

    assert "scripts\\win\\bootstrap-uv.ps1" in content
    assert "uv run --no-sync backrec setup" in content


def test_the_setup_wrapper_hands_its_arguments_on() -> None:
    """The update helper calls it with --unattended --start."""
    assert "%*" in text_of("Setup.cmd")


def test_the_start_wrapper_uses_the_entry_point_of_the_environment() -> None:
    content = text_of("Start.cmd")

    assert ".venv\\Scripts\\backrec.exe" in content
    assert "start" in content


def test_the_start_wrapper_keeps_its_window_open_only_on_failure() -> None:
    content = text_of("Start.cmd")

    assert 'if "%EXITCODE%"=="0" goto :raus' in content


def test_the_start_wrapper_names_the_setup_when_nothing_is_set_up() -> None:
    content = text_of("Start.cmd")

    assert "Was ist passiert" in content
    assert "Setup.cmd" in content


def test_the_retired_script_only_points_at_the_new_way() -> None:
    content = text_of(THE_LEFTOVER)

    assert "Setup.cmd" in content
    assert "Start.cmd" in content
    assert "pause" in content
    assert "exit /b 1" in content


def test_the_retired_script_builds_nothing_and_starts_nothing() -> None:
    content = text_of(THE_LEFTOVER).lower()

    for forbidden in ("uv ", "pythonw", "python ", "activate", "pip "):
        assert forbidden not in content


def test_the_helper_scripts_live_under_scripts() -> None:
    """The one place a wrapper is allowed to delegate procedure to."""
    assert (ROOT / "scripts" / "win" / "bootstrap-uv.ps1").is_file()
    assert (ROOT / "scripts" / "win" / "apply-update.ps1").is_file()


def test_the_bootstrap_reinstalls_this_package() -> None:
    """Without it a mirrored update would silently keep the old state running."""
    content = (ROOT / "scripts" / "win" / "bootstrap-uv.ps1").read_text(encoding="utf-8")

    assert "--reinstall-package backrec" in content


def test_the_update_helper_calls_the_setup_by_its_full_path() -> None:
    """`Push-Location` moves the session, not the folder a child process inherits.

    Called by its bare name the setup was looked for wherever Backrec had been
    started from - and an update ended with mirrored files, an environment that
    was never brought up to date and no restart at all.
    """
    content = (ROOT / "scripts" / "win" / "apply-update.ps1").read_text(encoding="utf-8")

    assert "Join-Path $RepoPath 'Setup.cmd'" in content
    assert "-WorkingDirectory $RepoPath" in content
    assert "cmd.exe /c" not in content


def test_the_update_helper_puts_the_new_list_into_the_folder() -> None:
    """Without it the setup right afterwards deletes what just arrived.

    The accompanying list does not list itself, so mirroring by list leaves the
    previous release's copy in the folder - and every file new in this release
    then looks like a leftover of the one before.
    """
    content = (ROOT / "scripts" / "win" / "apply-update.ps1").read_text(encoding="utf-8")

    assert "Join-Path $RepoPath 'release-manifest.json'" in content


def test_the_update_helper_starts_the_tool_again() -> None:
    """It stopped the tool for this update; it has to bring it back."""
    content = (ROOT / "scripts" / "win" / "apply-update.ps1").read_text(encoding="utf-8")

    assert "'--unattended', '--start'" in content


def test_the_update_helper_does_not_wait_for_the_tool_it_restarts() -> None:
    """`-Wait` waits for the process *and every descendant* of it.

    The setup starts Backrec detached at the end, so this window would stay open
    for as long as Backrec runs and never say that it is finished.
    """
    content = (ROOT / "scripts" / "win" / "apply-update.ps1").read_text(encoding="utf-8")
    code = "\n".join(line for line in content.splitlines() if not line.lstrip().startswith("#"))

    assert "-Wait " not in code
    assert "WaitForExit()" in code


def test_the_helper_scripts_stay_within_powershell_5() -> None:
    """Windows 11 ships 5.1; anything newer is an extra installation.

    Comments are stripped first - both scripts name the constructs they avoid,
    and a check that trips over its own documentation gets deleted, not fixed.
    """
    for name in ("bootstrap-uv.ps1", "apply-update.ps1"):
        raw = (ROOT / "scripts" / "win" / name).read_text(encoding="utf-8")
        code = "\n".join(
            line for line in raw.splitlines() if not line.lstrip().startswith("#")
        )
        assert "??" not in code
        assert "-Parallel" not in code
