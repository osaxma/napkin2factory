"""Every verb chooses: forwarded to the warm engine (and what a dropped connection means), or not.

The table is ``VERB_CLASSES`` in ``cli/engine.py``. A verb that is in neither it nor
``NEVER_FORWARD`` fails here, so whoever adds a verb has to say whether the engine may run it and
whether repeating it is harmless (S-310).
"""

from __future__ import annotations

from typing import Any

import typer

from napkin2factory.cli import engine as eng
from napkin2factory.cli.app import app


def _leaves(command: Any, path: tuple[str, ...] = ()) -> set[tuple[str, ...]]:
    kids = getattr(command, "commands", None)
    if kids is None:
        return {path}
    out: set[tuple[str, ...]] = set()
    for name, child in kids.items():
        out |= _leaves(child, (*path, name))
    return out


def test_every_verb_is_classified_or_never_forwarded() -> None:
    leaves = _leaves(typer.main.get_command(app))
    classified, never = set(eng.VERB_CLASSES), set(eng.NEVER_FORWARD)
    assert not classified & never, f"both classified and never forwarded: {classified & never}"
    undecided = leaves - classified - never
    assert not undecided, (
        f"new verbs must be added to VERB_CLASSES (SAFE or changes state) or NEVER_FORWARD in "
        f"cli/engine.py: {sorted(undecided)}"
    )
    gone = (classified | never) - leaves
    assert not gone, f"the table names verbs the CLI no longer has: {sorted(gone)}"


def test_a_state_changing_verb_names_a_real_read_only_look_at() -> None:
    leaves = _leaves(typer.main.get_command(app))
    changing = {p: c for p, c in eng.VERB_CLASSES.items() if c.changes_state}
    assert changing  # undo, redo, rollback, the ecr and concept writers
    for path, klass in changing.items():
        assert klass.look_at and klass.look_at.startswith("n2f "), path
        target = tuple(klass.look_at.split()[1:])
        assert target in leaves, f"{path}: look_at {klass.look_at!r} is not a verb"
        assert target in eng.VERB_CLASSES and not eng.VERB_CLASSES[target].changes_state, path
    for path, klass in eng.VERB_CLASSES.items():
        if not klass.changes_state:
            assert klass.look_at is None, path


def test_the_verbs_that_change_the_product_are_not_marked_safe() -> None:
    must_change = {
        ("undo",),
        ("redo",),
        ("rollback",),
        ("ecr", "start"),
        ("ecr", "quick"),
        ("ecr", "approve"),
        ("ecr", "close"),
        ("ecr", "abort"),
        ("concept", "new"),
        ("concept", "promote"),
        ("concept", "reject"),
        ("concept", "switch"),
        ("concept", "fork-from-model"),
    }
    assert {p for p, c in eng.VERB_CLASSES.items() if c.changes_state} == must_change


def test_verb_path_reads_group_verbs() -> None:
    assert eng.verb_path(["ecr", "impact", "--json"]) == ("ecr", "impact")
    # an option's value before the verb is not read as the verb: not forwarded, so run cold
    assert not eng.verb_allowed(["ecr", "--dir", "x", "start"])
    assert eng.verb_path(["build", "--offline"]) == ("build",)
    assert eng.verb_path(["ecr"]) == ("ecr",) and not eng.verb_allowed(["ecr"])
    assert not eng.verb_allowed(["ecr", "nonsense"])
    assert not eng.verb_allowed(["concept"])
