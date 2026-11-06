"""``n2f concept fork-from-model`` and ``n2f concept compare`` (v0.8 R11).

The verbs land in M3a; this module is registered from ``cli/concept.py``, S-257: new verbs
go in their own module, not in the concept command file.
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


@handle_errors
def _fork_from_model(
    title: str | None = typer.Option(None, "--title", help="A short name for the new card."),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Turn the built design into a new concept card (a starting point for a variant)."""
    from napkin2factory.concepts.fork import fork_from_model

    root = product_root(dir)
    result = fork_from_model(root, title)
    if json_out:
        emit_json(result.to_dict())
        return
    console.print(
        f"[green]✓[/green] {result.card_id} ({escape(result.title)}) forked from the built design",
        soft_wrap=True,
    )
    if result.checkpoint is not None:
        console.print(f"  saved as checkpoint #{result.checkpoint.number}", soft_wrap=True)
    for note in result.notes:
        console.print(f"  [dim]note: {escape(note)}[/dim]", soft_wrap=True)


@handle_errors
def _compare(
    cards: list[str] = typer.Argument(None, help="Cards to compare (default: every built card)."),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Print one table: a row per value, a column per card."""
    from napkin2factory.concepts.compare import compare, render_text

    root = product_root(dir)
    data = compare(root, list(cards) if cards else None)
    if json_out:
        emit_json(data)
        return
    console.print(render_text(data), markup=False, highlight=False, soft_wrap=False)


def register(app: typer.Typer) -> None:
    """Attach the ``fork-from-model`` and ``compare`` verbs to the concept command group."""
    app.command("fork-from-model")(_fork_from_model)
    app.command("compare")(_compare)
