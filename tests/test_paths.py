"""Where the tool looks for its files - and where it must not look."""

from __future__ import annotations

import os
from pathlib import Path

from backrec import paths, version


def test_without_variables_everything_sits_under_the_local_app_data(tmp_path, monkeypatch):
    monkeypatch.delenv(paths.ENV_SUITE_HOME, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData"))

    assert paths.tool_home() == tmp_path / "AppData" / "MemoSuite" / "Backrec"
    assert paths.config_path() == paths.tool_home() / "config.toml"
    assert paths.log_path() == paths.tool_home() / "logs" / "backrec.log"
    assert paths.state_dir() == paths.tool_home() / "state"


def test_a_moved_suite_folder_takes_everything_with_it(tmp_path, monkeypatch):
    moved = tmp_path / "woanders"
    monkeypatch.setenv(paths.ENV_SUITE_HOME, str(moved))

    assert paths.tool_home() == moved / "Backrec"
    assert paths.logs_dir() == moved / "Backrec" / "logs"
    assert paths.suite_handshake_path() == moved / "suite.toml"


def test_a_redirected_configuration_file_leaves_logs_and_state_alone(tmp_path, monkeypatch):
    elsewhere = tmp_path / "profile" / "backrec.toml"
    monkeypatch.setenv(paths.ENV_CONFIG, str(elsewhere))

    assert paths.config_path() == elsewhere
    assert paths.logs_dir() == paths.tool_home() / "logs"


def test_the_command_line_beats_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv(paths.ENV_CONFIG, str(tmp_path / "aus-der-umgebung.toml"))

    assert paths.config_path(tmp_path / "von-der-zeile.toml") == tmp_path / "von-der-zeile.toml"


def test_a_foreign_working_directory_changes_nothing(tmp_path, monkeypatch):
    before = paths.repo_root()
    monkeypatch.chdir(tmp_path)

    assert paths.repo_root() == before


def test_the_override_wins_over_every_search(tmp_path, monkeypatch):
    monkeypatch.setenv(paths.ENV_HOME, str(tmp_path / "eigener-ordner"))

    assert paths.repo_root() == tmp_path / "eigener-ordner"


def test_the_override_comes_back_in_its_canonical_spelling(tmp_path, monkeypatch):
    """The folder is compared as text - against a record and against a shortcut.

    A relative or an abbreviated spelling would read as a different installation
    and make a running instance or an existing icon look like somebody else's.
    """
    folder = tmp_path / "eigener-ordner"
    folder.mkdir()
    monkeypatch.setenv(paths.ENV_HOME, str(tmp_path / "eigener-ordner" / "." / ""))

    assert paths.repo_root() == folder.resolve()
    assert paths.repo_root().is_absolute()


def test_the_repository_of_this_working_tree_carries_its_marker():
    root = paths.repo_root()

    assert paths.has_repo_marker(root), root
    assert (root / "pyproject.toml").is_file()


def test_the_marker_search_stops_at_the_first_folder_that_has_one(tmp_path):
    outer = tmp_path / "aussen"
    inner = outer / "innen"
    inner.mkdir(parents=True)
    (outer / paths.VERSION_FILE_NAME).write_text("2026.09.1\n", encoding="utf-8")

    assert paths.has_repo_marker(outer)
    assert not paths.has_repo_marker(inner)


def test_a_path_value_expands_variables_in_both_spellings(monkeypatch):
    monkeypatch.setenv("BACKREC_TESTORT", str(Path("C:/Ablage")))

    assert paths.expand_path("%BACKREC_TESTORT%\\Recording") == Path("C:/Ablage/Recording")
    assert paths.expand_path("$BACKREC_TESTORT/Recording") == Path("C:/Ablage/Recording")
    assert paths.expand_path("~").is_absolute()


def test_the_version_comes_from_the_file_and_compares_as_numbers(tmp_path):
    (tmp_path / paths.VERSION_FILE_NAME).write_text("2026.09.2\r\n", encoding="utf-8-sig")

    assert version.read_version(tmp_path) == "2026.09.2"
    assert version.is_newer("2026.10.1", "2026.09.2")
    assert not version.is_newer("2026.09.2", "2026.10.1")
    assert not version.is_newer("irgendwas", "2026.09.2")
    assert version.parse_version("2026.09.1") == (2026, 9, 1)


def test_a_missing_version_file_is_no_reason_to_fail(tmp_path):
    assert version.read_version(tmp_path) == version.UNKNOWN


def test_the_tool_version_of_this_working_tree_has_the_agreed_shape():
    assert version.parse_version(paths.tool_version()) is not None


def test_no_module_creates_a_folder_when_it_is_imported(tmp_path, monkeypatch):
    """The old module level made two folders on import (main.pyw:37-38)."""
    home = tmp_path / "unberuehrt"
    monkeypatch.setenv(paths.ENV_SUITE_HOME, str(home))

    import importlib

    for name in ("backrec.paths", "backrec.merge", "backrec.delivery", "backrec.instance"):
        importlib.reload(importlib.import_module(name))

    assert not home.exists()
    assert not os.path.exists(paths.tool_home())
