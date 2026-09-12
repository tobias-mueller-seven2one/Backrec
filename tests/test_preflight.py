"""The checked start sequence: every cause on its own, and in the right order."""

from __future__ import annotations

from pathlib import Path

from backrec import external, instance, paths, preflight
from backrec.wizard import write_config

USABLE = external.FfmpegState(found_at=r"C:\tools\ffmpeg.exe", runs=True, version="7.1.1")
MISSING = external.FfmpegState(found_at=None, runs=False, detail="nicht im Suchpfad gefunden")
BROKEN = external.FfmpegState(found_at=r"C:\tools\ffmpeg.exe", runs=False, detail="der Aufruf scheitert")


def _write(config_values: dict[str, str], repo: Path) -> Path:
    target = paths.config_path()
    write_config(target, config_values, repo=repo)
    return target


def test_missing_configuration_names_the_setup(tmp_path: Path) -> None:
    result = preflight.run()

    assert not result.ok
    assert result.problem is not None
    assert "Setup.cmd" in result.problem.next_step


def test_unreadable_configuration_names_file_and_cause(tmp_path: Path) -> None:
    target = paths.config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("recording_dir = 'C:\\x\n", encoding="utf-8")

    result = preflight.run()

    assert not result.ok
    assert result.problem is not None
    assert str(target) in result.problem.cause


def test_missing_mandatory_key_is_reported(tmp_path: Path, repo: Path) -> None:
    target = paths.config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"recording_dir = '{tmp_path / 'Recording'}'\n", encoding="utf-8")

    result = preflight.run()

    assert not result.ok
    assert result.problem is not None
    assert "target_dir" in result.problem.cause


def test_unusable_recording_directory_names_path_and_cause(
    tmp_path: Path, repo: Path, config_values: dict[str, str]
) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("", encoding="utf-8")
    values = dict(config_values, recording_dir=str(blocker / "Recording"))
    _write(values, repo)

    result = preflight.run()

    assert not result.ok
    assert result.problem is not None
    assert str(blocker / "Recording") in result.problem.cause


def test_unusable_target_directory_names_the_chain(
    tmp_path: Path, repo: Path, config_values: dict[str, str]
) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("", encoding="utf-8")
    values = dict(config_values, target_dir=str(blocker / "Input"))
    _write(values, repo)

    result = preflight.run(ffmpeg_state=USABLE)

    assert not result.ok
    assert result.problem is not None
    assert "nächste" in result.problem.next_step


def test_missing_ffmpeg_is_a_cause_of_its_own() -> None:
    problem = preflight.check_ffmpeg(MISSING)

    assert problem is not None
    assert "fehlt" in problem.cause
    assert "Setup.cmd" in problem.next_step


def test_present_but_unusable_ffmpeg_is_a_different_cause() -> None:
    problem = preflight.check_ffmpeg(BROKEN)

    assert problem is not None
    assert "starten" in problem.cause
    assert problem.cause != preflight.check_ffmpeg(MISSING).cause


def test_usable_ffmpeg_is_no_problem() -> None:
    assert preflight.check_ffmpeg(USABLE) is None


def test_successful_run_creates_both_directories(
    repo: Path, config_values: dict[str, str]
) -> None:
    _write(config_values, repo)

    result = preflight.run(ffmpeg_state=USABLE)

    assert result.ok
    assert result.config is not None
    assert result.config.recording_dir.is_dir()
    assert result.config.target_dir.is_dir()


def test_successful_run_leaves_no_probe_behind(repo: Path, config_values: dict[str, str]) -> None:
    _write(config_values, repo)

    result = preflight.run(ffmpeg_state=USABLE)

    assert result.config is not None
    assert not (result.config.recording_dir / preflight.PROBE_NAME).exists()


def test_a_left_over_stop_request_is_cleared(repo: Path, config_values: dict[str, str]) -> None:
    _write(config_values, repo)
    instance.request_stop()

    preflight.run(ffmpeg_state=USABLE)

    assert not instance.stop_requested()


def test_importing_the_package_creates_no_directory(tmp_path: Path, monkeypatch) -> None:
    """The retired module level made both folders while being imported."""
    import importlib

    monkeypatch.setenv("BACKREC_RECORDING_DIR", str(tmp_path / "Neu" / "Recording"))
    monkeypatch.setenv("BACKREC_TARGET_DIR", str(tmp_path / "Neu" / "Input"))

    for name in ("backrec.config", "backrec.preflight", "backrec.app"):
        importlib.reload(importlib.import_module(name))

    assert not (tmp_path / "Neu").exists()
