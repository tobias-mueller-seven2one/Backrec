"""The questions the setup asks, and the writing of the settings.

Both folders are derived from one base folder, shown for confirmation and then
stored **separately**. That redundancy is deliberate: the base folder is only
the input aid of the setup and is never read at runtime; the tool stays
standalone, and one folder may later point at another drive without the other
moving with it (design D3).

The recording folder is the one exception to the derivation: it lands in the
user profile and explicitly not below the base folder, because three files per
recording at roughly 20 MB a minute have no business in a cloud
synchronisation.

Written from `config.example.toml` by text substitution rather than through a
TOML writer. That keeps the template the single source of the comments - a
generated file would have none - and saves a dependency that would be needed
for the setup only.

Settings that are new in the template are added to an existing file by
`complete_from_template`, with the template's value and the template's comment.
A colleague never adds a setting by hand: the diagnosis used to report the drift
and leave the handwork to them, which is precisely what it must not do
(convention section 4, revision of 12.09.2026). Existing entries are never
touched.

Every setting of the template can be answered, not only the two folders
(convention section 5 step 3, revision of 12.09.2026 in the evening). The first
run asks the required values and then offers the remaining ones; a later run
shows what is set and offers to change it. That makes "run Setup.cmd again" the
official way to change a setting, and it is why the type of an answer is checked
here rather than at the next start: a colleague who typed a word where a number
belongs learns it while the question is still on screen.
"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import config as config_module, paths
from .config import missing_keys, read_toml
from .console import Assistant
from .logging_setup import get_logger

logger = get_logger(__name__)

TARGET_FOLDER_NAME = "Input"
RECORDING_FOLDER_NAME = "Recording"
DATA_ROOT_FOLDER_NAME = "Aufnahmen"

# The keys the base folder question answers. They are asked as one folder and
# derived from it, never one by one -- on the first run.
DERIVED_KEYS: tuple[str, ...] = ("recording_dir", "target_dir")

# Key names whose value must never be echoed. None of them exists in this tool
# today; the rule is kept because the overview is the one place where a value
# would end up on screen without anyone asking for it.
SECRET_MARKERS: tuple[str, ...] = ("token", "key", "passwort", "password", "secret", "geheim")

# A key holding a location rather than a word.
_PATH_KEY = re.compile(r"(_dir|_path)$")

# How many wrong answers to one question before it is left as it was. Without a
# limit a run that gets its answers from somewhere other than a keyboard -- a
# closed channel, a test -- would ask the same question forever.
MAX_ATTEMPTS = 3

TRUE_WORDS: tuple[str, ...] = ("j", "ja", "y", "yes", "true", "1", "ein")
FALSE_WORDS: tuple[str, ...] = ("n", "nein", "no", "false", "0", "aus")

LOG_LEVELS: tuple[str, ...] = ("DEBUG", "INFO", "WARNING", "ERROR")


class Kind(Enum):
    """What an answer to a setting has to look like."""

    BOOL = "bool"
    NUMBER = "number"
    LIST = "list"
    PATH = "path"
    CHOICE = "choice"
    TEXT = "text"


@dataclass(frozen=True)
class Setting:
    """One question: which key, what it means, what fits as an answer."""

    key: str
    kind: Kind
    description: str = ""
    choices: tuple[str, ...] = field(default_factory=tuple)
    secret: bool = False

# A key at the start of a line, used to attach a comment block to the key below
# it while the template is parsed.
_KEY_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=")

# A table header. Everything after it belongs to that table, which is why a new
# top-level key may never simply be appended behind one.
_TABLE_LINE = re.compile(r"^\s*\[")


@dataclass(frozen=True)
class WizardResult:
    config_path: Path
    values: dict[str, Any]
    handshake_written: bool = False
    created: bool = True


@dataclass(frozen=True)
class ReviewResult:
    """What a later run did with the settings that were already there."""

    config_path: Path
    changed: tuple[str, ...] = field(default_factory=tuple)


def default_data_root(env: Mapping[str, str] | None = None) -> Path:
    """The suggestion for the base folder: cloud folder, otherwise user profile."""
    environ = os.environ if env is None else env
    cloud = environ.get(paths.CLOUD_VARIABLE, "").strip()
    if cloud:
        return Path(cloud) / DATA_ROOT_FOLDER_NAME
    return Path(environ.get("USERPROFILE", str(Path.home()))) / DATA_ROOT_FOLDER_NAME


def default_recording_dir(env: Mapping[str, str] | None = None) -> Path:
    """Never below the base folder - see the module docstring."""
    environ = os.environ if env is None else env
    profile = environ.get("USERPROFILE", str(Path.home()))
    return Path(profile) / DATA_ROOT_FOLDER_NAME / RECORDING_FOLDER_NAME


def derive_directories(
    data_root: Path,
    env: Mapping[str, str] | None = None,
) -> dict[str, Path]:
    """The two working folders, derived from the base folder."""
    return {
        "recording_dir": default_recording_dir(env),
        "target_dir": data_root / TARGET_FOLDER_NAME,
    }


def format_value(value: Any) -> str:
    """Writes a value as TOML.

    Strings as a literal string in single quotes: a backslash means nothing in
    those, and a Windows path needs no doubling. Only a path that carries a
    single quote itself falls back to the escaped form.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(format_value(item) for item in value) + "]"

    text = str(value)
    if "'" in text:
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return f"'{text}'"


def render(template: str, values: Mapping[str, Any]) -> str:
    """Puts the values into the template and leaves every comment standing."""
    rendered = template
    for key, value in values.items():
        pattern = re.compile(rf"^{re.escape(key)}\s*=.*$", re.MULTILINE)
        replacement = f"{key} = {format_value(value)}"
        rendered, count = pattern.subn(lambda _match, text=replacement: text, rendered, count=1)
        if count == 0:
            rendered = rendered.rstrip("\n") + f"\n{replacement}\n"
    return rendered


def template_text(template_path: Path | None = None, repo: Path | None = None) -> str:
    return (template_path or paths.example_config_path(repo)).read_text(encoding="utf-8")


def template_values(template_path: Path | None = None, repo: Path | None = None) -> dict[str, Any]:
    """The values the template carries, in the template's order."""
    return read_toml(template_path or paths.example_config_path(repo))


def template_comments(template_path: Path | None = None, repo: Path | None = None) -> dict[str, str]:
    """The comment block belonging to each key of the template.

    Parsed instead of duplicated: the template is the one place a setting is
    explained, and a setting written into the local file has to carry the same
    explanation or nobody can read it there. A blank line ends a block, which is
    what keeps the file header from being attributed to the first key.
    """
    comments: dict[str, str] = {}
    block: list[str] = []

    for line in template_text(template_path, repo).splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            block.append(stripped.lstrip("#").strip())
            continue
        if not stripped:
            block.clear()
            continue
        match = _KEY_LINE.match(stripped)
        if match and block:
            comments[match.group(1)] = "\n".join(block)
        block.clear()

    return comments


def render_additions(
    keys: Sequence[str],
    values: Mapping[str, Any],
    comments: Mapping[str, str],
) -> str:
    """The text block for settings that are new in the template. Pure."""
    blocks: list[str] = []
    for key in keys:
        lines = [f"# {line}" if line else "#" for line in comments.get(key, "").splitlines()]
        lines.append(f"{key} = {format_value(values[key])}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def insert_position(lines: Sequence[str]) -> int:
    """Where a new top-level key may go: before the first table header.

    Appended behind `[abschnitt]` a key would silently become part of that
    section, and the tool would never see it again under its own name. Backrec's
    template is flat today; the rule costs eight lines and prevents a fault
    nobody would notice.
    """
    for index, line in enumerate(lines):
        if _TABLE_LINE.match(line):
            return index
    return len(lines)


def complete_from_template(
    config_file: Path,
    template_path: Path | None = None,
    repo: Path | None = None,
) -> tuple[str, ...]:
    """Add settings the template has and the local file lacks.

    Value and comment come from the template; an existing entry is never read,
    never moved and never overwritten. A colleague therefore never adds a
    setting by hand (convention section 4, revision of 12.09.2026).
    """
    if not config_file.is_file():
        return ()

    template = template_values(template_path, repo)
    added = missing_keys(read_toml(config_file), template)
    if not added:
        return ()

    lines = config_file.read_text(encoding="utf-8").splitlines()
    position = insert_position(lines)
    block = render_additions(added, template, template_comments(template_path, repo)).splitlines()

    merged = [*lines[:position], "", *block, *lines[position:]]
    config_file.write_text("\n".join(merged).rstrip("\n") + "\n", encoding="utf-8")
    logger.info("Einstellungen ergaenzt: %s", ", ".join(added))
    return added


def completion_message(count: int) -> str:
    """The one line the setup reports about added settings."""
    if count == 1:
        return "1 neue Einstellung mit Standardwert ergänzt."
    return f"{count} neue Einstellungen mit Standardwerten ergänzt."


def change_message(count: int) -> str:
    """The one line a run reports about changed settings."""
    if count == 1:
        return "1 Einstellung geändert."
    return f"{count} Einstellungen geändert."


# --- The settings as questions ------------------------------------------------


def choices_for(key: str) -> tuple[str, ...]:
    """The permitted values of a setting, empty when it is free text.

    Taken from the same table the validation uses, so that a value accepted here
    cannot be rejected at the next start.
    """
    if key == "log_level":
        return LOG_LEVELS
    return ()


def is_secret(key: str) -> bool:
    return any(marker in key.lower() for marker in SECRET_MARKERS)


def kind_of(key: str, value: Any) -> Kind:
    """What an answer to this setting has to look like.

    Derived from the template's own value instead of from a second table: the
    template is the one place a setting exists, and a list that says "this one is
    a number" would drift away from it on the first new key.
    """
    if isinstance(value, bool):
        return Kind.BOOL
    if isinstance(value, (int, float)):
        return Kind.NUMBER
    if isinstance(value, (list, tuple)):
        return Kind.LIST
    if choices_for(key):
        return Kind.CHOICE
    if _PATH_KEY.search(key):
        return Kind.PATH
    return Kind.TEXT


def first_sentence(comment: str, limit: int = 100) -> str:
    """One line of meaning out of a comment block of the template."""
    joined = " ".join(line.strip() for line in comment.splitlines() if line.strip())
    if not joined:
        return ""

    head = joined.split(". ")[0].rstrip(".")
    if len(head) > limit:
        head = head[: limit - 3].rstrip() + "..."
    return f"{head}."


def settings_from_template(
    template_path: Path | None = None,
    repo: Path | None = None,
    *,
    include_directories: bool = False,
) -> tuple[Setting, ...]:
    """Every setting of the template as a question, in the template's order.

    The two working folders are left out on the first run: they are answered
    there as one base folder. A later run does include them, because by then they
    exist individually and a base folder would overwrite a folder someone
    deliberately moved to another drive.
    """
    values = template_values(template_path, repo)
    comments = template_comments(template_path, repo)

    return tuple(
        Setting(
            key=key,
            kind=kind_of(key, value),
            description=first_sentence(comments.get(key, "")),
            choices=choices_for(key),
            secret=is_secret(key),
        )
        for key, value in values.items()
        if not isinstance(value, dict) and (include_directories or key not in DERIVED_KEYS)
    )


def display_value(setting: Setting, value: Any) -> str:
    """The value as it appears in the overview and in the brackets of a question."""
    if setting.secret:
        return "nicht gesetzt" if value in (None, "") else "gesetzt"
    if value is None:
        return "nicht gesetzt"
    if isinstance(value, bool):
        return "ja" if value else "nein"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    return str(value) or "nicht gesetzt"


def overview_lines(settings: Sequence[Setting], values: Mapping[str, Any]) -> list[str]:
    """The compact overview of the current settings. Pure, therefore testable."""
    return [
        f"{setting.key}: {display_value(setting, values.get(setting.key))}" for setting in settings
    ]


def parse_answer(setting: Setting, answer: str, current: Any) -> Any:
    """The typed value behind an answer, or a plain sentence saying what fits."""
    text = answer.strip()

    if setting.kind is Kind.BOOL:
        if text.lower() in TRUE_WORDS:
            return True
        if text.lower() in FALSE_WORDS:
            return False
        raise ValueError("Bitte ja oder nein eingeben.")

    if setting.kind is Kind.NUMBER:
        try:
            number = float(text.replace(",", "."))
        except ValueError:
            raise ValueError("Bitte eine Zahl eingeben, zum Beispiel 5.") from None
        if number < 0:
            raise ValueError("Bitte eine Zahl ab 0 eingeben.")
        if isinstance(current, int) and not isinstance(current, bool) and number.is_integer():
            return int(number)
        return number

    if setting.kind is Kind.LIST:
        parts = [part.strip() for part in text.split(",") if part.strip()]
        if not parts:
            raise ValueError("Bitte mindestens einen Eintrag eingeben, mehrere mit Komma getrennt.")
        return parts

    if setting.kind is Kind.PATH:
        if not text:
            raise ValueError("Bitte einen Ordner angeben.")
        return str(paths.expand_path(text))

    if setting.kind is Kind.CHOICE:
        if text == str(current) or text in setting.choices:
            return text
        raise ValueError("Bitte einen dieser Werte eingeben: " + ", ".join(setting.choices) + ".")

    return text


def ask_setting(assistant: Assistant, setting: Setting, current: Any) -> Any:
    """One setting, asked until the answer fits -- at most MAX_ATTEMPTS times."""
    default_text = display_value(setting, current)
    if setting.description:
        assistant.note(setting.description)

    for _attempt in range(MAX_ATTEMPTS):
        answer = assistant.ask(setting.key, default_text)
        if answer == default_text:
            return current
        try:
            return parse_answer(setting, answer, current)
        except ValueError as exc:
            assistant.note(str(exc))

    assistant.note("Der bisherige Wert bleibt stehen.")
    return current


def ask_settings(
    assistant: Assistant,
    settings: Sequence[Setting],
    values: Mapping[str, Any],
) -> dict[str, Any]:
    """Walks the settings one question at a time and returns what changed."""
    changed: dict[str, Any] = {}
    for setting in settings:
        current = values.get(setting.key)
        answer = ask_setting(assistant, setting, current)
        if answer != current:
            changed[setting.key] = answer
    return changed


def review(
    assistant: Assistant,
    config_file: Path,
    *,
    unattended: bool = False,
    template_path: Path | None = None,
    repo: Path | None = None,
) -> ReviewResult:
    """Shows the settings that exist and offers to change them.

    The overview comes first and the question second, because "change settings?"
    without them is a question nobody can answer. Enter leaves everything as it
    is, which is what makes running the setup again safe rather than a detour
    through every value.
    """
    if unattended or not config_file.is_file():
        return ReviewResult(config_path=config_file)

    try:
        current = read_toml(config_file)
    # Through the module, not through an imported name: a name bound at import
    # time stops matching as soon as anything reloads the module it came from.
    except config_module.ConfigError as exc:
        logger.warning("Einstellungen nicht lesbar -- keine Uebersicht: %s", exc)
        return ReviewResult(config_path=config_file)

    settings = settings_from_template(template_path, repo, include_directories=True)
    assistant.note("Die Einstellungen sind gerade so:")
    for line in overview_lines(settings, current):
        assistant.note(f"  {line}")

    if not assistant.ask_yes_no("Einstellungen ändern?", default=False):
        return ReviewResult(config_path=config_file)

    changed = ask_settings(assistant, settings, current)
    if not changed:
        return ReviewResult(config_path=config_file)

    # Written through the same substitution as the template, so that every
    # comment in the file survives a change.
    config_file.write_text(
        render(config_file.read_text(encoding="utf-8"), changed), encoding="utf-8"
    )
    logger.info("Einstellungen geaendert: %s", ", ".join(sorted(changed)))
    return ReviewResult(config_path=config_file, changed=tuple(sorted(changed)))


def write_config(
    target: Path,
    values: Mapping[str, Any],
    template_path: Path | None = None,
    repo: Path | None = None,
) -> Path:
    """Writes the settings. An existing file is never touched."""
    if target.is_file():
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(template_text(template_path, repo), values), encoding="utf-8")
    logger.info("Einstellungen angelegt: %s", target)
    return target


def read_handshake(path: Path | None = None) -> str | None:
    """The base folder from the shared suite file, if there is one.

    Purely an input aid of the setup. No command reads this file at runtime and
    none requires it to exist.
    """
    target = path or paths.suite_handshake_path()
    if not target.is_file():
        return None

    try:
        with target.open("rb") as handle:
            data = tomllib.load(handle)
    except (tomllib.TOMLDecodeError, OSError) as exc:
        logger.debug("Gemeinsame Datei '%s' nicht lesbar: %s", target, exc)
        return None

    value = data.get("data_root")
    return str(value) if value else None


def write_handshake(data_root: Path, path: Path | None = None) -> Path:
    """Writes the base folder into the shared suite file."""
    target = path or paths.suite_handshake_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "# Gemeinsamer Basisordner der MemoSuite-Werkzeuge.\n"
        "# Nur eine Eingabehilfe beim Einrichten; zur Laufzeit liest sie niemand.\n"
        f"data_root = {format_value(str(data_root))}\n",
        encoding="utf-8",
    )
    logger.info("Gemeinsame Datei geschrieben: %s", target)
    return target


def _show(assistant: Assistant, directories: Mapping[str, Path]) -> None:
    assistant.note("Daraus ergeben sich zwei Ordner:")
    assistant.note(f"  {directories['target_dir']}  --  hierhin kommt die fertige Aufnahme.")
    assistant.note(f"  {directories['recording_dir']}  --  hier wird aufgenommen.")


def run(
    assistant: Assistant,
    target: Path | None = None,
    *,
    unattended: bool = False,
    template_path: Path | None = None,
    handshake_path: Path | None = None,
    env: Mapping[str, str] | None = None,
    preset_values: Mapping[str, Any] | None = None,
    repo: Path | None = None,
) -> WizardResult:
    """Asks for the base folder, shows the derivation and writes the file."""
    config_file = target or paths.config_path()

    if config_file.is_file():
        assistant.ok(f"Die Einstellungen gibt es schon ({config_file}) -- unverändert übernommen")
        return WizardResult(config_path=config_file, values={}, created=False)

    suggested = read_handshake(handshake_path)
    default_root = Path(suggested) if suggested else default_data_root(env)
    if suggested and not unattended:
        assistant.note("Ein anderes Werkzeug der Reihe benutzt bereits einen Ordner für Aufnahmen.")

    answer = (
        str(default_root)
        if unattended
        else assistant.ask("In welchem Ordner sollen deine Aufnahmen landen?", str(default_root))
    )
    data_root = paths.expand_path(answer)

    directories = derive_directories(data_root, env)
    directories.update({key: Path(str(value)) for key, value in (preset_values or {}).items()})
    _show(assistant, directories)

    # Shown is not confirmed: both folders are created and written in a moment,
    # and a typo in the base folder only shows up when the first recording ends
    # up nowhere.
    while not unattended and not assistant.ask_yes_no("Passen diese beiden Ordner?", default=True):
        answer = assistant.ask("In welchem Ordner sollen deine Aufnahmen landen?", str(data_root))
        data_root = paths.expand_path(answer)
        directories = derive_directories(data_root, env)
        _show(assistant, directories)

    values: dict[str, Any] = {key: str(value) for key, value in directories.items()}

    # Offered, not walked through: the required values are answered, everything
    # else has a default that works, and a colleague who says no here gets
    # exactly the template.
    if not unattended and assistant.ask_yes_no("Weitere Einstellungen anpassen?", default=False):
        settings = settings_from_template(template_path, repo)
        values.update(ask_settings(assistant, settings, template_values(template_path, repo)))

    for directory in directories.values():
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning("Ordner '%s' konnte nicht angelegt werden: %s", directory, exc)

    write_config(config_file, values, template_path, repo)

    handshake_written = False
    if not unattended and read_handshake(handshake_path) is None:
        if assistant.ask_yes_no(
            "Sollen die anderen Werkzeuge diesen Ordner später vorgeschlagen bekommen?",
            default=True,
        ):
            write_handshake(data_root, handshake_path)
            handshake_written = True

    return WizardResult(config_path=config_file, values=values, handshake_written=handshake_written)
