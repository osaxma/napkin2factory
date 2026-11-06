"""``n2f snapshot`` and ``n2f discard``: the owner-level save and undo (gate-2 B1, v0.8 R4)."""

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
from napkin2factory.core.vcs import Vcs, VcsError


@handle_errors
def snapshot(
    message: str = typer.Option("Save changes", "--message", "-m", help="What this checkpoint is."),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Save the current state of the model as a checkpoint (what releasing and diffing build on)."""
    from napkin2factory.cli.checkpointing import checkpoint

    root = product_root(dir)
    vcs = Vcs(root)
    vcs.require_repo_root()
    before = vcs.head()
    cp = checkpoint(root, message)
    changed = cp.id != before
    if json_out:
        emit_json(
            {
                "snapshot": cp.id,
                "checkpoint": {"id": cp.id, "number": cp.number, "label": cp.label},
                "changed": changed,
            }
        )
    elif changed:
        console.print(f"[green]✓[/green] saved as checkpoint #{cp.number}: {escape(message)}")
    else:
        console.print("nothing changed since the last checkpoint")


@handle_errors
def discard(
    yes: bool = typer.Option(False, "--yes", help="Do it without asking."),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Throw away every change since the last checkpoint (`n2f redo` brings them back)."""
    from napkin2factory.cli.checkpointing import checkpoint
    from napkin2factory.cli.undo import do_undo

    root = product_root(dir)
    vcs = Vcs(root)
    vcs.require_repo_root()
    if vcs.is_clean():
        console.print("nothing to discard: the model matches the last checkpoint")
        return
    undone = vcs.unsaved_files()
    if not yes and not json_out:
        typer.confirm("Discard all changes since the last checkpoint?", abort=True)
    # The edits are saved as a checkpoint first, then put back as an undo would, so the
    # edits can come back with `n2f redo` (v0.8 R2, S-253).
    dropped = checkpoint(root, "edits discarded")
    step = do_undo(root)
    if step.reason is not None or step.shown is None:  # cannot happen with a checkpoint behind
        raise VcsError(
            step.reason or "there is no earlier checkpoint to go back to", code="no-history"
        )
    new, back = step.new, step.shown
    if json_out:
        emit_json(
            {
                "discarded": True,
                "files": undone,
                "checkpoint": {"id": new.id, "number": new.number, "label": new.label},
                "edits_saved_as": {"id": dropped.id, "number": dropped.number},
            }
        )
        return
    where = f"the model matches checkpoint #{back.number} again"
    files_str = ", ".join(undone)
    what = f"discarded changes in {escape(files_str)}" if files_str else "changes discarded"
    console.print(f"[yellow]•[/yellow] {what}; {where}")
    console.print("  [dim]`n2f redo` brings them back[/dim]")
