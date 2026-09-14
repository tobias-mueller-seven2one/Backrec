"""The command line: ten commands, documented exit codes, and no jargon.

The last test is the one with teeth. It walks the package's own source, picks
out every literal string handed to the output layer, and checks it against the
blocklist. It is meant to be annoying: it is the only place in day-to-day work
where the audience of these sentences shows up at all (design D19).
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from backrec import cli, console, paths

PACKAGE = Path(cli.__file__).parent

COMMANDS = (
    "setup",
    "start",
    "stop",
    "status",
    "doctor",
    "shortcut",
    "uninstall",
    "update",
    "logs",
    "release",
)

# What writes to a colleague. `print` is on the list although the package must
# not use it at all - a test that only knows the output layer would wave through
# exactly the line that walks around it. `Check` and `Problem` are on it because
# their sentences reach the same console through `render_text` and the error
# dialog, only one indirection later.
#
# The four dialog calls are on it for the same reason and are the ones a
# colleague is most likely to meet: everything the gear menu says goes through
# them, and Backrec has no other surface - it is the one tool of the suite whose
# messages reach the reader through a window rather than through a console.
OUTPUT_CALLS = (
    "ok",
    "warn",
    "fail",
    "note",
    "write",
    "ask",
    "ask_yes_no",
    "header",
    "print",
    "Check",
    "Problem",
    "showinfo",
    "showwarning",
    "showerror",
    "askyesno",
)

# Not vocabulary but shape: a stack trace has no business in any of these lines,
# and the whole of it is in the log anyway.
FORBIDDEN_SHAPES = ("Traceback", "File \"", "Exception:")


def parse(argv: list[str]):
    return cli.build_parser().parse_args(argv)


# --- The ten commands ---------------------------------------------------------


def test_the_help_names_all_ten_commands(capsys) -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["--help"])

    printed = capsys.readouterr().out
    for command in COMMANDS:
        assert command in printed


def test_every_command_is_wired_to_a_function() -> None:
    for command in COMMANDS:
        assert command in cli._COMMANDS


def test_every_command_help_states_its_exit_code(capsys) -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["--help"])

    printed = capsys.readouterr().out
    assert printed.count("Exit") >= len(COMMANDS)


def test_the_second_start_has_an_exit_code_of_its_own() -> None:
    assert cli.EXIT_ALREADY_RUNNING == 3


def test_calling_without_a_command_means_the_window() -> None:
    assert parse([]).command is None


# --- Argument shapes ----------------------------------------------------------


def test_setup_knows_unattended_and_start() -> None:
    args = parse(["setup", "--unattended", "--start"])

    assert args.unattended and args.start


def test_shortcut_status_and_remove_exclude_each_other() -> None:
    with pytest.raises(SystemExit):
        parse(["shortcut", "--status", "--remove"])


def test_update_takes_an_archive_or_the_developer_route() -> None:
    assert parse(["update", "irgendwo.zip"]).archive == Path("irgendwo.zip")
    assert parse(["update", "--git"]).git


def test_uninstall_knows_purge() -> None:
    assert parse(["uninstall", "--purge"]).purge


# --- Behaviour ----------------------------------------------------------------


def test_status_ends_without_error_when_nothing_runs(capsys) -> None:
    assert cli.main(["status"]) == 0
    assert "Backrec" in capsys.readouterr().out


def test_about_names_the_guide(capsys) -> None:
    assert cli.main(["about"]) == 0
    assert paths.GUIDE_FILE_NAME in capsys.readouterr().out


def test_stop_without_a_running_instance_ends_without_error() -> None:
    assert cli.main(["stop"]) == 0


def test_update_without_an_archive_names_the_one_way(capsys) -> None:
    """Weg B ist entfallen -- was bleibt, ist das Entpacken über den Ordner."""
    assert cli.main(["update"]) == 0

    printed = capsys.readouterr().out
    assert "Setup.cmd" in printed
    assert "Archiv" in printed
    assert "Menü" not in printed and "Zahnrad" not in printed


def test_doctor_json_is_machine_readable(capsys) -> None:
    code = cli.main(["doctor", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert code in (0, 1)
    assert payload["tool"] == paths.TOOL_NAME
    assert payload["checks"]


def test_doctor_json_and_the_readable_form_hold_the_same_checks(capsys) -> None:
    cli.main(["doctor", "--json"])
    machine = json.loads(capsys.readouterr().out)

    cli.main(["doctor"])
    readable = capsys.readouterr().out

    assert len(machine["checks"]) >= 1
    for check in machine["checks"]:
        assert check["name"] in readable


# --- The assistant rules ------------------------------------------------------


def literal_parts(node: ast.AST) -> list[str]:
    """The literal text of an argument - a plain string or the fixed parts of an f-string."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.JoinedStr):
        return [
            part.value
            for part in node.values
            if isinstance(part, ast.Constant) and isinstance(part.value, str)
        ]
    return []


def output_strings() -> list[tuple[str, int, str]]:
    """Every literal string the package hands to its output layer."""
    found: list[tuple[str, int, str]] = []

    for source in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = (
                node.func.attr
                if isinstance(node.func, ast.Attribute)
                else node.func.id
                if isinstance(node.func, ast.Name)
                else ""
            )
            if name not in OUTPUT_CALLS:
                continue
            for argument in node.args:
                for text in literal_parts(argument):
                    found.append((source.name, node.lineno, text))

    return found


def test_the_source_is_searched_at_all() -> None:
    """Guards the check itself: an empty result would pass every test below."""
    assert len(output_strings()) > 40


def test_no_line_of_output_carries_a_term_from_the_blocklist() -> None:
    offences = [
        (name, line, text, console.contains_forbidden(text))
        for name, line, text in output_strings()
        if console.contains_forbidden(text)
    ]

    assert offences == []


def test_no_line_of_output_carries_a_stack_trace() -> None:
    offences = [
        (name, line, text)
        for name, line, text in output_strings()
        if any(shape in text for shape in FORBIDDEN_SHAPES)
    ]

    assert offences == []


# The one place allowed to write past the output layer, with its reason: it
# reports that there is no log, and routing that through a layer which writes
# into the log would be the one message guaranteed to disappear.
ALLOWED_PRINTS: tuple[tuple[str, str], ...] = (
    ("logging_setup.py", "_report_unwritable_log"),
)


def test_the_package_never_writes_past_its_output_layer() -> None:
    offences: list[tuple[str, str, int]] = []

    for source in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for holder in ast.walk(tree):
            if not isinstance(holder, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if (source.name, holder.name) in ALLOWED_PRINTS:
                continue
            for node in ast.walk(holder):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "print"
                ):
                    offences.append((source.name, holder.name, node.lineno))

    assert offences == []
