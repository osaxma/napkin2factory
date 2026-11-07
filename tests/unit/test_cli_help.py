"""``n2f --help`` starts an agent off, and what it says is true (S-313)."""

from __future__ import annotations

import re
from typing import Any

import typer
from typer.testing import CliRunner

from napkin2factory.cli.app import EPILOG, app
from napkin2factory.cli.engine import EXIT_INTERNAL
from napkin2factory.core.errors import CheckFailed, EnvironmentProblem, GateBlocked, N2FError


def _leaves(command: Any, path: tuple[str, ...] = ()) -> dict[tuple[str, ...], Any]:
    kids = getattr(command, "commands", None)
    if kids is None:
        return {path: command}
    out: dict[tuple[str, ...], Any] = {}
    for name, child in kids.items():
        out |= _leaves(child, (*path, name))
    return out


def test_the_root_help_has_the_start_here_epilogue() -> None:
    result = CliRunner().invoke(app, ["--help"], env={"COLUMNS": "120"})
    assert result.exit_code == 0
    for text in ("Start here", "n2f version", "n2f doctor", "n2f init <dir>", "n2f concept new"):
        assert text in result.output
    for text in ("n2f build", "n2f check", "n2f serve", "N2F_NO_ENGINE=1", "n2f engine status"):
        assert text in result.output
    assert "n2f docs" in result.output


def test_every_verb_the_epilogue_names_exists() -> None:
    verbs = _leaves(typer.main.get_command(app))
    groups = {p[0] for p in verbs if len(p) > 1}
    named = re.findall(r"`n2f ([a-z-]+)(?: ([a-z-]+))?", EPILOG)
    assert named
    for first, second in named:
        if first in groups and second:
            assert (first, second) in verbs, f"n2f {first} {second}"
        else:
            assert (first,) in verbs or first in groups, f"n2f {first}"


def test_the_json_claim_is_true_and_its_exceptions_are_exactly_these() -> None:
    lacking = set()
    for path, command in _leaves(typer.main.get_command(app)).items():
        opts = {o for p in command.params for o in getattr(p, "opts", [])}
        if "--json" not in opts:
            lacking.add(path)
    assert lacking == {("graph",), ("serve",), ("mcp",), ("skill",)}
    for name in ("graph", "serve", "mcp", "skill"):
        assert f"`{name}`" in EPILOG


def test_the_exit_codes_in_the_epilogue_are_the_real_ones() -> None:
    assert (N2FError.exit_code, CheckFailed.exit_code, GateBlocked.exit_code) == (1, 5, 3)
    assert (EnvironmentProblem.exit_code, EXIT_INTERNAL) == (4, 70)
    for text in ("0 ok", "1 the model", "2 a usage error", "3 a gate", "4 a", "5 a failed check"):
        assert text in EPILOG
    assert "70 the warm engine" in EPILOG


def test_serve_mcp_and_engine_name_each_other() -> None:
    root = typer.main.get_command(app)
    helps = {
        "serve": root.commands["serve"].help,
        "mcp": root.commands["mcp"].help,
        "engine": root.commands["engine"].help,
    }
    for name, text in helps.items():
        assert "Not this" in text, name
        for other in set(helps) - {name}:
            assert f"n2f {other}" in text, (name, other)
