"""The derivation from one base folder, and the optional handshake."""

from __future__ import annotations

import io
import tomllib
from pathlib import Path

import pytest

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
    # Name the base folder, confirm both folders, decline the further settings,
    # accept the shared file.
    assistant, _stream = make(answers=[str(tmp_path / "Basis"), "", "n", "j"])

    result = wizard.run(assistant, tmp_path / "config.toml", handshake_path=handshake, repo=REPO)

    assert result.handshake_written
    assert wizard.read_handshake(handshake) == str(tmp_path / "Basis")


def test_a_refusal_does_not_harm_the_setup(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "Profil"))
    handshake = tmp_path / "suite.toml"
    assistant, _stream = make(answers=[str(tmp_path / "Basis"), "", "n", "n"])

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


# --- Every setting as a question (convention section 5 step 3) ----------------


def setting(key: str, value, description: str = "") -> wizard.Setting:
    return wizard.Setting(
        key=key,
        kind=wizard.kind_of(key, value),
        description=description,
        choices=wizard.choices_for(key),
        secret=wizard.is_secret(key),
    )


def test_the_kind_of_a_setting_comes_from_the_value_of_the_template():
    assert wizard.kind_of("aktiv", True) is wizard.Kind.BOOL
    assert wizard.kind_of("anzahl", 5) is wizard.Kind.NUMBER
    assert wizard.kind_of("liste", ["a", "b"]) is wizard.Kind.LIST
    assert wizard.kind_of("log_level", "INFO") is wizard.Kind.CHOICE
    assert wizard.kind_of("target_dir", "C:\\A") is wizard.Kind.PATH
    assert wizard.kind_of("name", "Backrec") is wizard.Kind.TEXT


def test_a_yes_or_no_answer_is_read_as_such():
    entry = setting("aktiv", True)

    assert wizard.parse_answer(entry, "ja", True) is True
    assert wizard.parse_answer(entry, "nein", True) is False


def test_a_word_where_a_yes_belongs_is_refused_in_plain_language():
    entry = setting("aktiv", True)

    with pytest.raises(ValueError, match="ja oder nein"):
        wizard.parse_answer(entry, "vielleicht", True)


def test_a_whole_number_stays_a_whole_number():
    entry = setting("anzahl", 5)

    assert wizard.parse_answer(entry, "7", 5) == 7
    assert wizard.parse_answer(entry, "2,5", 5.0) == 2.5


def test_a_word_where_a_number_belongs_is_refused():
    entry = setting("anzahl", 5)

    with pytest.raises(ValueError, match="Zahl"):
        wizard.parse_answer(entry, "viele", 5)


def test_a_negative_number_is_refused():
    entry = setting("anzahl", 5)

    with pytest.raises(ValueError, match="ab 0"):
        wizard.parse_answer(entry, "-1", 5)


def test_a_list_is_split_at_the_commas():
    entry = setting("liste", ["a"])

    assert wizard.parse_answer(entry, "a, b ,c", ["a"]) == ["a", "b", "c"]


def test_an_empty_list_is_refused():
    entry = setting("liste", ["a"])

    with pytest.raises(ValueError, match="mindestens einen Eintrag"):
        wizard.parse_answer(entry, " , ", ["a"])


def test_a_value_outside_the_permitted_ones_is_refused_with_the_permitted_ones():
    entry = setting("log_level", "INFO")

    with pytest.raises(ValueError, match="DEBUG"):
        wizard.parse_answer(entry, "LAUT", "INFO")


def test_a_permitted_value_is_taken():
    entry = setting("log_level", "INFO")

    assert wizard.parse_answer(entry, "DEBUG", "INFO") == "DEBUG"


def test_a_folder_answer_is_expanded(monkeypatch, tmp_path):
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "Profil"))
    entry = setting("target_dir", "X")

    assert wizard.parse_answer(entry, "%USERPROFILE%\\Ziel", "X") == str(
        tmp_path / "Profil" / "Ziel"
    )


def test_an_empty_folder_answer_is_refused():
    entry = setting("target_dir", "X")

    with pytest.raises(ValueError, match="Ordner"):
        wizard.parse_answer(entry, "   ", "X")


def test_a_secret_never_appears_in_the_overview():
    entry = setting("api_key", "")

    assert entry.secret
    assert wizard.overview_lines([entry], {"api_key": "abc123"}) == ["api_key: gesetzt"]
    assert wizard.overview_lines([entry], {}) == ["api_key: nicht gesetzt"]


def test_the_overview_shows_every_other_value_as_it_is():
    entries = [setting("log_level", "INFO"), setting("aktiv", True)]

    assert wizard.overview_lines(entries, {"log_level": "DEBUG", "aktiv": False}) == [
        "log_level: DEBUG",
        "aktiv: nein",
    ]


def test_the_meaning_of_a_setting_is_one_sentence_from_the_template():
    comments = wizard.template_comments(repo=REPO)

    assert wizard.first_sentence(comments["log_level"]).endswith(".")
    assert len(wizard.first_sentence(comments["recording_dir"])) <= 101


def test_the_first_run_leaves_out_the_two_derived_folders(tmp_path):
    template = template_file(tmp_path)

    keys = [entry.key for entry in wizard.settings_from_template(template)]

    assert keys == ["log_level"]


def test_a_later_run_does_include_the_two_folders(tmp_path):
    template = template_file(tmp_path)

    keys = [
        entry.key for entry in wizard.settings_from_template(template, include_directories=True)
    ]

    assert keys == ["recording_dir", "target_dir", "log_level"]


def test_the_first_run_offers_the_remaining_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "Profil"))
    # Accept the base folder, confirm both folders, accept the offer, answer the
    # one remaining setting, decline the shared file.
    assistant, _stream = make(answers=["", "", "j", "DEBUG", "n"])

    result = wizard.run(
        assistant, tmp_path / "config.toml", handshake_path=tmp_path / "suite.toml", repo=REPO
    )

    assert result.values["log_level"] == "DEBUG"
    assert "log_level = 'DEBUG'" in result.config_path.read_text(encoding="utf-8")


def test_declining_the_offer_leaves_the_values_of_the_template(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "Profil"))
    assistant, _stream = make(answers=["", "", "n", "n"])

    result = wizard.run(
        assistant, tmp_path / "config.toml", handshake_path=tmp_path / "suite.toml", repo=REPO
    )

    assert "log_level" not in result.values
    assert "log_level = 'INFO'" in result.config_path.read_text(encoding="utf-8")


def test_an_unattended_first_run_asks_nothing_at_all(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "Profil"))
    assistant, stream = make()

    wizard.run(
        assistant,
        tmp_path / "config.toml",
        unattended=True,
        handshake_path=tmp_path / "suite.toml",
        repo=REPO,
    )

    assert "Weitere Einstellungen" not in stream.getvalue()


# --- A later run: overview and change -----------------------------------------


def written(tmp_path: Path, level: str = "INFO") -> Path:
    config = tmp_path / "config.toml"
    config.write_text(
        f"recording_dir = 'C:\\A'\ntarget_dir = 'C:\\B'\nlog_level = '{level}'\n",
        encoding="utf-8",
    )
    return config


def test_a_later_run_shows_what_is_set(tmp_path):
    config = written(tmp_path)
    assistant, stream = make(answers=["n"])

    wizard.review(assistant, config, repo=REPO)

    printed = stream.getvalue()
    assert "Die Einstellungen sind gerade so:" in printed
    assert "log_level: INFO" in printed
    assert "recording_dir: C:\\A" in printed


def test_pressing_enter_changes_nothing(tmp_path):
    config = written(tmp_path)
    before = config.read_text(encoding="utf-8")
    assistant, _stream = make(answers=[""])

    result = wizard.review(assistant, config, repo=REPO)

    assert result.changed == ()
    assert config.read_text(encoding="utf-8") == before


def test_a_later_run_changes_the_value_that_was_answered(tmp_path):
    config = written(tmp_path)
    # Change settings, keep both folders, then a new level.
    assistant, _stream = make(answers=["j", "", "", "ERROR"])

    result = wizard.review(assistant, config, repo=REPO)

    assert result.changed == ("log_level",)
    assert "log_level = 'ERROR'" in config.read_text(encoding="utf-8")
    assert "recording_dir = 'C:\\A'" in config.read_text(encoding="utf-8")


def test_a_change_keeps_every_comment_of_the_file(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        "# Wohin aufgenommen wird.\nrecording_dir = 'C:\\A'\n"
        "target_dir = 'C:\\B'\nlog_level = 'INFO'\n",
        encoding="utf-8",
    )
    assistant, _stream = make(answers=["j", "", "", "ERROR"])

    wizard.review(assistant, config, repo=REPO)

    assert "# Wohin aufgenommen wird." in config.read_text(encoding="utf-8")


def test_three_wrong_answers_leave_the_previous_value(tmp_path):
    config = written(tmp_path)
    assistant, stream = make(answers=["j", "", "", "laut", "lauter", "am lautesten"])

    result = wizard.review(assistant, config, repo=REPO)

    assert result.changed == ()
    assert "Der bisherige Wert bleibt stehen." in stream.getvalue()
    assert "log_level = 'INFO'" in config.read_text(encoding="utf-8")


def test_an_unattended_later_run_shows_nothing_and_asks_nothing(tmp_path):
    config = written(tmp_path)
    assistant, stream = make()

    result = wizard.review(assistant, config, unattended=True, repo=REPO)

    assert result.changed == ()
    assert stream.getvalue() == ""


def test_settings_that_cannot_be_read_are_no_reason_to_stop(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text("kein = = gueltiges", encoding="utf-8")
    assistant, _stream = make(answers=["j"])

    result = wizard.review(assistant, config, repo=REPO)

    assert result.changed == ()


def test_the_message_names_how_many_settings_were_changed():
    assert wizard.change_message(1) == "1 Einstellung geändert."
    assert wizard.change_message(2) == "2 Einstellungen geändert."
