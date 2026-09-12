"""The derivation from one base folder, and the optional handshake."""

from __future__ import annotations

import io
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
