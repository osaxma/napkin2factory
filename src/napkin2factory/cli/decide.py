"""``n2f decide``: record the owner's pick for a choice a check offered (F12, S-130)."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.markup import escape

from napkin2factory.cli.common import (
    DirOption,
    JsonOption,
    console,
    emit_json,
    handle_errors,
    product_root,
    warn_if_pin_excludes,
)
from napkin2factory.core.loader import load_product


@handle_errors
def decide(
    check: str = typer.Argument(
        ..., help="The choice's check id (`n2f status` shows it), e.g. fastening://a/b."
    ),
    pick: str = typer.Option(..., "--pick", help="The option chosen (its id)."),
    by: str = typer.Option(..., "--by", help="Who chose."),
    note: str | None = typer.Option(None, "--note", help="Why, in the chooser's words."),
    agent: bool = typer.Option(
        False,
        "--agent",
        help="An agent decided under the delegation rule (only a choice that holds nothing).",
    ),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Record a choice: a decision naming the check, the option and what it was decided on.

    The check then reads OK with its decision, until something it was decided on changes.
    """
    from napkin2factory.cli.check import _ensure_checks
    from napkin2factory.core.checks.choices import (
        append_decision,
        decision_entry,
        find_choice,
    )

    root = product_root(dir)
    warn_if_pin_excludes(root, json_out)
    product = load_product(root)
    data = _ensure_checks(product)  # the choice as the current model offers it
    row = find_choice(data["results"], check)
    entry = decision_entry(product, row, pick, by, note, agent)
    append_decision(product.paths.decisions, entry)
    # refresh the checks so `n2f status` agrees, and save: a decision is a record
    after = _ensure_checks(load_product(root))
    now = next((r for r in after["results"] if r["id"] == row["id"]), None)
    from napkin2factory.core.vcs import Vcs

    vcs = Vcs(root)
    saved = None
    if vcs.is_tracked() and vcs.is_repo_root():
        saved = vcs.snapshot(f"Decide {entry['id']}: {entry['title']}")
    if json_out:
        emit_json(
            {
                "decision": {k: str(v) if k == "date" else v for k, v in entry.items()},
                "check": row["id"],
                "status": now["status"] if now else None,
                "snapshot": saved,
            }
        )
        return
    console.print(f"[green]✓[/green] {entry['id']} recorded and saved: {escape(entry['title'])}")
    console.print(
        "  the check reads OK with this decision; it opens again by itself if what it was "
        "decided on changes"
    )
