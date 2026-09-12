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
import tkinter as tk
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Callable

import customtkinter as ctk

from . import control, instance, paths, preflight
from .delivery import Outcome, discard as discard_takes, finish as finish_recording
from .devices import PYCAW_AVAILABLE, get_default_comm_device_name, get_default_speaker_device_name
from .logging_setup import bootstrap, get_logger
from .recording import DEVICE_POLL_SEC, MicRecorder, SystemRecorder
from .update import UpdatePlan

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

# The one place for everything a tray menu would carry (design D20). A button,
# not a menu bar: the window is 280 px wide and defends that width, and every
# visible element would come out of the recording controls - which are what the
# window is for.
GEAR_ICON = "⚙"
GEAR_TOOLTIP = "Menü: Aktualisieren, Diagnose, Logs öffnen, Einstellungen öffnen, Info"

MENU_UPDATE = "Aktualisieren…"
MENU_DOCTOR = "Diagnose"
MENU_LOGS = "Logs öffnen"
MENU_SETTINGS = "Einstellungen öffnen"
MENU_ABOUT = "Info"

# Why an entry is greyed out has to be readable, so the reason travels in the
# label itself - a menu has no second line for it.
RECORDING_SUFFIX = " (während der Aufnahme gesperrt)"

# Long enough for the closing line to be read, short enough that a stop from
# outside does not run into its own deadline.
EXIT_DELAY_MS = 900


def short_label(name: str, max_len: int = LABEL_MAX_LEN) -> str:
    cleaned = " ".join(str(name).split())
    if not cleaned:
        return "unknown"
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[:max_len - 1].rstrip() + "…"


def update_question(decision: UpdatePlan) -> str:
    """The one question before an update, with both versions in it.

    A pure function so the wording of the case that matters - an archive that is
    not newer - is checkable without a window. The specification asks for both
    versions in either case, and for a step older or equal to happen only with
    explicit consent.
    """
    if decision.newer:
        return (
            f"Von {decision.installed_version} auf {decision.info.version}.\n\n"
            "Backrec beendet sich dafür und meldet sich gleich wieder.\n\n"
            "Jetzt einspielen?"
        )
    return (
        f"Die gewählte Fassung ist nicht neuer: hier läuft "
        f"{decision.installed_version}, gewählt ist {decision.info.version}.\n\n"
        "Trotzdem einspielen?"
    )


def menu_entry(label: str, recording: bool) -> tuple[str, str]:
    """Label and state of a menu entry a running recording rules out.

    The reason travels inside the label because a menu has no second line for
    it, and an entry that is simply grey tells the reader nothing (design D20).
    """
    if not recording:
        return label, "normal"
    return f"{label}{RECORDING_SUFFIX}", "disabled"


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

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(side="top", fill="x", padx=14, pady=(12, 0))

        self.status_label = ctk.CTkLabel(
            header, text="○ ready", font=("Segoe UI", 11),
            text_color=TEXT_MUTED, anchor="w"
        )
        self.status_label.pack(side="left", fill="x", expand=True)

        self.menu_button = ctk.CTkButton(
            header, text=GEAR_ICON, font=("Segoe UI", 12),
            fg_color=BTN_IDLE, hover_color=BTN_HOVER, text_color=TEXT_MUTED,
            border_width=0, corner_radius=4, width=24, height=20,
            command=self._open_menu
        )
        self.menu_button.pack(side="right", padx=(6, 0))
        self._install_tooltip(self.menu_button, GEAR_TOOLTIP)

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

        self._closing = False
        self._menu_busy = False
        self._silent_failures = False
        self._tooltip: ctk.CTkToplevel | None = None
        self._build_menu()

        # Without this the window X kills the process and takes the daemon
        # threads with it: the closing sequence never runs and a recording in
        # progress is gone (design D7).
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        threading.Thread(target=self._idle_device_poll_loop, daemon=True).start()

        self._lock_window_size()
        self._poll_ui_loop()

    def report_callback_exception(
        self,
        exc_type: type[BaseException],
        exc_value: BaseException,
        traceback_object: TracebackType | None,
    ) -> None:
        """Tk hands an exception in a callback to stderr - which is None here.

        Without this override the process keeps a window that no longer reacts,
        and the reason for it exists nowhere: under `pythonw` stderr is None,
        so Tk's own report writes into nothing.
        """
        log.error(
            "Unerwarteter Fehler im Fenster",
            exc_info=(exc_type, exc_value, traceback_object),
        )

    # --- The gear menu ------------------------------------------------------

    def _install_tooltip(self, widget: ctk.CTkButton, text: str) -> None:
        """A gear without a label is not self-explanatory for this audience."""

        def show(_event: object = None) -> None:
            if self._tooltip is not None:
                return
            tip = ctk.CTkToplevel(self)
            tip.overrideredirect(True)
            tip.attributes("-topmost", True)
            ctk.CTkLabel(
                tip, text=text, font=("Segoe UI", 9), text_color=TEXT,
                fg_color=BTN_IDLE, corner_radius=4, padx=6, pady=2,
            ).pack()
            tip.geometry(f"+{widget.winfo_rootx() - 150}+{widget.winfo_rooty() + 24}")
            self._tooltip = tip

        def hide(_event: object = None) -> None:
            if self._tooltip is not None:
                self._tooltip.destroy()
                self._tooltip = None

        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)

    def _build_menu(self) -> None:
        """The suite-wide order, as far as a tool without a tray icon carries it.

        "Einstellungen öffnen" sits between the logs and the details, which is
        position 9 of the order in section 6 of the convention - the same place
        the neighbouring tools give it in their tray menu.
        """
        self._menu = tk.Menu(self, tearoff=0)
        self._menu.add_command(label=MENU_UPDATE, command=self._menu_update)
        self._menu.add_command(label=MENU_DOCTOR, command=self._menu_doctor)
        self._menu.add_command(label=MENU_LOGS, command=self._menu_logs)
        self._menu.add_command(label=MENU_SETTINGS, command=self._menu_settings)
        self._menu.add_command(label=MENU_ABOUT, command=self._menu_about)

    def _open_menu(self) -> None:
        """Opens the menu, with the entries a recording rules out greyed out."""
        if self._menu_busy or self._closing:
            log.debug("Menue ignoriert (ein Vorgang laeuft)")
            return

        for index, label in ((0, MENU_UPDATE), (1, MENU_DOCTOR), (3, MENU_SETTINGS)):
            text, state = menu_entry(label, self._recording)
            self._menu.entryconfigure(index, state=state, label=text)

        try:
            self._menu.tk_popup(
                self.menu_button.winfo_rootx(),
                self.menu_button.winfo_rooty() + self.menu_button.winfo_height(),
            )
        finally:
            self._menu.grab_release()

    def _in_background(self, label: str, work: Callable[[], None]) -> None:
        """Runs a long menu action with the menu locked and the window talking."""
        if self._menu_busy:
            return

        self._menu_busy = True
        self.menu_button.configure(state="disabled")
        previous = self.status_label.cget("text")
        self.status_label.configure(text=label, text_color=TEXT_MUTED)

        def run() -> None:
            try:
                work()
            except Exception:  # noqa: BLE001 - a menu action must not end the window
                log.error("Menuepunkt '%s' fehlgeschlagen", label, exc_info=True)
            finally:
                self.after(0, lambda: self._release_menu(previous))

        threading.Thread(target=run, daemon=True).start()

    def _release_menu(self, previous: str) -> None:
        self._menu_busy = False
        self.menu_button.configure(state="normal")
        if not self._busy:
            self._refresh_status()
        else:
            self.status_label.configure(text=previous)

    def _menu_update(self) -> None:
        """Choose an archive, name both versions, ask once, then act.

        The question comes before the first change, not after: the archive is
        only read for its version here, and the expensive part - unpacking and
        checking every file - happens once the answer is yes.
        """
        log.info("Menue: %s", MENU_UPDATE)
        from tkinter import filedialog, messagebox

        chosen = filedialog.askopenfilename(
            parent=self,
            title="Neue Fassung auswählen",
            filetypes=[("Archiv", "*.zip")],
        )
        if not chosen:
            log.info("Menue: Aktualisieren abgebrochen, keine Datei gewaehlt")
            return

        archive = Path(chosen)
        decision, problem = control.inspect_archive(archive)
        if decision is None:
            messagebox.showwarning(
                f"{paths.TOOL_NAME}: Aktualisieren", "\n".join(problem), parent=self
            )
            return

        if not messagebox.askyesno(
            f"{paths.TOOL_NAME}: Aktualisieren", update_question(decision), parent=self
        ):
            log.info(
                "Menue: Aktualisieren abgelehnt (%s -> %s)",
                decision.installed_version,
                decision.info.version,
            )
            return

        def work() -> None:
            # `allow_older`, because the question above has just been answered
            # for exactly this case and asking twice is asking nothing.
            result = control.apply_archive(archive, allow_older=True)
            self.after(
                0,
                lambda: messagebox.showinfo(
                    f"{paths.TOOL_NAME}: Aktualisieren", "\n".join(result.lines), parent=self
                ),
            )
            if result.ok:
                self.after(EXIT_DELAY_MS, self._finalize_exit)

        self._in_background("updating", work)

    def _menu_doctor(self) -> None:
        log.info("Menue: %s", MENU_DOCTOR)

        def work() -> None:
            # Writing and opening the report is the only effect a diagnosis has;
            # it changes neither the state nor the display (design D21).
            control.run_doctor(report=True, open_report=True)

        self._in_background("checking", work)

    def _menu_logs(self) -> None:
        log.info("Menue: %s", MENU_LOGS)
        result = control.open_logs()
        if not result.ok:
            log.warning("Aufzeichnungsordner liess sich nicht oeffnen: %s", " ".join(result.lines))

    def _menu_settings(self) -> None:
        """The second way to a changed setting, next to running the setup again.

        In a thread of its own like every long menu action here: the window draws
        on the main one, and the message about the restart would freeze it until
        someone clicked the message away. Locked during a recording like the two
        entries above it - a changed folder takes effect at the next start, and
        the running recording would go on writing where it started.
        """
        log.info("Menue: %s", MENU_SETTINGS)
        from tkinter import messagebox

        def work() -> None:
            result = control.open_settings()
            self.after(
                0,
                lambda: messagebox.showinfo(
                    f"{paths.TOOL_NAME}: Einstellungen", "\n".join(result.lines), parent=self
                ),
            )

        self._in_background("settings", work)

    def _menu_about(self) -> None:
        log.info("Menue: %s", MENU_ABOUT)
        from tkinter import messagebox

        messagebox.showinfo(
            f"{paths.TOOL_NAME}: Info", "\n".join(control.about_lines()), parent=self
        )

    # --- Ending -------------------------------------------------------------

    def _on_close(self) -> None:
        """The window X. Never loses a recording (design D7).

        No question is asked. The window already has a two-stage button for
        discarding; whoever closes the window does not want to throw the
        recording away, and a dialog that asks the obvious gets confirmed
        unread after the third time.
        """
        self._request_shutdown("Fenster geschlossen", silent=False)

    def _request_shutdown(self, reason: str, *, silent: bool) -> None:
        if self._closing:
            log.debug("Zweites Beenden verworfen, der Abschluss laeuft bereits")
            return

        self._closing = True
        self._silent_failures = silent
        log.info(">>> Beenden: %s", reason)

        if not self._recording:
            self._finalize_exit()
            return

        self._disarm_discard()
        self._set_busy("finishing")
        threading.Thread(target=lambda: self._do_stop(then_exit=True), daemon=True).start()

    def _finalize_exit(self) -> None:
        log.info("=== Recorder UI beendet ===")
        try:
            self.destroy()
        except Exception:  # noqa: BLE001 - a window already gone is the wanted outcome
            log.debug("Fenster war bereits geschlossen", exc_info=True)

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
            # Noted in the state folder so `status` can answer the question from
            # another process entirely.
            instance.mark_recording()
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

    def _do_stop(self, then_exit: bool = False) -> None:
        outcome: Outcome | None = None
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
            instance.clear_recording()
            outcome = self._merge_and_save()
            message = outcome.status

        except Exception:
            message = "stop error"
            self._recording = False
            instance.clear_recording()
            log.error("Unerwarteter Fehler in _do_stop()", exc_info=True)

        self.after(0, lambda: self._finish_stop(message, then_exit=then_exit, outcome=outcome))

    def _merge_and_save(self) -> Outcome:
        """Hands the recording over. What is shown is decided in `_finish_stop`."""
        return finish_recording(
            self._mic_filepath,
            self._system_filepath,
            self._timestamp or datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
            self.recording_dir,
            self.target_dir,
        )

    def _report_failure(self, outcome: Outcome) -> None:
        from tkinter import messagebox

        messagebox.showwarning(
            f"{paths.TOOL_NAME}: Aufnahme nicht abgeschlossen",
            f"Was ist passiert:\n{outcome.cause}\n\n{outcome.whereabouts}\n\n"
            "Was tun: Die Ursache beheben; danach lässt sich die Aufnahme aus "
            "diesen beiden Spuren noch zusammenmischen.",
            parent=self,
        )

    def _finish_stop(
        self,
        message: str,
        then_exit: bool = False,
        outcome: Outcome | None = None,
    ) -> None:
        self._busy = False
        self._refresh_status()
        self.status_label.configure(text=message, text_color=TEXT_MUTED)
        log.info(f"Status final: {message}")

        # Shown here and not from the working thread, and shown *before* the
        # window may go: the status line is 280 px wide and carries neither the
        # cause nor a folder, so this dialog is the only place that names where
        # the takes stayed. Scheduled the other way round it would be torn down
        # by `_finalize_exit` a second later - unread, on exactly the route
        # where a recording is at stake. Suppressed for a stop from outside:
        # nobody is in front of the window then, and a modal dialog would hold
        # the process until its deadline runs out.
        if outcome is not None and not outcome.ok and not self._silent_failures:
            self._report_failure(outcome)

        if then_exit:
            self.after(EXIT_DELAY_MS, self._finalize_exit)
            return

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
            instance.clear_recording()
            deleted = self._delete_raw_files()
            message = "discarded" if deleted else "discarded (cleanup failed)"

        except Exception:
            message = "discard error"
            self._recording = False
            instance.clear_recording()
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

    def _poll_ui_loop(self) -> None:
        """The clock of the window. It has to survive its own mistakes.

        Everything the application still notices while it stands open rides in
        here: the geometry it defends and the stop request from outside. An
        exception used to end the chain of `after` calls for good - the window
        stayed on screen, `stop` ran into its deadline and nothing said why.
        """
        try:
            self._poll_ui_once()
        except Exception:  # noqa: BLE001 - see docstring
            log.error("Fehler in der Anzeigeschleife", exc_info=True)
        finally:
            try:
                self.after(UI_POLL_MS, self._poll_ui_loop)
            except tk.TclError:
                log.debug("Anzeigeschleife endet mit dem Fenster")

    def _poll_ui_once(self) -> None:
        self._enforce_window_size()

        # The loop that already defends the window geometry is the only clock
        # this application has, so the stop request rides along in it rather
        # than getting a timer of its own (design D10). Console signals never
        # reach a windowless process, which is why the request is a file.
        if not self._closing and instance.stop_requested():
            self._request_shutdown("von außen angefordert", silent=True)

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


EXIT_ALREADY_RUNNING = 3
EXIT_PREFLIGHT_FAILED = 2
EXIT_UNEXPECTED = 4


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


def _report_unexpected() -> None:
    """The last visible channel a windowless start has left.

    Everything below the preflight has a message of its own; this one catches
    what nobody foresaw - a broken installation, a display that refuses, a
    dependency that is not there. Without it such a start ends the way this whole
    change set out to abolish: no window, no message, nothing on screen.

    The cause is deliberately not in the text. Whatever ends up here is a
    technical sentence in English, and the reader's next move does not depend on
    it; it stands in full, with its whole trace, in the log the message names.
    """
    try:
        import tkinter
        from tkinter import messagebox

        root = tkinter.Tk()
        root.withdraw()
        messagebox.showerror(
            f"{paths.TOOL_NAME} kann nicht starten",
            "Was ist passiert:\nBeim Starten ist etwas schiefgegangen, "
            "das nicht vorgesehen war.\n\n"
            "Was tun:\nSetup.cmd im Ordner von Backrec doppelklicken. "
            f"Bleibt es dabei, die Aufzeichnung unter {paths.logs_dir()} an Tobias schicken.",
        )
        root.destroy()
    except Exception:  # noqa: BLE001 - the log entry is the part that matters
        log.error("Hinweis auf den unerwarteten Fehler liess sich nicht anzeigen", exc_info=True)


def _thread_failed(args: threading.ExceptHookArgs) -> None:
    """An uncaught exception in a worker thread, into the log instead of nowhere.

    The default hook writes to stderr, and under `pythonw` there is none. A
    recording thread that ends this way would otherwise simply stop delivering
    audio, with no trace of the reason.
    """
    log.error(
        "Unerwarteter Fehler im Hintergrund (%s)",
        getattr(args.thread, "name", "unbekannt"),
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )


def main() -> int:
    """The checked way into the window (design D5, D6).

    Log first, then the single-instance check, then the preflight, and only
    afterwards a window. Every step before the window is one that used to fail
    silently under `pythonw`.
    """
    bootstrap()
    threading.excepthook = _thread_failed

    try:
        return _open_window()
    except Exception:  # noqa: BLE001 - see `_report_unexpected`
        log.critical("Start durch einen unerwarteten Fehler abgebrochen", exc_info=True)
        _report_unexpected()
        return EXIT_UNEXPECTED


def _open_window() -> int:
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
        instance.clear_recording()
    return 0


if __name__ == "__main__":
    sys.exit(main())
