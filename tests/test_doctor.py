"""The diagnosis: every finding on its own, and the promise that it changes nothing.

`evaluate` is a pure function, so an empty disk, a missing playback device and
an environment that no longer matches the locked list can all be handed to it as
facts rather than produced on the machine.
"""

from __future__ import annotations

from pathlib import Path

from backrec import doctor, external, paths, shortcut as shortcut_module
from backrec.wizard import write_config

USABLE_FFMPEG = external.FfmpegState(found_at=r"C:\tools\ffmpeg.exe", runs=True, version="8.1.2")


def facts(**overrides) -> doctor.Observations:
    """A machine on which everything is in order - one fact at a time changed."""
    base = doctor.Observations(
        installed_version="2026.09.1",
        repo_path=Path(r"C:\Backrec"),
        repo_recognised=True,
        uv_path=r"C:\uv\uv.exe",
        python_version="3.11.9",
        required_python="3.11",
        venv_present=True,
        venv_matches_lock=True,
        config_path=Path(r"C:\cfg\config.toml"),
        config_exists=True,
        ffmpeg=USABLE_FFMPEG,
        device_detection=True,
        microphone="Mikrofon (Headset)",
        speaker="Lautsprecher (Realtek)",
        directories=(
            doctor.DirectoryFact(
                "Aufnahme",
                Path(r"C:\Aufnahmen\Recording"),
                exists=True,
                writable=True,
                free_bytes=doctor.SPACE_RESERVE_BYTES * 5,
            ),
            doctor.DirectoryFact(
                "Ziel",
                Path(r"C:\Aufnahmen\Input"),
                exists=True,
                writable=True,
                free_bytes=doctor.SPACE_RESERVE_BYTES * 5,
            ),
        ),
        shortcut=shortcut_module.ShortcutStatus(
            path=Path(r"C:\Desktop\Backrec.lnk"),
            exists=True,
            readable=True,
            belongs_here=True,
            target_exists=True,
            target_current=True,
        ),
        logs_dir=Path(r"C:\logs"),
        logs_exists=True,
        logs_writable=True,
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def find(checks, key: str) -> doctor.Check:
    for check in checks:
        if check.key == key:
            return check
    raise AssertionError(f"Befund '{key}' fehlt")


# --- Shape of the result ------------------------------------------------------


def test_a_clean_machine_ends_with_exit_code_zero() -> None:
    checks = doctor.evaluate(facts())

    assert doctor.exit_code(checks) == 0
    assert not doctor.has_failure(checks)


def test_a_warning_alone_never_changes_the_exit_code() -> None:
    checks = doctor.evaluate(facts(orphan_record=True, stop_request=True))

    assert any(check.level is doctor.Level.WARN for check in checks)
    assert doctor.exit_code(checks) == 0


def test_one_failure_makes_the_exit_code_non_zero() -> None:
    checks = doctor.evaluate(facts(uv_path=None))

    assert doctor.exit_code(checks) != 0
    assert find(checks, "runtime.uv").next_step


def test_every_check_carries_exactly_one_level_and_a_cause() -> None:
    for check in doctor.evaluate(facts()):
        assert isinstance(check.level, doctor.Level)
        assert check.cause


def test_the_machine_readable_form_holds_the_same_checks() -> None:
    checks = doctor.evaluate(facts())

    payload = doctor.as_json(checks)

    assert len(payload["checks"]) == len(checks)
    assert {"id", "category", "level", "cause", "next_step"} <= set(payload["checks"][0])
    assert payload["result"] == "pass"


def test_the_readable_form_groups_by_category() -> None:
    lines = doctor.render_text(doctor.evaluate(facts()))

    assert doctor.CATEGORY_RUNTIME in lines
    assert doctor.CATEGORY_DEVICES in lines


# --- Runtime and environment --------------------------------------------------


def test_a_missing_environment_names_the_setup() -> None:
    check = find(doctor.evaluate(facts(venv_present=False)), "runtime.environment")

    assert check.level is doctor.Level.FAIL
    assert "Setup.cmd" in check.next_step


def test_a_different_python_version_names_both() -> None:
    check = find(doctor.evaluate(facts(python_version="3.10.14")), "runtime.python")

    assert check.level is doctor.Level.FAIL
    assert "3.10.14" in check.cause and "3.11" in check.cause


def test_an_environment_that_no_longer_matches_is_a_failure() -> None:
    check = find(doctor.evaluate(facts(venv_matches_lock=False)), "runtime.environment")

    assert check.level is doctor.Level.FAIL
    assert "Setup.cmd" in check.next_step


def test_an_unanswerable_match_is_a_warning_and_not_a_failure() -> None:
    check = find(doctor.evaluate(facts(venv_matches_lock=None)), "runtime.environment")

    assert check.level is doctor.Level.WARN


# --- Configuration ------------------------------------------------------------


def test_a_missing_mandatory_key_names_the_key() -> None:
    check = find(doctor.evaluate(facts(missing_required=("target_dir",))), "config.required")

    assert check.level is doctor.Level.FAIL
    assert "target_dir" in check.cause


def test_an_unknown_key_is_a_warning_and_is_never_removed() -> None:
    check = find(doctor.evaluate(facts(unknown_keys=("farbe",))), "config.unknown")

    assert check.level is doctor.Level.WARN
    assert "farbe" in check.cause
    assert "geändert wird hier nichts" in check.next_step


def test_a_key_new_in_the_template_is_a_warning_and_is_not_added() -> None:
    check = find(doctor.evaluate(facts(missing_keys=("log_level",))), "config.template")

    assert check.level is doctor.Level.WARN
    assert "log_level" in check.cause


def test_a_key_new_in_the_template_is_no_handwork() -> None:
    """The setup adds it; the diagnosis says so instead of handing over work."""
    check = find(doctor.evaluate(facts(missing_keys=("log_level",))), "config.template")

    assert check.next_step == "Setup.cmd doppelklicken ergänzt sie."
    assert "von Hand" not in check.next_step


def test_the_layer_a_value_came_from_is_named() -> None:
    check = find(
        doctor.evaluate(facts(origins={"target_dir": "Umgebungsvariable"})), "config.origins"
    )

    assert "Umgebungsvariable" in check.cause


def test_an_unreadable_configuration_is_the_only_configuration_finding() -> None:
    checks = doctor.evaluate(facts(config_error="Zeile 3 ist nicht lesbar"))

    found = [check for check in checks if check.category == doctor.CATEGORY_CONFIG]
    assert len(found) == 1
    assert found[0].level is doctor.Level.FAIL


# --- ffmpeg -------------------------------------------------------------------


def test_a_usable_ffmpeg_is_reported_with_its_version() -> None:
    check = find(doctor.evaluate(facts()), "external.ffmpeg")

    assert check.level is doctor.Level.PASS
    assert "8.1.2" in check.cause


def test_a_missing_ffmpeg_names_the_setup() -> None:
    missing = external.FfmpegState(found_at=None, runs=False)
    check = find(doctor.evaluate(facts(ffmpeg=missing)), "external.ffmpeg")

    assert check.level is doctor.Level.FAIL
    assert "Setup.cmd" in check.next_step


def test_found_but_not_callable_is_a_different_cause() -> None:
    broken = external.FfmpegState(found_at=r"C:\tools\ffmpeg.exe", runs=False)
    present = find(doctor.evaluate(facts(ffmpeg=broken)), "external.ffmpeg")
    absent = find(
        doctor.evaluate(facts(ffmpeg=external.FfmpegState(found_at=None, runs=False))),
        "external.ffmpeg",
    )

    assert present.level is doctor.Level.FAIL
    assert present.cause != absent.cause
    assert "Aufruf" in present.cause


# --- Devices ------------------------------------------------------------------


def test_both_devices_are_named_by_name() -> None:
    checks = doctor.evaluate(facts())

    assert "Headset" in find(checks, "devices.microphone").cause
    assert "Realtek" in find(checks, "devices.speaker").cause


def test_a_missing_playback_device_is_a_failure_that_names_the_system_recording() -> None:
    check = find(doctor.evaluate(facts(speaker=None)), "devices.speaker")

    assert check.level is doctor.Level.FAIL
    assert "Systemton" in check.next_step


def test_an_unavailable_detection_is_its_own_finding() -> None:
    checks = doctor.evaluate(facts(device_detection=False, microphone=None, speaker=None))

    detection = find(checks, "devices.detection")
    assert detection.level is doctor.Level.FAIL
    assert "Erkennung" in detection.cause
    assert not [check for check in checks if check.key == "devices.speaker"]


# --- Directories and disk space -----------------------------------------------


def test_a_missing_target_folder_names_the_next_tool() -> None:
    missing = (
        doctor.DirectoryFact("Ziel", Path(r"C:\weg"), exists=False, writable=False),
    )
    check = find(doctor.evaluate(facts(directories=missing)), "directory.Ziel")

    assert check.level is doctor.Level.FAIL
    assert "nächste Werkzeug" in check.next_step


def test_an_unwritable_folder_is_a_failure() -> None:
    blocked = (doctor.DirectoryFact("Ziel", Path(r"C:\voll"), exists=True, writable=False),)
    check = find(doctor.evaluate(facts(directories=blocked)), "directory.Ziel")

    assert check.level is doctor.Level.FAIL


def test_little_free_space_warns_and_names_the_need_per_minute() -> None:
    tight = (
        doctor.DirectoryFact(
            "Aufnahme",
            Path(r"C:\Aufnahmen"),
            exists=True,
            writable=True,
            free_bytes=doctor.SPACE_RESERVE_BYTES // 2,
        ),
    )
    check = find(doctor.evaluate(facts(directories=tight)), "space.Aufnahme")

    assert check.level is doctor.Level.WARN
    assert str(doctor.MEGABYTES_PER_MINUTE) in check.next_step


def test_a_recording_folder_in_the_cloud_warns() -> None:
    synced = (
        doctor.DirectoryFact(
            "Aufnahme",
            Path(r"C:\Wolke\Recording"),
            exists=True,
            writable=True,
            free_bytes=doctor.SPACE_RESERVE_BYTES * 3,
            in_cloud=True,
        ),
    )
    check = find(doctor.evaluate(facts(directories=synced)), "cloud.Aufnahme")

    assert check.level is doctor.Level.WARN


# --- Shortcut and state -------------------------------------------------------


def test_a_shortcut_of_another_installation_is_named_as_such() -> None:
    foreign = shortcut_module.ShortcutStatus(
        path=Path(r"C:\Desktop\Backrec.lnk"), exists=True, readable=True, belongs_here=False
    )
    check = find(doctor.evaluate(facts(shortcut=foreign)), "shortcut.entry")

    assert "anderen Installation" in check.cause


def test_a_shortcut_whose_target_is_gone_is_a_failure() -> None:
    dangling = shortcut_module.ShortcutStatus(
        path=Path(r"C:\Desktop\Backrec.lnk"),
        exists=True,
        readable=True,
        belongs_here=True,
        target_exists=False,
    )
    check = find(doctor.evaluate(facts(shortcut=dangling)), "shortcut.entry")

    assert check.level is doctor.Level.FAIL


def test_a_shortcut_on_the_retired_start_route_is_a_warning() -> None:
    outdated = shortcut_module.ShortcutStatus(
        path=Path(r"C:\Desktop\Backrec.lnk"),
        exists=True,
        readable=True,
        belongs_here=True,
        target_exists=True,
        target_current=False,
    )
    check = find(doctor.evaluate(facts(shortcut=outdated)), "shortcut.entry")

    assert check.level is doctor.Level.WARN
    assert "abgelösten Startweg" in check.cause


def test_an_orphaned_record_is_a_warning_and_nothing_is_tidied() -> None:
    check = find(doctor.evaluate(facts(orphan_record=True)), "state.record")

    assert check.level is doctor.Level.WARN
    assert "nächste Start" in check.next_step


def test_an_unwritable_log_folder_is_a_failure_with_its_path() -> None:
    check = find(doctor.evaluate(facts(logs_writable=False)), "state.logs")

    assert check.level is doctor.Level.FAIL
    assert r"C:\logs" in check.cause


def test_a_log_folder_that_does_not_exist_yet_is_no_failure() -> None:
    check = find(doctor.evaluate(facts(logs_exists=False, logs_writable=False)), "state.logs")

    assert check.level is doctor.Level.WARN


def test_a_left_over_folder_of_a_superseded_version_warns_without_removing() -> None:
    check = find(
        doctor.evaluate(facts(stale_folders=(Path(r"C:\Backrec.old-2026.08.1"),))),
        "state.stale_folders",
    )

    assert check.level is doctor.Level.WARN
    assert "löschen" in check.next_step
    assert "fasst ihn nicht an" in check.next_step


def test_piled_up_reports_warn_with_their_number() -> None:
    check = find(doctor.evaluate(facts(report_count=doctor.REPORT_LIMIT + 5)), "state.reports")

    assert check.level is doctor.Level.WARN
    assert str(doctor.REPORT_LIMIT + 5) in check.cause


def test_a_left_over_earlier_settings_file_warns() -> None:
    check = find(doctor.evaluate(facts(legacy_env=Path(r"C:\Backrec\.env"))), "state.legacy")

    assert check.level is doctor.Level.WARN


# --- Read-only ----------------------------------------------------------------


def test_the_probe_leaves_no_file_behind(tmp_path: Path) -> None:
    assert doctor.is_writable(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_a_folder_that_does_not_exist_is_never_created_by_the_probe(tmp_path: Path) -> None:
    missing = tmp_path / "gibt-es-nicht"

    assert not doctor.is_writable(missing)
    assert not missing.exists()


def test_a_full_run_against_an_incomplete_installation_writes_nothing(tmp_path: Path) -> None:
    before = sorted(path.name for path in tmp_path.iterdir())

    checks = doctor.run(with_devices=False)

    assert checks
    assert sorted(path.name for path in tmp_path.iterdir()) == before


def test_a_full_run_creates_no_configured_directory(
    tmp_path: Path, repo: Path, config_values: dict[str, str]
) -> None:
    write_config(paths.config_path(), config_values, repo=repo)

    doctor.run(with_devices=False)

    assert not Path(config_values["recording_dir"]).exists()
    assert not Path(config_values["target_dir"]).exists()


# --- Report -------------------------------------------------------------------


def test_the_report_header_names_tool_version_folder_settings_and_time(tmp_path: Path) -> None:
    lines = doctor.report_lines(doctor.evaluate(facts()))
    joined = "\n".join(lines)

    assert paths.TOOL_NAME in lines[0]
    assert "Ordner des Werkzeugs" in joined
    assert "Einstellungen" in joined
    assert "Erstellt am" in joined


def test_a_second_report_never_overwrites_the_first(tmp_path: Path, monkeypatch) -> None:
    from datetime import datetime as real

    moments = [real(2026, 9, 12, 10, 0, 0), real(2026, 9, 12, 10, 0, 1)]

    class SteppingClock:
        """One moment per report; the header reads the same one as the file name."""

        calls = 0

        @classmethod
        def now(cls):
            moment = moments[min(cls.calls // 2, len(moments) - 1)]
            cls.calls += 1
            return moment

    monkeypatch.setattr(doctor, "datetime", SteppingClock)

    first = doctor.write_report(doctor.evaluate(facts()), tmp_path)
    content = first.read_bytes()
    second = doctor.write_report(doctor.evaluate(facts()), tmp_path)

    assert first != second
    assert first.read_bytes() == content


def test_the_report_is_written_for_the_default_editor(tmp_path: Path) -> None:
    target = doctor.write_report(doctor.evaluate(facts()), tmp_path)
    raw = target.read_bytes()

    assert raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" in raw


def test_writing_the_report_is_the_only_change(tmp_path: Path) -> None:
    doctor.write_report(doctor.evaluate(facts()), tmp_path)

    assert len(list(tmp_path.iterdir())) == 1


# --- Leftover icons on the desktop (H5) ---------------------------------------


def test_a_leftover_icon_is_a_failure() -> None:
    """A double click on it prints a notice instead of opening the window."""
    checks = doctor.evaluate(facts(shortcut_stale=(Path(r"C:\Desktop\Start_Recorder.lnk"),)))
    check = find(checks, "shortcut.stale")

    assert check.level is doctor.Level.FAIL
    assert "zeigt auf eine Datei, die es nicht mehr gibt" in check.cause
    assert "Start_Recorder.lnk" in check.cause
    assert doctor.exit_code(checks) == 1


def test_a_leftover_is_reported_next_to_a_working_icon() -> None:
    """Both can be true at once, and the leftover is the one that misleads."""
    checks = doctor.evaluate(facts(shortcut_stale=(Path("alt.lnk"),)))

    assert find(checks, "shortcut.entry").level is doctor.Level.PASS
    assert find(checks, "shortcut.stale").level is doctor.Level.FAIL


def test_without_leftovers_nothing_is_reported() -> None:
    assert not [check for check in doctor.evaluate(facts()) if check.key == "shortcut.stale"]
