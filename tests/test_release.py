"""Building the archive - above all: what never gets into it.

The guide check has a test per rule, because it is the one check that stands
between a colleague and an archive that drops him exactly where the guide was
written to catch him.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from backrec import paths, release

GUIDE = paths.guide_path()


def make_repo(tmp_path: Path, *, version: str = "2026.09.1") -> Path:
    """A small tool folder without version control - the walking fallback."""
    root = tmp_path / "Backrec"
    (root / "src" / "backrec").mkdir(parents=True)
    (root / "openspec" / "changes" / "irgendwas").mkdir(parents=True)
    (root / ".venv" / "Scripts").mkdir(parents=True)
    (root / "logs").mkdir()

    (root / paths.VERSION_FILE_NAME).write_text(f"{version}\n", encoding="utf-8")
    (root / "Setup.cmd").write_text("@echo off\n", encoding="utf-8")
    (root / "README.md").write_text("# Backrec\n", encoding="utf-8")
    (root / "config.example.toml").write_text("recording_dir = ''\n", encoding="utf-8")
    (root / "src" / "backrec" / "__init__.py").write_text("", encoding="utf-8")

    (root / "config.toml").write_text("recording_dir = 'C:/irgendwo'\n", encoding="utf-8")
    (root / ".env").write_text("BACKREC_TARGET_DIR=C:/irgendwo\n", encoding="utf-8")
    (root / "Backrec.lnk").write_bytes(b"lnk")
    (root / ".venv" / "Scripts" / "pythonw.exe").write_bytes(b"MZ")
    (root / "logs" / "backrec.log").write_text("alt\n", encoding="utf-8")
    (root / "openspec" / "changes" / "irgendwas" / "tasks.md").write_text("- [ ]\n", encoding="utf-8")
    (root / "openspec" / "config.yaml").write_text("schema: x\n", encoding="utf-8")

    (root / paths.GUIDE_FILE_NAME).write_bytes(GUIDE.read_bytes())
    return root


def build(root: Path, output: Path) -> release.ReleaseResult:
    return release.build(root, output, skip_lock_check=True)


# --- Selection ----------------------------------------------------------------


def test_the_archive_carries_one_folder_as_its_top_level(tmp_path: Path) -> None:
    root = make_repo(tmp_path)

    result = build(root, tmp_path / "out")

    with zipfile.ZipFile(result.archive) as bundle:
        tops = {name.split("/")[0] for name in bundle.namelist()}
    assert tops == {paths.TOOL_NAME}


def test_the_archive_is_named_after_tool_and_version(tmp_path: Path) -> None:
    root = make_repo(tmp_path, version="2026.10.2")

    result = build(root, tmp_path / "out")

    assert result.archive.name == "Backrec-2026.10.2.zip"


@pytest.mark.parametrize(
    "unwanted",
    [".venv/Scripts/pythonw.exe", "logs/backrec.log", ".env", "config.toml", "Backrec.lnk"],
)
def test_nothing_local_ever_reaches_the_archive(tmp_path: Path, unwanted: str) -> None:
    root = make_repo(tmp_path)

    result = build(root, tmp_path / "out")

    with zipfile.ZipFile(result.archive) as bundle:
        packed = {name.split("/", 1)[1] for name in bundle.namelist()}
    assert unwanted not in packed


def test_the_acceptance_list_stays_out_of_the_archive() -> None:
    """It names internal tasks and belongs to Tobias, not to a colleague."""
    assert release.is_excluded(Path("ABNAHME.md"))
    assert not release.is_excluded(Path("README.md"))


def test_the_planning_artefacts_stay_out(tmp_path: Path) -> None:
    """The whole folder, not only the proposals in it.

    Section 12 of the convention keeps planning off a colleague's machine, and
    a folder that arrives half empty is a question waiting to be asked.
    """
    root = make_repo(tmp_path)

    result = build(root, tmp_path / "out")

    with zipfile.ZipFile(result.archive) as bundle:
        assert not [name for name in bundle.namelist() if "openspec/" in name]


def test_the_guide_sits_at_the_top_level_and_is_listed_with_its_checksum(tmp_path: Path) -> None:
    root = make_repo(tmp_path)

    result = build(root, tmp_path / "out")

    with zipfile.ZipFile(result.archive) as bundle:
        assert f"{paths.TOOL_NAME}/{paths.GUIDE_FILE_NAME}" in bundle.namelist()
        manifest = json.loads(
            bundle.read(f"{paths.TOOL_NAME}/{release.MANIFEST_NAME}").decode("utf-8")
        )

    listed = {entry["path"]: entry for entry in manifest["files"]}
    assert paths.GUIDE_FILE_NAME in listed
    assert len(listed[paths.GUIDE_FILE_NAME]["sha256"]) == 64


def test_the_manifest_names_tool_version_date_and_every_file(tmp_path: Path) -> None:
    root = make_repo(tmp_path)

    result = build(root, tmp_path / "out")

    with zipfile.ZipFile(result.archive) as bundle:
        manifest = json.loads(
            bundle.read(f"{paths.TOOL_NAME}/{release.MANIFEST_NAME}").decode("utf-8")
        )

    assert manifest["tool"] == paths.TOOL_NAME
    assert manifest["version"] == "2026.09.1"
    assert manifest["created"]
    assert len(manifest["files"]) == len(result.entries)


# --- Checks -------------------------------------------------------------------


def test_a_version_of_the_wrong_shape_aborts(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    (root / paths.VERSION_FILE_NAME).write_text("irgendwas\n", encoding="utf-8")

    with pytest.raises(release.ReleaseError, match="Fassung"):
        build(root, tmp_path / "out")


def test_a_user_path_aborts_the_build_and_names_the_file(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    (root / "README.md").write_text(
        "Ablage unter " + "C:" + "\\Users" + "\\tobias\\Backrec\n", encoding="utf-8"
    )

    with pytest.raises(release.ReleaseError, match="README.md"):
        build(root, tmp_path / "out")


def test_a_cloud_folder_with_the_company_name_aborts(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    (root / "README.md").write_text("Ablage unter " + "One" + "Drive" + " - Firma\n", encoding="utf-8")

    with pytest.raises(release.ReleaseError):
        build(root, tmp_path / "out")


def test_the_own_user_name_aborts_even_without_a_drive_letter(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    (root / "README.md").write_text("Verantwortlich: keinmensch\n", encoding="utf-8")
    files = release.collect_files(root)

    with pytest.raises(release.ReleaseError):
        release.check_user_paths(root, files, username="keinmensch")


def test_something_that_looks_like_an_access_key_aborts(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    (root / "README.md").write_text("token = " + "sk" + "-abcdefgh12345678\n", encoding="utf-8")

    with pytest.raises(release.ReleaseError, match="Zugangs"):
        build(root, tmp_path / "out")


def test_a_file_in_another_character_set_is_still_checked(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    (root / "README.md").write_bytes(
        ("Ablage unter " + "C:" + "\\Users" + "\\t\u00f6bias\n").encode("cp1252")
    )

    with pytest.raises(release.ReleaseError, match="README.md"):
        build(root, tmp_path / "out")


# --- The guide ----------------------------------------------------------------


def write_guide(root: Path, lines: list[str], *, bom: bool = True, crlf: bool = True) -> Path:
    target = root / paths.GUIDE_FILE_NAME
    separator = "\r\n" if crlf else "\n"
    body = (separator.join(lines) + separator).encode("utf-8")
    target.write_bytes((b"\xef\xbb\xbf" if bom else b"") + body)
    return target


def valid_lines() -> list[str]:
    raw = GUIDE.read_bytes()[3:].decode("utf-8").split("\r\n")
    while raw and raw[-1] == "":
        raw.pop()
    return raw


def test_the_shipped_guide_obeys_every_rule() -> None:
    release.check_guide(GUIDE)


def test_a_missing_guide_aborts(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    (root / paths.GUIDE_FILE_NAME).unlink()

    with pytest.raises(release.ReleaseError, match="fehlt"):
        build(root, tmp_path / "out")


def test_a_guide_with_too_many_lines_aborts(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    lines = valid_lines()
    lines.extend(["  noch eine Zeile"] * (release.GUIDE_MAX_LINES + 1 - len(lines)))
    write_guide(root, lines)

    with pytest.raises(release.ReleaseError, match="Zeilen"):
        build(root, tmp_path / "out")


def test_a_line_that_is_too_long_aborts(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    lines = valid_lines()
    lines[1] = "x" * (release.GUIDE_MAX_LINE_LENGTH + 1)
    write_guide(root, lines)

    with pytest.raises(release.ReleaseError, match="Zeichen"):
        build(root, tmp_path / "out")


def test_a_guide_without_a_byte_order_mark_aborts(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    write_guide(root, valid_lines(), bom=False)

    with pytest.raises(release.ReleaseError, match="Bytereihenfolge"):
        build(root, tmp_path / "out")


def test_a_guide_with_the_wrong_line_endings_aborts(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    write_guide(root, valid_lines(), crlf=False)

    with pytest.raises(release.ReleaseError, match="Zeilenenden"):
        build(root, tmp_path / "out")


def test_a_technical_term_in_the_guide_aborts(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    lines = valid_lines()
    lines[1] = "Das Archiv liegt als zip bereit."
    write_guide(root, lines)

    with pytest.raises(release.ReleaseError, match="Fachbegriff"):
        build(root, tmp_path / "out")


def test_a_missing_section_aborts(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    lines = [line for line in valid_lines() if "Im Alltag" not in line]
    write_guide(root, lines)

    with pytest.raises(release.ReleaseError, match="Im Alltag"):
        build(root, tmp_path / "out")


def test_two_swapped_sections_abort(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    lines = valid_lines()
    first = next(index for index, line in enumerate(lines) if line.startswith("Im Alltag"))
    second = next(index for index, line in enumerate(lines) if line.startswith("Entfernen"))
    lines[first], lines[second] = lines[second], lines[first]
    write_guide(root, lines)

    with pytest.raises(release.ReleaseError):
        build(root, tmp_path / "out")


def test_a_path_in_the_guide_aborts(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    lines = valid_lines()
    lines[1] = "Entpacke es nach " + "C:" + "\\Werkzeuge."
    write_guide(root, lines)

    with pytest.raises(release.ReleaseError):
        build(root, tmp_path / "out")


def test_a_foreign_file_name_in_the_guide_aborts(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    lines = valid_lines()
    lines[1] = "Starte danach Start.cmd."
    write_guide(root, lines)

    with pytest.raises(release.ReleaseError, match="Dateiname"):
        build(root, tmp_path / "out")


def test_an_uncommitted_change_aborts_the_build(tmp_path: Path, monkeypatch) -> None:
    root = make_repo(tmp_path)
    (root / ".git").mkdir()

    def dirty(command, **_kwargs):
        import subprocess

        return subprocess.CompletedProcess(
            args=command, returncode=0, stdout=" M README.md\n?? notiz.txt\n", stderr=""
        )

    monkeypatch.setattr(release.subprocess, "run", dirty)

    with pytest.raises(release.ReleaseError, match="README.md"):
        release.check_worktree(root)


def test_an_untracked_file_alone_is_no_reason_to_abort(tmp_path: Path, monkeypatch) -> None:
    root = make_repo(tmp_path)
    (root / ".git").mkdir()

    def only_untracked(command, **_kwargs):
        import subprocess

        return subprocess.CompletedProcess(
            args=command, returncode=0, stdout="?? notiz.txt\n", stderr=""
        )

    monkeypatch.setattr(release.subprocess, "run", only_untracked)

    release.check_worktree(root)


def test_without_version_control_the_state_of_the_folder_is_not_checked(tmp_path: Path) -> None:
    release.check_worktree(make_repo(tmp_path))


def test_no_archive_is_left_behind_when_a_guide_rule_fails(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    output = tmp_path / "out"
    write_guide(root, valid_lines(), bom=False)

    with pytest.raises(release.ReleaseError):
        build(root, output)

    assert not output.exists() or list(output.glob("*.zip")) == []
