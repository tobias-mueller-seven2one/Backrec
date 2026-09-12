"""Where everything outside the repository lives.

Every path is derived from this module's own location or from the environment,
never from the current working directory: the window is started from a desktop
shortcut whose working directory is whatever Explorer felt like, and the
previous code built its folders relative to the process's cwd.

Kept free of imports from the rest of the package (except `version`, which
imports nothing itself) so that the logging bootstrap can ask for the log
directory before any configuration has been read.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from .version import VERSION_FILE_NAME, is_newer, parse_version, read_version

TOOL_NAME = "Backrec"
SUITE_DIR_NAME = "MemoSuite"

ENV_SUITE_HOME = "MEMOSUITE_HOME"
ENV_CONFIG = "BACKREC_CONFIG"
ENV_HOME = "BACKREC_HOME"
ENV_PREFIX = "BACKREC_"

CONFIG_FILE_NAME = "config.toml"
EXAMPLE_CONFIG_FILE_NAME = "config.example.toml"
LEGACY_CONFIG_FILE_NAME = ".env"
SUITE_HANDSHAKE_FILE_NAME = "suite.toml"
GUIDE_FILE_NAME = "LIES-MICH-ZUERST.txt"

PID_RECORD_NAME = "backrec.pid"
STOP_REQUEST_NAME = "stop.request"
INSTALLED_RECORD_NAME = "installed.json"
INSTALLED_MANIFEST_NAME = "release-manifest.json"

LOG_FILE_NAME = "backrec.log"

# What marks a folder as this tool's. Three files, because any single one may be
# absent: `VERSION` is written by the release build, the guide only ships in the
# archive and in the folder, the template only in the folder. No other place
# carries the combination.
REPO_MARKERS: tuple[str, ...] = (
    VERSION_FILE_NAME,
    GUIDE_FILE_NAME,
    EXAMPLE_CONFIG_FILE_NAME,
)

# Folder name of an installed package. From the outside it looks like any other
# intermediate folder, but it is never the one we are looking for.
_INSTALL_DIR_NAME = "site-packages"


def has_repo_marker(folder: Path) -> bool:
    """Whether `folder` looks like this tool's folder."""
    return any((folder / name).is_file() for name in REPO_MARKERS)


def repo_root(env: Mapping[str, str] | None = None) -> Path:
    """The folder the tool runs out of.

    Three ways to arrive at it, in this order: the `BACKREC_HOME` override, the
    source checkout next to the package, and - for the non-editable install the
    setup builds - the folder that holds the environment, found by its
    `pyvenv.cfg`.

    The search stops at the first folder that actually carries a marker instead
    of walking to the top. Without that rule a stranger's `pyvenv.cfg` anywhere
    above wins, a `pyvenv.cfg` in the folder itself hands back its parent, and
    an environment outside the folder hands back something unrelated - three
    ways to a wrong answer that later shows up as a missing configuration far
    from its cause. The diagnosis reports a result without a marker rather than
    letting it pass.
    """
    environ = os.environ if env is None else env
    override = environ.get(ENV_HOME, "").strip()
    if override:
        return Path(os.path.expandvars(override)).expanduser()

    module_dir = Path(__file__).resolve().parent
    fallback: Path | None = None

    for candidate in module_dir.parents:
        if candidate.name == _INSTALL_DIR_NAME:
            continue
        if has_repo_marker(candidate):
            return candidate
        if (candidate / "pyvenv.cfg").is_file():
            if has_repo_marker(candidate.parent):
                return candidate.parent
            fallback = fallback or candidate.parent

    return fallback or module_dir.parent


def suite_home(env: Mapping[str, str] | None = None) -> Path:
    """The shared MemoSuite folder, movable through `MEMOSUITE_HOME`."""
    environ = os.environ if env is None else env

    override = environ.get(ENV_SUITE_HOME, "").strip()
    if override:
        return Path(os.path.expandvars(override)).expanduser()

    local_appdata = environ.get("LOCALAPPDATA", "").strip()
    base = Path(local_appdata) if local_appdata else Path.home() / "AppData" / "Local"
    return base / SUITE_DIR_NAME


def tool_home(env: Mapping[str, str] | None = None) -> Path:
    return suite_home(env) / TOOL_NAME


def logs_dir(env: Mapping[str, str] | None = None) -> Path:
    return tool_home(env) / "logs"


def state_dir(env: Mapping[str, str] | None = None) -> Path:
    return tool_home(env) / "state"


def reports_dir(env: Mapping[str, str] | None = None) -> Path:
    """Diagnosis reports live next to the log (design D21)."""
    return logs_dir(env)


def releases_dir(env: Mapping[str, str] | None = None) -> Path:
    return suite_home(env) / "releases"


def log_path(env: Mapping[str, str] | None = None) -> Path:
    return logs_dir(env) / LOG_FILE_NAME


def pid_record_path(env: Mapping[str, str] | None = None) -> Path:
    return state_dir(env) / PID_RECORD_NAME


def stop_request_path(env: Mapping[str, str] | None = None) -> Path:
    return state_dir(env) / STOP_REQUEST_NAME


def installed_record_path(env: Mapping[str, str] | None = None) -> Path:
    return state_dir(env) / INSTALLED_RECORD_NAME


def installed_manifest_path(env: Mapping[str, str] | None = None) -> Path:
    return state_dir(env) / INSTALLED_MANIFEST_NAME


def suite_handshake_path(env: Mapping[str, str] | None = None) -> Path:
    return suite_home(env) / SUITE_HANDSHAKE_FILE_NAME


def example_config_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / EXAMPLE_CONFIG_FILE_NAME


def legacy_config_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / LEGACY_CONFIG_FILE_NAME


def guide_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / GUIDE_FILE_NAME


def version_file_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / VERSION_FILE_NAME


def tool_version(root: Path | None = None) -> str:
    return read_version(root or repo_root())


def config_path(
    cli_value: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> Path:
    """The configuration file in force: command line, then environment, then default."""
    if cli_value:
        return Path(os.path.expandvars(str(cli_value))).expanduser()

    environ = os.environ if env is None else env
    from_env = environ.get(ENV_CONFIG, "").strip()
    if from_env:
        return Path(os.path.expandvars(from_env)).expanduser()

    return tool_home(env) / CONFIG_FILE_NAME


def expand_path(value: str) -> Path:
    """Expand `%VAR%`, `$VAR` and `~` in a configured path value.

    Both spellings, because the template has to carry a default such as
    `%USERPROFILE%\\Aufnahmen` without naming a user, and a value copied out of
    a POSIX habit should not silently become a relative folder next to the tool.
    """
    return Path(os.path.expanduser(os.path.expandvars(value)))


__all__ = [
    "TOOL_NAME",
    "ENV_SUITE_HOME",
    "ENV_CONFIG",
    "ENV_HOME",
    "ENV_PREFIX",
    "CONFIG_FILE_NAME",
    "EXAMPLE_CONFIG_FILE_NAME",
    "LEGACY_CONFIG_FILE_NAME",
    "GUIDE_FILE_NAME",
    "VERSION_FILE_NAME",
    "INSTALLED_MANIFEST_NAME",
    "REPO_MARKERS",
    "has_repo_marker",
    "repo_root",
    "suite_home",
    "tool_home",
    "logs_dir",
    "state_dir",
    "reports_dir",
    "releases_dir",
    "log_path",
    "pid_record_path",
    "stop_request_path",
    "installed_record_path",
    "installed_manifest_path",
    "suite_handshake_path",
    "example_config_path",
    "legacy_config_path",
    "guide_path",
    "version_file_path",
    "tool_version",
    "config_path",
    "expand_path",
    "read_version",
    "parse_version",
    "is_newer",
]
