"""The window, as far as it can be checked without a recording.

The recording core itself has no coverage on purpose - it needs real devices
(design, Non-Goals). What is checked here is everything around it: the geometry
the window defends, the click on the status line that is the only route out of
the window, and the two ways out that must never lose a recording.
"""

from __future__ import annotations

import pytest

from backrec import app, instance
from backrec.delivery import Outcome


@pytest.fixture(scope="module")
def window(tmp_path_factory):
    """One real window for all of these tests.

    Built once per module on purpose: a second Tk root in the same process
    occasionally fails to find its own Tcl library, and a flaky skip is worse
    than a shared window that none of these tests changes.
    """
    base = tmp_path_factory.mktemp("fenster")
    recording_dir = base / "Recording"
    target_dir = base / "Input"
    recording_dir.mkdir()
    target_dir.mkdir()

    try:
        app.configure_appearance()
        built = app.RecorderApp(recording_dir, target_dir)
    except Exception as exc:  # noqa: BLE001 - a machine without a display is not a failure
        pytest.skip(f"Kein Fenster moeglich: {exc}")

    built.update()
    yield built

    try:
        built.destroy()
    except Exception:  # noqa: BLE001 - already gone is the wanted outcome
        pass


# --- Geometry and controls ----------------------------------------------------


def test_the_window_keeps_its_width(window) -> None:
    assert window.winfo_width() == app.WINDOW_WIDTH
    assert window._fixed_size == (app.WINDOW_WIDTH, window.winfo_height())


def test_the_window_carries_no_menu_button(window) -> None:
    """The gear is gone, and nothing took its place (design D25)."""
    assert not hasattr(window, "menu_button")
    assert not hasattr(window, "_menu")


def test_every_recording_control_is_on_screen(window) -> None:
    assert window.status_label.winfo_ismapped()
    assert window.btn_start.winfo_ismapped()
    assert window.btn_stop.winfo_ismapped()
    assert window.btn_discard.winfo_ismapped()


def test_the_status_line_opens_no_hover_window(window) -> None:
    """The hand cursor is the only hint. A hover text was a second top-level
    window that landed outside the 280 px frame."""
    label = window.status_label._label
    before = set(window.winfo_children())

    label.event_generate("<Enter>")
    window.update()

    assert set(window.winfo_children()) == before
    assert window.status_label.cget("cursor") == "hand2"


# --- The click on the status line ---------------------------------------------


class Clicked:
    """Only what `_open_diagnosis` touches - the route to the control surface is under test."""

    def __init__(self, *, running: bool = False, closing: bool = False) -> None:
        self._diagnosis_running = running
        self._closing = closing


def _immediate_thread(monkeypatch) -> list[object]:
    started: list[object] = []

    class ImmediateThread:
        def __init__(self, target=None, daemon=False) -> None:
            self.target = target

        def start(self) -> None:
            started.append(self)
            self.target()

    monkeypatch.setattr(app.threading, "Thread", ImmediateThread)
    return started


def test_a_click_asks_the_control_surface_for_a_report(monkeypatch) -> None:
    """The window knows no checks of its own - it asks `control.run_doctor`."""
    calls: list[tuple[tuple, dict]] = []

    monkeypatch.setattr(
        app.control, "run_doctor", lambda *args, **kwargs: calls.append((args, kwargs))
    )
    started = _immediate_thread(monkeypatch)
    stub = Clicked()

    app.RecorderApp._open_diagnosis(stub)

    assert calls == [((), {"report": True, "open_report": True})]
    assert len(started) == 1, "in einem eigenen Faden, nie im Aufnahmefaden"


def test_a_second_click_during_the_first_run_does_nothing(monkeypatch) -> None:
    calls: list[object] = []

    monkeypatch.setattr(app.control, "run_doctor", lambda **_kwargs: calls.append(True))
    _immediate_thread(monkeypatch)

    app.RecorderApp._open_diagnosis(Clicked(running=True))

    assert calls == []


def test_a_click_while_the_window_is_closing_does_nothing(monkeypatch) -> None:
    calls: list[object] = []

    monkeypatch.setattr(app.control, "run_doctor", lambda **_kwargs: calls.append(True))
    _immediate_thread(monkeypatch)

    app.RecorderApp._open_diagnosis(Clicked(closing=True))

    assert calls == []


def test_a_failed_diagnosis_never_ends_the_window(monkeypatch) -> None:
    def boom(**_kwargs):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(app.control, "run_doctor", boom)
    _immediate_thread(monkeypatch)
    stub = Clicked()

    app.RecorderApp._open_diagnosis(stub)

    assert stub._diagnosis_running is False, "der Riegel faellt auch nach einem Fehler"


def test_a_click_leaves_the_status_line_untouched(window, monkeypatch) -> None:
    """The line is the only place that says "recording" in red (design D26)."""
    monkeypatch.setattr(app.control, "run_doctor", lambda **_kwargs: None)
    _immediate_thread(monkeypatch)
    window._recording = True
    window._refresh_status()
    before = window.status_label.cget("text")

    window._open_diagnosis()
    window.update()

    assert window.status_label.cget("text") == before
    window._recording = False
    window._refresh_status()


def test_the_click_is_allowed_during_a_recording(window, monkeypatch) -> None:
    """The diagnosis only reads, and a recording going wrong is when it is
    needed most (design D27)."""
    calls: list[object] = []

    monkeypatch.setattr(app.control, "run_doctor", lambda **_kwargs: calls.append(True))
    _immediate_thread(monkeypatch)
    window._recording = True

    window._open_diagnosis()

    assert calls == [True]
    window._recording = False


# --- Ending -------------------------------------------------------------------


class Stub:
    """Only what `_request_shutdown` touches - the guard is what is under test."""

    def __init__(self, recording: bool) -> None:
        self._closing = False
        self._silent_failures = False
        self._recording = recording
        self.finalised = 0
        self.busy_with: list[str] = []
        self.disarmed = 0

    def _disarm_discard(self) -> None:
        self.disarmed += 1

    def _set_busy(self, text: str) -> None:
        self.busy_with.append(text)

    def _finalize_exit(self) -> None:
        self.finalised += 1

    def _do_stop(self, then_exit: bool = False) -> None:
        self.stopped_with_exit = then_exit


def shutdown(stub: Stub, monkeypatch, *, silent: bool = False) -> None:
    started: list[object] = []

    class ImmediateThread:
        def __init__(self, target=None, daemon=False) -> None:
            self.target = target

        def start(self) -> None:
            started.append(self)
            self.target()

    monkeypatch.setattr(app.threading, "Thread", ImmediateThread)
    app.RecorderApp._request_shutdown(stub, "Test", silent=silent)


def test_closing_without_a_recording_ends_at_once(monkeypatch) -> None:
    stub = Stub(recording=False)

    shutdown(stub, monkeypatch)

    assert stub.finalised == 1
    assert stub.busy_with == []


def test_closing_during_a_recording_runs_the_closing_sequence(monkeypatch) -> None:
    stub = Stub(recording=True)

    shutdown(stub, monkeypatch)

    assert stub.busy_with == ["finishing"]
    assert stub.stopped_with_exit is True
    assert stub.finalised == 0


def test_a_second_close_never_starts_the_sequence_again(monkeypatch) -> None:
    stub = Stub(recording=True)

    shutdown(stub, monkeypatch)
    stub.busy_with.clear()
    shutdown(stub, monkeypatch)

    assert stub.busy_with == []


def test_a_stop_from_outside_suppresses_the_modal_failure_message(monkeypatch) -> None:
    """Nobody is in front of the window then, and a dialog would hold the process."""
    stub = Stub(recording=True)

    shutdown(stub, monkeypatch, silent=True)

    assert stub._silent_failures is True


def test_closing_by_the_window_shows_a_failure(monkeypatch) -> None:
    stub = Stub(recording=True)

    shutdown(stub, monkeypatch, silent=False)

    assert stub._silent_failures is False


# --- The request from outside -------------------------------------------------


def test_the_polling_loop_picks_up_a_stop_request(window, monkeypatch) -> None:
    asked: list[tuple[str, bool]] = []
    monkeypatch.setattr(
        window,
        "_request_shutdown",
        lambda reason, *, silent: asked.append((reason, silent)),
    )
    instance.request_stop()

    window._poll_ui_loop()

    assert asked and asked[0][1] is True


def test_the_polling_loop_stays_quiet_without_a_request(window, monkeypatch) -> None:
    asked: list[str] = []
    monkeypatch.setattr(
        window, "_request_shutdown", lambda reason, *, silent: asked.append(reason)
    )

    window._poll_ui_loop()

    assert asked == []


def test_the_polling_loop_survives_a_mistake_of_its_own(window, monkeypatch) -> None:
    """It is the only clock the application has.

    An exception used to end the chain of calls for good: the window stayed on
    screen, a stop from outside ran into its deadline, and the reason was
    nowhere - Tk reports into a channel that does not exist here.
    """
    rearmed: list[int] = []

    def boom() -> None:
        raise RuntimeError("kaputt")

    monkeypatch.setattr(window, "_poll_ui_once", boom)
    monkeypatch.setattr(window, "after", lambda delay, _callback: rearmed.append(delay))

    window._poll_ui_loop()

    assert rearmed == [app.UI_POLL_MS]


# --- The visible failure ------------------------------------------------------


FAILED = Outcome(
    ok=False,
    status="no result: mixer missing",
    cause="Das Programm zum Zusammenmischen ist nicht aufrufbar.",
    whereabouts="Beide Spuren liegen weiterhin in C:\\Aufnahmen.",
)


class Label:
    def configure(self, **_kwargs) -> None:
        pass


class Finishing:
    """Only what `_finish_stop` touches - the order of two steps is under test."""

    def __init__(self, *, silent: bool) -> None:
        self._busy = True
        self._silent_failures = silent
        self.status_label = Label()
        self.order: list[str] = []

    def _refresh_status(self) -> None:
        pass

    def _report_failure(self, _outcome) -> None:
        self.order.append("meldung")

    def _finalize_exit(self) -> None:
        self.order.append("ende")

    def after(self, _delay, _callback) -> None:
        self.order.append("geplant")


def test_a_failed_close_shows_its_message_before_the_window_may_go() -> None:
    """The dialog is the only place naming where the takes stayed.

    Scheduled the other way round it is torn down by the exit a second later -
    unread, and on exactly the route where a recording is at stake.
    """
    stub = Finishing(silent=False)

    app.RecorderApp._finish_stop(stub, "no result", then_exit=True, outcome=FAILED)

    assert stub.order == ["meldung", "geplant"]


def test_a_stop_from_outside_closes_without_a_dialog() -> None:
    stub = Finishing(silent=True)

    app.RecorderApp._finish_stop(stub, "no result", then_exit=True, outcome=FAILED)

    assert stub.order == ["geplant"]


def test_a_successful_close_shows_no_failure() -> None:
    stub = Finishing(silent=False)

    app.RecorderApp._finish_stop(
        stub, "saved (merged)", then_exit=True, outcome=Outcome(ok=True, status="saved (merged)")
    )

    assert stub.order == ["geplant"]


# --- The start that nobody foresaw --------------------------------------------


def test_an_unexpected_start_failure_is_reported_instead_of_silent(monkeypatch) -> None:
    """Under `pythonw` there is no console, so this is the last channel left."""
    shown: list[bool] = []

    def boom() -> int:
        raise RuntimeError("kaputt")

    monkeypatch.setattr(app, "bootstrap", lambda: None)
    monkeypatch.setattr(app, "_open_window", boom)
    monkeypatch.setattr(app, "_report_unexpected", lambda: shown.append(True))

    assert app.main() == app.EXIT_UNEXPECTED
    assert shown == [True]
