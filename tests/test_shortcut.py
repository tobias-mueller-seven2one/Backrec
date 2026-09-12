"""The desktop shortcut: what it contains, what it reports, what it removes.

COM is replaced by a writer and a reader that keep the link in a dictionary.
That is not only convenience: the decisions - is one there, is it ours, is its
target still there - are the part that can go wrong, and they have to be
reachable without a desktop.
"""

from __future__ import annotations

import os
from pathlib import Path

from backrec import shortcut


class FakeDesktop:
    """A desktop that stores links as text files plus their contents."""

    def __init__(self) -> None:
        self.written: dict[Path, shortcut.ShortcutSpec] = {}
        self.error: str | None = None

    def write(self, link: Path, spec: shortcut.ShortcutSpec) -> str | None:
        if self.error is not None:
            return self.error
        link.parent.mkdir(parents=True, exist_ok=True)
        link.write_text("lnk", encoding="utf-8")
        self.written[link] = spec
        return None

    def read(self, link: Path) -> dict[str, str] | None:
        spec = self.written.get(link)
        if spec is None:
            return None
        return {"target": spec.target, "arguments": spec.arguments, "workdir": spec.workdir}


def _installed_repo(tmp_path: Path) -> Path:
    """A folder that looks set up: the windowless interpreter exists."""
    repo = tmp_path / "Backrec"
    scripts = repo / ".venv" / "Scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "pythonw.exe").write_bytes(b"MZ")
    return repo


def test_the_link_starts_the_environment_interpreter_with_the_module(tmp_path: Path) -> None:
    repo = _installed_repo(tmp_path)

    spec = shortcut.build_spec(repo)

    assert spec.target == str(repo / ".venv" / "Scripts" / "pythonw.exe")
    assert spec.arguments == "-m backrec"
    assert spec.workdir == str(repo)


def test_building_names_path_name_and_the_fixed_paths(tmp_path: Path) -> None:
    repo = _installed_repo(tmp_path)
    desktop = tmp_path / "Desktop"
    fake = FakeDesktop()

    result = shortcut.create(repo, desktop, writer=fake.write)

    assert result.ok
    assert result.path == desktop / shortcut.SHORTCUT_NAME
    joined = " ".join(result.lines)
    assert str(result.path) in joined
    assert "Backrec" in joined
    assert "neu aufgebaut" in joined


def test_building_twice_replaces_without_failing(tmp_path: Path) -> None:
    repo = _installed_repo(tmp_path)
    desktop = tmp_path / "Desktop"
    fake = FakeDesktop()

    shortcut.create(repo, desktop, writer=fake.write)
    second = shortcut.create(repo, desktop, writer=fake.write)

    assert second.ok
    assert len(fake.written) == 1


def test_building_without_an_environment_names_the_setup(tmp_path: Path) -> None:
    repo = tmp_path / "Backrec"
    repo.mkdir()
    fake = FakeDesktop()

    result = shortcut.create(repo, tmp_path / "Desktop", writer=fake.write)

    assert not result.ok
    assert result.code != 0
    assert "Setup.cmd" in " ".join(result.lines)


def test_a_failed_build_names_path_and_reason(tmp_path: Path) -> None:
    repo = _installed_repo(tmp_path)
    fake = FakeDesktop()
    fake.error = "Zugriff verweigert"

    result = shortcut.create(repo, tmp_path / "Desktop", writer=fake.write)

    assert not result.ok
    assert "Zugriff verweigert" in " ".join(result.lines)


def test_status_reads_target_arguments_and_workdir_back(tmp_path: Path) -> None:
    repo = _installed_repo(tmp_path)
    desktop = tmp_path / "Desktop"
    fake = FakeDesktop()
    shortcut.create(repo, desktop, writer=fake.write)

    result = shortcut.status(repo, desktop, reader=fake.read)

    assert result.installed
    joined = " ".join(result.notes)
    assert "pythonw.exe" in joined
    assert "-m backrec" in joined
    assert str(repo) in joined


def test_status_names_a_link_of_another_installation(tmp_path: Path) -> None:
    mine = _installed_repo(tmp_path)
    other = _installed_repo(tmp_path / "anderswo")
    desktop = tmp_path / "Desktop"
    fake = FakeDesktop()
    shortcut.create(other, desktop, writer=fake.write)

    result = shortcut.status(mine, desktop, reader=fake.read)

    assert not result.installed
    assert result.belongs_here is False
    assert "andere" in " ".join(result.notes)


def test_status_without_a_link_ends_without_error(tmp_path: Path) -> None:
    result = shortcut.status(tmp_path / "Backrec", tmp_path / "Desktop")

    assert not result.exists
    assert not result.installed
    assert "keine" in " ".join(result.notes).lower()


def test_status_reports_an_unreadable_link_as_present(tmp_path: Path) -> None:
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    (desktop / shortcut.SHORTCUT_NAME).write_text("kaputt", encoding="utf-8")

    result = shortcut.status(tmp_path / "Backrec", desktop, reader=lambda _link: None)

    assert result.exists
    assert not result.readable
    assert "nicht lesen" in " ".join(result.notes)


def test_a_link_of_the_retired_start_route_does_not_count_as_installed(tmp_path: Path) -> None:
    """The old `Start_Recorder.bat` icon satisfies every other condition."""
    repo = _installed_repo(tmp_path)
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    (repo / "Start_Recorder.bat").write_text("@echo off", encoding="utf-8")

    fake = FakeDesktop()
    fake.written[desktop / shortcut.SHORTCUT_NAME] = shortcut.ShortcutSpec(
        target=str(repo / "Start_Recorder.bat"),
        arguments="",
        workdir=str(repo),
        description="alt",
    )
    (desktop / shortcut.SHORTCUT_NAME).write_text("lnk", encoding="utf-8")

    result = shortcut.status(repo, desktop, reader=fake.read)

    assert result.belongs_here
    assert result.target_exists
    assert not result.target_current
    assert not result.installed
    assert "abgelösten Startweg" in " ".join(result.notes)


def test_status_reports_a_target_that_no_longer_exists(tmp_path: Path) -> None:
    repo = _installed_repo(tmp_path)
    desktop = tmp_path / "Desktop"
    fake = FakeDesktop()
    shortcut.create(repo, desktop, writer=fake.write)
    (repo / ".venv" / "Scripts" / "pythonw.exe").unlink()

    result = shortcut.status(repo, desktop, reader=fake.read)

    assert not result.installed
    assert "gibt es nicht mehr" in " ".join(result.notes)


def test_removing_deletes_only_the_link(tmp_path: Path) -> None:
    repo = _installed_repo(tmp_path)
    desktop = tmp_path / "Desktop"
    fake = FakeDesktop()
    link = shortcut.create(repo, desktop, writer=fake.write).path

    result = shortcut.remove(desktop)

    assert result.ok
    assert link is not None and not link.exists()
    assert (repo / ".venv" / "Scripts" / "pythonw.exe").is_file()


def test_removing_mentions_that_a_running_application_stays(tmp_path: Path) -> None:
    repo = _installed_repo(tmp_path)
    desktop = tmp_path / "Desktop"
    fake = FakeDesktop()
    shortcut.create(repo, desktop, writer=fake.write)

    result = shortcut.remove(desktop)

    assert "Fenster-X" in " ".join(result.lines)


def test_removing_without_a_link_ends_without_error(tmp_path: Path) -> None:
    result = shortcut.remove(tmp_path / "Desktop")

    assert result.ok
    assert result.code == 0


def test_a_failed_removal_names_path_and_reason(tmp_path: Path, monkeypatch) -> None:
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    link = desktop / shortcut.SHORTCUT_NAME
    link.write_text("lnk", encoding="utf-8")

    def refuse(_self) -> None:
        raise OSError(5, "Zugriff verweigert")

    monkeypatch.setattr(Path, "unlink", refuse)

    result = shortcut.remove(desktop)

    assert not result.ok
    assert result.code != 0
    assert str(link) in " ".join(result.lines)


def test_the_desktop_folder_follows_a_redirected_profile(monkeypatch, tmp_path: Path) -> None:
    """Without the registry the fallback has to at least follow the profile."""
    monkeypatch.setattr(shortcut, "_SHELL_FOLDERS_KEY", r"Software\Backrec\definitiv-nicht-da")
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "Profil"))

    assert shortcut.desktop_folder() == tmp_path / "Profil" / "Desktop"


def test_building_establishes_no_logon_persistence(tmp_path: Path) -> None:
    """The whole point of the desktop over the startup folder (design D14)."""
    repo = _installed_repo(tmp_path)
    fake = FakeDesktop()

    shortcut.create(repo, tmp_path / "Desktop", writer=fake.write)

    for link, spec in fake.written.items():
        assert "Startup" not in str(link)
        assert os.path.normcase(spec.workdir) == os.path.normcase(str(repo))


# --- Leftover icons on the desktop (H5) ---------------------------------------


def _entry(desktop: Path, name: str = shortcut.SHORTCUT_NAME) -> Path:
    desktop.mkdir(parents=True, exist_ok=True)
    link = desktop / name
    link.write_text("lnk", encoding="utf-8")
    return link


def _reader(links: dict[Path, dict[str, str]]):
    return lambda link: links.get(link)


def test_a_dead_icon_of_ours_is_found_under_any_name(tmp_path: Path) -> None:
    """Tobias' leftover pointed at `Start_Recorder.bat` and could be named anything.

    Assignment therefore runs over the target path, not over the name.
    """
    repo = _installed_repo(tmp_path)
    desktop = tmp_path / "Desktop"
    dead = _entry(desktop, "Start_Recorder.lnk")

    found = shortcut.stale_entries(
        desktop,
        repo,
        _reader({dead: {"target": str(repo / "Start_Recorder.bat"), "arguments": "", "workdir": str(repo)}}),
    )

    assert found == [dead]


def test_a_dead_icon_of_ours_is_removed(tmp_path: Path) -> None:
    repo = _installed_repo(tmp_path)
    desktop = tmp_path / "Desktop"
    dead = _entry(desktop, "Backrec starten.lnk")

    removed = shortcut.remove_stale(
        desktop,
        repo,
        _reader({dead: {"target": str(repo / "Start_Recorder.bat"), "arguments": "", "workdir": str(repo)}}),
    )

    assert removed == (dead,)
    assert not dead.exists()


def test_an_icon_on_a_former_start_route_counts_as_stale(tmp_path: Path) -> None:
    """The file exists, but it is not the way this version starts."""
    repo = _installed_repo(tmp_path)
    (repo / "Start_Recorder.bat").write_text("@echo off", encoding="utf-8")
    desktop = tmp_path / "Desktop"
    old = _entry(desktop, "Aufnahme.lnk")

    assert shortcut.is_stale(
        {"target": str(repo / "Start_Recorder.bat"), "arguments": "", "workdir": str(repo)}, repo
    )

    removed = shortcut.remove_stale(
        desktop,
        repo,
        _reader({old: {"target": str(repo / "Start_Recorder.bat"), "arguments": "", "workdir": str(repo)}}),
    )

    assert removed == (old,)


def test_a_foreign_icon_is_never_removed(tmp_path: Path) -> None:
    """The desktop belongs to the user, not to this tool."""
    repo = _installed_repo(tmp_path)
    other = _installed_repo(tmp_path / "anderswo")
    desktop = tmp_path / "Desktop"
    stranger = _entry(desktop, "Irgendein anderes Programm.lnk")
    second = _entry(desktop, "Backrec - Kopie.lnk")

    removed = shortcut.remove_stale(
        desktop,
        repo,
        _reader(
            {
                stranger: {"target": r"D:\fremd\weg.exe", "arguments": "", "workdir": r"D:\fremd"},
                second: {"target": str(other / "weg.exe"), "arguments": "", "workdir": str(other)},
            }
        ),
    )

    assert removed == ()
    assert stranger.exists()
    assert second.exists(), "die zweite Einrichtung gehört jemand anderem"


def test_the_current_icon_survives(tmp_path: Path) -> None:
    repo = _installed_repo(tmp_path)
    desktop = tmp_path / "Desktop"
    fake = FakeDesktop()
    shortcut.create(repo, desktop, writer=fake.write)
    current = desktop / shortcut.SHORTCUT_NAME

    removed = shortcut.remove_stale(desktop, repo, fake.read)

    assert removed == ()
    assert current.exists()


def test_a_dead_icon_next_to_a_working_one_is_removed_alone(tmp_path: Path) -> None:
    repo = _installed_repo(tmp_path)
    desktop = tmp_path / "Desktop"
    fake = FakeDesktop()
    shortcut.create(repo, desktop, writer=fake.write)
    current = desktop / shortcut.SHORTCUT_NAME
    dead = _entry(desktop, "Start_Recorder.lnk")
    fake.written[dead] = shortcut.ShortcutSpec(
        target=str(repo / "Start_Recorder.bat"), arguments="", workdir=str(repo), description="alt"
    )

    removed = shortcut.remove_stale(desktop, repo, fake.read)

    assert removed == (dead,)
    assert current.exists()
    assert not dead.exists()


def test_an_unreadable_icon_is_left_alone(tmp_path: Path) -> None:
    """Unreadable is not ours: without contents nothing places it in this folder."""
    repo = _installed_repo(tmp_path)
    desktop = tmp_path / "Desktop"
    broken = _entry(desktop, "kaputt.lnk")

    assert shortcut.remove_stale(desktop, repo, lambda _link: None) == ()
    assert broken.exists()


def test_the_message_names_how_many_icons_were_removed() -> None:
    assert shortcut.stale_message(1) == "1 veraltete Verknüpfung vom Desktop entfernt."
    assert shortcut.stale_message(2) == "2 veraltete Verknüpfungen vom Desktop entfernt."


def test_the_plain_status_reads_only_the_expected_name(tmp_path: Path) -> None:
    """Reading every link starts a helper per file; `status` must stay cheap."""
    repo = _installed_repo(tmp_path)
    desktop = tmp_path / "Desktop"
    stranger = _entry(desktop, "Irgendein anderes Programm.lnk")
    read: list[Path] = []

    def counting(link: Path) -> dict[str, str] | None:
        read.append(link)
        return None

    shortcut.status(repo, desktop, reader=counting)

    assert read == []
    assert stranger in shortcut.all_entries(desktop)
