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
    """Stopping and the diagnosis are commands, not files (design D16).

    `Update.cmd` stays on this list although the tool has no way to update
    itself: the list is what must never appear in the root folder.
    """
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
    """A script calls it with --unattended --start."""
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


def test_the_bootstrap_reinstalls_this_package() -> None:
    """A plain sync does not notice changed sources of this package.

    Only this script stands outside the environment it rebuilds, so it is the
    one place where the reinstall can happen at all.
    """
    content = (ROOT / "scripts" / "win" / "bootstrap-uv.ps1").read_text(encoding="utf-8")

    assert "--reinstall-package backrec" in content


def bootstrap_text() -> str:
    return (ROOT / "scripts" / "win" / "bootstrap-uv.ps1").read_text(encoding="utf-8-sig")


def test_the_bootstrap_stops_a_running_application_before_the_sync() -> None:
    """The reinstall above is what makes the order matter (design D10).

    On the double click route this script runs before the setup does, so its own
    sync would hit an open window first and the stop inside `control.setup`
    would come too late.
    """
    content = bootstrap_text()

    stop_call = content.find("$entryPoint stop")
    sync_call = content.find("uv sync")

    assert ".venv\\Scripts\\backrec.exe" in content
    assert stop_call != -1
    assert stop_call < sync_call


def test_the_bootstrap_brings_no_stop_mechanics_of_its_own() -> None:
    """It calls the existing command and waits - no deadline, no process list."""
    content = bootstrap_text()

    for forbidden in ("Stop-Process", "Get-Process", "Wait-Process", "Start-Sleep", "pythonw"):
        assert forbidden not in content


def test_a_failed_stop_never_ends_the_bootstrap() -> None:
    """No environment, no entry point, nothing to stop - and a stop that fails
    is the worse reason to leave the environment unbuilt."""
    content = bootstrap_text()
    block = content[content.index("$entryPoint = ") : content.index("& uv sync")]

    assert "Test-Path $entryPoint" in block
    assert "exit 1" not in block


def test_no_helper_script_replaces_the_tool_itself() -> None:
    """Backrec has no way to update itself (decision of 15.09.2026).

    A new state is fetched by downloading the program again and replacing the
    old one - a deletion followed by an ordinary setup. No script stages a
    folder, mirrors files in or fetches a console of its own for it.
    """
    found = sorted(path.name for path in (ROOT / "scripts" / "win").iterdir())

    assert found == ["bootstrap-uv.ps1"]


HELFER = ("bootstrap-uv.ps1",)

# Spellings that replace an umlaut. The first lines a colleague ever sees come
# out of the bootstrap, and "fuer" in them says the tool could not manage its
# own alphabet.
ERSATZSCHREIBWEISEN = (
    "fuer",
    "ueber",
    "laeuft",
    "liess",
    "unvollstaendig",
    "Rueckfrage",
    "benoetigt",
    "uebernommen",
    "unveraendert",
    "pruefen",
)


def test_the_helper_scripts_carry_the_byte_order_mark() -> None:
    """Without it PowerShell 5.1 reads the file as ANSI and every umlaut breaks.

    That is the reason the sentences in these two files used to spell their
    umlauts out - and the reason they no longer have to.
    """
    for name in HELFER:
        assert (ROOT / "scripts" / "win" / name).read_bytes().startswith(b"\xef\xbb\xbf"), name


def test_no_visible_line_of_a_helper_script_spells_an_umlaut_out() -> None:
    offences: list[tuple[str, int, str]] = []

    for name in HELFER:
        raw = (ROOT / "scripts" / "win" / name).read_text(encoding="utf-8-sig")
        for number, line in enumerate(raw.splitlines(), start=1):
            if line.lstrip().startswith("#") or "'" not in line and '"' not in line:
                continue
            offences.extend(
                (name, number, ersatz) for ersatz in ERSATZSCHREIBWEISEN if ersatz in line
            )

    assert offences == []


def test_the_helper_scripts_stay_within_powershell_5() -> None:
    """Windows 11 ships 5.1; anything newer is an extra installation.

    Comments are stripped first - both scripts name the constructs they avoid,
    and a check that trips over its own documentation gets deleted, not fixed.
    """
    for name in HELFER:
        raw = (ROOT / "scripts" / "win" / name).read_text(encoding="utf-8")
        code = "\n".join(
            line for line in raw.splitlines() if not line.lstrip().startswith("#")
        )
        assert "??" not in code
        assert "-Parallel" not in code
