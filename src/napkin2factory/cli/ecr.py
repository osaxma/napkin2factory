"""``n2f ecr start|impact|approve|close|abort|quick|list|show`` (live change requests, v0.8).

``new`` and ``apply`` bridge to the new steps for one version (R9, S-254). A change request
filed before v0.8 (no baseline) keeps its old steps (``impact``, ``approve``, ``apply``,
``close``, ``reject``) until M2c migrates it.
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
from napkin2factory.core.checkpoints import Checkpoint
from napkin2factory.core.loader import Product, load_product
from napkin2factory.ecr import lifecycle, live
from napkin2factory.ecr.state import EcrError

ecr_app = typer.Typer(
    help="Change requests: start, edit the model, see the impact, approve, close (or abort).",
    no_args_is_help=True,
)

NO_PATCH = (
    "a change request no longer carries a patch: edit the model files directly after "
    "`n2f ecr start`"
)
#: The one line `ecr new` prints before it does what `ecr start` does (R9).
NEW_BRIDGE = "`ecr new` is now `ecr start`"


def _check_kind(kind: str) -> None:
    if kind not in ("parametric", "design"):
        raise typer.BadParameter("--kind must be parametric or design")


def _no_patch(patch: str | None) -> None:
    if patch is not None:
        raise EcrError(NO_PATCH)


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
    patch: str | None,
    by: str,
    dir: Path | None,
    json_out: bool,
    note: str | None = None,
) -> None:
    _no_patch(patch)
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
                **({"note": note} if note else {}),
            }
        )
        return
    if note:
        console.print(f"[dim]{note}[/dim]")
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
    patch: str | None = typer.Option(None, "--patch", hidden=True),
    by: str = typer.Option("human", "--by"),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Open a change request. Edit `model/` files directly, then `n2f ecr impact`."""
    _start(title, kind, reason, set_, task, patch, by, dir, json_out)


@ecr_app.command("new")
@handle_errors
def new(
    title: str = typer.Option(..., "--title", help="What the change is, in one line."),
    kind: str = typer.Option("parametric", "--kind", help="parametric | design"),
    reason: str | None = typer.Option(None, "--reason"),
    set_: list[str] = typer.Option([], "--set", help="Edit <uri>=<value>, applied now."),
    task: list[str] = typer.Option([], "--task", help="Designer task; repeatable (design)."),
    patch: str | None = typer.Option(None, "--patch", hidden=True),
    by: str = typer.Option("human", "--by"),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Bridge for one version: does what `n2f ecr start` does."""
    _start(title, kind, reason, set_, task, patch, by, dir, json_out, note=NEW_BRIDGE)


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
    if not live.is_live(ecr):
        # TODO(B-0263): M2c migrates requests without a baseline; this branch goes with it
        report, md = lifecycle.run_impact(product, ecr.id)
        if json_out:
            emit_json(report.to_dict())
        else:
            console.print(md, markup=False)
            console.print(
                f"  saved to build/changes/{ecr.id}-impact.md · next: "
                f"`n2f ecr approve {ecr.id} --by <name>` or `n2f ecr reject {ecr.id} --reason …`"
            )
        return
    ecr, block, text = live.impact(product, ecr.id)
    if json_out:
        from napkin2factory.core import checkpoints
        from napkin2factory.core.vcs import Vcs

        newest = checkpoints.read(Vcs(product.root), limit=1)
        emit_json({"id": ecr.id, "checkpoint": newest[0].id if newest else None, **block})
        return
    console.print(text, markup=False)
    console.print(
        f"  saved to build/changes/{ecr.id}-impact.md · next: `n2f ecr approve {ecr.id} --by "
        f"<name>`, or keep editing and run `n2f ecr impact {ecr.id}` again; "
        f"`n2f ecr abort {ecr.id}` drops it"
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
    if not live.is_live(ecr):
        # TODO(B-0263): the old steps go with the migration
        lifecycle.approve(product, ecr.id, by, note)
        if json_out:
            emit_json({"id": ecr.id, "status": "approved"})
        else:
            console.print(
                f"[green]✓[/green] {ecr.id} approved by {escape(by)} · next: "
                f"`n2f ecr apply {ecr.id}`"
            )
        return
    cp = live.approve(product, ecr.id, by, note)
    if json_out:
        emit_json({"id": ecr.id, "status": "approved", "checkpoint": cp.id})
    else:
        console.print(
            f"[green]✓[/green] {ecr.id} approved by {escape(by)} · checkpoint {escape(_cp(cp))} "
            f"· next: `n2f ecr close {ecr.id}`"
        )


@ecr_app.command("apply")
@handle_errors
def apply(
    ecr_id: str | None = typer.Argument(None),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Bridge for one version: there is nothing to apply, the model is edited in place."""
    product = load_product(product_root(dir))
    old = product.ecrs.get((ecr_id or "").replace("ecr://", ""))
    if old is None or live.is_live(old):
        open_one = live.open_request(product)
        target = ecr_id or (open_one.id if open_one else "ECR-xxx")
        raise EcrError(
            "there is no apply step any more: the model is edited in place. "
            f"Approve with `n2f ecr approve {target} --by <name>`, then close with "
            f"`n2f ecr close {target}`"
        )
    # TODO(B-0263): a request without a baseline still applies; M2c migrates it
    lines = lifecycle.apply(product, old.id)
    if json_out:
        emit_json({"id": old.id, "status": "applied", "changes": lines})
    else:
        for ln in lines:
            console.print(f"  {escape(ln)}")
        console.print(
            f"[green]✓[/green] {old.id} applied and saved · next: "
            f"`n2f build && n2f check`, then `n2f ecr close {old.id}`"
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
    if live.is_live(ecr):
        result = live.close(product, ecr.id)
        cp: Checkpoint | None = result.pop("checkpoint")
    else:
        # TODO(B-0263): the old steps go with the migration
        result = lifecycle.close(product, ecr.id)
        cp = None
    if json_out:
        emit_json({"id": ecr.id, "status": "closed", **result, "checkpoint": cp.id if cp else None})
        return
    from napkin2factory.core.checks.stage import STAGE_WORDS

    for uri, (old, new_rev) in result["bumped"].items():
        console.print(f"  {uri}: rev {old} → {new_rev}")
    nxt = result.get("next_step") or "`n2f release vX.Y.Z`"
    words = STAGE_WORDS[result["current_stage"]]
    saved = f" · checkpoint {escape(_cp(cp))}" if cp else ""
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
    patch: str | None = typer.Option(None, "--patch", hidden=True),
    by: str = typer.Option("human", "--by"),
    dir: Path | None = DirOption,
    json_out: bool = JsonOption,
) -> None:
    """Start, apply the edits and show the impact in one step (a small parameter change)."""
    _no_patch(patch)
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
    console.print(
        f"  next: `n2f ecr approve {ecr_id} --by <name> && n2f ecr close {ecr_id}`, "
        f"or `n2f ecr abort {ecr_id}`"
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
    found = lifecycle._require(product, ecr_id)
    if live.is_live(found):
        raise EcrError(
            f"{found.id} is edited in place; drop it with `n2f ecr abort {found.id}` "
            "(that also puts the model back)"
        )
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
        console.print("  none yet · `n2f ecr start --title …` or `n2f ecr quick --set param://x=…`")


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
        console.print(f"  started from checkpoint {ecr.baseline.checkpoint[:8]}")
    if ecr.impact:
        console.print(
            f"  impact: {len(ecr.impact.get('rules', []))} rule(s), "
            f"cost {ecr.impact.get('cost_delta', 0) or 0:+.2f} USD"
        )
    if ecr.aborted_reason:
        console.print(f"  aborted: {escape(ecr.aborted_reason)}")
    if ecr.approval:
        console.print(f"  approved by {escape(ecr.approval.by)} at {ecr.approval.at}")
    if ecr.released_in:
        console.print(f"  released in {ecr.released_in}")
