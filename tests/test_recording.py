"""The recording core: pacing of the write loop and the device switch.

The doubles are shared with later tests: `PacedStream` reproduces the measured
fault (a read that returns at once instead of blocking) and `FakeInputStream`
stands in for `sd.InputStream` in both the blocking and the callback mode, so
the device-switch test stays valid when the microphone moves to callbacks.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
import pytest
import soundfile as sf

from backrec import recording
from backrec.recording import SAMPLERATE, BaseRecorder, MicRecorder, SystemRecorder

TEST_CHUNK_SEC = 0.02
TEST_DEVICE_POLL_SEC = 0.1
TEST_CLOCK_GRACE_SEC = 0.1
TEST_MIC_STALL_SEC = 0.2
TIMING_TOLERANCE = 1.2
REGULAR_VALUE = 0.25
RACING_VALUE = 0.75


class _NoFlags:
    """Falsy stand-in for `sd.CallbackFlags`."""

    def __bool__(self) -> bool:
        return False


class PacedStream:
    """Context-manager stream whose `read` blocks for `regular_seconds`, then returns at once.

    `regular_seconds=None` never races, `0.0` races from the first read.
    `speed` scales the blocking time (0.999 delivers 0.1 % faster than real time).
    """

    def __init__(
        self,
        samplerate: int,
        channels: int,
        regular_seconds: Optional[float] = None,
        speed: float = 1.0,
        racing_value: float = REGULAR_VALUE,
    ) -> None:
        self.samplerate = samplerate
        self.channels = channels
        self.regular_seconds = regular_seconds
        self.speed = speed
        self.racing_value = racing_value
        self.created_at = time.monotonic()

    def __enter__(self) -> "PacedStream":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        return None

    def is_racing(self) -> bool:
        if self.regular_seconds is None:
            return False
        return time.monotonic() - self.created_at >= self.regular_seconds

    def read(self, frames: int) -> tuple[np.ndarray, bool]:
        if not self.is_racing():
            time.sleep(frames / self.samplerate * self.speed)
            return np.full((frames, self.channels), REGULAR_VALUE, dtype=np.float32), False
        return np.full((frames, self.channels), self.racing_value, dtype=np.float32), False


def regular_stream(samplerate: int, channels: int) -> PacedStream:
    return PacedStream(samplerate, channels, regular_seconds=None)


def fast_regular_stream(samplerate: int, channels: int) -> PacedStream:
    return PacedStream(samplerate, channels, regular_seconds=None, speed=0.999)


def racing_stream(samplerate: int, channels: int) -> PacedStream:
    return PacedStream(samplerate, channels, regular_seconds=0.0)


def regular_then_racing_stream(
    regular_seconds: float, racing_value: float = REGULAR_VALUE
) -> Callable[[int, int], PacedStream]:
    def factory(samplerate: int, channels: int) -> PacedStream:
        return PacedStream(samplerate, channels, regular_seconds=regular_seconds, racing_value=racing_value)

    return factory


class FakeRecorder(BaseRecorder):
    """Exercises the shared base path that the system track keeps."""

    log_prefix = "FAKE"

    def __init__(
        self,
        filepath: Path,
        stream_factory: Callable[[int, int], PacedStream],
        channels: int = 1,
    ) -> None:
        super().__init__(filepath, samplerate=SAMPLERATE, channels=channels, initial_device_name="fake")
        self.stream_factory = stream_factory

    def _get_default_device_name(self) -> str:
        return "fake"

    def _open_stream(self, device_name: Optional[str]) -> PacedStream:
        return self.stream_factory(self.samplerate, self.channels)

    def _read_block(self, stream: PacedStream, blocksize: int) -> tuple[np.ndarray, bool]:
        return stream.read(blocksize)


class FakeInputStream:
    """Replacement for `sd.InputStream` supporting blocking reads and callbacks."""

    instances: list["FakeInputStream"] = []

    def __init__(
        self,
        device: Any = None,
        samplerate: Optional[float] = None,
        channels: Optional[int] = None,
        blocksize: Optional[int] = None,
        callback: Optional[Callable[..., None]] = None,
        **kwargs: Any,
    ) -> None:
        self.device = device
        self.samplerate = int(samplerate or SAMPLERATE)
        self.channels = channels or 1
        self.blocksize = blocksize or 1024
        self.callback = callback
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        FakeInputStream.instances.append(self)

    @property
    def active(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def __enter__(self) -> "FakeInputStream":
        if self.callback is not None:
            self.start()
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.stop()
        self.close()

    def start(self) -> None:
        if self.callback is None or self.active:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._pump, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2)

    def close(self) -> None:
        self.stop()

    def read(self, frames: int) -> tuple[np.ndarray, bool]:
        time.sleep(frames / self.samplerate)
        return np.full((frames, self.channels), 0.25, dtype=np.float32), False

    def _pump(self) -> None:
        interval = self.blocksize / self.samplerate
        while not self._stop_event.wait(interval):
            indata = np.full((self.blocksize, self.channels), 0.25, dtype=np.float32)
            self.callback(indata, self.blocksize, None, _NoFlags())


class StallingInputStream(FakeInputStream):
    """Stops calling the callback `stall_after_sec` after it was started."""

    stall_after_sec = 0.3

    def _pump(self) -> None:
        deadline = time.monotonic() + self.stall_after_sec
        interval = self.blocksize / self.samplerate
        while not self._stop_event.wait(interval):
            if time.monotonic() >= deadline:
                continue
            indata = np.full((self.blocksize, self.channels), 0.25, dtype=np.float32)
            self.callback(indata, self.blocksize, None, _NoFlags())


@pytest.fixture
def fast_timing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(recording, "CHUNK_SEC", TEST_CHUNK_SEC)
    monkeypatch.setattr(recording, "DEVICE_POLL_SEC", TEST_DEVICE_POLL_SEC)
    monkeypatch.setattr(recording, "CLOCK_GRACE_SEC", TEST_CLOCK_GRACE_SEC)
    monkeypatch.setattr(recording, "MIC_STALL_SEC", TEST_MIC_STALL_SEC)
    monkeypatch.setattr(recording, "PYCAW_AVAILABLE", False)
    monkeypatch.setattr(logging.getLogger("backrec"), "propagate", True)


@pytest.fixture
def device_name() -> dict[str, str]:
    """Mutable holder for the name the fake Windows reports as default device."""
    return {"current": "Headset A"}


@pytest.fixture
def fake_mic_environment(
    monkeypatch: pytest.MonkeyPatch, fast_timing: None, device_name: dict[str, str]
) -> type[FakeInputStream]:
    indices = {"Headset A": 1, "Headset B": 2}
    FakeInputStream.instances = []
    monkeypatch.setattr(recording, "get_default_comm_device_name", lambda: device_name["current"])
    monkeypatch.setattr(recording, "resolve_sounddevice_index", lambda name: indices[name])
    monkeypatch.setattr(recording.sd, "InputStream", FakeInputStream)
    return FakeInputStream


def record_for(recorder: BaseRecorder, seconds: float) -> float:
    """Runs the recorder for `seconds` and returns the elapsed wall time including the stop."""
    started = time.monotonic()
    recorder.start()
    time.sleep(seconds)
    recorder.stop()
    recorder.close_file()
    return time.monotonic() - started


def frames_in(path: Path) -> int:
    with sf.SoundFile(str(path)) as wav:
        return len(wav)


def opened_devices(streams: list[FakeInputStream]) -> list[Any]:
    devices: list[Any] = []
    for stream in streams:
        if devices and devices[-1] == stream.device:
            continue
        devices.append(stream.device)
    return devices


def test_a_device_switch_mid_recording_reopens_the_stream_and_keeps_the_pace(
    tmp_path: Path,
    fake_mic_environment: type[FakeInputStream],
    device_name: dict[str, str],
) -> None:
    recorder = MicRecorder(tmp_path / "mic.wav", initial_device_name="Headset A")
    blocksize = int(SAMPLERATE * TEST_CHUNK_SEC)

    started = time.monotonic()
    recorder.start()
    time.sleep(0.4)
    device_name["current"] = "Headset B"
    time.sleep(0.6)
    recorder.stop()
    recorder.close_file()
    elapsed = time.monotonic() - started

    assert opened_devices(fake_mic_environment.instances) == [1, 2]
    assert all(stream.callback is not None for stream in fake_mic_environment.instances)
    assert recorder.current_device_name == "Headset B"
    frames = frames_in(tmp_path / "mic.wav")
    assert frames > 0
    assert frames <= elapsed * SAMPLERATE * TIMING_TOLERANCE + blocksize


def test_a_regular_stream_is_recorded_as_long_as_the_wall_clock(
    tmp_path: Path, fast_timing: None
) -> None:
    recorder = FakeRecorder(tmp_path / "fake.wav", regular_stream)
    blocksize = int(SAMPLERATE * TEST_CHUNK_SEC)

    elapsed = record_for(recorder, 0.4)

    frames = frames_in(tmp_path / "fake.wav")
    assert frames > 0
    assert frames <= elapsed * SAMPLERATE * TIMING_TOLERANCE + blocksize


def test_a_racing_stream_does_not_produce_a_track_longer_than_the_recording(
    tmp_path: Path, fast_timing: None
) -> None:
    recorder = FakeRecorder(tmp_path / "fake.wav", racing_stream)
    blocksize = int(SAMPLERATE * TEST_CHUNK_SEC)

    elapsed = record_for(recorder, 0.5)

    frames = frames_in(tmp_path / "fake.wav")
    assert frames <= elapsed * SAMPLERATE * TIMING_TOLERANCE + blocksize


def test_audio_before_the_fault_survives_the_rewind(tmp_path: Path, fast_timing: None) -> None:
    recorder = FakeRecorder(tmp_path / "fake.wav", regular_then_racing_stream(0.4, RACING_VALUE))
    blocksize = int(SAMPLERATE * TEST_CHUNK_SEC)

    elapsed = record_for(recorder, 0.7)

    with sf.SoundFile(str(tmp_path / "fake.wav")) as wav:
        frames = len(wav)
        head = wav.read(int(0.3 * SAMPLERATE), dtype="float32")
    assert frames <= elapsed * SAMPLERATE * TIMING_TOLERANCE + blocksize
    assert np.allclose(head, REGULAR_VALUE, atol=1e-3)


def test_a_slightly_fast_regular_stream_is_neither_rewound_nor_logged(
    tmp_path: Path, fast_timing: None, caplog: pytest.LogCaptureFixture
) -> None:
    recorder = FakeRecorder(tmp_path / "fake.wav", fast_regular_stream)
    blocksize = int(SAMPLERATE * TEST_CHUNK_SEC)

    with caplog.at_level(logging.DEBUG, logger="backrec.recording"):
        elapsed = record_for(recorder, 1.0)

    frames = frames_in(tmp_path / "fake.wav")
    assert frames > 0.5 * elapsed * SAMPLERATE
    assert frames <= elapsed * SAMPLERATE * TIMING_TOLERANCE + blocksize
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


def test_the_clock_check_applies_to_the_system_track(
    tmp_path: Path,
    fast_timing: None,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    recorder = SystemRecorder(tmp_path / "sys.wav")
    monkeypatch.setattr(recorder, "_get_default_device_name", lambda: "speaker")
    monkeypatch.setattr(recorder, "_open_stream", lambda name: racing_stream(recorder.samplerate, recorder.channels))
    monkeypatch.setattr(recorder, "_after_open", lambda stream: None)
    monkeypatch.setattr(recorder, "_read_block", lambda stream, blocksize: stream.read(blocksize))
    blocksize = int(SAMPLERATE * TEST_CHUNK_SEC)

    with caplog.at_level(logging.WARNING, logger="backrec.recording"):
        elapsed = record_for(recorder, 0.5)

    frames = frames_in(tmp_path / "sys.wav")
    assert frames <= elapsed * SAMPLERATE * TIMING_TOLERANCE + blocksize
    assert any("[SYS]" in r.getMessage() and r.levelno == logging.WARNING for r in caplog.records)


def test_repeated_incidents_are_reported_once_as_a_device_fault(
    tmp_path: Path, fast_timing: None, caplog: pytest.LogCaptureFixture
) -> None:
    recorder = FakeRecorder(tmp_path / "fake.wav", racing_stream)

    with caplog.at_level(logging.WARNING, logger="backrec.recording"):
        record_for(recorder, 0.5)

    faults = [r for r in caplog.records if r.levelno == logging.ERROR and "Geraetestoerung" in r.getMessage()]
    assert len(faults) == 1


def test_the_clock_limit_respects_grace_and_tolerance(tmp_path: Path) -> None:
    recorder = FakeRecorder(tmp_path / "fake.wav", regular_stream)
    recorder._started_at = 100.0
    huge = 10 * SAMPLERATE * 1000

    assert not recorder._exceeds_clock(huge, 100.0 + recording.CLOCK_GRACE_SEC - 0.01)

    now = 100.0 + recording.CLOCK_GRACE_SEC + 5.0
    limit = int(recorder._allowed_frames(now) * (1 + recording.CLOCK_TOLERANCE))
    assert not recorder._exceeds_clock(limit, now)
    assert recorder._exceeds_clock(limit + 1, now)
    recorder.close_file()


def test_a_stalled_microphone_does_not_grow_the_track_and_the_stall_is_logged(
    tmp_path: Path,
    fake_mic_environment: type[FakeInputStream],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(recording.sd, "InputStream", StallingInputStream)
    recorder = MicRecorder(tmp_path / "mic.wav", initial_device_name="Headset A")
    blocksize = int(SAMPLERATE * TEST_CHUNK_SEC)

    with caplog.at_level(logging.WARNING, logger="backrec.recording"):
        elapsed = record_for(recorder, 1.0)

    frames = frames_in(tmp_path / "mic.wav")
    assert frames <= elapsed * SAMPLERATE * TIMING_TOLERANCE + blocksize
    assert any("kein Audio" in r.getMessage() for r in caplog.records)
    assert len(fake_mic_environment.instances) >= 2
