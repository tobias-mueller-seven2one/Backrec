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

from backrec import control, doctor, external, paths, release, shortcut as shortcut_module, update
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


def test_the_closing_words_name_the_start_route_and_the_menu(
    calm, tmp_path, monkeypatch
) -> None:
    desktop = Desktop(tmp_path / "Desktop")

    _result, printed = run_setup(calm, desktop, monkeypatch, unattended=True)

    assert "Desktop" in printed
    assert "Zahnrad" in printed


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
    """The update helper stopped the application; it has to come back.

    One warning - a folder offline for a moment - would otherwise leave a
    colleague after an update with no window and no reason for it.
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


# --- Idempotence --------------------------------------------------------------


def test_a_second_run_leaves_the_settings_untouched(calm, tmp_path, monkeypatch) -> None:
    desktop = Desktop(tmp_path / "Desktop")
    run_setup(calm, desktop, monkeypatch, unattended=True)
    before = paths.config_path().read_bytes()

    result, printed = run_setup(calm, desktop, monkeypatch, unattended=True)

    assert result.ok
    assert result.code == 0
    assert paths.config_path().read_bytes() == before
    assert "unverändert übernommen" in printed


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


# --- Version change -----------------------------------------------------------


def test_a_new_version_names_both_and_keeps_settings_logs_and_state(
    calm, tmp_path, monkeypatch
) -> None:
    desktop = Desktop(tmp_path / "Desktop")
    run_setup(calm, desktop, monkeypatch, unattended=True)
    settings = paths.config_path().read_bytes()
    paths.logs_dir().mkdir(parents=True, exist_ok=True)
    (paths.logs_dir() / "backrec.log").write_text("alte Zeilen", encoding="utf-8")

    (calm / paths.VERSION_FILE_NAME).write_text("2026.10.1\n", encoding="utf-8")
    result, printed = run_setup(calm, desktop, monkeypatch, unattended=True)

    assert result.updated_from == "2026.09.1"
    assert "2026.09.1" in printed and "2026.10.1" in printed
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


# --- Removing files of the previous release -----------------------------------


def write_manifest(repo: Path, names: list[str]) -> None:
    entries = tuple(
        release.ManifestEntry(path=name, sha256="x" * 64, size=1) for name in names
    )
    update.write_installed_manifest(entries, "2026.09.1")


def test_a_file_of_the_previous_release_is_removed(calm, tmp_path, monkeypatch) -> None:
    desktop = Desktop(tmp_path / "Desktop")
    run_setup(calm, desktop, monkeypatch, unattended=True)

    (calm / "alt.py").write_text("alt", encoding="utf-8")
    write_manifest(calm, ["alt.py", "bleibt.py"])
    (calm / "bleibt.py").write_text("bleibt", encoding="utf-8")
    (calm / release.MANIFEST_NAME).write_text(
        '{"tool": "Backrec", "version": "2026.10.1", "files": '
        '[{"path": "bleibt.py", "sha256": "y", "size": 1}]}',
        encoding="utf-8",
    )
    (calm / paths.VERSION_FILE_NAME).write_text("2026.10.1\n", encoding="utf-8")

    _result, printed = run_setup(calm, desktop, monkeypatch, unattended=True)

    assert not (calm / "alt.py").exists()
    assert (calm / "bleibt.py").is_file()
    assert "nicht mehr benötigte" in printed


def test_the_clean_up_never_touches_environment_settings_or_icons(
    calm, tmp_path, monkeypatch
) -> None:
    desktop = Desktop(tmp_path / "Desktop")
    run_setup(calm, desktop, monkeypatch, unattended=True)

    (calm / "Backrec.lnk").write_bytes(b"lnk")
    (calm / "config.toml").write_text("meins", encoding="utf-8")
    write_manifest(calm, ["alt.py"])
    (calm / release.MANIFEST_NAME).write_text(
        '{"tool": "Backrec", "version": "2026.10.1", "files": []}', encoding="utf-8"
    )
    (calm / paths.VERSION_FILE_NAME).write_text("2026.10.1\n", encoding="utf-8")

    run_setup(calm, desktop, monkeypatch, unattended=True)

    assert (calm / ".venv" / "pyvenv.cfg").is_file()
    assert (calm / "Backrec.lnk").is_file()
    assert (calm / "config.toml").read_text(encoding="utf-8") == "meins"


def test_a_missing_previous_list_only_skips_the_clean_up(calm, tmp_path, monkeypatch) -> None:
    desktop = Desktop(tmp_path / "Desktop")
    run_setup(calm, desktop, monkeypatch, unattended=True)
    (calm / "fremde-datei.txt").write_text("gehoert mir", encoding="utf-8")
    (calm / paths.VERSION_FILE_NAME).write_text("2026.10.1\n", encoding="utf-8")

    result, _printed = run_setup(calm, desktop, monkeypatch, unattended=True)

    assert result.ok
    assert (calm / "fremde-datei.txt").is_file()


# --- Migration ----------------------------------------------------------------


def test_an_existing_env_is_taken_over_once_and_left_lying(
    calm, tmp_path, monkeypatch
) -> None:
    desktop = Desktop(tmp_path / "Desktop")
    legacy = calm / paths.LEGACY_CONFIG_FILE_NAME
    legacy.write_text(
        f"BACKREC_RECORDING_DIR={tmp_path / 'Alt' / 'Recording'}\n"
        f"BACKREC_TARGET_DIR={tmp_path / 'Alt' / 'Input'}\n",
        encoding="utf-8",
    )

    _result, printed = run_setup(calm, desktop, monkeypatch, unattended=True)

    written = paths.config_path().read_text(encoding="utf-8")
    assert str(tmp_path / "Alt" / "Recording") in written
    assert str(tmp_path / "Alt" / "Input") in written
    assert legacy.is_file()
    assert str(legacy) in printed
    assert "wirkt aber nicht mehr" in printed


def test_settings_that_were_already_there_still_get_their_folders(
    calm, tmp_path, monkeypatch
) -> None:
    """Neither of the two ways past the wizard would otherwise create them."""
    desktop = Desktop(tmp_path / "Desktop")
    recording = tmp_path / "Vorgegeben" / "Recording"
    target = tmp_path / "Vorgegeben" / "Input"
    write_config(
        paths.config_path(), {"recording_dir": str(recording), "target_dir": str(target)}, repo=calm
    )

    result, _printed = run_setup(calm, desktop, monkeypatch, unattended=True)

    assert result.ok
    assert recording.is_dir()
    assert target.is_dir()


def test_a_migrated_env_gets_its_folders_too(calm, tmp_path, monkeypatch) -> None:
    desktop = Desktop(tmp_path / "Desktop")
    recording = tmp_path / "Alt" / "Recording"
    target = tmp_path / "Alt" / "Input"
    (calm / paths.LEGACY_CONFIG_FILE_NAME).write_text(
        f"BACKREC_RECORDING_DIR={recording}\nBACKREC_TARGET_DIR={target}\n", encoding="utf-8"
    )

    result, _printed = run_setup(calm, desktop, monkeypatch, unattended=True)

    assert result.ok
    assert recording.is_dir()
    assert target.is_dir()


def test_folders_that_cannot_be_created_end_the_run(calm, tmp_path, monkeypatch) -> None:
    desktop = Desktop(tmp_path / "Desktop")
    blocker = tmp_path / "blocker"
    blocker.write_text("", encoding="utf-8")
    write_config(
        paths.config_path(),
        {"recording_dir": str(blocker / "Recording"), "target_dir": str(tmp_path / "Input")},
        repo=calm,
    )

    result, printed = run_setup(calm, desktop, monkeypatch, unattended=True)

    assert not result.ok
    assert result.code == 2
    assert "lassen sich nicht anlegen" in printed


def test_an_existing_settings_file_beats_an_old_env(calm, tmp_path, monkeypatch) -> None:
    desktop = Desktop(tmp_path / "Desktop")
    (calm / paths.LEGACY_CONFIG_FILE_NAME).write_text(
        "BACKREC_RECORDING_DIR=D:\\Alt\nBACKREC_TARGET_DIR=D:\\Alt\n", encoding="utf-8"
    )
    write_config(
        paths.config_path(),
        {"recording_dir": str(tmp_path / "Neu" / "R"), "target_dir": str(tmp_path / "Neu" / "I")},
        repo=calm,
    )
    before = paths.config_path().read_bytes()

    run_setup(calm, desktop, monkeypatch, unattended=True)

    assert paths.config_path().read_bytes() == before
