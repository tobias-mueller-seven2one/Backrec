"""The version, read from the `VERSION` file, and the comparison of two of them.

Free of every package import on purpose: the setup reads the version before a
runtime exists, and an update compares it before anything is unpacked. That is
also why the version lives in a text file and not in `pyproject.toml` - one line
of text is readable from a batch file, a TOML value is not (design D18).
"""

from __future__ import annotations

import re
from pathlib import Path

VERSION_FILE_NAME = "VERSION"
UNKNOWN = "unbekannt"

_VERSION_PATTERN = re.compile(r"^\s*(\d+)\.(\d+)\.(\d+)\s*$")


def version_file_path(root: Path) -> Path:
    return root / VERSION_FILE_NAME


def read_version(root: Path) -> str:
    """The installed version, straight from the file.

    Returns `unbekannt` instead of raising: a missing version file must never be
    the reason a diagnosis cannot run.
    """
    try:
        text = version_file_path(root).read_text(encoding="utf-8-sig")
    except OSError:
        return UNKNOWN

    stripped = text.strip()
    if not stripped:
        return UNKNOWN
    return stripped.splitlines()[0].strip() or UNKNOWN


def parse_version(value: str) -> tuple[int, int, int] | None:
    """`2026.09.1` as three numbers, or None if it is not one.

    Compared as numbers, never as text: `2026.10.1` has to come after
    `2026.09.2`, and as strings it does not.
    """
    match = _VERSION_PATTERN.match(value)
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def is_newer(candidate: str, installed: str) -> bool:
    """Whether `candidate` is a later version than `installed`.

    An unparsable version on either side counts as not newer, so a damaged
    version file can never talk an update into overwriting a working install.
    """
    left = parse_version(candidate)
    right = parse_version(installed)
    if left is None or right is None:
        return False
    return left > right
