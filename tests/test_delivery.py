"""What arrives in the target folder - and, above all, what never does.

Every failure of `finish` has to leave the target folder empty: the tool
downstream reads every file it finds there, and a raw take that slipped through
would be transcribed as a second conversation (design D8).
"""

from __future__ import annotations

from pathlib import Path

from backrec import delivery
from backrec.merge import MIN_USABLE_BYTES

TIMESTAMP = "2026-09-12_10-00-00"


def _take(path: Path, size: int = MIN_USABLE_BYTES * 2) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\0" * size)
    return path


def _folders(tmp_path: Path) -> tuple[Path, Path]:
    recording_dir = tmp_path / "Recording"
    target_dir = tmp_path / "Input"
    recording_dir.mkdir(parents=True, exist_ok=True)
    target_dir.mkdir(parents=True, exist_ok=True)
    return recording_dir, target_dir


def _mixer(ok: bool = True, detail: str = "", size: int = MIN_USABLE_BYTES * 3):
    def run(_mic: Path, _system: Path, output: Path) -> tuple[bool, str]:
        if ok:
            output.write_bytes(b"\0" * size)
        return ok, detail

    return run


def _finish(tmp_path: Path, **kwargs) -> tuple[delivery.Outcome, Path, Path]:
    recording_dir, target_dir = _folders(tmp_path)
    mic = _take(recording_dir / f"mic_{TIMESTAMP}.wav", kwargs.pop("mic_size", MIN_USABLE_BYTES * 2))
    system = _take(
        recording_dir / f"system_{TIMESTAMP}.wav", kwargs.pop("system_size", MIN_USABLE_BYTES * 2)
    )
    outcome = delivery.finish(
        mic,
        system,
        TIMESTAMP,
        recording_dir,
        target_dir,
        merge_fn=kwargs.pop("merge_fn", _mixer()),
    )
    return outcome, recording_dir, target_dir


def test_a_successful_recording_leaves_exactly_one_file_in_the_target(tmp_path: Path) -> None:
    outcome, _recording_dir, target_dir = _finish(tmp_path)

    assert outcome.ok
    delivered = list(target_dir.iterdir())
    assert len(delivered) == 1
    assert delivered[0].name == f"{TIMESTAMP}.wav"


def test_both_takes_and_the_mix_stay_in_the_recording_folder(tmp_path: Path) -> None:
    outcome, recording_dir, _target_dir = _finish(tmp_path)

    assert outcome.ok
    assert (recording_dir / f"mic_{TIMESTAMP}.wav").is_file()
    assert (recording_dir / f"system_{TIMESTAMP}.wav").is_file()
    assert (recording_dir / f"{TIMESTAMP}.wav").is_file()


def test_an_existing_file_of_that_name_is_never_overwritten(tmp_path: Path) -> None:
    recording_dir, target_dir = _folders(tmp_path)
    occupied = target_dir / f"{TIMESTAMP}.wav"
    occupied.write_bytes(b"altbestand")

    outcome, _recording_dir, target_dir = _finish(tmp_path)

    assert outcome.ok
    assert occupied.read_bytes() == b"altbestand"
    assert outcome.destination is not None
    assert outcome.destination.name == f"{TIMESTAMP}_1.wav"


def test_a_missing_mixer_is_its_own_cause_and_delivers_nothing(tmp_path: Path) -> None:
    outcome, recording_dir, target_dir = _finish(
        tmp_path, merge_fn=_mixer(ok=False, detail=delivery.MISSING_MIXER_MARKER)
    )

    assert not outcome.ok
    assert "Zusammenmischen" in outcome.cause
    assert list(target_dir.iterdir()) == []
    assert len(list(recording_dir.glob("*.wav"))) == 2


def test_a_failed_mixing_run_delivers_nothing(tmp_path: Path) -> None:
    outcome, _recording_dir, target_dir = _finish(
        tmp_path, merge_fn=_mixer(ok=False, detail="Invalid data found when processing input")
    )

    assert not outcome.ok
    assert outcome.cause != "Das Programm zum Zusammenmischen ist nicht aufrufbar."
    assert list(target_dir.iterdir()) == []


def test_an_unusably_small_mix_delivers_nothing(tmp_path: Path) -> None:
    outcome, _recording_dir, target_dir = _finish(tmp_path, merge_fn=_mixer(size=10))

    assert not outcome.ok
    assert list(target_dir.iterdir()) == []


def test_a_missing_take_delivers_nothing_and_keeps_the_other(tmp_path: Path) -> None:
    recording_dir, target_dir = _folders(tmp_path)
    system = _take(recording_dir / f"system_{TIMESTAMP}.wav")

    outcome = delivery.finish(None, system, TIMESTAMP, recording_dir, target_dir, merge_fn=_mixer())

    assert not outcome.ok
    assert list(target_dir.iterdir()) == []
    assert system.is_file()


def test_a_take_that_is_too_small_delivers_nothing(tmp_path: Path) -> None:
    outcome, _recording_dir, target_dir = _finish(tmp_path, system_size=10)

    assert not outcome.ok
    assert list(target_dir.iterdir()) == []


def test_a_copy_that_came_out_different_counts_as_a_failure(tmp_path: Path, monkeypatch) -> None:
    def shrinking_copy(source: str, destination: str) -> None:
        Path(destination).write_bytes(b"zu kurz")

    monkeypatch.setattr(delivery.shutil, "copy2", shrinking_copy)

    outcome, _recording_dir, _target_dir = _finish(tmp_path)

    assert not outcome.ok
    assert outcome.destination is None


def test_every_failure_names_the_recording_folder_as_the_whereabouts(tmp_path: Path) -> None:
    outcome, recording_dir, _target_dir = _finish(tmp_path, merge_fn=_mixer(ok=False, detail="x"))

    assert str(recording_dir) in outcome.whereabouts


def test_a_failure_carries_a_status_line_short_enough_for_the_window(tmp_path: Path) -> None:
    outcome, _recording_dir, _target_dir = _finish(tmp_path, merge_fn=_mixer(ok=False, detail="x"))

    assert 0 < len(outcome.status) <= 32


def test_discarding_removes_both_takes_and_touches_no_target(tmp_path: Path) -> None:
    recording_dir, target_dir = _folders(tmp_path)
    mic = _take(recording_dir / f"mic_{TIMESTAMP}.wav")
    system = _take(recording_dir / f"system_{TIMESTAMP}.wav")

    assert delivery.discard(mic, system)
    assert not mic.exists()
    assert not system.exists()
    assert list(target_dir.iterdir()) == []


def test_discarding_reports_a_take_it_could_not_remove(tmp_path: Path, monkeypatch) -> None:
    recording_dir, target_dir = _folders(tmp_path)
    mic = _take(recording_dir / f"mic_{TIMESTAMP}.wav")

    def refuse(_self, missing_ok: bool = False) -> None:
        raise OSError(32, "Die Datei wird von einem anderen Programm verwendet")

    monkeypatch.setattr(Path, "unlink", refuse)

    assert not delivery.discard(mic)
    assert list(target_dir.iterdir()) == []


def test_discarding_without_takes_is_harmless() -> None:
    assert delivery.discard(None, None)
