"""``n2f snapshot`` and ``n2f discard``: the owner-level save and undo (gate-2 B1)."""

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
from napkin2factory.core.vcs import Vcs


@handle_errors
def snapshot(
    message: str = typer.Option("Save changes", "--message", "-m", help="What this snapshot is."),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Save the current state of the model (what releasing and diffing build on)."""
    root = product_root(dir)
    vcs = Vcs(root)
    vcs.require_repo_root()
    before = vcs.head()
    sha = vcs.snapshot(message)
    changed = sha != before
    if json_out:
        emit_json({"snapshot": sha, "changed": changed})
    elif changed:
        console.print(f"[green]✓[/green] saved as snapshot {sha[:10]}: {escape(message)}")
    else:
        console.print("nothing changed since the last snapshot")


@handle_errors
def discard(
    yes: bool = typer.Option(False, "--yes", help="Do it without asking."),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Throw away every change since the last snapshot (cannot be undone)."""
    root = product_root(dir)
    vcs = Vcs(root)
    vcs.require_repo_root()
    if vcs.is_clean():
        console.print("nothing to discard: the model matches the last snapshot")
        return
    if not yes and not json_out:
        typer.confirm("Discard all changes since the last snapshot?", abort=True)
    vcs.discard()
    if json_out:
        emit_json({"discarded": True})
    else:
        console.print(
            "[yellow]•[/yellow] changes discarded; the model matches the last snapshot again"
        )
