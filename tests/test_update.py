"""Updating from an archive: check first, then stage, then mirror.

Every check has to be able to fail before the first file is touched - that is
what makes "the previous state stays runnable" more than an intention.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from backrec import paths, release, update


def archive(
    tmp_path: Path,
    files: dict[str, str],
    *,
    version: str = "2026.10.1",
    tool: str = "Backrec",
    top_level: str = "Backrec",
    manifest: bool = True,
    corrupt: str | None = None,
) -> Path:
    target = tmp_path / f"{tool}-{version}.zip"
    entries = [
        {
            "path": name,
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "size": len(content.encode("utf-8")),
        }
        for name, content in files.items()
    ]

    with zipfile.ZipFile(target, "w") as bundle:
        for name, content in files.items():
            payload = "verfaelscht" if name == corrupt else content
            bundle.writestr(f"{top_level}/{name}", payload)
        if manifest:
            bundle.writestr(
                f"{top_level}/{release.MANIFEST_NAME}",
                json.dumps({"tool": tool, "version": version, "files": entries}),
            )
    return target


def installed(tmp_path: Path, version: str = "2026.09.1") -> Path:
    root = tmp_path / "Backrec"
    root.mkdir(parents=True, exist_ok=True)
    (root / paths.VERSION_FILE_NAME).write_text(f"{version}\n", encoding="utf-8")
    (root / ".venv").mkdir(exist_ok=True)
    (root / ".venv" / "marker").write_text("bleibt", encoding="utf-8")
    return root


# --- Reading ------------------------------------------------------------------


def test_an_archive_of_this_tool_is_read_with_version_and_files(tmp_path: Path) -> None:
    bundle = archive(tmp_path, {"README.md": "neu"})

    info = update.inspect(bundle)

    assert info.tool == "Backrec"
    assert info.version == "2026.10.1"
    assert [entry.path for entry in info.entries] == ["README.md"]


def test_an_archive_of_another_tool_is_refused(tmp_path: Path) -> None:
    bundle = archive(tmp_path, {"README.md": "neu"}, tool="AMD-Transcription", top_level="AMD")

    with pytest.raises(update.UpdateError, match="Werkzeug"):
        update.inspect(bundle)


def test_an_archive_without_the_accompanying_list_is_refused(tmp_path: Path) -> None:
    bundle = archive(tmp_path, {"README.md": "neu"}, manifest=False)

    with pytest.raises(update.UpdateError):
        update.inspect(bundle)


def test_a_file_that_is_not_an_archive_is_refused(tmp_path: Path) -> None:
    broken = tmp_path / "kaputt.zip"
    broken.write_bytes(b"keinesfalls ein Archiv")

    with pytest.raises(update.UpdateError, match="beschädigt"):
        update.inspect(broken)


def test_a_missing_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(update.UpdateError, match="gibt es nicht"):
        update.inspect(tmp_path / "nichts.zip")


def test_the_plan_names_both_versions(tmp_path: Path) -> None:
    root = installed(tmp_path)
    bundle = archive(tmp_path, {"README.md": "neu"})

    decision = update.plan(bundle, repo=root)

    assert decision.installed_version == "2026.09.1"
    assert decision.info.version == "2026.10.1"
    assert decision.newer


def test_an_older_archive_is_recognised_as_such(tmp_path: Path) -> None:
    root = installed(tmp_path, version="2026.11.1")
    bundle = archive(tmp_path, {"README.md": "neu"})

    decision = update.plan(bundle, repo=root)

    assert not decision.newer
    assert decision.needs_confirmation_for_age


# --- Staging ------------------------------------------------------------------


def test_staging_checks_every_file_against_its_checksum(tmp_path: Path) -> None:
    bundle = archive(tmp_path, {"README.md": "neu", "VERSION": "2026.10.1"})
    info = update.inspect(bundle)

    staged = update.stage(info, tmp_path / "staging")

    assert (staged / "README.md").read_text(encoding="utf-8") == "neu"


def test_a_corrupt_file_aborts_and_leaves_nothing_behind(tmp_path: Path) -> None:
    bundle = archive(tmp_path, {"README.md": "neu"}, corrupt="README.md")
    info = update.inspect(bundle)
    staging = tmp_path / "staging"

    with pytest.raises(update.UpdateError, match="beschädigt"):
        update.stage(info, staging)

    assert not staging.exists()


def test_an_entry_leading_out_of_the_folder_is_refused(tmp_path: Path) -> None:
    target = tmp_path / "boese.zip"
    with zipfile.ZipFile(target, "w") as bundle:
        bundle.writestr("Backrec/../ausgebrochen.txt", "x")
        bundle.writestr(
            f"Backrec/{release.MANIFEST_NAME}",
            json.dumps({"tool": "Backrec", "version": "2026.10.1", "files": []}),
        )
    info = update.inspect(target)

    with pytest.raises(update.UpdateError, match="unzulässig"):
        update.stage(info, tmp_path / "staging")


# --- Mirroring ----------------------------------------------------------------


def test_mirroring_copies_the_new_files_into_the_existing_folder(tmp_path: Path) -> None:
    root = installed(tmp_path)
    bundle = archive(tmp_path, {"README.md": "neu", "src/backrec/app.py": "code"})
    info = update.inspect(bundle)
    staged = update.stage(info, tmp_path / "staging")

    copied, removed = update.mirror(staged, info, root, previous=())

    assert copied == 2
    assert removed == ()
    assert (root / "README.md").read_text(encoding="utf-8") == "neu"
    assert (root / "src" / "backrec" / "app.py").is_file()


def test_mirroring_leaves_the_built_environment_alone(tmp_path: Path) -> None:
    root = installed(tmp_path)
    bundle = archive(tmp_path, {"README.md": "neu"})
    info = update.inspect(bundle)
    staged = update.stage(info, tmp_path / "staging")

    update.mirror(staged, info, root, previous=())

    assert (root / ".venv" / "marker").read_text(encoding="utf-8") == "bleibt"


def test_a_file_of_the_previous_release_is_removed(tmp_path: Path) -> None:
    root = installed(tmp_path)
    (root / "alt.py").write_text("alt", encoding="utf-8")
    previous = (release.ManifestEntry(path="alt.py", sha256="x", size=3),)
    bundle = archive(tmp_path, {"README.md": "neu"})
    info = update.inspect(bundle)
    staged = update.stage(info, tmp_path / "staging")

    _copied, removed = update.mirror(staged, info, root, previous=previous)

    assert removed == ("alt.py",)
    assert not (root / "alt.py").exists()


def test_a_file_the_user_created_is_never_touched(tmp_path: Path) -> None:
    root = installed(tmp_path)
    mine = root / "meine-notizen.txt"
    mine.write_text("gehoert mir", encoding="utf-8")
    bundle = archive(tmp_path, {"README.md": "neu"})
    info = update.inspect(bundle)
    staged = update.stage(info, tmp_path / "staging")

    update.mirror(staged, info, root, previous=())

    assert mine.read_text(encoding="utf-8") == "gehoert mir"


def test_a_missing_previous_list_removes_nothing(tmp_path: Path) -> None:
    root = installed(tmp_path)
    (root / "alt.py").write_text("alt", encoding="utf-8")
    bundle = archive(tmp_path, {"README.md": "neu"})
    info = update.inspect(bundle)
    staged = update.stage(info, tmp_path / "staging")

    _copied, removed = update.mirror(staged, info, root)

    assert removed == ()
    assert (root / "alt.py").is_file()


def test_the_accompanying_list_is_kept_outside_the_folder(tmp_path: Path) -> None:
    """Extracting over the folder would otherwise destroy the yardstick."""
    entries = (release.ManifestEntry(path="README.md", sha256="x", size=3),)

    written = update.write_installed_manifest(entries, "2026.10.1")

    assert written == paths.installed_manifest_path()
    assert paths.state_dir() in written.parents
    assert update.read_installed_manifest() == entries


def test_an_unreadable_previous_list_is_treated_as_absent() -> None:
    target = paths.installed_manifest_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{kein gueltiger Inhalt", encoding="utf-8")

    assert update.read_installed_manifest() == ()


def test_stale_files_are_exactly_the_difference() -> None:
    previous = (
        release.ManifestEntry(path="alt.py", sha256="a", size=1),
        release.ManifestEntry(path="bleibt.py", sha256="b", size=1),
    )
    current = (release.ManifestEntry(path="bleibt.py", sha256="c", size=1),)

    assert update.stale_files(previous, current) == ("alt.py",)


def test_the_staging_folder_sits_next_to_the_tool_folder(tmp_path: Path) -> None:
    root = installed(tmp_path)

    assert update.staging_dir(root).parent == root.parent
    assert update.staging_dir(root).name.startswith(root.name)
