"""The derivation from one base folder, and the optional handshake."""

from __future__ import annotations

import io
import tomllib
from pathlib import Path

from backrec import config as config_module, paths, wizard
from backrec.console import Assistant

REPO = paths.repo_root()


def make(answers: list[str] | None = None) -> tuple[Assistant, io.StringIO]:
    stream = io.StringIO()
    supplied = list(answers or [])
    assistant = Assistant(
        total_steps=7,
        stream=stream,
        interactive=True,
        color=False,
        input_fn=lambda _prompt: supplied.pop(0) if supplied else "",
    )
    return assistant, stream


def test_the_cloud_folder_is_the_suggestion_when_there_is_one(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.CLOUD_VARIABLE, str(tmp_path / "Wolke"))

    assert wizard.default_data_root() == tmp_path / "Wolke" / "Aufnahmen"


def test_without_a_cloud_folder_the_user_profile_is_the_suggestion(monkeypatch, tmp_path):
    monkeypatch.delenv(paths.CLOUD_VARIABLE, raising=False)
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "Profil"))

    assert wizard.default_data_root() == tmp_path / "Profil" / "Aufnahmen"


def test_the_recording_folder_never_sits_below_the_base_folder(monkeypatch, tmp_path):
    """Three files at roughly 20 MB a minute have no business in a cloud folder."""
    monkeypatch.setenv(paths.CLOUD_VARIABLE, str(tmp_path / "Wolke"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "Profil"))
    data_root = wizard.default_data_root()

    derived = wizard.derive_directories(data_root)

    assert derived["target_dir"] == data_root / "Input"
    assert derived["recording_dir"] == tmp_path / "Profil" / "Aufnahmen" / "Recording"
    assert tmp_path / "Wolke" not in derived["recording_dir"].parents


def test_both_values_end_up_in_the_file_as_explicit_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "Profil"))
    monkeypatch.delenv(paths.CLOUD_VARIABLE, raising=False)
    assistant, stream = make(answers=["", "", "n"])
    target = tmp_path / "config.toml"

    result = wizard.run(assistant, target, handshake_path=tmp_path / "suite.toml", repo=REPO)

    raw = config_module.read_toml(target)
    assert raw["recording_dir"] == result.values["recording_dir"]
    assert raw["target_dir"] == result.values["target_dir"]
    assert "Daraus ergeben sich zwei Ordner" in stream.getvalue()


def test_a_later_start_needs_no_knowledge_of_the_base_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "Profil"))
    assistant, _stream = make(answers=[str(tmp_path / "Basis"), "", "n"])
    target = tmp_path / "config.toml"

    wizard.run(assistant, target, handshake_path=tmp_path / "suite.toml", repo=REPO)

    loaded = config_module.load_config(target)
    assert loaded.target_dir == tmp_path / "Basis" / "Input"


def test_an_own_path_replaces_the_suggestion(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "Profil"))
    assistant, _stream = make(answers=[str(tmp_path / "Eigen"), "", "n"])

    result = wizard.run(
        assistant, tmp_path / "config.toml", handshake_path=tmp_path / "suite.toml", repo=REPO
    )

    assert result.values["target_dir"] == str(tmp_path / "Eigen" / "Input")


def test_a_rejected_derivation_asks_again(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "Profil"))
    assistant, _stream = make(answers=[str(tmp_path / "Erst"), "n", str(tmp_path / "Dann"), "", "n"])

    result = wizard.run(
        assistant, tmp_path / "config.toml", handshake_path=tmp_path / "suite.toml", repo=REPO
    )

    assert result.values["target_dir"] == str(tmp_path / "Dann" / "Input")


def test_a_value_taken_over_from_the_old_file_survives_the_derivation(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "Profil"))
    assistant, _stream = make(answers=["", "", "n"])

    result = wizard.run(
        assistant,
        tmp_path / "config.toml",
        handshake_path=tmp_path / "suite.toml",
        preset_values={"target_dir": str(tmp_path / "Uebernommen")},
        repo=REPO,
    )

    assert result.values["target_dir"] == str(tmp_path / "Uebernommen")


def test_an_existing_file_is_reported_and_left_alone(tmp_path, config_values):
    target = tmp_path / "config.toml"
    target.write_text("recording_dir = 'C:\\A'\ntarget_dir = 'C:\\B'\n", encoding="utf-8")
    assistant, stream = make()

    result = wizard.run(assistant, target, repo=REPO)

    assert not result.created
    assert "gibt es schon" in stream.getvalue()
    assert target.read_text(encoding="utf-8").startswith("recording_dir = 'C:\\A'")


# --- Handshake ----------------------------------------------------------------


def test_an_existing_handshake_is_the_suggestion(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "Profil"))
    handshake = tmp_path / "suite.toml"
    wizard.write_handshake(tmp_path / "Gemeinsam", handshake)
    assistant, stream = make(answers=["", ""])

    result = wizard.run(assistant, tmp_path / "config.toml", handshake_path=handshake, repo=REPO)

    assert result.values["target_dir"] == str(tmp_path / "Gemeinsam" / "Input")
    assert "Ein anderes Werkzeug" in stream.getvalue()


def test_without_a_handshake_writing_one_is_offered(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "Profil"))
    handshake = tmp_path / "suite.toml"
    assistant, _stream = make(answers=[str(tmp_path / "Basis"), "", "j"])

    result = wizard.run(assistant, tmp_path / "config.toml", handshake_path=handshake, repo=REPO)

    assert result.handshake_written
    assert wizard.read_handshake(handshake) == str(tmp_path / "Basis")


def test_a_refusal_does_not_harm_the_setup(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "Profil"))
    handshake = tmp_path / "suite.toml"
    assistant, _stream = make(answers=[str(tmp_path / "Basis"), "", "n"])

    result = wizard.run(assistant, tmp_path / "config.toml", handshake_path=handshake, repo=REPO)

    assert not result.handshake_written
    assert not handshake.exists()
    assert config_module.load_config(result.config_path).target_dir.name == "Input"


def test_an_unattended_run_writes_no_handshake(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "Profil"))
    handshake = tmp_path / "suite.toml"
    assistant, _stream = make()

    result = wizard.run(
        assistant, tmp_path / "config.toml", unattended=True, handshake_path=handshake, repo=REPO
    )

    assert result.created
    assert not handshake.exists()


def test_the_application_starts_without_the_shared_file(tmp_path, config_values):
    """Nothing reads the handshake at runtime; that is the whole point."""
    target = tmp_path / "config.toml"
    target.write_text(
        f"recording_dir = '{config_values['recording_dir']}'\n"
        f"target_dir = '{config_values['target_dir']}'\n",
        encoding="utf-8",
    )
    assert not paths.suite_handshake_path().exists()

    loaded = config_module.load_config(target)

    assert loaded.target_dir == Path(config_values["target_dir"])


def test_an_unreadable_handshake_is_simply_no_suggestion(tmp_path):
    handshake = tmp_path / "suite.toml"
    handshake.write_text("kein = = gueltiges", encoding="utf-8")

    assert wizard.read_handshake(handshake) is None


# --- New settings from the template (H2) --------------------------------------


TEMPLATE = """# Kopfzeile der Vorlage.

# Der Ordner, in den aufgenommen wird.
recording_dir = 'X'

# Der Ordner, in den kopiert wird.
target_dir = 'Y'

# Ausführlichkeit der Aufzeichnung,
# eine von vier Stufen.
log_level = 'INFO'
"""


def template_file(tmp_path: Path) -> Path:
    path = tmp_path / paths.EXAMPLE_CONFIG_FILE_NAME
    path.write_text(TEMPLATE, encoding="utf-8")
    return path


def test_the_setup_adds_a_setting_that_is_new_in_the_template(tmp_path):
    template = template_file(tmp_path)
    config = tmp_path / "config.toml"
    config.write_text("recording_dir = 'A'\ntarget_dir = 'B'\n", encoding="utf-8")

    added = wizard.complete_from_template(config, template)

    assert added == ("log_level",)
    assert "log_level = 'INFO'" in config.read_text(encoding="utf-8")


def test_the_added_setting_carries_the_comment_of_the_template(tmp_path):
    template = template_file(tmp_path)
    config = tmp_path / "config.toml"
    config.write_text("recording_dir = 'A'\ntarget_dir = 'B'\n", encoding="utf-8")

    wizard.complete_from_template(config, template)

    text = config.read_text(encoding="utf-8")
    assert "# Ausführlichkeit der Aufzeichnung," in text
    assert "# eine von vier Stufen." in text
    assert "# Kopfzeile der Vorlage." not in text, "die Kopfzeile gehört keinem Schlüssel"


def test_an_existing_value_is_never_overwritten(tmp_path):
    template = template_file(tmp_path)
    config = tmp_path / "config.toml"
    config.write_text("recording_dir = 'mein-ordner'\ntarget_dir = 'B'\n", encoding="utf-8")

    wizard.complete_from_template(config, template)

    with config.open("rb") as handle:
        values = tomllib.load(handle)
    assert values["recording_dir"] == "mein-ordner"
    assert values["target_dir"] == "B"


def test_adding_twice_changes_nothing_the_second_time(tmp_path):
    template = template_file(tmp_path)
    config = tmp_path / "config.toml"
    config.write_text("recording_dir = 'A'\ntarget_dir = 'B'\n", encoding="utf-8")

    first = wizard.complete_from_template(config, template)
    after_first = config.read_text(encoding="utf-8")
    second = wizard.complete_from_template(config, template)

    assert first
    assert second == ()
    assert config.read_text(encoding="utf-8") == after_first


def test_the_extended_file_stays_readable(tmp_path):
    """Read back with the real loader, not just eyeballed."""
    template = template_file(tmp_path)
    config = tmp_path / "config.toml"
    config.write_text(r"recording_dir = 'C:\Aufnahmen\Recording'" + "\n", encoding="utf-8")

    wizard.complete_from_template(config, template)

    with config.open("rb") as handle:
        values = tomllib.load(handle)
    assert values["recording_dir"] == r"C:\Aufnahmen\Recording"
    assert values["target_dir"] == "Y"
    assert values["log_level"] == "INFO"


def test_a_new_key_lands_before_the_first_section(tmp_path):
    """Appended behind a section header the key would belong to that section."""
    template = template_file(tmp_path)
    config = tmp_path / "config.toml"
    config.write_text(
        "recording_dir = 'A'\ntarget_dir = 'B'\n\n[eigenes]\nnotiz = 'x'\n", encoding="utf-8"
    )

    wizard.complete_from_template(config, template)

    with config.open("rb") as handle:
        values = tomllib.load(handle)
    assert values["log_level"] == "INFO"
    assert values["eigenes"] == {"notiz": "x"}


def test_a_missing_settings_file_is_left_alone(tmp_path):
    template = template_file(tmp_path)
    config = tmp_path / "config.toml"

    assert wizard.complete_from_template(config, template) == ()
    assert not config.exists()


def test_the_real_template_needs_no_completion_of_a_file_the_wizard_wrote(tmp_path, config_values):
    """A freshly written file carries every key the template has."""
    target = tmp_path / "config.toml"
    wizard.write_config(target, config_values, repo=REPO)

    assert wizard.complete_from_template(target, repo=REPO) == ()


def test_the_message_names_how_many_settings_were_added():
    assert wizard.completion_message(1) == "1 neue Einstellung mit Standardwert ergänzt."
    assert wizard.completion_message(3) == "3 neue Einstellungen mit Standardwerten ergänzt."
