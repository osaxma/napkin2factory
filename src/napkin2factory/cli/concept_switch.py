"""``n2f concept switch`` (v0.8 R10): move the chosen direction to another card.

Registered from ``cli/concept.py``, S-257: new verbs go in their own module.
"""

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
)

SHOWN_FILES = 6


@handle_errors
def switch_cmd(
    card: str = typer.Argument(..., help="The card to make the chosen direction, e.g. C-001."),
    fresh: bool = typer.Option(
        False, "--fresh", help="Start from the card's sketch even if its parked direction exists."
    ),
    override: bool = typer.Option(
        False, "--override", help="Switch to a red card, or overwrite differing parameters."
    ),
    reason: str | None = typer.Option(None, "--reason", help="Why (recorded with --override)."),
    by: str | None = typer.Option(None, "--by", help="Who chose (recorded in the decision)."),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Choose another card as the design direction; the current one is parked, not lost."""
    from napkin2factory.concepts.switch import switch

    root = product_root(dir)
    res = switch(root, card, fresh=fresh, override=override, reason=reason, by=by)
    if json_out:
        emit_json(
            {
                "switched": True,
                "card": res.card_id,
                "title": res.title,
                "parked": res.parked_id,
                "decision": res.dec_id,
                "route": res.route,
                "checkpoint": {"id": res.checkpoint, "number": res.number},
                "saved_edits": res.saved_edits,
                "changed": [{"path": c.path, "status": c.status} for c in res.changes],
                "seeded": {
                    "parameters": res.seeded_parameters,
                    "requirements": res.seeded_requirements,
                },
                "failing": res.failing,
                "notes": res.notes,
                "stale": res.stale,
            }
        )
        return
    if res.saved_edits is not None:
        console.print(
            f"[dim]your unsaved edits were saved first as #{res.saved_edits}[/dim]", soft_wrap=True
        )
    console.print(
        f"[green]✓[/green] {res.card_id} ({escape(res.title)}) is now the design direction "
        f"({res.dec_id}); {res.parked_id} ({escape(res.parked_title)}) is parked: kept, "
        f"and `n2f concept switch {res.parked_id}` brings it back "
        f"(now checkpoint #{res.number}). `n2f undo` takes the switch back",
        soft_wrap=True,
    )
    if res.route == "restored":
        shown = [c.path for c in res.changes]
        more = f" and {len(shown) - SHOWN_FILES} more" if len(shown) > SHOWN_FILES else ""
        console.print(
            f"  brought back from when it was parked: {escape(', '.join(shown[:SHOWN_FILES]))}"
            f"{more}"
            if shown
            else "  the design files already matched its parked direction"
        )
    else:
        console.print(
            f"  seeded {res.seeded_parameters} parameter(s) and {res.seeded_requirements} "
            "requirement(s) from the sketch"
        )
    if res.failing:
        console.print(f"  {res.card_id} fails its screening:", soft_wrap=True)
        for line in res.failing:
            console.print(f"    ✗ {escape(line)}", soft_wrap=True, highlight=False)
    for line in [*res.notes, *res.stale]:
        console.print(f"  [yellow]![/yellow] {escape(line)}", soft_wrap=True)
    console.print("  next: `n2f build` and `n2f check`", soft_wrap=True)


def register(app: typer.Typer) -> None:
    """Attach the ``switch`` verb to the concept command group."""
    app.command("switch")(switch_cmd)
