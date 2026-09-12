"""The window, as far as it can be checked without a recording.

The recording core itself has no coverage on purpose - it needs real devices
(design, Non-Goals). What is checked here is everything around it: the geometry
the window defends, the menu, and the two ways out that must never lose a
recording.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backrec import app, instance
from backrec.delivery import Outcome
from backrec.update import ArchiveInfo, UpdatePlan


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


def test_the_gear_displaces_no_recording_control(window) -> None:
    assert window.menu_button.winfo_ismapped()
    assert window.btn_start.winfo_ismapped()
    assert window.btn_stop.winfo_ismapped()
    assert window.btn_discard.winfo_ismapped()


def test_the_gear_shows_and_hides_its_hover_text(window) -> None:
    """A gear without a label is not self-explanatory - and an untried tooltip
    is a second window that only fails in front of the user."""
    # On the canvas, not on the button: CustomTkinter forwards `bind` to the
    # canvas and the text label, and a real mouse enters those, not the frame
    # around them.
    canvas = window.menu_button._canvas

    canvas.event_generate("<Enter>")
    window.update()
    assert window._tooltip is not None

    canvas.event_generate("<Leave>")
    window.update()
    assert window._tooltip is None


def test_the_menu_carries_the_five_entries(window) -> None:
    labels = [window._menu.entrycget(index, "label") for index in range(5)]

    assert labels == [
        app.MENU_UPDATE,
        app.MENU_DOCTOR,
        app.MENU_LOGS,
        app.MENU_SETTINGS,
        app.MENU_ABOUT,
    ]


def test_the_settings_sit_at_position_nine_of_the_suite_order(window) -> None:
    """After the logs, before the details - as in the tray of the neighbours."""
    labels = [window._menu.entrycget(index, "label") for index in range(5)]

    assert labels.index(app.MENU_SETTINGS) == labels.index(app.MENU_LOGS) + 1
    assert labels.index(app.MENU_ABOUT) == labels.index(app.MENU_SETTINGS) + 1


# --- Menu state ---------------------------------------------------------------


def test_without_a_recording_every_entry_can_be_chosen() -> None:
    assert app.menu_entry(app.MENU_DOCTOR, recording=False) == (app.MENU_DOCTOR, "normal")
    assert app.menu_entry(app.MENU_SETTINGS, recording=False) == (app.MENU_SETTINGS, "normal")


def test_during_a_recording_the_three_long_entries_are_locked_with_a_reason() -> None:
    for label in (app.MENU_UPDATE, app.MENU_DOCTOR, app.MENU_SETTINGS):
        text, state = app.menu_entry(label, recording=True)
        assert state == "disabled"
        assert label in text
        assert "Aufnahme" in text


# --- The question before an update --------------------------------------------


def _plan(version: str, installed: str, *, newer: bool) -> UpdatePlan:
    return UpdatePlan(
        info=ArchiveInfo(
            archive=Path("Backrec.zip"),
            tool="Backrec",
            version=version,
            top_level="Backrec",
            entries=(),
        ),
        installed_version=installed,
        newer=newer,
        same=version == installed,
    )


def test_the_question_before_an_update_names_both_versions() -> None:
    text = app.update_question(_plan("2026.10.1", "2026.09.1", newer=True))

    assert "2026.09.1" in text
    assert "2026.10.1" in text


def test_an_archive_that_is_not_newer_says_so_before_anything_happens() -> None:
    text = app.update_question(_plan("2026.08.1", "2026.09.1", newer=False))

    assert "nicht neuer" in text
    assert "2026.09.1" in text
    assert "2026.08.1" in text


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
