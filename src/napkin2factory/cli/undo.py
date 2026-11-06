"""``n2f checkpoints``, ``undo``, ``redo`` and ``rollback``: step back and forward (v0.8 R2-R5).

Every restore saves unsaved edits first (as their own checkpoint), puts an earlier state back
in the folder and records that as a new checkpoint: history only moves forward, so a restore
is itself undoable and no saved state is ever lost (R2). The checkpoint list is read from the
log alone (S-246); the shared calls live in ``ecr/checkpointing.py``.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
from napkin2factory.core import checkpoints as cps
from napkin2factory.core.checkpoints import Checkpoint, Vitals
from napkin2factory.core.loader import load_product
from napkin2factory.core.vcs import FileChange, Vcs, VcsError
from napkin2factory.ecr.checkpointing import (
    checkpoint,
    open_change_request,
    save_edits_first,
    stale_after_restore,
)

NO_HISTORY = (
    "this folder has no saved history to go back to (it was copied without it, or change "
    "tracking was never set up): the steps before this copy are not in it; "
    "`n2f init .` starts saving from now"
)
SHOWN_FILES = 6


# ---- words ---------------------------------------------------------------------------------


def ago(when: int, now: float | None = None) -> str:
    """How long ago a time was, in the words an owner uses ("10 min ago", "2 days ago")."""
    seconds = max(0, int((now if now is not None else time.time()) - when))
    if seconds < 45:
        return "just now"
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"{minutes} min ago"
    hours = round(minutes / 60)
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = round(hours / 24)
    if days < 60:
        return f"{days} day{'s' if days != 1 else ''} ago"
    return time.strftime("%Y-%m-%d", time.localtime(when))


def vitals_words(vitals: Vitals) -> str:
    """``46.0 kg, 1,014 USD`` or ``not measured`` when the checkpoint has no vitals."""
    parts = [p for p in (vitals.mass, vitals.cost) if p]
    return ", ".join(parts) if parts else "not measured"


def _ref(cp: Checkpoint) -> str:
    """``#12 "Promoted C-002"``: a checkpoint's number always travels with its label."""
    return f'#{cp.number} "{cp.label}"'


def _as_json(cp: Checkpoint | None) -> dict[str, Any] | None:
    if cp is None:
        return None
    return {
        "id": cp.id,
        "number": cp.number,
        "label": cp.label,
        "when": cp.when,
        "mass": cp.vitals.mass,
        "cost": cp.vitals.cost,
    }


def _group(changes: list[FileChange]) -> list[str]:
    """Plain lines for what a restore changed in the folder (``removed`` seen from the state)."""
    words = {"changed": "changed", "removed": "brought back", "added": "removed"}
    lines = []
    for status in ("changed", "removed", "added"):
        paths = [c.path for c in changes if c.status == status]
        if not paths:
            continue
        shown = ", ".join(paths[:SHOWN_FILES])
        more = f" and {len(paths) - SHOWN_FILES} more" if len(paths) > SHOWN_FILES else ""
        lines.append(f"{words[status]}: {shown}{more}")
    return lines


# ---- the steps (no printing: the verbs report, the property tests call these) ---------------


@dataclass
class Step:
    """What one restore did: the checkpoint it recorded and the state it brought back.

    ``reason`` is set instead when there was nothing to do (nothing recorded, ``new`` is the
    newest checkpoint).
    """

    verb: str
    new: Checkpoint
    shown: Checkpoint | None = None
    changes: list[FileChange] = field(default_factory=list)
    saved: Checkpoint | None = None
    headline: str = ""
    reason: str | None = None


def open_history(root: Path) -> Vcs:
    """The folder's store, or the plain-words error when it has no history (DoD 1)."""
    vcs = Vcs(root)
    if not (vcs.is_tracked() and vcs.is_repo_root()) or vcs.snapshot_count() == 0:
        raise VcsError(NO_HISTORY, code="no-history")
    return vcs


def _nothing(verb: str, vcs: Vcs, saved: Checkpoint | None, reason: str) -> Step:
    return Step(verb, cps.read(vcs, limit=1)[0], saved=saved, reason=reason)


def do_undo(root: Path) -> Step:
    """Save unsaved edits, then go back one step (never past an open change request's start)."""
    vcs = open_history(root)
    saved = save_edits_first(root)
    log = cps.read(vcs)
    found = open_change_request(root)
    try:
        plan = cps.undo_plan(log, found[1] if found else None)
    except ValueError:  # the request's start is not on this line
        plan = None
    if plan is None:
        if found:
            why = (
                f"nothing more to undo inside the change request {found[0]}: that is where it "
                f"started. To leave it and go back, run `n2f ecr abort {found[0]}`."
            )
        else:
            why = "nothing to undo: this is the first checkpoint"
        return _nothing("undone", vcs, saved, why)
    changes = vcs.restore(plan.restores.id)
    new = checkpoint(
        root,
        f"Undid: {plan.undoes.label}",
        restores=plan.restores.id,
        undoes=plan.undoes.id,
        vitals=plan.restores.vitals,
    )
    headline = (
        f"undid {_ref(plan.undoes)}; back to {_ref(plan.restores)}. `n2f redo` brings it back"
    )
    return Step("undone", new, plan.restores, changes, saved, headline)


def do_redo(root: Path) -> Step:
    """Save unsaved edits, then bring back the step undone last."""
    vcs = open_history(root)
    saved = save_edits_first(root)
    plan = cps.redo_plan(cps.read(vcs))
    if plan is None:
        why = "nothing to redo: no step has been undone since the last change"
        return _nothing("redone", vcs, saved, why)
    changes = vcs.restore(plan.restores.id)
    new = checkpoint(
        root,
        f"Redid: {plan.redoes.label}",
        restores=plan.restores.id,
        redoes=plan.redoes.id,
        vitals=plan.restores.vitals,
    )
    return Step("redone", new, plan.restores, changes, saved, f"brought back {_ref(plan.redoes)}")


_NUMBER = re.compile(r"^#?(\d+)$")
_ECR = re.compile(r"^(?:ecr://)?(ECR-\d+)$")


def _resolve(root: Path, vcs: Vcs, log: list[Checkpoint], target: str) -> tuple[str, str, Vitals]:
    """``(state id, words for the label, vitals)`` of a rollback target, or an error."""
    text = target.strip()
    if m := _NUMBER.match(text):
        number = int(m.group(1))
        cp = next((c for c in log if c.number == number), None)
        if cp is None:
            raise VcsError(
                f"there is no checkpoint #{number}; `n2f checkpoints --all` lists them",
                code="no-such-checkpoint",
            )
        return cp.id, _ref(cp), cp.vitals
    if m := _ECR.match(text):
        ecr = load_product(root).ecrs.get(m.group(1))
        if ecr is None:
            raise VcsError(f"there is no change request {m.group(1)}", code="no-such-ecr")
        if ecr.baseline is None:
            raise VcsError(
                f"{ecr.id} does not record where it started, so there is nothing to go back to",
                code="no-baseline",
            )
        cp = next((c for c in log if c.id == ecr.baseline.checkpoint), None)
        vitals = cp.vitals if cp else Vitals(ecr.baseline.mass, ecr.baseline.cost)
        return ecr.baseline.checkpoint, f"before {ecr.id} ({ecr.title})", vitals
    state = vcs.revision_snapshot(text) if text in vcs.tags() else None
    if state is None:
        raise VcsError(
            f"{target!r} is not a checkpoint number, a change request or a released "
            "Revision; `n2f checkpoints` lists checkpoints",
            code="no-such-target",
        )
    cp = next((c for c in log if c.id == state), None)
    return state, f"Revision {text}", cp.vitals if cp else Vitals()


def do_rollback(root: Path, target: str) -> Step:
    """Refuse while a change request is open; else save edits and restore ``target``."""
    vcs = open_history(root)
    found = open_change_request(root)
    if found:
        raise VcsError(
            f"the change request {found[0]} is still open, so nothing can be rolled back "
            f"behind it: finish it, or leave it with `n2f ecr abort {found[0]}`",
            code="change-request-open",
        )
    saved = save_edits_first(root)
    log = cps.read(vcs)
    state, words, vitals = _resolve(root, vcs, log, target)
    if vcs.tree_of(state) == vcs.working_hash():
        why = f"the design already matches {words}: nothing to roll back"
        return _nothing("rolled_back", vcs, saved, why)
    changes = vcs.restore(state)
    new = checkpoint(root, f"Rolled back to {words}", restores=state, vitals=vitals)
    shown = next((c for c in log if c.id == state), None) or Checkpoint(
        id=state, number=0, label=words, when=new.when, vitals=vitals
    )
    return Step(
        "rolled_back", new, shown, changes, saved, f"rolled back to {words}. `n2f undo` reverses it"
    )


# ---- the verbs -----------------------------------------------------------------------------


def _report(root: Path, step: Step, json_out: bool) -> None:
    """Print (or emit) a step: what came back, the numbers there, what went stale."""
    if step.reason is not None:
        if json_out:
            emit_json(
                {
                    step.verb: False,
                    "reason": step.reason,
                    "checkpoint": _as_json(step.new),
                    "saved_edits": _as_json(step.saved),
                }
            )
        else:
            console.print(escape(step.reason), soft_wrap=True)
        return
    assert step.shown is not None
    stale = stale_after_restore(root)
    if json_out:
        emit_json(
            {
                step.verb: True,
                "checkpoint": _as_json(step.new),
                "restored": _as_json(step.shown),
                "saved_edits": _as_json(step.saved),
                "changed": [{"path": c.path, "status": c.status} for c in step.changes],
                "stale": stale,
            }
        )
        return
    if step.saved is not None:
        console.print(
            f"[dim]your unsaved edits were saved first as #{step.saved.number}; "
            "`n2f undo` takes them back out[/dim]",
            soft_wrap=True,
        )
    console.print(
        f"[green]✓[/green] {escape(step.headline)} (now checkpoint #{step.new.number})",
        soft_wrap=True,
    )
    for line in _group(step.changes) or ["no files differ: the folder already matched"]:
        console.print(f"  {escape(line)}")
    console.print(f"  numbers at that point: {escape(vitals_words(step.shown.vitals))}")
    for line in stale:
        console.print(f"  [yellow]![/yellow] {escape(line)}", soft_wrap=True)


@handle_errors
def checkpoints(
    all_rows: bool = typer.Option(False, "--all", help="Every checkpoint, not the last 20."),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """List the saved states of the design, newest first, with what they weighed and cost."""
    vcs = open_history(product_root(dir))
    log = cps.read(vcs)
    undone = {c.id for c in cps.stacks(log).redo}
    shown = log if all_rows else log[:20]
    unsaved = vcs.unsaved_files()
    if json_out:
        emit_json(
            {
                "checkpoints": [
                    {
                        **(_as_json(c) or {}),
                        "undone": c.id in undone,
                        "current": c is log[0],
                        "restores": c.restores,
                        "undoes": c.undoes,
                        "redoes": c.redoes,
                    }
                    for c in shown
                ],
                "total": len(log),
                "unsaved_files": unsaved,
            }
        )
        return
    if unsaved:
        console.print(
            f"[yellow]unsaved edits[/yellow] in {len(unsaved)} file(s) since #{log[0].number}"
        )
    for c in shown:
        marks = ("  (undone)" if c.id in undone else "") + (
            "  <- the folder is here" if c is log[0] else ""
        )
        console.print(
            f"#{c.number:<4}{ago(c.when):<14}{escape(c.label)}  "
            f"({escape(vitals_words(c.vitals))}){marks}",
            soft_wrap=True,
            highlight=False,
        )
    if len(shown) < len(log):
        console.print(f"[dim]{len(log) - len(shown)} older ones: `n2f checkpoints --all`[/dim]")


@handle_errors
def undo(dir: Path | None = DirOption, json_out: bool = JsonOption) -> None:
    """Go back one step: put the design back as it was before the last checkpoint."""
    root = product_root(dir)
    _report(root, do_undo(root), json_out)


@handle_errors
def redo(dir: Path | None = DirOption, json_out: bool = JsonOption) -> None:
    """Bring back the step that `undo` took away last."""
    root = product_root(dir)
    _report(root, do_redo(root), json_out)


@handle_errors
def rollback(
    target: str = typer.Argument(
        ..., help="A checkpoint (#12 or 12), a change request (ECR-002) or a Revision (v1.0.0)."
    ),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Put the design back as it was at a checkpoint, before a change request, or at a Revision."""
    root = product_root(dir)
    _report(root, do_rollback(root, target), json_out)


def register(app: typer.Typer) -> None:
    """Add the four verbs to the application (one call from ``cli/app.py``)."""
    app.command("checkpoints")(checkpoints)
    app.command("undo")(undo)
    app.command("redo")(redo)
    app.command("rollback")(rollback)
