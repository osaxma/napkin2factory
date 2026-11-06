"""docs/cli.md has a row for every verb the CLI answers to (B-0271).

The verb names come from the Typer app itself, so a verb added to the CLI without a row in the
command map fails here, and so does a row for a verb that was renamed away.
"""

from __future__ import annotations

import re
from pathlib import Path

import typer

from napkin2factory.cli.app import app

REPO = Path(__file__).resolve().parents[2]
# Top-level verbs, and the two sub-apps whose verbs are listed with their group name.
SUB_APPS = ("ecr", "concept")


def _expected_rows() -> list[str]:
    """Every `n2f <verb>` the CLI answers to, as it must appear in docs/cli.md."""
    root = typer.main.get_command(app)
    rows = [f"n2f {name}" for name in sorted(root.commands) if name not in SUB_APPS]
    for group in SUB_APPS:
        sub = root.commands[group]
        rows += [f"n2f {group} {name}" for name in sorted(sub.commands)]
    return rows


def test_every_cli_verb_has_a_row_in_cli_doc() -> None:
    doc = (REPO / "docs/cli.md").read_text(encoding="utf-8")
    missing = [
        row
        for row in _expected_rows()
        # a verb name ends at a word boundary: `n2f ecr new` is not `n2f ecr newer`
        if not re.search(re.escape(row) + r"(?![\w-])", doc)
    ]
    assert not missing, f"docs/cli.md has no row for: {', '.join(missing)}"


def test_no_removed_verb_is_still_documented_as_usage() -> None:
    # `--patch` and the apply step went with the live change loop (v0.8, R9): the map must not
    # teach them as current usage. `ecr apply` and `ecr new` stay, as bridges that say so.
    doc = (REPO / "docs/cli.md").read_text(encoding="utf-8")
    assert "--patch" not in doc
    assert "n2f ecr apply ECR-" not in doc
