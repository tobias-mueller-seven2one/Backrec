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


def test_the_menu_carries_the_four_entries(window) -> None:
    labels = [window._menu.entrycget(index, "label") for index in range(4)]

    assert labels == [app.MENU_UPDATE, app.MENU_DOCTOR, app.MENU_LOGS, app.MENU_ABOUT]


# --- Menu state ---------------------------------------------------------------


def test_without_a_recording_every_entry_can_be_chosen() -> None:
    assert app.menu_entry(app.MENU_DOCTOR, recording=False) == (app.MENU_DOCTOR, "normal")


def test_during_a_recording_the_two_long_entries_are_locked_with_a_reason() -> None:
    for label in (app.MENU_UPDATE, app.MENU_DOCTOR):
        text, state = app.menu_entry(label, recording=True)
        assert state == "disabled"
        assert label in text
        assert "Aufnahme" in text


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
