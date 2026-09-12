"""Shared fixtures.

Every test runs against a suite folder inside `tmp_path`. That is not only
hygiene: the point of `MEMOSUITE_HOME` is that nothing outside it is needed, so
pointing it at a throwaway folder is also the test of that claim.
"""

from __future__ import annotations

import pytest

from backrec import logging_setup, paths


@pytest.fixture(autouse=True)
def suite_home(tmp_path, monkeypatch):
    """Moves configuration, logs and state into a throwaway folder."""
    home = tmp_path / "MemoSuite"
    monkeypatch.setenv(paths.ENV_SUITE_HOME, str(home))
    monkeypatch.delenv(paths.ENV_CONFIG, raising=False)
    monkeypatch.delenv(paths.ENV_HOME, raising=False)
    for name in ("BACKREC_RECORDING_DIR", "BACKREC_TARGET_DIR"):
        monkeypatch.delenv(name, raising=False)
    logging_setup.reset_for_tests()
    yield home
    logging_setup.reset_for_tests()


@pytest.fixture
def config_values(tmp_path) -> dict[str, str]:
    """A complete set of mandatory values with folders in the throwaway area."""
    base = tmp_path / "Aufnahmen"
    return {
        "recording_dir": str(base / "Recording"),
        "target_dir": str(base / "Input"),
    }
