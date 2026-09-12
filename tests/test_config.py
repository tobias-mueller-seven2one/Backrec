"""Format, layers, expansion, strict checking - and the one-time migration."""

from __future__ import annotations

from pathlib import Path

import pytest

from backrec import config as config_module, paths, wizard

REPO = paths.repo_root()


def write_config_file(target: Path, values: dict[str, str]) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key} = '{value}'" for key, value in values.items()]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def test_a_complete_file_yields_exactly_those_folders(tmp_path, config_values):
    target = write_config_file(tmp_path / "config.toml", config_values)

    loaded = config_module.load_config(target)

    assert loaded.recording_dir == Path(config_values["recording_dir"])
    assert loaded.target_dir == Path(config_values["target_dir"])
    assert loaded.log_level == "INFO"
    assert loaded.source_path == target


def test_a_missing_mandatory_key_names_the_key_and_the_file(tmp_path, config_values):
    target = write_config_file(tmp_path / "config.toml", {"recording_dir": config_values["recording_dir"]})

    with pytest.raises(config_module.ConfigError) as error:
        config_module.load_config(target)

    assert "target_dir" in str(error.value)
    assert str(target) in str(error.value)


def test_an_unreadable_file_names_the_cause(tmp_path):
    target = tmp_path / "config.toml"
    target.write_text("recording_dir = 'C:\\Ablage\nkaputt", encoding="utf-8")

    with pytest.raises(config_module.ConfigError) as error:
        config_module.load_config(target)

    assert str(target) in str(error.value)


def test_a_missing_file_points_at_the_setup(tmp_path):
    with pytest.raises(config_module.ConfigError, match="Setup.cmd"):
        config_module.load_config(tmp_path / "gibtesnicht.toml")


def test_a_relative_path_is_a_configuration_error(tmp_path, config_values):
    target = write_config_file(
        tmp_path / "config.toml", {**config_values, "target_dir": "Aufnahmen\\Input"}
    )

    with pytest.raises(config_module.ConfigError, match="vollständiger Pfad"):
        config_module.load_config(target)


def test_an_empty_value_is_a_missing_value(tmp_path, config_values):
    target = write_config_file(tmp_path / "config.toml", {**config_values, "target_dir": "  "})

    with pytest.raises(config_module.ConfigError, match="target_dir"):
        config_module.load_config(target)


def test_a_variable_is_expanded_before_use(tmp_path, config_values, monkeypatch):
    monkeypatch.setenv("BACKREC_TESTABLAGE", str(tmp_path / "woanders"))
    target = write_config_file(
        tmp_path / "config.toml", {**config_values, "target_dir": "%BACKREC_TESTABLAGE%\\Input"}
    )

    loaded = config_module.load_config(target)

    assert loaded.target_dir == tmp_path / "woanders" / "Input"


def test_an_unresolvable_variable_names_key_and_name(tmp_path, config_values, monkeypatch):
    monkeypatch.delenv("BACKREC_GIBTESNICHT", raising=False)
    target = write_config_file(
        tmp_path / "config.toml", {**config_values, "target_dir": "%BACKREC_GIBTESNICHT%\\Input"}
    )

    with pytest.raises(config_module.ConfigError) as error:
        config_module.load_config(target)

    assert "target_dir" in str(error.value)
    assert "BACKREC_GIBTESNICHT" in str(error.value)


# --- Layers -------------------------------------------------------------------


def test_an_environment_variable_beats_the_file(tmp_path, config_values, monkeypatch):
    target = write_config_file(tmp_path / "config.toml", config_values)
    monkeypatch.setenv("BACKREC_TARGET_DIR", str(tmp_path / "aus-der-umgebung"))

    loaded = config_module.load_config(target)

    assert loaded.target_dir == tmp_path / "aus-der-umgebung"
    assert loaded.origin_of("target_dir") == config_module.LAYER_ENV
    assert loaded.origin_of("recording_dir") == config_module.LAYER_FILE


def test_the_command_line_beats_the_environment(tmp_path, config_values, monkeypatch):
    target = write_config_file(tmp_path / "config.toml", config_values)
    monkeypatch.setenv("BACKREC_TARGET_DIR", str(tmp_path / "aus-der-umgebung"))

    loaded = config_module.load_config(
        target, overrides={"target_dir": str(tmp_path / "von-der-zeile")}
    )

    assert loaded.target_dir == tmp_path / "von-der-zeile"
    assert loaded.origin_of("target_dir") == config_module.LAYER_CLI


def test_the_variables_that_choose_the_file_are_no_values_in_it(monkeypatch):
    monkeypatch.setenv(paths.ENV_CONFIG, "C:\\woanders\\config.toml")
    monkeypatch.setenv(paths.ENV_HOME, "C:\\woanders")
    monkeypatch.setenv("BACKREC_TARGET_DIR", "C:\\Ziel")

    assert config_module.env_overrides() == {"target_dir": "C:\\Ziel"}


def test_a_value_without_a_layer_comes_from_the_code():
    values, origins = config_module.layered({}, {}, {})

    assert values["log_level"] == config_module.DEFAULT_LOG_LEVEL
    assert origins["log_level"] == config_module.LAYER_CODE


# --- Template -----------------------------------------------------------------


def test_the_template_carries_every_known_key():
    raw = config_module.read_toml(paths.example_config_path(REPO))

    assert set(raw) == set(config_module.KNOWN_KEYS)
    assert not config_module.unknown_keys(raw)


def test_the_template_names_no_installation():
    """Checked through the release build's own patterns, not a second list.

    Spelling the company name out here would make this file a hit against
    itself and abort the very build the check exists for.
    """
    from backrec import release

    text = paths.example_config_path(REPO).read_text(encoding="utf-8")

    assert release.user_path_hits(text) == []
    assert paths.CLOUD_VARIABLE not in text


def test_an_unknown_key_is_reported_and_never_removed(tmp_path, config_values):
    target = write_config_file(tmp_path / "config.toml", {**config_values, "vertipper": "x"})

    raw = config_module.read_toml(target)

    assert config_module.unknown_keys(raw) == ("vertipper",)
    assert config_module.load_config(target).target_dir == Path(config_values["target_dir"])


def test_a_key_that_is_new_in_the_template_shows_up_as_drift(config_values):
    template = config_module.read_toml(paths.example_config_path(REPO))

    assert config_module.missing_keys(config_values, template) == ("log_level",)


# --- Migration ----------------------------------------------------------------


def write_env(target: Path, lines: list[str]) -> Path:
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def test_a_complete_env_is_taken_over_once(tmp_path):
    legacy = write_env(
        tmp_path / ".env",
        [
            "# Kommentar",
            "BACKREC_RECORDING_DIR=C:\\Ablage\\Recording",
            'BACKREC_TARGET_DIR="C:\\Ablage\\Input"',
        ],
    )
    destination = tmp_path / "config.toml"

    result = config_module.migrate_legacy(legacy, destination, repo=REPO)

    assert result.migrated
    assert result.keys == ("recording_dir", "target_dir")
    assert result.source == legacy and result.target == destination
    written = config_module.read_toml(destination)
    assert written["recording_dir"] == "C:\\Ablage\\Recording"
    assert written["target_dir"] == "C:\\Ablage\\Input"


def test_the_old_file_stays_where_it_is(tmp_path):
    legacy = write_env(
        tmp_path / ".env",
        ["BACKREC_RECORDING_DIR=C:\\Ablage\\Recording", "BACKREC_TARGET_DIR=C:\\Ablage\\Input"],
    )

    config_module.migrate_legacy(legacy, tmp_path / "config.toml", repo=REPO)

    assert legacy.is_file()


def test_an_existing_new_file_is_never_overwritten(tmp_path, config_values):
    legacy = write_env(
        tmp_path / ".env",
        ["BACKREC_RECORDING_DIR=C:\\Alt\\Recording", "BACKREC_TARGET_DIR=C:\\Alt\\Input"],
    )
    destination = write_config_file(tmp_path / "config.toml", config_values)

    result = config_module.migrate_legacy(legacy, destination, repo=REPO)

    assert not result.migrated
    assert result.reason == "vorhanden"
    assert config_module.read_toml(destination)["target_dir"] == config_values["target_dir"]


def test_an_incomplete_env_hands_over_what_it_has(tmp_path):
    legacy = write_env(tmp_path / ".env", ["BACKREC_TARGET_DIR=C:\\Ablage\\Input"])
    destination = tmp_path / "config.toml"

    result = config_module.migrate_legacy(legacy, destination, repo=REPO)

    assert not result.migrated
    assert result.missing == ("recording_dir",)
    assert result.values == {"target_dir": "C:\\Ablage\\Input"}
    assert not destination.exists()


def test_without_an_old_file_nothing_happens(tmp_path):
    result = config_module.migrate_legacy(tmp_path / ".env", tmp_path / "config.toml", repo=REPO)

    assert not result.migrated
    assert result.reason == "keine alte Datei"


def test_the_written_file_keeps_the_comments_of_the_template(tmp_path):
    destination = tmp_path / "config.toml"

    wizard.write_config(
        destination, {"recording_dir": "C:\\A\\Recording", "target_dir": "C:\\A\\Input"}, repo=REPO
    )

    text = destination.read_text(encoding="utf-8")
    assert text.count("#") > 5
    assert "recording_dir = 'C:\\A\\Recording'" in text
