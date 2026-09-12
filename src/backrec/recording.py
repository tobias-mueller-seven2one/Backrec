"""The recording core: one thread per source, writing straight to disk.

Moved unchanged out of `main.pyw` (lines 40-44 and 227-426). Not one line of
logic was rewritten - the loop, the device tracking, the per-thread COM
initialisation and the mute-writes-silence behaviour are the ones that have been
in daily use.

Two details worth keeping in mind when reading it: every block is flushed, so a
hard end of the process still leaves a playable file, and the loop re-opens its
stream whenever Windows switches the default device, which is what makes
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

                        with self._lock:
                            if self.file is not None:
                                if self.muted:
                                    self.file.write(np.zeros_like(data))
                                    self.last_peak = 0.0
                                else:
                                    self.file.write(data)
                                    self.last_peak = float(np.abs(data).max()) if data.size else 0.0
                                self.file.flush()
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

    def start(self):
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

    def _get_default_device_name(self):
        return get_default_comm_device_name()

    def _open_stream(self, device_name):
        device_index = resolve_sounddevice_index(device_name)
        return sd.InputStream(
            device=device_index,
            samplerate=self.samplerate,
            channels=self.channels,
            blocksize=int(self.samplerate * CHUNK_SEC),
        )

    def _read_block(self, stream, blocksize):
        return stream.read(blocksize)


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
