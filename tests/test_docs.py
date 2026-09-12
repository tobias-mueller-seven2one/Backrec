"""The colleague's text lives in exactly one place, and the README points at it.

Two audiences, two documents, and the failure mode they have is drift: the same
procedure described twice diverges at the first change. So the guide is the only
place with the colleague's text, and these tests keep the boundary.
"""

from __future__ import annotations

from backrec import control, paths, release

ROOT = paths.repo_root()

README = (ROOT / "README.md").read_text(encoding="utf-8")
GUIDE = paths.guide_path(ROOT).read_bytes()[3:].decode("utf-8")

# Developer routes. They belong in the README and nowhere near the guide.
DEVELOPER_ONLY = ("release", "update --git", "git pull", "pytest", "uv sync")


def test_the_readme_points_at_the_guide_in_its_first_lines() -> None:
    head = "\n".join(README.splitlines()[:8])

    assert paths.GUIDE_FILE_NAME in head


def test_the_readme_calls_the_guide_german_and_meant_for_colleagues() -> None:
    head = "\n".join(README.splitlines()[:8]).lower()

    assert "german" in head
    assert "colleague" in head


def test_the_readme_carries_no_section_for_colleagues() -> None:
    assert "For colleagues" not in README
    assert "Für Kollegen" not in README


def test_the_developer_routes_appear_only_in_the_readme() -> None:
    for route in DEVELOPER_ONLY:
        assert route in README
        assert route not in GUIDE


def test_the_readme_names_python_311_and_says_it_changed() -> None:
    assert "3.11" in README
    assert "3.10" in README


def test_the_readme_describes_the_failed_merge_and_where_the_takes_stay() -> None:
    assert "recording folder" in README
    assert "nothing" in README.lower()
    assert "transcribe the same conversation twice" in README


def test_the_readme_no_longer_promises_the_old_fallback() -> None:
    assert "falls back to saving both raw files" not in README


def test_the_readme_names_the_smartscreen_warning_for_third_party_installers() -> None:
    assert "SmartScreen" in README
    assert "Trotzdem ausführen" in README


def test_the_guide_explains_the_windows_warning_without_a_technical_term() -> None:
    """Step 2 of the guide, in the wording of the buttons."""
    assert "Weitere Informationen" in GUIDE
    assert "Trotzdem ausführen" in GUIDE
    assert "SmartScreen" not in GUIDE


def test_the_guide_names_the_gear_in_its_everyday_section() -> None:
    assert "Zahnrad" in GUIDE


def test_the_guide_carries_the_closing_line_the_convention_asks_for() -> None:
    assert "README.md" in GUIDE
    assert "das brauchst du nicht" in GUIDE


def test_the_guide_describes_no_procedure_backrec_does_not_have() -> None:
    for absent in ("Autostart", "neben der Uhr", "Infobereich", "Anmelden"):
        assert absent not in GUIDE


def test_the_about_entry_points_at_a_guide_that_exists() -> None:
    lines = control.about_lines(ROOT)

    assert any(str(paths.guide_path(ROOT)) in line for line in lines)
    assert paths.guide_path(ROOT).is_file()


def test_no_versioned_file_gives_a_machine_away() -> None:
    files = release.collect_files(ROOT)

    release.check_user_paths(ROOT, files)
    release.check_secrets(ROOT, files)


def test_the_template_and_the_documents_are_part_of_that_check() -> None:
    """Guards the check above: it is worthless if it skipped these three."""
    packed = {path.as_posix() for path in release.collect_files(ROOT)}

    assert "README.md" in packed
    assert paths.GUIDE_FILE_NAME in packed
    assert paths.EXAMPLE_CONFIG_FILE_NAME in packed
