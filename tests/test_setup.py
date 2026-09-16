"""The setup: seven steps, idempotent, and it never starts by itself.

The three steps that touch the outside world - fetching the helper, building the
environment, fetching ffmpeg - are replaced here. What is under test is the
procedure: the order, what a failure does to it, what a second run does, and
what the output tells the reader at the end.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from backrec import control, doctor, external, paths, shortcut as shortcut_module
from backrec.console import Assistant
from backrec.wizard import write_config

OK_CHECK = doctor.Check("x.ok", "Laufzeit", "Alles", doctor.Level.PASS, "in Ordnung")
FAIL_CHECK = doctor.Check("x.bad", "Laufzeit", "Etwas", doctor.Level.FAIL, "kaputt", "Reparieren.")


class Desktop:
    """A desktop whose links are files plus a remembered specification."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.written: dict[Path, shortcut_module.ShortcutSpec] = {}
        self.error: str | None = None

    def write(self, link: Path, spec: shortcut_module.ShortcutSpec) -> str | None:
        if self.error is not None:
            return self.error
        link.parent.mkdir(parents=True, exist_ok=True)
        link.write_text("lnk", encoding="utf-8")
        self.written[link] = spec
        return None

    def read(self, link: Path) -> dict[str, str] | None:
        spec = self.written.get(link)
        if spec is None:
            return None
        return {"target": spec.target, "arguments": spec.arguments, "workdir": spec.workdir}


@pytest.fixture
def repo_folder(tmp_path: Path) -> Path:
    root = tmp_path / "Backrec"
    (root / ".venv" / "Scripts").mkdir(parents=True)
    (root / ".venv" / "pyvenv.cfg").write_text("version = 3.11.9\n", encoding="utf-8")
    (root / ".venv" / "Scripts" / "pythonw.exe").write_bytes(b"MZ")
    (root / paths.VERSION_FILE_NAME).write_text("2026.09.1\n", encoding="utf-8")
    (root / paths.EXAMPLE_CONFIG_FILE_NAME).write_bytes(
        paths.example_config_path().read_bytes()
    )
    return root


@pytest.fixture
def calm(monkeypatch, repo_folder: Path):
    """Everything that would touch the machine, replaced."""
    monkeypatch.setattr(control, "_ensure_uv", lambda ui: ui.ok("Hilfsprogramm da") or True)
    monkeypatch.setattr(
        control, "_ensure_environment", lambda ui, repo: ui.ok("Umgebung da") or True
    )
    monkeypatch.setattr(
        external,
        "ensure",
        lambda **_kwargs: external.DependencyResult(ok=True, message="Mischprogramm da"),
    )
    monkeypatch.setattr(doctor, "run", lambda *_a, **_k: [OK_CHECK])
    monkeypatch.setattr(control, "start", lambda *_a, **_k: control.StartResult(started=True))
    return repo_folder


def run_setup(repo: Path, desktop: Desktop, monkeypatch, answers=None, **kwargs):
    stream = io.StringIO()
    supplied = list(answers or [])
    assistant = Assistant(
        total_steps=control.SETUP_STEPS,
        stream=stream,
        interactive=not kwargs.get("unattended", False),
        color=False,
        input_fn=lambda _prompt: supplied.pop(0) if supplied else "",
    )
    monkeypatch.setattr(shortcut_module, "read_link", desktop.read)
    monkeypatch.setattr(shortcut_module, "write_link", desktop.write)

    result = control.setup(assistant, repo=repo, desktop=desktop.folder, **kwargs)
    return result, stream.getvalue()


# --- Procedure ----------------------------------------------------------------


def test_both_failed_routes_to_the_helper_are_named_separately(monkeypatch) -> None:
    """"Neither worked" leaves open what the reader should do next."""
    import subprocess

    stream = io.StringIO()
    assistant = Assistant(total_steps=1, stream=stream, interactive=False, color=False)
    monkeypatch.setattr(control.shutil, "which", lambda _name: None)
    monkeypatch.setattr(
        control,
        "_run",
        lambda command, **_k: subprocess.CompletedProcess(
            args=command,
            returncode=1,
            stdout="",
            stderr="unable to connect to host"
            if command[0] == "winget"
            else "'irm' is not recognized",
        ),
    )

    assert control._ensure_uv(assistant) is False

    printed = stream.getvalue()
    assert "Internet" in printed
    assert "Kommando" in printed
    assert "Setup.cmd erneut" in printed


def test_a_sync_blocked_by_the_running_program_names_the_right_way_out(monkeypatch) -> None:
    """Windows does not release a running program file.

    The plain message would send the reader to their internet connection, and
    the actual fix is the route that stands outside the environment.
    """
    import subprocess

    stream = io.StringIO()
    assistant = Assistant(total_steps=1, stream=stream, interactive=False, color=False)
    monkeypatch.setattr(
        control,
        "_run",
        lambda command, **_k: subprocess.CompletedProcess(
            args=command,
            returncode=2,
            stdout="",
            stderr=(
                r"error: failed to remove file `C:\x\.venv\Scripts\backrec.exe`: "
                "Zugriff verweigert (os error 5)"
            ),
        ),
    )

    assert control._ensure_environment(assistant, Path(r"C:\x")) is False

    printed = stream.getvalue()
    assert "aus ihr heraus läuft" in printed
    assert "Setup.cmd" in printed
    assert "Internetverbindung" not in printed


def test_an_existing_helper_is_never_fetched_again(monkeypatch) -> None:
    stream = io.StringIO()
    assistant = Assistant(total_steps=1, stream=stream, interactive=False, color=False)
    calls: list[list[str]] = []
    monkeypatch.setattr(control.shutil, "which", lambda _name: r"C:\uv\uv.exe")
    monkeypatch.setattr(control, "_run", lambda command, **_k: calls.append(command))

    assert control._ensure_uv(assistant) is True
    assert calls == []


def test_every_step_produces_a_message(calm, tmp_path, monkeypatch) -> None:
    desktop = Desktop(tmp_path / "Desktop")

    result, printed = run_setup(calm, desktop, monkeypatch, unattended=True)

    assert result.ok
    for number in range(1, control.SETUP_STEPS + 1):
        assert f"Schritt {number} von {control.SETUP_STEPS}" in printed


def test_the_steps_come_in_the_specified_order(calm, tmp_path, monkeypatch) -> None:
    desktop = Desktop(tmp_path / "Desktop")

    _result, printed = run_setup(calm, desktop, monkeypatch, unattended=True)

    order = [
        "Hilfsprogramme",
        "Arbeitsumgebung",
        "Einstellungen",
        "Zusatzprogramme",
        "Prüfung",
        "Symbol auf dem Desktop",
        "Loslegen",
    ]
    positions = [printed.index(name) for name in order]
    assert positions == sorted(positions)


def test_a_failing_step_ends_the_run(calm, tmp_path, monkeypatch) -> None:
    desktop = Desktop(tmp_path / "Desktop")
    monkeypatch.setattr(control, "_ensure_uv", lambda ui: False)

    result, printed = run_setup(calm, desktop, monkeypatch, unattended=True)

    assert not result.ok
    assert result.code == 2
    assert "Schritt 2" not in printed


def test_the_closing_words_name_the_start_route_and_the_status_line(
    calm, tmp_path, monkeypatch
) -> None:
    """Der Klick ist nicht selbsterklärend -- hier steht er zum ersten Mal."""
    desktop = Desktop(tmp_path / "Desktop")

    _result, printed = run_setup(calm, desktop, monkeypatch, unattended=True)

    assert "Desktop" in printed
    assert "Statuszeile" in printed
    assert "Diagnose" in printed


def test_the_closing_words_name_the_file_and_both_ways_to_change_it(
    calm, tmp_path, monkeypatch
) -> None:
    """The question "and how do I change that folder now" comes right here."""
    desktop = Desktop(tmp_path / "Desktop")
    config = tmp_path / "config.toml"

    _result, printed = run_setup(
        calm, desktop, monkeypatch, unattended=True, config_path=config
    )

    assert str(config) in printed
    assert control.SETTINGS_CHANGE_HINT in printed


def test_the_unattended_run_asks_nothing_and_starts_nothing(
    calm, tmp_path, monkeypatch
) -> None:
    desktop = Desktop(tmp_path / "Desktop")
    started: list[int] = []
    monkeypatch.setattr(
        control, "start", lambda *_a, **_k: started.append(1) or control.StartResult(started=True)
    )

    result, printed = run_setup(calm, desktop, monkeypatch, unattended=True)

    assert result.ok
    assert started == []
    assert "Jetzt starten?" not in printed


def test_a_hard_check_failure_ends_with_a_non_zero_code(calm, tmp_path, monkeypatch) -> None:
    desktop = Desktop(tmp_path / "Desktop")
    monkeypatch.setattr(doctor, "run", lambda *_a, **_k: [FAIL_CHECK])

    result, printed = run_setup(calm, desktop, monkeypatch, unattended=True)

    assert not result.ok
    assert result.code == 1
    assert "offene Punkte" in printed


def test_a_demanded_start_happens_even_with_an_open_point(calm, tmp_path, monkeypatch) -> None:
    """A caller who asked for a window has to get one.

    One warning - a folder offline for a moment - would otherwise leave the
    caller with no window at all and no reason for it.
    """
    desktop = Desktop(tmp_path / "Desktop")
    started: list[bool] = []
    monkeypatch.setattr(doctor, "run", lambda *_a, **_k: [FAIL_CHECK])
    monkeypatch.setattr(
        control,
        "start",
        lambda *_a, **_k: started.append(True) or control.StartResult(started=True),
    )

    result, _printed = run_setup(
        calm, desktop, monkeypatch, unattended=True, start_after=True
    )

    assert started == [True]
    assert result.code == 1


# --- The running application --------------------------------------------------


def test_a_running_application_is_stopped_before_the_environment_is_built(
    calm, tmp_path, monkeypatch
) -> None:
    """Setup hygiene, not an update step (design D5, revised).

    The bootstrap outside this process replaces the package in the environment
    an open window took its code from. No version has to change for that, so
    nothing here compares one.
    """
    desktop = Desktop(tmp_path / "Desktop")
    run_setup(calm, desktop, monkeypatch, unattended=True)
    version_before = control.read_installed_version()

    events: list[str] = []
    monkeypatch.setattr(control.instance, "running_instance", lambda **_kwargs: object())
    monkeypatch.setattr(
        control,
        "stop",
        lambda *_a, **_k: events.append("stop")
        or control.StopResult(stopped=True, was_running=True),
    )
    monkeypatch.setattr(
        control,
        "_ensure_environment",
        lambda ui, repo: events.append("environment") or ui.ok("Umgebung da") or True,
    )

    result, printed = run_setup(calm, desktop, monkeypatch, unattended=True)

    assert events == ["stop", "environment"]
    assert "Die laufende Anwendung wird vorher beendet." in printed
    assert result.version == version_before
    assert "Fassung" not in printed


def test_a_forced_stop_during_the_setup_is_said_out_loud(calm, tmp_path, monkeypatch) -> None:
    """The route that made this case routine (design D8).

    A colleague double-clicks `Setup.cmd` next to a running recording. Until now
    a forced stop counted as success here and said nothing at all - and he is
    exactly the person who would otherwise never learn where his takes are.
    """
    desktop = Desktop(tmp_path / "Desktop")
    monkeypatch.setattr(control.instance, "running_instance", lambda **_kwargs: object())
    monkeypatch.setattr(
        control,
        "stop",
        lambda *_a, **_k: control.StopResult(
            stopped=True,
            was_running=True,
            forced=True,
            message=(
                "Beendet, nach Ablauf der Frist -- die Nachbereitung der Aufnahme wurde "
                "abgeschnitten. Die Rohspuren liegen in C:\\Aufnahmen."
            ),
            raw_takes="C:\\Aufnahmen",
        ),
    )

    result, printed = run_setup(calm, desktop, monkeypatch, unattended=True)

    assert "C:\\Aufnahmen" in printed
    assert "abgeschnitten" in printed
    assert result.code in (0, 1), "die Einrichtung laeuft weiter"


def test_a_setup_without_a_running_application_says_nothing_about_stopping(
    calm, tmp_path, monkeypatch
) -> None:
    desktop = Desktop(tmp_path / "Desktop")
    stopped: list[str] = []
    monkeypatch.setattr(
        control,
        "stop",
        lambda *_a, **_k: stopped.append("stop")
        or control.StopResult(stopped=True, was_running=False),
    )

    _result, printed = run_setup(calm, desktop, monkeypatch, unattended=True)

    assert stopped == []
    assert "beendet" not in printed


# --- Idempotence --------------------------------------------------------------


def test_a_second_run_leaves_the_settings_untouched(calm, tmp_path, monkeypatch) -> None:
    desktop = Desktop(tmp_path / "Desktop")
    run_setup(calm, desktop, monkeypatch, unattended=True)
    before = paths.config_path().read_bytes()

    result, printed = run_setup(calm, desktop, monkeypatch, unattended=True)

    assert result.ok
    assert result.code == 0
    assert paths.config_path().read_bytes() == before
    assert "gibt es schon" in printed


def test_a_second_run_names_the_steps_it_skipped(calm, tmp_path, monkeypatch) -> None:
    desktop = Desktop(tmp_path / "Desktop")
    run_setup(calm, desktop, monkeypatch, unattended=True)

    _result, printed = run_setup(calm, desktop, monkeypatch, unattended=True)

    assert "gibt es schon" in printed
    assert "liegt schon auf dem Desktop" in printed


# --- New settings from the template (H2) --------------------------------------


def test_the_setup_adds_a_setting_the_template_gained(calm, tmp_path, monkeypatch) -> None:
    """A colleague never adds a setting by hand (convention section 4)."""
    desktop = Desktop(tmp_path / "Desktop")
    run_setup(calm, desktop, monkeypatch, unattended=True)
    settings = paths.config_path()
    settings.write_text(
        "\n".join(
            line
            for line in settings.read_text(encoding="utf-8").splitlines()
            if not line.startswith("log_level")
        )
        + "\n",
        encoding="utf-8",
    )

    _result, printed = run_setup(calm, desktop, monkeypatch, unattended=True)

    assert "1 neue Einstellung mit Standardwert ergänzt." in printed
    assert "log_level = 'INFO'" in settings.read_text(encoding="utf-8")


def test_a_run_without_a_gap_reports_no_addition(calm, tmp_path, monkeypatch) -> None:
    desktop = Desktop(tmp_path / "Desktop")
    run_setup(calm, desktop, monkeypatch, unattended=True)

    _result, printed = run_setup(calm, desktop, monkeypatch, unattended=True)

    assert "ergänzt" not in printed


# --- The desktop icon ---------------------------------------------------------


def test_pressing_enter_creates_the_icon_without_a_manual_step(
    calm, tmp_path, monkeypatch
) -> None:
    desktop = Desktop(tmp_path / "Desktop")

    result, printed = run_setup(calm, desktop, monkeypatch, answers=["", "", "n"])

    assert result.shortcut_installed
    assert (desktop.folder / shortcut_module.SHORTCUT_NAME).is_file()
    assert "ziehen" not in printed.lower()


def test_refusing_the_icon_is_no_failure_and_names_the_command(
    calm, tmp_path, monkeypatch
) -> None:
    desktop = Desktop(tmp_path / "Desktop")

    result, printed = run_setup(calm, desktop, monkeypatch, answers=["", "", "n", "n", "n"])

    assert result.ok
    assert not result.shortcut_installed
    assert "shortcut" in printed


def test_an_existing_icon_is_not_asked_about_again(calm, tmp_path, monkeypatch) -> None:
    desktop = Desktop(tmp_path / "Desktop")
    run_setup(calm, desktop, monkeypatch, unattended=True)

    _result, printed = run_setup(calm, desktop, monkeypatch, unattended=True)

    assert "Soll ein Symbol" not in printed


def test_a_failed_icon_is_a_warning_and_the_setup_still_finishes(
    calm, tmp_path, monkeypatch
) -> None:
    desktop = Desktop(tmp_path / "Desktop")
    desktop.error = "Zugriff verweigert"

    result, printed = run_setup(calm, desktop, monkeypatch, unattended=True)

    assert result.ok
    assert not result.shortcut_installed
    assert "[!]" in printed
    assert "Zugriff verweigert" in printed
    assert "Schritt 7" in printed


# --- Leftover icons on the desktop (H5) ---------------------------------------


def test_a_leftover_icon_of_the_retired_route_is_removed_and_replaced(
    calm, tmp_path, monkeypatch
) -> None:
    """Tobias' desktop held one pointing at `Start_Recorder.bat` (H5)."""
    desktop = Desktop(tmp_path / "Desktop")
    desktop.folder.mkdir(parents=True)
    old = desktop.folder / "Start_Recorder.lnk"
    old.write_text("lnk", encoding="utf-8")
    desktop.written[old] = shortcut_module.ShortcutSpec(
        target=str(calm / "Start_Recorder.bat"), arguments="", workdir=str(calm), description="alt"
    )

    result, printed = run_setup(calm, desktop, monkeypatch, unattended=True)

    assert not old.exists()
    assert "1 veraltete Verknüpfung vom Desktop entfernt." in printed
    assert result.shortcut_installed
    assert (desktop.folder / shortcut_module.SHORTCUT_NAME).is_file()


def test_a_foreign_icon_survives_the_setup(calm, tmp_path, monkeypatch) -> None:
    desktop = Desktop(tmp_path / "Desktop")
    desktop.folder.mkdir(parents=True)
    stranger = desktop.folder / "Irgendein anderes Programm.lnk"
    stranger.write_text("lnk", encoding="utf-8")
    desktop.written[stranger] = shortcut_module.ShortcutSpec(
        target=r"D:\fremd\weg.exe", arguments="", workdir=r"D:\fremd", description="fremd"
    )

    _result, printed = run_setup(calm, desktop, monkeypatch, unattended=True)

    assert stranger.exists()
    assert "entfernt" not in printed


# --- Version change -----------------------------------------------------------


def test_a_changed_version_is_no_event_and_keeps_settings_logs_and_state(
    calm, tmp_path, monkeypatch
) -> None:
    """Backrec has no way to update itself (decision of 15.09.2026).

    A second run on a folder whose version file has moved on is an ordinary
    second run: it knows nothing about a predecessor, names none, compares
    none and removes nothing.
    """
    desktop = Desktop(tmp_path / "Desktop")
    run_setup(calm, desktop, monkeypatch, unattended=True)
    settings = paths.config_path().read_bytes()
    paths.logs_dir().mkdir(parents=True, exist_ok=True)
    (paths.logs_dir() / "backrec.log").write_text("alte Zeilen", encoding="utf-8")
    (calm / "alt.py").write_text("alt", encoding="utf-8")

    (calm / paths.VERSION_FILE_NAME).write_text("2026.10.1\n", encoding="utf-8")
    result, printed = run_setup(calm, desktop, monkeypatch, unattended=True)

    assert result.version == "2026.10.1"
    assert "2026.09.1" not in printed
    assert (calm / "alt.py").is_file()
    assert paths.config_path().read_bytes() == settings
    # Appended to, never replaced: the setup writes its own technical lines into
    # the same file.
    assert (paths.logs_dir() / "backrec.log").read_text(encoding="utf-8").startswith("alte Zeilen")


def test_the_installed_version_is_recorded_even_with_an_open_point(
    calm, tmp_path, monkeypatch
) -> None:
    """A colleague with one red line would otherwise never get a yardstick."""
    desktop = Desktop(tmp_path / "Desktop")
    monkeypatch.setattr(doctor, "run", lambda *_a, **_k: [FAIL_CHECK])

    run_setup(calm, desktop, monkeypatch, unattended=True)

    assert control.read_installed_version() == "2026.09.1"

