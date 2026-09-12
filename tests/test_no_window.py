"""No child process of this tool may open a window nobody asked for.

The window runs under `pythonw.exe` and owns no console. Every console child
started from there gets a brand-new console, and on a machine where Windows
Terminal is the default host that console is a visible window in front of
whatever the reader is doing. The expensive one here is ffmpeg: it runs after
*every* recording, so a missing flag is a terminal window flashing up at the end
of each take.

The rule this test enforces is deliberately blunt: every `subprocess` call in the
package says what it wants to happen to the window -- `CREATE_NO_WINDOW`,
`CREATE_NEW_CONSOLE` or `DETACHED_PROCESS` -- or it stands on the list below with
a reason. A call that says nothing is the defect, and saying nothing is exactly
what a new call does by default.
"""

from __future__ import annotations

import ast
from pathlib import Path

from backrec import paths

PACKAGE_DIR = paths.repo_root() / "src" / "backrec"

SPAWNING_CALLS = frozenset({"run", "Popen", "call", "check_call", "check_output"})

# The values that count as an answer. Anything else -- a bare 0 included -- is
# not one.
WINDOW_FLAGS = ("CREATE_NO_WINDOW", "CREATE_NEW_CONSOLE", "DETACHED_PROCESS")

# Calls that are meant to put something on screen, keyed by module and the
# function they sit in. Folders are opened through `os.startfile`, which is not
# a subprocess at all; the one entry here is the branch beside it.
ALLOWED_WITHOUT_FLAG: dict[tuple[str, str], str] = {
    ("control.py", "open_settings"): (
        "xdg-open, and only outside Windows -- there the os.startfile branch above it runs"
    ),
}


def enclosing_functions(tree: ast.AST) -> dict[int, str]:
    """Every line of the module mapped to the function it belongs to."""
    owner: dict[int, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for line in range(node.lineno, (node.end_lineno or node.lineno) + 1):
            # Innermost wins: a nested definition overwrites the outer one, and
            # `ast.walk` reaches it after its parent.
            owner[line] = node.name
    return owner


def flag_text(tree: ast.AST, name: str) -> str:
    """Everything ever assigned to `name` or to `name["creationflags"]`.

    Two indirections are common enough to be worth resolving: a module constant
    (`NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)`) and a keyword
    dictionary built before the call (`kwargs["creationflags"] = ...`).
    """
    parts: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name) and target.id == name:
                parts.append(ast.unparse(node.value) if node.value else "")
            if (
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Name)
                and target.value.id == name
            ):
                parts.append(ast.unparse(node.value) if node.value else "")
    return " ".join(parts)


def declares_a_window_behaviour(tree: ast.AST, call: ast.Call) -> bool:
    for keyword in call.keywords:
        if keyword.arg not in ("creationflags", None):
            continue

        source = ast.unparse(keyword.value)
        if isinstance(keyword.value, ast.Name):
            source = f"{source} {flag_text(tree, keyword.value.id)}"
        if any(flag in source for flag in WINDOW_FLAGS):
            return True

    return False


def spawning_calls() -> list[tuple[str, str, int, bool]]:
    """Module, function, line and whether the call declares a window behaviour."""
    found: list[tuple[str, str, int, bool]] = []

    for module in sorted(PACKAGE_DIR.rglob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        owner = enclosing_functions(tree)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute) or node.func.attr not in SPAWNING_CALLS:
                continue
            if not (isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess"):
                continue

            found.append(
                (
                    module.name,
                    owner.get(node.lineno, "<module>"),
                    node.lineno,
                    declares_a_window_behaviour(tree, node),
                )
            )

    return found


def test_every_external_call_says_what_happens_to_the_window():
    offenders = [
        (module, function, line)
        for module, function, line, declared in spawning_calls()
        if not declared and (module, function) not in ALLOWED_WITHOUT_FLAG
    ]
    assert not offenders, offenders


def test_the_exception_list_names_nothing_that_has_since_been_fixed():
    """An entry that no longer describes a real call is a stale permission."""
    seen = {(module, function) for module, function, _line, _declared in spawning_calls()}
    assert not [entry for entry in ALLOWED_WITHOUT_FLAG if entry not in seen]


def test_the_merge_after_every_recording_is_covered():
    """The call this rule exists for, named rather than left to the walk."""
    merge_calls = [row for row in spawning_calls() if row[0] == "merge.py"]
    assert merge_calls
    assert all(declared for *_rest, declared in merge_calls)


def test_the_walk_actually_finds_the_calls():
    """A silent zero-match walk would pass forever without checking anything."""
    assert len(spawning_calls()) > 5
