"""``n2f ecr new|impact|approve|apply|close|reject|list|show``."""

from __future__ import annotations

from pathlib import Path

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
from napkin2factory.core.loader import load_product
from napkin2factory.ecr import lifecycle

ecr_app = typer.Typer(
    help="Change requests: file, assess impact, approve, apply, close.", no_args_is_help=True
)


@ecr_app.command("new")
@handle_errors
def new(
    title: str = typer.Option(..., "--title", help="What the change is, in one line."),
    kind: str = typer.Option("parametric", "--kind", help="parametric | design"),
    reason: str | None = typer.Option(None, "--reason"),
    set_: list[str] = typer.Option(
        [], "--set", help="Edit <uri>=<value>; repeatable (parametric)."
    ),
    task: list[str] = typer.Option([], "--task", help="Designer task; repeatable (design)."),
    patch: str | None = typer.Option(None, "--patch", help="Unified diff over model/ (design)."),
    by: str = typer.Option("human", "--by"),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """File a new change request (draft)."""
    product = load_product(product_root(dir))
    if kind not in ("parametric", "design"):
        raise typer.BadParameter("--kind must be parametric or design")
    ecr = lifecycle.new_ecr(product, title, kind, reason, set_, task, patch, by)
    if json_out:
        emit_json({"id": ecr.id, "status": ecr.status, "file": f"changes/{ecr.id}.yaml"})
    else:
        console.print(
            f"[green]✓[/green] filed {ecr.id} ({kind}): {escape(title)} → changes/{ecr.id}.yaml"
        )
        console.print(f"  next: `n2f ecr impact {ecr.id}` to see what it would touch")


@ecr_app.command("impact")
@handle_errors
def impact(
    ecr_id: str = typer.Argument(...), dir: Path | None = DirOption, json_out: bool = JsonOption
) -> None:
    """Assess what the change request would touch; nothing changes."""
    product = load_product(product_root(dir))
    report, md = lifecycle.run_impact(product, ecr_id)
    if json_out:
        emit_json(report.to_dict())
    else:
        console.print(md, markup=False)
        console.print(
            f"  saved to build/changes/{ecr_id}-impact.md · next: "
            f"`n2f ecr approve {ecr_id} --by <name>` or `n2f ecr reject {ecr_id} --reason …`"
        )


@ecr_app.command("approve")
@handle_errors
def approve(
    ecr_id: str = typer.Argument(...),
    by: str = typer.Option(..., "--by"),
    note: str | None = typer.Option(None, "--note"),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Approve a change request after reading its impact report."""
    product = load_product(product_root(dir))
    lifecycle.approve(product, ecr_id, by, note)
    if json_out:
        emit_json({"id": ecr_id, "status": "approved"})
    else:
        console.print(
            f"[green]✓[/green] {ecr_id} approved by {escape(by)} · next: `n2f ecr apply {ecr_id}`"
        )


@ecr_app.command("apply")
@handle_errors
def apply(
    ecr_id: str = typer.Argument(...), dir: Path | None = DirOption, json_out: bool = JsonOption
) -> None:
    """Apply an approved change request to the model and save a snapshot."""
    product = load_product(product_root(dir))
    lines = lifecycle.apply(product, ecr_id)
    if json_out:
        emit_json({"id": ecr_id, "status": "applied", "changes": lines})
    else:
        for ln in lines:
            console.print(f"  {escape(ln)}")
        console.print(
            f"[green]✓[/green] {ecr_id} applied and snapshotted · next: "
            f"`n2f build && n2f check`, then `n2f ecr close {ecr_id}`"
        )


@ecr_app.command("close")
@handle_errors
def close(
    ecr_id: str = typer.Argument(...), dir: Path | None = DirOption, json_out: bool = JsonOption
) -> None:
    """Close an applied change request: checks must be green; revisions bump; changelog grows."""
    product = load_product(product_root(dir))
    result = lifecycle.close(product, ecr_id)
    if json_out:
        emit_json({"id": ecr_id, "status": "closed", **result})
    else:
        for uri, (old, new) in result["bumped"].items():
            console.print(f"  {uri}: rev {old} → {new}")
        nxt = result.get("next_step") or "`n2f release vX.Y.Z`"
        console.print(
            f"[green]✓[/green] {ecr_id} closed · stage: {result['stage']} · next: {escape(nxt)}"
        )


@ecr_app.command("reject")
@handle_errors
def reject(
    ecr_id: str = typer.Argument(...),
    reason: str = typer.Option(..., "--reason"),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Reject a change request."""
    product = load_product(product_root(dir))
    lifecycle.reject(product, ecr_id, reason)
    if json_out:
        emit_json({"id": ecr_id, "status": "rejected"})
    else:
        console.print(f"[yellow]•[/yellow] {ecr_id} rejected: {escape(reason)}")


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
        console.print("  none yet · `n2f ecr new --title … --set param://x=…`")


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
    if ecr.impact:
        console.print(
            f"  impact: {len(ecr.impact.get('rules', []))} rule(s), "
            f"cost {ecr.impact.get('cost_delta', 0):+.2f} USD"
        )
    if ecr.approval:
        console.print(f"  approved by {escape(ecr.approval.by)} at {ecr.approval.at}")
    if ecr.released_in:
        console.print(f"  released in {ecr.released_in}")
