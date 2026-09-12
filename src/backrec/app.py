"""The window: recording controls, level indicators, status line.

Moved out of `main.pyw` (lines 50-84 and 429-907). The layout, the colours, the
150 ms polling loop that defends the window geometry and the two-stage discard
button are unchanged.

What did change is where the window gets its folders from: they are handed in
rather than read at import time. The old module level created both folders as a
side effect of importing (`main.pyw:37-38`), so a bad path meant a program that
simply did not start - no window, no message, no log (design D5).
"""

from __future__ import annotations

import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import customtkinter as ctk

from . import instance, paths, preflight
from .delivery import Outcome, discard as discard_takes, finish as finish_recording
from .devices import PYCAW_AVAILABLE, get_default_comm_device_name, get_default_speaker_device_name
from .logging_setup import bootstrap, get_logger
from .recording import DEVICE_POLL_SEC, MicRecorder, SystemRecorder

if PYCAW_AVAILABLE:
    import comtypes

log = get_logger(__name__)

WINDOW_WIDTH = 280
WINDOW_MIN_HEIGHT = 160

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
DISCARD_ICON = "✕"
DISCARD_CONFIRM_MS = 3000

UI_POLL_MS = 150


def short_label(name: str, max_len: int = LABEL_MAX_LEN) -> str:
    cleaned = " ".join(str(name).split())
    if not cleaned:
        return "unknown"
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[:max_len - 1].rstrip() + "…"


def configure_appearance() -> None:
    """Keeps the process DPI-unaware so CustomTkinter never rescales widgets.

    Windows then scales the whole window instead, which keeps the layout
    pixel-stable (at the cost of slight blur above 100% display scaling). Must
    run before the CTk window is created - its constructor calls
    `ScalingTracker.activate_high_dpi_awareness()`.
    """
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    ctk.deactivate_automatic_dpi_awareness()
    ctk.set_widget_scaling(1.0)
    ctk.set_window_scaling(1.0)


class RecorderApp(ctk.CTk):
    def __init__(self, recording_dir: Path, target_dir: Path):
        super().__init__()
        log.info("=== Recorder UI gestartet ===")

        self.recording_dir = recording_dir
        self.target_dir = target_dir

        self.title("Backrec")
        self.attributes("-topmost", True)
        self.configure(fg_color=BG)
        self._fixed_size: tuple[int, int] | None = None

        self.mic_recorder = None
        self.system_recorder = None
        self._busy = False
        self._recording = False

        # The button row is packed first and anchored to the bottom, so the pack
        # manager assigns it space before anything else. Even if the remaining
        # rows ever grow, the buttons can no longer be pushed out of the window.
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(side="bottom", fill="x", padx=12, pady=(8, 12))
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        btn_frame.columnconfigure(2, weight=0, minsize=34)

        self.status_label = ctk.CTkLabel(
            self, text="○ ready", font=("Segoe UI", 11),
            text_color=TEXT_MUTED, anchor="w"
        )
        self.status_label.pack(side="top", fill="x", padx=14, pady=(12, 0))

        mic_row = ctk.CTkFrame(self, fg_color="transparent")
        mic_row.pack(side="top", fill="x", padx=14, pady=(4, 0))

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
        sys_row.pack(side="top", fill="x", padx=14, pady=(2, 0))

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

        self.btn_discard = ctk.CTkButton(
            btn_frame, text=DISCARD_ICON, font=("Segoe UI", 13, "bold"),
            fg_color=BTN_IDLE, hover_color=BTN_HOVER, text_color=TEXT_MUTED,
            border_width=1, border_color=BORDER, corner_radius=4,
            height=34, width=34,
            state="disabled", command=self.discard_recording
        )
        self.btn_discard.grid(row=0, column=2, padx=(4, 0), sticky="ew")

        self._mic_filepath = None
        self._system_filepath = None
        self._timestamp = None
        self._mic_muted = False
        self._sys_muted = False
        self._discard_armed = False
        self._discard_disarm_job = None

        self._idle_mic_name = None
        self._idle_sys_name = None
        threading.Thread(target=self._idle_device_poll_loop, daemon=True).start()

        self._lock_window_size()
        self._poll_ui_loop()

    def _lock_window_size(self) -> None:
        """Pin the window to the height its layout actually requires.

        Deriving the height from the content instead of hard-coding it means the
        button row is always inside the window. minsize/maxsize are set through
        the CTk API so CustomTkinter keeps valid bounds to restore.
        """
        self.update_idletasks()
        height = max(self.winfo_reqheight(), WINDOW_MIN_HEIGHT)
        self._fixed_size = (WINDOW_WIDTH, height)

        self.minsize(WINDOW_WIDTH, height)
        self.maxsize(WINDOW_WIDTH, height)
        self.geometry(f"{WINDOW_WIDTH}x{height}")
        self.resizable(False, False)
        log.info(f"Fenstergroesse fixiert: {WINDOW_WIDTH}x{height}")

    def _enforce_window_size(self) -> None:
        """Safety net: restore the pinned geometry if anything shrank the window."""
        if self._fixed_size is None:
            return
        if not self.winfo_viewable():
            return

        width, height = self._fixed_size
        if self.winfo_width() >= width and self.winfo_height() >= height:
            return

        log.warning(
            f"Fenstergroesse abgewichen ({self.winfo_width()}x{self.winfo_height()}), "
            f"stelle {width}x{height} wieder her"
        )
        self.minsize(width, height)
        self.maxsize(width, height)
        self.geometry(f"{width}x{height}")

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
        self.btn_discard.configure(state="disabled", text_color=TEXT_MUTED, fg_color=BTN_IDLE)
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
        mic_filepath = self.recording_dir / f"mic_{timestamp}.wav"
        system_filepath = self.recording_dir / f"system_{timestamp}.wav"

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
        self._disarm_discard()
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
        """Hands the recording over and shows a failure where it can be seen."""
        outcome = finish_recording(
            self._mic_filepath,
            self._system_filepath,
            self._timestamp or datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
            self.recording_dir,
            self.target_dir,
        )

        if not outcome.ok:
            # The status line is 280 px wide and carries neither the cause nor a
            # folder. Without this dialog the failure would exist only in a log
            # nobody opens - and the takes that could still be rescued would go
            # unnoticed.
            self.after(0, lambda: self._report_failure(outcome))

        return outcome.status

    def _report_failure(self, outcome: Outcome) -> None:
        from tkinter import messagebox

        messagebox.showwarning(
            f"{paths.TOOL_NAME}: Aufnahme nicht abgeschlossen",
            f"Was ist passiert:\n{outcome.cause}\n\n{outcome.whereabouts}\n\n"
            "Was tun: Die Ursache beheben; danach lässt sich die Aufnahme aus "
            "diesen beiden Spuren noch zusammenmischen.",
            parent=self,
        )

    def _finish_stop(self, message: str):
        self._busy = False
        self._refresh_status()
        self.status_label.configure(text=message, text_color=TEXT_MUTED)
        log.info(f"Status final: {message}")
        self.after(2500, self._refresh_status)

    # --- Discard: stop threads, close files, delete raw takes without saving ---
    def discard_recording(self):
        """Two-stage guard: first click arms the button, second click within
        DISCARD_CONFIRM_MS actually drops the take."""
        if self._busy or not self._recording:
            log.debug("discard_recording() ignoriert (busy oder nicht aktiv)")
            return

        if not self._discard_armed:
            self._arm_discard()
            return

        self._disarm_discard()
        log.info(">>> DISCARD bestaetigt")
        self._set_busy("discarding")
        threading.Thread(target=self._do_discard, daemon=True).start()

    def _arm_discard(self) -> None:
        self._discard_armed = True
        log.info("UI: Discard bewaffnet, wartet auf Bestaetigung")
        self._discard_disarm_job = self.after(DISCARD_CONFIRM_MS, self._disarm_discard)
        self._refresh_status()

    def _disarm_discard(self) -> None:
        if self._discard_disarm_job is not None:
            self.after_cancel(self._discard_disarm_job)
            self._discard_disarm_job = None
        if not self._discard_armed:
            return
        self._discard_armed = False
        log.debug("UI: Discard entschaerft")

    def _do_discard(self) -> None:
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
            deleted = self._delete_raw_files()
            message = "discarded" if deleted else "discarded (cleanup failed)"

        except Exception:
            message = "discard error"
            log.error("Unerwarteter Fehler in _do_discard()", exc_info=True)

        self.after(0, lambda: self._finish_stop(message))

    def _delete_raw_files(self) -> bool:
        """Remove the raw takes from the recording folder. Nothing is copied to the target."""
        all_removed = discard_takes(self._mic_filepath, self._system_filepath)

        self._mic_filepath = None
        self._system_filepath = None
        self._timestamp = None
        return all_removed

    def _refresh_status(self):
        if self._busy:
            return
        if self._recording:
            switching_mic = bool(self.mic_recorder and self.mic_recorder.is_switching)
            switching_sys = bool(self.system_recorder and self.system_recorder.is_switching)

            if self._discard_armed:
                text = f"{DISCARD_ICON} discard? confirm"
            elif switching_mic and switching_sys:
                text = "● switching..."
            elif switching_mic:
                text = "● switching mic..."
            elif switching_sys:
                text = "● switching system..."
            else:
                text = "● recording"

            highlighted = text in ("● recording", f"{DISCARD_ICON} discard? confirm")
            self.status_label.configure(text=text, text_color=RED if highlighted else TEXT_MUTED)
            self.btn_start.configure(state="disabled", text_color=TEXT_MUTED)
            self.btn_stop.configure(state="normal", text_color=TEXT)
            self.btn_discard.configure(
                state="normal",
                text_color=TEXT if self._discard_armed else TEXT_MUTED,
                fg_color=RED if self._discard_armed else BTN_IDLE,
            )
        else:
            self.status_label.configure(text="○ ready", text_color=TEXT_MUTED)
            self.btn_start.configure(state="normal", text_color=TEXT)
            self.btn_stop.configure(state="disabled", text_color=TEXT_MUTED)
            self.btn_discard.configure(state="disabled", text_color=TEXT_MUTED, fg_color=BTN_IDLE)

    def _poll_ui_loop(self):
        self._enforce_window_size()

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

        self.after(UI_POLL_MS, self._poll_ui_loop)


EXIT_ALREADY_RUNNING = 3
EXIT_PREFLIGHT_FAILED = 2


def _report_already_running(pid: int) -> None:
    """Says that the tool runs already - visibly, even without a console.

    Only reached when Windows refused the foreground change (design D6). The
    exit code is the same in both cases, so nothing but this sentence depends on
    which of the two happened.
    """
    log.info("Zweiter Start abgewiesen, Anwendung %d laeuft bereits", pid)
    try:
        import tkinter
        from tkinter import messagebox

        root = tkinter.Tk()
        root.withdraw()
        messagebox.showinfo(
            paths.TOOL_NAME,
            f"{paths.TOOL_NAME} läuft bereits. Das Fenster ist geöffnet, "
            "vielleicht hinter einem anderen.",
        )
        root.destroy()
    except Exception:  # noqa: BLE001 - the log entry is the part that matters
        log.warning("Hinweis auf die laufende Anwendung liess sich nicht anzeigen", exc_info=True)


def main() -> int:
    """The checked way into the window (design D5, D6).

    Log first, then the single-instance check, then the preflight, and only
    afterwards a window. Every step before the window is one that used to fail
    silently under `pythonw`.
    """
    bootstrap()

    running = instance.running_instance()
    if running is not None:
        if not instance.raise_window(running.pid):
            _report_already_running(running.pid)
        else:
            log.info("Zweiter Start abgewiesen, Fenster der Anwendung %d nach vorn geholt", running.pid)
        return EXIT_ALREADY_RUNNING

    result = preflight.run()
    if not result.ok or result.config is None:
        if result.problem is not None:
            preflight.show_error(result.problem)
        return EXIT_PREFLIGHT_FAILED

    configure_appearance()
    instance.write_record()
    try:
        RecorderApp(result.config.recording_dir, result.config.target_dir).mainloop()
    finally:
        instance.clear_record()
        instance.clear_stop_request()
    return 0


if __name__ == "__main__":
    sys.exit(main())
