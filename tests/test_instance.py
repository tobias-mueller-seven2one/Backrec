"""The record of the running instance - and every way it may be invalid."""

from __future__ import annotations

import json
import os
import time

import psutil
import pytest

from backrec import instance, paths


def write_raw(path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_a_record_of_this_process_counts_as_valid(tmp_path):
    record = instance.write_record(repo=tmp_path)

    assert instance.live_process(record, tmp_path) is not None
    assert instance.running_instance(repo=tmp_path) is not None
    assert paths.pid_record_path().is_file()


def test_a_missing_record_is_no_running_instance(tmp_path):
    assert instance.read_record() is None
    assert instance.running_instance(repo=tmp_path) is None


def test_a_damaged_record_counts_as_orphaned(tmp_path):
    target = paths.pid_record_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{kein gueltiges", encoding="utf-8")

    assert instance.read_record() is None


def test_a_record_without_a_process_id_counts_as_orphaned():
    write_raw(paths.pid_record_path(), {"create_time": 1.0, "repo": "x"})

    assert instance.read_record() is None


def test_a_record_of_a_finished_process_is_taken_over(tmp_path):
    write_raw(
        paths.pid_record_path(),
        {"pid": _free_pid(), "create_time": 1.0, "started": "", "repo": str(tmp_path)},
    )

    assert instance.running_instance(repo=tmp_path) is None


def test_a_reused_process_id_is_recognised_by_its_creation_time(tmp_path):
    write_raw(
        paths.pid_record_path(),
        {"pid": os.getpid(), "create_time": 1.0, "started": "", "repo": str(tmp_path)},
    )

    assert instance.running_instance(repo=tmp_path) is None


def test_a_record_without_a_creation_time_counts_as_orphaned(tmp_path):
    write_raw(
        paths.pid_record_path(),
        {"pid": os.getpid(), "create_time": 0, "started": "", "repo": str(tmp_path)},
    )

    assert instance.running_instance(repo=tmp_path) is None


def test_a_record_of_another_installation_blocks_nothing(tmp_path):
    other = tmp_path / "zweite-installation"
    write_raw(
        paths.pid_record_path(),
        {
            "pid": os.getpid(),
            "create_time": psutil.Process().create_time(),
            "started": "",
            "repo": str(other),
        },
    )

    assert instance.running_instance(repo=tmp_path) is None
    assert instance.foreign_repo(instance.read_record(), tmp_path) == str(other)


def test_the_own_record_is_never_a_foreign_installation(tmp_path):
    record = instance.write_record(repo=tmp_path)

    assert instance.foreign_repo(record, tmp_path) is None


def test_the_repository_comparison_ignores_upper_and_lower_case(tmp_path):
    record = instance.InstanceRecord(
        pid=os.getpid(), create_time=1.0, started="", repo=str(tmp_path).upper()
    )

    assert instance.belongs_to_repo(record, tmp_path)


def test_clearing_a_record_that_is_not_there_is_harmless():
    instance.clear_record()
    instance.clear_record()


def test_the_stop_request_is_a_file_that_can_be_taken_back():
    assert not instance.stop_requested()

    written = instance.request_stop()
    assert written.is_file()
    assert instance.stop_requested()

    instance.clear_stop_request()
    assert not instance.stop_requested()


# --- The sign of life of the closing sequence ---------------------------------


def test_a_written_beat_is_read_back():
    assert instance.finishing_beat() is None
    assert not instance.is_finishing()

    instance.mark_finishing(7)

    assert instance.finishing_beat() == 7
    assert instance.is_finishing()

    instance.clear_finishing()
    assert instance.finishing_beat() is None


def test_an_unreadable_sign_of_life_counts_as_none():
    """A stop consulting this file must never fail because of it."""
    paths.finishing_marker_path().parent.mkdir(parents=True, exist_ok=True)
    paths.finishing_marker_path().write_text("kein Takt", encoding="utf-8")

    assert instance.finishing_beat() is None


def test_clearing_a_sign_of_life_that_is_not_there_is_harmless():
    instance.clear_finishing()
    instance.clear_finishing()


def test_the_beacon_keeps_beating_and_takes_its_file_with_it():
    with instance.FinishingBeacon(interval_seconds=0.01):
        first = instance.finishing_beat()
        assert first is not None

        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            current = instance.finishing_beat()
            if current is not None and current > first:
                break
            time.sleep(0.01)

        assert current is not None and current > first, "der Takt steht still"

    assert instance.finishing_beat() is None


def test_the_beacon_ends_its_sign_of_life_after_a_failure():
    """Success and failure leave the closing sequence through the same door."""
    with pytest.raises(RuntimeError):
        with instance.FinishingBeacon(interval_seconds=0.01):
            assert instance.is_finishing()
            raise RuntimeError("kaputt")

    assert not instance.is_finishing()


def test_the_beacon_never_ends_the_work_it_only_describes(monkeypatch):
    def refuse(_beat, _path=None):
        raise OSError("Datentraeger voll")

    monkeypatch.setattr(instance, "mark_finishing", refuse)

    with instance.FinishingBeacon(interval_seconds=0.01):
        pass


def test_the_window_search_survives_a_machine_without_the_windows_api(monkeypatch):
    """A second start still reports and still exits - with or without a window."""
    monkeypatch.setattr(instance, "window_handles_of", lambda pid: [])

    assert instance.raise_window(os.getpid()) is False


def _free_pid() -> int:
    """A process id that is certainly not in use right now."""
    taken = set(psutil.pids())
    for candidate in range(40000, 60000, 2):
        if candidate not in taken:
            return candidate
    raise AssertionError("kein freier Wert gefunden")
