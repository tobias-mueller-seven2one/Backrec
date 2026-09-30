"""The recording core: one thread per source, writing straight to disk.

Originally moved out of `main.pyw`. The microphone is now driven by the
PortAudio callback (the driver paces the writes; a monitor thread only watches
the default device and re-opens the stream), while the system track still pulls
blocks in a loop. Both tracks are bound to a monotonic clock anchor: a write
position that runs ahead of the wall clock is rewound and truncated.

Two details worth keeping in mind when reading it: every block is flushed, so a
hard end of the process still leaves a playable file, and the stream is
re-opened whenever Windows switches the default device, which is what makes
plugging in a headset mid-call survivable.
"""

from __future__ import annotations

import threading
import time

import numpy as np
import sounddevice as sd
import soundcard as sc
import soundfile as sf

from .devices import (
    PYCAW_AVAILABLE,
    get_default_comm_device_name,
    get_default_speaker_device_name,
    resolve_sounddevice_index,
    resolve_soundcard_speaker,
)
from .logging_setup import get_logger

if PYCAW_AVAILABLE:
    import comtypes

log = get_logger(__name__)

SAMPLERATE = 44100
MIC_CHANNELS = 1
SYSTEM_CHANNELS = 2
CHUNK_SEC = 0.2
DEVICE_POLL_SEC = 1.0

# Regular device/system clock drift is a few hundred ppm, observed faults were 9400-24800 %, so 20 % is four orders of magnitude away from both.
CLOCK_TOLERANCE = 0.20
# Stream opening and the first buffers must not count as a fault.
CLOCK_GRACE_SEC = 5.0
# Repeated incidents within this window are reported as a device fault.
CLOCK_FAULT_WINDOW_SEC = 60.0
# Number of incidents within the window that turns the report into a device fault.
CLOCK_FAULT_INCIDENTS = 3
# Ten blocks without a callback is no scheduling jitter but a dead stream.
MIC_STALL_SEC = 2.0
MONITOR_STEP_SEC = 0.05


class BaseRecorder:
    """Gemeinsame Aufnahme-Logik fuer Mikrofon- und Systemaudio-Quelle."""

    log_prefix = "BASE"

    def __init__(self, filepath, samplerate, channels, initial_device_name=None):
        self.filepath = filepath
        self.samplerate = samplerate
        self.channels = channels

        log.info(f"[{self.log_prefix}] Oeffne WAV-Datei zum Schreiben: {filepath}")
        self.file = sf.SoundFile(
            str(filepath), mode="w",
            samplerate=samplerate, channels=channels,
            subtype="PCM_16", format="WAV"
        )

        self._running = False
        self._lock = threading.Lock()
        self._thread = None

        self._started_at: float | None = None
        self._frames_written = 0
        self._incident_times: list[float] = []
        self._fault_reported = False

        self.last_peak = 0.0
        self.current_device_name = initial_device_name
        self.is_switching = False
        self.last_error = None
        self.muted = False

    def set_muted(self, muted: bool):
        """Mute schreibt Stille statt Audio, Stream/Datei bleiben offen."""
        self.muted = muted
        log.info(f"[{self.log_prefix}] Mute {'aktiviert' if muted else 'deaktiviert'}")

    def _get_default_device_name(self):
        raise NotImplementedError

    def _open_stream(self, device_name):
        """Return Context-Manager for stream (with ... as stream)."""
        raise NotImplementedError

    def _read_block(self, stream, blocksize):
        """Return (data ndarray, overflowed bool)."""
        raise NotImplementedError

    def _after_open(self, stream):
        """Optional hook after stream opened."""
        pass

    def _recording_loop(self):
        log.info(f"[{self.log_prefix}] Aufnahme-Thread gestartet")

        if PYCAW_AVAILABLE:
            comtypes.CoInitialize()

        try:
            self._recording_loop_body()
        finally:
            if PYCAW_AVAILABLE:
                comtypes.CoUninitialize()

        log.info(f"[{self.log_prefix}] Aufnahme-Thread beendet")

    def _recording_loop_body(self):
        blocksize = int(self.samplerate * CHUNK_SEC)

        while self._running:
            device_name = self._get_default_device_name()
            self.current_device_name = device_name or "default"
            self.is_switching = False

            log.info(f"[{self.log_prefix}] Oeffne Stream fuer Geraet: {self.current_device_name}")

            try:
                with self._open_stream(device_name) as stream:
                    log.info(f"[{self.log_prefix}] Stream erfolgreich geoeffnet ({self.current_device_name})")
                    self._after_open(stream)
                    last_check = time.time()
                    blocks_written = 0

                    while self._running:
                        try:
                            data, overflowed = self._read_block(stream, blocksize)
                            if overflowed:
                                log.warning(f"[{self.log_prefix}] Audio-Buffer-Overflow erkannt (Block verloren)")
                        except Exception as e:
                            self.last_error = str(e)
                            log.error(f"[{self.log_prefix}] Fehler beim Lesen vom Stream", exc_info=True)
                            break

                        self._write_block(data)
                        blocks_written += 1

                        log.debug(f"[{self.log_prefix}] Block #{blocks_written} geschrieben, peak={self.last_peak:.4f}")

                        now = time.time()
                        if now - last_check >= DEVICE_POLL_SEC:
                            last_check = now
                            new_name = self._get_default_device_name()
                            if new_name and new_name != device_name:
                                log.info(f"[{self.log_prefix}] Geraetewechsel erkannt: '{device_name}' -> '{new_name}'")
                                self.is_switching = True
                                break

                    log.info(f"[{self.log_prefix}] Stream wird geschlossen ({blocks_written} Bloecke geschrieben)")

            except Exception as e:
                self.last_error = str(e)
                self.is_switching = True
                log.error(f"[{self.log_prefix}] Stream-Fehler bei Geraet '{self.current_device_name}', erneuter Versuch in 0.3s", exc_info=True)
                time.sleep(0.3)

    def _allowed_frames(self, now: float) -> int:
        if self._started_at is None:
            return 0
        return int((now - self._started_at) * self.samplerate)

    def _exceeds_clock(self, pending_frames: int, now: float) -> bool:
        if self._started_at is None:
            return False
        if now - self._started_at < CLOCK_GRACE_SEC:
            return False
        limit = self._allowed_frames(now) * (1 + CLOCK_TOLERANCE)
        return self._frames_written + pending_frames > limit

    def _write_block(self, data: np.ndarray) -> None:
        """Single write path for all sources; keeps the file position bound to the wall clock."""
        with self._lock:
            if self.file is None:
                return
            now = time.monotonic()
            if self.muted:
                data = np.zeros_like(data)
                self.last_peak = 0.0
            else:
                self.last_peak = float(np.abs(data).max()) if data.size else 0.0
            if self._exceeds_clock(len(data), now):
                self._rewind_to_clock(now)
                return
            self.file.write(data)
            self.file.flush()
            self._frames_written += len(data)

    def _rewind_to_clock(self, now: float) -> None:
        """Truncate the file to the frames the wall clock allows. Caller holds `self._lock`."""
        allowed = self._allowed_frames(now)
        discarded = max(self._frames_written - allowed, 0)
        if discarded:
            self.file.seek(allowed)
            self.file.truncate(allowed)
            self._frames_written = allowed

        self._incident_times = [t for t in self._incident_times if now - t <= CLOCK_FAULT_WINDOW_SEC]
        self._incident_times.append(now)
        incidents = len(self._incident_times)

        if incidents < CLOCK_FAULT_INCIDENTS:
            self._fault_reported = False
            log.warning(
                f"[{self.log_prefix}] Spur lief der Uhr davon, zurueckgespult: "
                f"geschrieben {(self._frames_written + discarded) / self.samplerate:.1f}s, "
                f"verstrichen {now - self._started_at:.1f}s, verworfen {discarded / self.samplerate:.1f}s"
            )
            return
        if self._fault_reported:
            log.debug(f"[{self.log_prefix}] Weiterer Uhr-Vorfall, verworfen {discarded / self.samplerate:.1f}s")
            return
        self._fault_reported = True
        log.error(
            f"[{self.log_prefix}] Geraetestoerung: {incidents} Uhr-Vorfaelle innerhalb von "
            f"{CLOCK_FAULT_WINDOW_SEC:.0f}s, das Geraet liefert Audio schneller als Echtzeit"
        )

    def start(self):
        self._started_at = time.monotonic()
        self._frames_written = 0
        self._incident_times = []
        self._fault_reported = False
        self._running = True
        self._thread = threading.Thread(target=self._recording_loop, daemon=True)
        self._thread.start()
        log.info(f"[{self.log_prefix}] start() aufgerufen")

    def stop(self, timeout=5):
        """Signalisiert dem Thread das Ende und wartet auf ihn. Schliesst die Datei NICHT."""
        log.info(f"[{self.log_prefix}] stop() aufgerufen, warte auf Thread-Ende...")
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                log.warning(f"[{self.log_prefix}] Aufnahme-Thread nach {timeout}s Timeout immer noch aktiv!")
            else:
                log.info(f"[{self.log_prefix}] Aufnahme-Thread sauber beendet")

    def close_file(self):
        with self._lock:
            if self.file is not None:
                self.file.close()
                log.info(f"[{self.log_prefix}] Datei geschlossen: {self.filepath}")
                self.file = None


class MicRecorder(BaseRecorder):
    """Mikrofon-Aufnahme ueber sounddevice/PortAudio."""

    log_prefix = "MIC"

    def __init__(self, filepath, initial_device_name=None):
        super().__init__(filepath, samplerate=SAMPLERATE, channels=MIC_CHANNELS, initial_device_name=initial_device_name)
        self._last_callback_at = time.monotonic()
        self._pending_status: str | None = None

    def _get_default_device_name(self):
        return get_default_comm_device_name()

    def _callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        """PortAudio thread: must stay short, no logging, device queries, COM or sleeping."""
        if status:
            self.last_error = str(status)
            self._pending_status = self.last_error
        self._last_callback_at = time.monotonic()
        self._write_block(indata)

    def _recording_loop_body(self) -> None:
        while self._running:
            device_name = self._get_default_device_name()
            self.current_device_name = device_name or "default"
            self.is_switching = False

            log.info(f"[{self.log_prefix}] Oeffne Stream fuer Geraet: {self.current_device_name}")

            try:
                self._run_stream(device_name)
            except Exception as e:
                self.last_error = str(e)
                self.is_switching = True
                log.error(f"[{self.log_prefix}] Stream-Fehler bei Geraet '{self.current_device_name}', erneuter Versuch in 0.3s", exc_info=True)
                time.sleep(0.3)

    def _run_stream(self, device_name: str | None) -> None:
        stream = sd.InputStream(
            device=resolve_sounddevice_index(device_name),
            samplerate=self.samplerate,
            channels=self.channels,
            blocksize=int(self.samplerate * CHUNK_SEC),
            callback=self._callback,
        )
        with stream:
            log.info(f"[{self.log_prefix}] Stream erfolgreich geoeffnet ({self.current_device_name})")
            self._last_callback_at = time.monotonic()
            self._monitor_stream(device_name)
            log.info(f"[{self.log_prefix}] Stream wird geschlossen")

    def _monitor_stream(self, device_name: str | None) -> None:
        last_check = time.monotonic()
        while self._running:
            time.sleep(min(MONITOR_STEP_SEC, DEVICE_POLL_SEC))
            self._log_pending_status()
            now = time.monotonic()
            if now - last_check < DEVICE_POLL_SEC:
                continue
            last_check = now
            if self._device_changed(device_name) or self._is_stalled(now):
                return

    def _log_pending_status(self) -> None:
        status = self._pending_status
        if status is None:
            return
        self._pending_status = None
        log.warning(f"[{self.log_prefix}] Treiber-Status: {status}")

    def _device_changed(self, device_name: str | None) -> bool:
        new_name = self._get_default_device_name()
        if not new_name or new_name == device_name:
            return False
        log.info(f"[{self.log_prefix}] Geraetewechsel erkannt: '{device_name}' -> '{new_name}'")
        self.is_switching = True
        return True

    def _is_stalled(self, now: float) -> bool:
        silent_for = now - self._last_callback_at
        if silent_for <= MIC_STALL_SEC:
            return False
        self.last_error = f"Keine Audiodaten seit {silent_for:.1f}s"
        log.warning(f"[{self.log_prefix}] Geraet liefert kein Audio seit {silent_for:.1f}s, Stream wird neu geoeffnet")
        self.is_switching = True
        return True


class SystemRecorder(BaseRecorder):
    """Systemausgabe-Aufnahme via WASAPI-Loopback ueber soundcard."""

    log_prefix = "SYS"

    def __init__(self, filepath, initial_device_name=None):
        super().__init__(filepath, samplerate=SAMPLERATE, channels=SYSTEM_CHANNELS, initial_device_name=initial_device_name)

    def _get_default_device_name(self):
        return get_default_speaker_device_name()

    def _open_stream(self, device_name):
        speaker = resolve_soundcard_speaker(device_name)
        if speaker is None:
            raise RuntimeError("Kein Wiedergabegeraet fuer Loopback-Aufnahme gefunden")
        microphone = sc.get_microphone(id=speaker.id, include_loopback=True)
        return microphone.recorder(
            samplerate=self.samplerate,
            channels=self.channels,
            blocksize=int(self.samplerate * CHUNK_SEC),
        )

    def _after_open(self, stream):
        # Issue#166 workaround: dummy init read prevents silence-at-start
        try:
            stream.record(numframes=int(self.samplerate * CHUNK_SEC))
            log.info(f"[{self.log_prefix}] Dummy-Init-Read durchgefuehrt (Stille-Workaround Issue #166)")
        except Exception:
            log.warning(f"[{self.log_prefix}] Dummy-Init-Read fehlgeschlagen", exc_info=True)

    def _read_block(self, stream, blocksize):
        data = stream.record(numframes=blocksize)
        return data, False
