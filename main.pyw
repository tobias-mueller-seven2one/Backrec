import customtkinter as ctk
import sounddevice as sd
import soundcard as sc
import soundfile as sf
import numpy as np
import threading
import shutil
import subprocess
import time
import logging
from pathlib import Path
from datetime import datetime

try:
    import comtypes
    from pycaw.utils import AudioUtilities
    PYCAW_AVAILABLE = True
except Exception:
    PYCAW_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("recorder")

logging.captureWarnings(True)
logging.getLogger("py.warnings").setLevel(logging.WARNING)

RECORDING_DIR = Path(r"C:\Users\tobias.mueller\Aufnahmen\Recording")
TARGET_DIR = Path(r"C:\Users\tobias.mueller\OneDrive - Seven2one Informationssysteme GmbH\Aufnahmen\Input")
RECORDING_DIR.mkdir(parents=True, exist_ok=True)
TARGET_DIR.mkdir(parents=True, exist_ok=True)

SAMPLERATE = 44100
MIC_CHANNELS = 1
SYSTEM_CHANNELS = 2
CHUNK_SEC = 0.2
DEVICE_POLL_SEC = 1.0

FFMPEG_EXE = "ffmpeg"
MERGE_SAMPLERATE = SAMPLERATE
MERGE_CHANNELS = 1

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BG         = "#111111"
BORDER     = "#2a2a2a"
TEXT       = "#e0e0e0"
TEXT_MUTED = "#6b6b6b"
BTN_IDLE   = "#222222"
BTN_HOVER  = "#2e2e2e"
RED        = "#c0392b"
DOT_ON     = "#d9d9d9"
DOT_OFF    = "#4a4a4a"
MUTE_COLOR = "#8a4b4b"

LABEL_MAX_LEN = 32

EDataFlow_eRender = 0
EDataFlow_eCapture = 1
ERole_eMultimedia = 1
ERole_eCommunications = 2


def short_label(name: str, max_len: int = LABEL_MAX_LEN) -> str:
    cleaned = " ".join(str(name).split())
    if not cleaned:
        return "unknown"
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[:max_len - 1].rstrip() + "…"


def unique_destination(dst: Path) -> Path:
    if not dst.exists():
        return dst
    stem, suffix, counter = dst.stem, dst.suffix, 1
    while True:
        candidate = dst.with_name(f"{stem}_{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def merge_audio_files(mic_path: Path, system_path: Path, output_path: Path) -> tuple[bool, str]:
    """FFmpeg amix: duration=longest, dropout_transition=0, weights=1 1:normalize=0."""
    cmd = [
        FFMPEG_EXE, "-y",
        "-i", str(mic_path),
        "-i", str(system_path),
        "-filter_complex",
        "[0:a]aresample=44100,aformat=channel_layouts=mono[a0];"
        "[1:a]aresample=44100,aformat=channel_layouts=mono[a1];"
        "[a0][a1]amix=inputs=2:duration=longest:dropout_transition=0:weights=1 1:normalize=0",
        "-ar", str(MERGE_SAMPLERATE), "-ac", str(MERGE_CHANNELS),
        str(output_path)
    ]
    log.info(f"[MERGE] FFmpeg-Befehl: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except FileNotFoundError:
        log.error("[MERGE] ffmpeg nicht gefunden (nicht installiert oder nicht im PATH)", exc_info=True)
        return False, "ffmpeg nicht gefunden"
    except Exception as e:
        log.error("[MERGE] Unerwarteter Fehler beim Aufruf von ffmpeg", exc_info=True)
        return False, str(e)

    if result.returncode == 0:
        log.info(f"[MERGE] Merge erfolgreich: {output_path}")
        return True, result.stderr

    log.error(f"[MERGE] ffmpeg-Fehler (Exit {result.returncode}): {result.stderr}")
    return False, result.stderr


def get_default_comm_device_name(retries=3, retry_delay=0.05):
    if not PYCAW_AVAILABLE:
        log.warning("pycaw nicht verfuegbar, Geraeteerkennung deaktiviert")
        return None
    for attempt in range(1, retries + 1):
        try:
            enumerator = AudioUtilities.GetDeviceEnumerator()
            endpoint = enumerator.GetDefaultAudioEndpoint(
                EDataFlow_eCapture, ERole_eCommunications
            )
            device = AudioUtilities.CreateDevice(endpoint)
            name = device.FriendlyName
            if name:
                log.debug(f"pycaw meldet Default-Communications-Geraet: {name}")
                return name
            log.warning(
                f"pycaw lieferte kein FriendlyName fuer Default-Communications-Geraet "
                f"(Property-Store-Fehler, Versuch {attempt}/{retries})"
            )
        except Exception:
            log.error(f"pycaw-Aufruf fehlgeschlagen (GetDefaultAudioEndpoint), Versuch {attempt}/{retries}", exc_info=True)
        if attempt < retries:
            time.sleep(retry_delay)
    return None


def resolve_sounddevice_index(preferred_name):
    if preferred_name:
        try:
            devices = sd.query_devices()
            for idx, dev in enumerate(devices):
                if dev["max_input_channels"] > 0 and preferred_name.lower() in str(dev["name"]).lower():
                    log.info(f"Geraet gemappt: '{preferred_name}' -> Index {idx} ({dev['name']})")
                    return idx
            log.warning(f"Kein sounddevice-Match fuer '{preferred_name}', nutze Systemstandard")
        except Exception:
            log.error("Fehler bei query_devices()", exc_info=True)
    try:
        default_idx = sd.default.device[0]
        log.info(f"Nutze PortAudio-Systemstandard, Index {default_idx}")
        return default_idx
    except Exception:
        log.error("Kein Systemstandard-Geraet ermittelbar", exc_info=True)
        return None


def get_default_speaker_device_name(retries=3, retry_delay=0.05):
    if not PYCAW_AVAILABLE:
        log.warning("[SYS] pycaw nicht verfuegbar, Geraeteerkennung deaktiviert")
        return None
    for attempt in range(1, retries + 1):
        try:
            enumerator = AudioUtilities.GetDeviceEnumerator()
            endpoint = enumerator.GetDefaultAudioEndpoint(
                EDataFlow_eRender, ERole_eCommunications
            )
            device = AudioUtilities.CreateDevice(endpoint)
            name = device.FriendlyName
            if name:
                log.debug(f"[SYS] pycaw meldet Default-Wiedergabegeraet (Kommunikation): {name}")
                return name
            log.warning(
                f"[SYS] pycaw lieferte kein FriendlyName fuer Default-Wiedergabegeraet "
                f"(Property-Store-Fehler, Versuch {attempt}/{retries})"
            )
        except Exception:
            log.error(f"[SYS] pycaw-Aufruf fehlgeschlagen (GetDefaultAudioEndpoint Render), Versuch {attempt}/{retries}", exc_info=True)
        if attempt < retries:
            time.sleep(retry_delay)
    return None


def resolve_soundcard_speaker(preferred_name):
    try:
        if preferred_name:
            for spk in sc.all_speakers():
                if preferred_name.lower() in str(spk.name).lower():
                    log.info(f"[SYS] Geraet gemappt: '{preferred_name}' -> {spk.name}")
                    return spk
            log.warning(f"[SYS] Kein soundcard-Match fuer '{preferred_name}', nutze Systemstandard")
        default_speaker = sc.default_speaker()
        log.info(f"[SYS] Nutze soundcard-Systemstandard: {default_speaker.name}")
        return default_speaker
    except Exception:
        log.error("[SYS] Fehler bei soundcard-Geraeteaufloesung (all_speakers/default_speaker)", exc_info=True)
        return None


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


class RecorderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        log.info("=== Recorder UI gestartet ===")

        self.title("REC")
        self.geometry("280x160")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.configure(fg_color=BG)

        self.mic_recorder = None
        self.system_recorder = None
        self._busy = False
        self._recording = False

        self.status_label = ctk.CTkLabel(
            self, text="○ ready", font=("Segoe UI", 11),
            text_color=TEXT_MUTED, anchor="w"
        )
        self.status_label.pack(fill="x", padx=14, pady=(12, 0))

        mic_row = ctk.CTkFrame(self, fg_color="transparent")
        mic_row.pack(fill="x", padx=14, pady=(4, 0))

        self.mic_level_dot = ctk.CTkLabel(mic_row, text="●", width=14, font=("Segoe UI", 11), text_color=DOT_OFF)
        self.mic_level_dot.pack(side="left")

        self.mic_level_label = ctk.CTkLabel(
            mic_row, text=short_label("mic in", LABEL_MAX_LEN),
            font=("Segoe UI", 10), text_color=TEXT_MUTED, anchor="w"
        )
        self.mic_level_label.pack(side="left", padx=(4, 0))

        for widget in (self.mic_level_dot, self.mic_level_label):
            widget.bind("<Button-1>", self._toggle_mic_mute)
            widget.configure(cursor="hand2")

        sys_row = ctk.CTkFrame(self, fg_color="transparent")
        sys_row.pack(fill="x", padx=14, pady=(2, 0))

        self.sys_level_dot = ctk.CTkLabel(sys_row, text="●", width=14, font=("Segoe UI", 11), text_color=DOT_OFF)
        self.sys_level_dot.pack(side="left")

        self.sys_level_label = ctk.CTkLabel(
            sys_row, text=short_label("system out", LABEL_MAX_LEN),
            font=("Segoe UI", 10), text_color=TEXT_MUTED, anchor="w"
        )
        self.sys_level_label.pack(side="left", padx=(4, 0))

        for widget in (self.sys_level_dot, self.sys_level_label):
            widget.bind("<Button-1>", self._toggle_sys_mute)
            widget.configure(cursor="hand2")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=12, pady=(8, 12))
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        self.btn_start = ctk.CTkButton(
            btn_frame, text="REC", font=("Segoe UI", 12, "bold"),
            fg_color=BTN_IDLE, hover_color=BTN_HOVER, text_color=TEXT,
            border_width=1, border_color=BORDER, corner_radius=4, height=34,
            command=self.start_recording
        )
        self.btn_start.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        self.btn_stop = ctk.CTkButton(
            btn_frame, text="STOP", font=("Segoe UI", 12, "bold"),
            fg_color=BTN_IDLE, hover_color=BTN_HOVER, text_color=TEXT_MUTED,
            border_width=1, border_color=BORDER, corner_radius=4, height=34,
            state="disabled", command=self.stop_recording
        )
        self.btn_stop.grid(row=0, column=1, padx=(4, 0), sticky="ew")

        self._mic_filepath = None
        self._system_filepath = None
        self._timestamp = None
        self._mic_muted = False
        self._sys_muted = False

        self._idle_mic_name = None
        self._idle_sys_name = None
        threading.Thread(target=self._idle_device_poll_loop, daemon=True).start()

        self._poll_ui_loop()

    def _idle_device_poll_loop(self):
        if PYCAW_AVAILABLE:
            comtypes.CoInitialize()
        try:
            while True:
                if not self._recording:
                    self._idle_mic_name = get_default_comm_device_name()
                    self._idle_sys_name = get_default_speaker_device_name()
                time.sleep(DEVICE_POLL_SEC)
        finally:
            if PYCAW_AVAILABLE:
                comtypes.CoUninitialize()

    def _toggle_mic_mute(self, event=None):
        self._mic_muted = not self._mic_muted
        if self.mic_recorder is not None:
            self.mic_recorder.set_muted(self._mic_muted)
        log.info(f"UI: Mic-Mute -> {self._mic_muted}")

    def _toggle_sys_mute(self, event=None):
        self._sys_muted = not self._sys_muted
        if self.system_recorder is not None:
            self.system_recorder.set_muted(self._sys_muted)
        log.info(f"UI: System-Mute -> {self._sys_muted}")

    def _set_busy(self, base_text: str):
        self._busy = True
        self.btn_start.configure(state="disabled", text_color=TEXT_MUTED)
        self.btn_stop.configure(state="disabled", text_color=TEXT_MUTED)
        self._animate_dots(base_text)

    def _animate_dots(self, base: str, step: int = 0):
        if not self._busy:
            return
        dots = ["   ", ".  ", ".. ", "..."]
        self.status_label.configure(text=f"{base}{dots[step % 4]}", text_color=TEXT_MUTED)
        self.after(300, lambda: self._animate_dots(base, step + 1))

    # --- Start ---
    def start_recording(self):
        if self._busy or self._recording:
            log.debug("start_recording() ignoriert (busy oder bereits aktiv)")
            return
        log.info(">>> REC gedrueckt")
        self._set_busy("starting")
        threading.Thread(target=self._do_start, daemon=True).start()

    def _do_start(self):
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        mic_filepath = RECORDING_DIR / f"mic_{timestamp}.wav"
        system_filepath = RECORDING_DIR / f"system_{timestamp}.wav"

        # Resolve device names before starting recorders (avoids UI lag from placeholder names)
        if PYCAW_AVAILABLE:
            comtypes.CoInitialize()
        try:
            mic_device_name = get_default_comm_device_name()
            sys_device_name = get_default_speaker_device_name()
        finally:
            if PYCAW_AVAILABLE:
                comtypes.CoUninitialize()

        try:
            self.mic_recorder = MicRecorder(mic_filepath, initial_device_name=mic_device_name)
            self.system_recorder = SystemRecorder(system_filepath, initial_device_name=sys_device_name)
            self.mic_recorder.set_muted(self._mic_muted)
            self.system_recorder.set_muted(self._sys_muted)
            self.mic_recorder.start()
            self.system_recorder.start()
            self._mic_filepath = mic_filepath
            self._system_filepath = system_filepath
            self._timestamp = timestamp
            self._recording = True
            log.info(f"Aufnahme erfolgreich gestartet: {mic_filepath}, {system_filepath}")
        except Exception:
            self.mic_recorder = None
            self.system_recorder = None
            self._recording = False
            log.error("Aufnahme konnte nicht gestartet werden", exc_info=True)

        self.after(0, self._finish_start)

    def _finish_start(self):
        self._busy = False
        self._refresh_status()

    # --- Stop: join both threads, close files, merge and save ---
    def stop_recording(self):
        if self._busy or not self._recording:
            log.debug("stop_recording() ignoriert (busy oder nicht aktiv)")
            return
        log.info(">>> STOP gedrueckt")
        self._set_busy("stopping")
        threading.Thread(target=self._do_stop, daemon=True).start()

    def _do_stop(self):
        try:
            if self.mic_recorder is not None:
                self.mic_recorder.stop(timeout=5)
            if self.system_recorder is not None:
                self.system_recorder.stop(timeout=5)

            if self.mic_recorder is not None:
                self.mic_recorder.close_file()
            if self.system_recorder is not None:
                self.system_recorder.close_file()

            self._recording = False
            message = self._merge_and_save()

        except Exception:
            message = "stop error"
            log.error("Unerwarteter Fehler in _do_stop()", exc_info=True)

        self.after(0, lambda: self._finish_stop(message))

    def _merge_and_save(self) -> str:
        """Merge mic+system via FFmpeg, fallback to raw copy if merge fails."""
        mic_src = self._mic_filepath
        sys_src = self._system_filepath

        if not (mic_src and mic_src.exists() and mic_src.stat().st_size >= 1024):
            log.error(f"[MERGE] Mic-Datei fehlt oder zu klein: {mic_src}")
            return self._fallback_copy_raw()
        if not (sys_src and sys_src.exists() and sys_src.stat().st_size >= 1024):
            log.error(f"[MERGE] System-Datei fehlt oder zu klein: {sys_src}")
            return self._fallback_copy_raw()

        merged_path = RECORDING_DIR / f"{self._timestamp}.wav"
        ok, stderr = merge_audio_files(mic_src, sys_src, merged_path)

        if not ok:
            log.error(f"[MERGE] Merge fehlgeschlagen, weiche auf Rohdateien aus: {stderr}")
            return self._fallback_copy_raw()

        if not (merged_path.exists() and merged_path.stat().st_size >= 1024):
            log.error(f"[MERGE] Merge-Ausgabedatei fehlt oder zu klein: {merged_path}")
            return self._fallback_copy_raw()

        dst = unique_destination(TARGET_DIR / merged_path.name)
        log.info(f"[MERGE] Kopiere gemischte Datei nach: {dst}")
        shutil.copy2(str(merged_path), str(dst))

        if dst.exists() and dst.stat().st_size == merged_path.stat().st_size:
            log.info("[MERGE] Kopie der gemischten Datei verifiziert")
            return "saved (merged)"

        log.error("[MERGE] Groessenabweichung bei der Kopie der gemischten Datei!")
        return self._fallback_copy_raw()

    def _fallback_copy_raw(self) -> str:
        """Fallback if merge failed: copy raw files individually."""
        mic_result = self._copy_to_target("MIC", self._mic_filepath)
        sys_result = self._copy_to_target("SYS", self._system_filepath)

        if mic_result == "ok" and sys_result == "ok":
            return "saved raw (merge failed)"
        elif mic_result == "ok" or sys_result == "ok":
            return "partial save"
        return "save failed"

    def _copy_to_target(self, prefix: str, src):
        """Copy recording file to target, verify by size. Original stays in Recording dir."""
        if not (src and src.exists()):
            log.error(f"[{prefix}] Quelldatei nicht gefunden: {src}")
            return "missing"

        original_size = src.stat().st_size
        log.info(f"[{prefix}] Quelldatei vorhanden: {src} ({original_size} Bytes)")

        if original_size < 1024:
            log.warning(f"[{prefix}] Datei zu klein ({original_size} Bytes), kein Kopiervorgang")
            return "too_small"

        dst = unique_destination(TARGET_DIR / src.name)
        log.info(f"[{prefix}] Kopiere nach: {dst}")
        shutil.copy2(str(src), str(dst))

        if dst.exists() and dst.stat().st_size == original_size:
            log.info(f"[{prefix}] Kopie verifiziert, Groesse identisch ({original_size} Bytes)")
            return "ok"

        log.error(f"[{prefix}] Groessenabweichung nach Kopie! Original={original_size}, Kopie={dst.stat().st_size if dst.exists() else 'fehlt'}")
        return "mismatch"

    def _finish_stop(self, message: str):
        self._busy = False
        self._refresh_status()
        self.status_label.configure(text=message, text_color=TEXT_MUTED)
        log.info(f"Status final: {message}")
        self.after(2500, self._refresh_status)

    def _refresh_status(self):
        if self._busy:
            return
        if self._recording:
            switching_mic = bool(self.mic_recorder and self.mic_recorder.is_switching)
            switching_sys = bool(self.system_recorder and self.system_recorder.is_switching)

            if switching_mic and switching_sys:
                text = "● switching..."
            elif switching_mic:
                text = "● switching mic..."
            elif switching_sys:
                text = "● switching system..."
            else:
                text = "● recording"

            self.status_label.configure(text=text, text_color=RED if text == "● recording" else TEXT_MUTED)
            self.btn_start.configure(state="disabled", text_color=TEXT_MUTED)
            self.btn_stop.configure(state="normal", text_color=TEXT)
        else:
            self.status_label.configure(text="○ ready", text_color=TEXT_MUTED)
            self.btn_start.configure(state="normal", text_color=TEXT)
            self.btn_stop.configure(state="disabled", text_color=TEXT_MUTED)

    def _poll_ui_loop(self):
        if not self._busy:
            self._refresh_status()

        if self._recording and self.mic_recorder is not None:
            peak = self.mic_recorder.last_peak
            active = peak > 0.02 and not self._mic_muted
            name = short_label(self.mic_recorder.current_device_name or "mic in", LABEL_MAX_LEN)
        else:
            active = False
            name = short_label(self._idle_mic_name or "mic in", LABEL_MAX_LEN)

        if self._mic_muted:
            self.mic_level_dot.configure(text_color=MUTE_COLOR)
            self.mic_level_label.configure(text=f"{name} (muted)", text_color=MUTE_COLOR)
        else:
            self.mic_level_dot.configure(text_color=DOT_ON if active else DOT_OFF)
            self.mic_level_label.configure(text=name, text_color=TEXT if active else TEXT_MUTED)

        if self._recording and self.system_recorder is not None:
            peak = self.system_recorder.last_peak
            active = peak > 0.02 and not self._sys_muted
            name = short_label(self.system_recorder.current_device_name or "system out", LABEL_MAX_LEN)
        else:
            active = False
            name = short_label(self._idle_sys_name or "system out", LABEL_MAX_LEN)

        if self._sys_muted:
            self.sys_level_dot.configure(text_color=MUTE_COLOR)
            self.sys_level_label.configure(text=f"{name} (muted)", text_color=MUTE_COLOR)
        else:
            self.sys_level_dot.configure(text_color=DOT_ON if active else DOT_OFF)
            self.sys_level_label.configure(text=name, text_color=TEXT if active else TEXT_MUTED)

        self.after(150, self._poll_ui_loop)


if __name__ == "__main__":
    app = RecorderApp()
    app.mainloop()