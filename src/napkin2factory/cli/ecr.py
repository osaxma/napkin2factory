"""``n2f ecr start|impact|approve|close|abort|quick|list|show`` (live change requests, v0.8).

A request filed before v0.8 was carried into this flow by the schema 2 upgrade
(``n2f init .``, ``ecr/upgrade.py``, S-261).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
from rich.markup import escape
from rich.table import Table

from napkin2factory.cli.common import (
    DirOption,
    JsonOption,
    console,
    emit_json,
    handle_errors,
    product_root,
)
from napkin2factory.core import checkpoints as cps
from napkin2factory.core.checkpoints import Checkpoint
from napkin2factory.core.loader import Product, load_product
from napkin2factory.core.vcs import Vcs
from napkin2factory.ecr import lifecycle, live, live_text
from napkin2factory.ecr.checkpointing import matches_approval

ecr_app = typer.Typer(
    help="Change requests: start, edit the model, see the impact, approve, close (or abort).",
    no_args_is_help=True,
)


def _check_kind(kind: str) -> None:
    if kind not in ("parametric", "design"):
        raise typer.BadParameter("--kind must be parametric or design")


def _cp(cp: Checkpoint) -> str:
    """A checkpoint as the owner reads it: ``#12 "Started ECR-001: …"``."""
    return f'#{cp.number} "{cp.label}"'


def _pick(product: Product, ecr_id: str | None) -> Any:
    return live.resolve(product, ecr_id)


def _start(
    title: str,
    kind: str,
    reason: str | None,
    set_: list[str],
    task: list[str],
    by: str,
    dir: Path | None,
    json_out: bool,
) -> None:
    _check_kind(kind)
    product = load_product(product_root(dir))
    out = live.start(product, title, kind, reason, set_, task, by)
    if json_out:
        emit_json(
            {
                "id": out["ecr"],
                "status": "draft",
                "file": f"changes/{out['ecr']}.yaml",
                "baseline": out["baseline"],
                "checkpoint": out["checkpoint"].id,
                "edits": out["edits"],
            }
        )
        return
    ecr_id = out["ecr"]
    console.print(
        f"[green]✓[/green] started {ecr_id} ({kind}): {escape(title)} · "
        f"checkpoint {escape(_cp(out['checkpoint']))}"
    )
    for line in out["edits"]:
        console.print(f"  {escape(line)}")
    console.print(
        f"  next: edit the files under `model/`, then `n2f ecr impact {ecr_id}`; "
        f"`n2f ecr abort {ecr_id}` drops it"
    )


@ecr_app.command("start")
@handle_errors
def start(
    title: str = typer.Option(..., "--title", help="What the change is, in one line."),
    kind: str = typer.Option("parametric", "--kind", help="parametric | design"),
    reason: str | None = typer.Option(None, "--reason"),
    set_: list[str] = typer.Option(
        [], "--set", help="Edit <uri>=<value>, applied now; repeatable."
    ),
    task: list[str] = typer.Option([], "--task", help="Designer task; repeatable (design)."),
    by: str = typer.Option("human", "--by"),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Open a change request. Edit `model/` files directly, then `n2f ecr impact`."""
    _start(title, kind, reason, set_, task, by, dir, json_out)


@ecr_app.command("impact")
@handle_errors
def impact(
    ecr_id: str | None = typer.Argument(None, help="Defaults to the open change request."),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Show what the change does: files, objects, mass, cost, envelope, rebuilds, sign-offs."""
    product = load_product(product_root(dir))
    ecr = _pick(product, ecr_id)
    ecr, block, text = live.impact(product, ecr.id)
    if json_out:
        from napkin2factory.core import checkpoints
        from napkin2factory.core.vcs import Vcs

        newest = checkpoints.read(Vcs(product.root), limit=1)
        emit_json({"id": ecr.id, "checkpoint": newest[0].id if newest else None, **block})
        return
    console.print(text, markup=False)
    console.print(
        f"  saved to build/changes/{ecr.id}-impact.md · next: "
        f"{escape(live_text.next_step(block, ecr.id))}"
    )


@ecr_app.command("approve")
@handle_errors
def approve(
    ecr_id: str | None = typer.Argument(None, help="Defaults to the open change request."),
    by: str = typer.Option(..., "--by"),
    note: str | None = typer.Option(None, "--note"),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Approve a change request after reading its impact report."""
    product = load_product(product_root(dir))
    ecr = _pick(product, ecr_id)
    cp = live.approve(product, ecr.id, by, note)
    if json_out:
        emit_json({"id": ecr.id, "status": "approved", "checkpoint": cp.id})
    else:
        console.print(
            f"[green]✓[/green] {ecr.id} approved by {escape(by)} · checkpoint {escape(_cp(cp))} "
            f"· next: `n2f ecr close {ecr.id}`"
        )


@ecr_app.command("close")
@handle_errors
def close(
    ecr_id: str | None = typer.Argument(None, help="Defaults to the open change request."),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Close an approved change request: checks must be green; revisions bump; changelog grows."""
    product = load_product(product_root(dir))
    ecr = _pick(product, ecr_id)
    result = live.close(product, ecr.id)
    cp: Checkpoint = result.pop("checkpoint")
    if json_out:
        emit_json({"id": ecr.id, "status": "closed", **result, "checkpoint": cp.id})
        return
    from napkin2factory.core.checks.stage import STAGE_WORDS

    for uri, (old, new_rev) in result["bumped"].items():
        console.print(f"  {uri}: rev {old} → {new_rev}")
    if result.get("stale_text"):
        from napkin2factory.ecr import stale_text

        console.print("  words that may still give the old size (not a refusal):", markup=False)
        for line in stale_text.lines(result["stale_text"]):
            console.print(f"  {line}", markup=False)
    nxt = result.get("next_step") or "`n2f release vX.Y.Z`"
    words = STAGE_WORDS[result["current_stage"]]
    saved = f" · checkpoint {escape(_cp(cp))}"
    console.print(f"[green]✓[/green] {ecr.id} closed{saved} · stage: {words} · next: {escape(nxt)}")


@ecr_app.command("abort")
@handle_errors
def abort(
    ecr_id: str | None = typer.Argument(None, help="Defaults to the open change request."),
    reason: str | None = typer.Option(None, "--reason"),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Drop an open change request and return the model to where it started (undoable)."""
    product = load_product(product_root(dir))
    ecr = _pick(product, ecr_id)
    out = live.abort(product, ecr.id, reason)
    cp, back, saved = out["checkpoint"], out["restored"], out["saved"]
    if json_out:
        emit_json(
            {
                "id": ecr.id,
                "status": "aborted",
                "checkpoint": cp.id,
                "restored": back.id,
                "saved": saved.id if saved else None,
                "stale": out["stale"],
            }
        )
        return
    console.print(
        f"[yellow]•[/yellow] {ecr.id} aborted: the model is back to where it started · "
        f"checkpoint {escape(_cp(cp))}"
    )
    if saved:
        console.print(f"  your work is kept as {escape(_cp(saved))}; `n2f undo` brings it back")
    else:
        console.print("  `n2f undo` brings the request and its edits back")
    for line in out["stale"]:
        console.print(f"  {escape(line)}")


@ecr_app.command("quick")
@handle_errors
def quick(
    set_: list[str] = typer.Option(..., "--set", help="Edit <uri>=<value>; repeatable."),
    reason: str | None = typer.Option(None, "--reason"),
    title: str | None = typer.Option(None, "--title", help="Defaults to the edit in words."),
    by: str = typer.Option("human", "--by"),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Start, apply the edits and show the impact in one step (a small parameter change)."""
    product = load_product(product_root(dir))
    out = live.quick(product, set_, reason, title, by)
    ecr_id = out["ecr"]
    if json_out:
        emit_json(
            {
                "id": ecr_id,
                "status": "draft",
                "baseline": out["baseline"],
                "checkpoint": out["checkpoint"].id,
                "edits": out["edits"],
                **out["impact"],
            }
        )
        return
    console.print(
        f"[green]✓[/green] started {ecr_id}: {escape(out['title'])} · "
        f"checkpoint {escape(_cp(out['checkpoint']))}"
    )
    console.print(out["text"], markup=False)
    console.print(f"  next: {escape(live_text.next_step(out['impact'], ecr_id, False))}")


@ecr_app.command("list")
@handle_errors
def list_(dir: Path | None = DirOption, json_out: bool = JsonOption) -> None:
    """List change requests."""
    product = load_product(product_root(dir))
    rows = lifecycle.ecr_table(product)
    if json_out:
        emit_json({"ecrs": rows})
        return
    t = Table(title="Change requests")
    for c in ("id", "title", "kind", "status", "released in"):
        t.add_column(c)
    for r in rows:
        t.add_row(r["id"], escape(r["title"]), r["kind"], r["status"], r["released_in"])
    console.print(t)
    if not rows:
        console.print("  none yet · `n2f ecr start --title …` or `n2f ecr quick --set param://x=…`")


def _named(product: Any, checkpoint_id: str) -> str:
    """``#<n> "<label>"`` for a checkpoint id, as `n2f checkpoints` numbers it."""
    vcs = Vcs(product.root)
    if vcs.is_repo_root():
        for cp in cps.read(vcs):
            if cp.id == checkpoint_id:
                return f'#{cp.number} "{escape(cp.label)}"'
    return "an earlier checkpoint"


@ecr_app.command("show")
@handle_errors
def show(
    ecr_id: str = typer.Argument(...), dir: Path | None = DirOption, json_out: bool = JsonOption
) -> None:
    """Show one change request."""
    product = load_product(product_root(dir))
    ecr = lifecycle._require(product, ecr_id)
    data = ecr.model_dump(mode="json")
    if json_out:
        emit_json(data)
        return
    console.print(f"[bold]{ecr.id}[/bold] {escape(ecr.title)} · {ecr.kind} · {ecr.status}")
    if ecr.reason:
        console.print(f"  reason: {escape(ecr.reason)}")
    for e in ecr.edits:
        console.print(f"  set {e.set} → {escape(str(e.to))}")
    for t in ecr.tasks:
        console.print(f"  task: {escape(t)}")
    if ecr.baseline:
        console.print(f"  started from {_named(product, ecr.baseline.checkpoint)}")
    if ecr.impact:
        console.print(
            f"  impact: {len(ecr.impact.get('rules', []))} rule(s), "
            f"cost {ecr.impact.get('cost_delta', 0) or 0:+.2f} USD"
        )
    if ecr.aborted_reason:
        console.print(f"  aborted: {escape(ecr.aborted_reason)}")
    if ecr.approval:
        console.print(f"  approved by {escape(ecr.approval.by)} at {ecr.approval.at}")
        if ecr.status == "approved":
            vcs = Vcs(product.root)
            if vcs.is_repo_root() and not matches_approval(vcs, ecr.id):
                console.print(
                    f"  approved, but the model changed since; review it: `n2f ecr impact {ecr.id}`"
                )
    if ecr.released_in:
        console.print(f"  released in {ecr.released_in}")
