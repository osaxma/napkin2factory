"""ECR state machine and mechanical application (decisions D7, D22, D23).

``new`` → ``impact`` → ``approve`` → ``apply`` → ``close`` (or ``reject``).  Parametric
change requests carry ``edits`` applied in place with ruamel (comments and order kept);
design change requests carry ``tasks`` for the designer and may carry a ``patch`` (a
unified diff over ``model/``) that ``apply`` applies.  Every step that changes the model
takes a snapshot through the vcs wrapper (D31) and is worded for the operator.

Split across state.py, apply.py and revisions.py (S-248).

v0.8: live change requests (``ecr start``, edited in place, no patch) live in ``live.py``.
The steps below are the old ones, kept for requests filed without a baseline (the kiln's
drafts) until M2c migrates them.  TODO(B-0263): M2c removes ``new_ecr``, ``run_impact``,
``approve``, ``reject`` and ``close`` here, ``apply.apply`` and the patch dry run
(``core/graph/impact_patch.py``).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from napkin2factory.core.graph.impact import (
    ImpactReport,
    compute_impact,
    parse_set,
    summarize,
)
from napkin2factory.core.loader import Product, load_product
from napkin2factory.core.model import Ecr
from napkin2factory.core.uris import Uri
from napkin2factory.core.vcs import Vcs
from napkin2factory.core.yamlio import write_yaml
from napkin2factory.ecr.apply import (
    _coerce,
    _edit_param_line,
    _move_invalidated_signoffs,
    _set_in_yaml,
    apply,
)
from napkin2factory.ecr.revisions import (
    _EMPTY_TREE,
    _append_changelog,
    _asm_order,
    _changed_files,
    _close_gate,
    _output_hashes,
    _part_rel,
    _snapshot_before,
    bump_revisions,
)
from napkin2factory.ecr.state import (
    EcrError,
    _ecr_path,
    _require,
    _transition,
    next_ecr_id,
)


def new_ecr(
    product: Product,
    title: str,
    kind: str = "parametric",
    reason: str | None = None,
    sets: list[str] | None = None,
    tasks: list[str] | None = None,
    patch: str | None = None,
    requested_by: str = "human",
    snapshot: bool = True,
) -> Ecr:
    """Create ``changes/ECR-xxx.yaml`` in ``draft``."""
    ecr_id = next_ecr_id(product)
    edits = [parse_set(s) for s in (sets or [])]
    for e in edits:
        if not product.exists(e.set.base):
            raise EcrError(f"{e.set} does not exist in the model; check the id")
    ecr = Ecr(
        id=ecr_id,
        title=title,
        kind=kind,
        reason=reason,
        edits=edits,
        tasks=list(tasks or []),
        patch=patch,
        requested_by=requested_by,
        created=dt.date.today(),
    )
    payload = ecr.model_dump(mode="json", exclude_none=False)
    payload["edits"] = [{"set": str(e.set), "to": e.to} for e in edits]
    product.paths.changes.mkdir(parents=True, exist_ok=True)
    write_yaml(_ecr_path(product, ecr_id), payload)
    if snapshot:
        vcs = Vcs(product.root)
        if vcs.is_tracked() and vcs.is_repo_root():
            vcs.snapshot(f"File {ecr_id}: {title}")
    return ecr


def run_impact(product: Product, ecr_id: str, write: bool = True) -> tuple[ImpactReport, str]:
    """Compute impact, store the structured block in the ECR, write the Markdown summary."""
    ecr = _require(product, ecr_id)
    if ecr.status not in ("draft", "impact"):
        raise EcrError(f"{ecr.id} is {ecr.status}; impact is assessed on draft change requests")
    # a design change request's patch is part of the change: its impact is the patched
    # model's (S-180)
    patch = product.root / ecr.patch if ecr.kind == "design" and ecr.patch else None
    report = compute_impact(
        product, list(ecr.edits), kind=ecr.kind, tasks=list(ecr.tasks), patch=patch
    )
    md = summarize(report, product)
    if write:
        removed = set(report.patch.objects.get("removed", [])) if report.patch else set()
        _transition(product, ecr, "impact", impact=_plain(report.to_dict(), product, removed))
        out = product.paths.build / "changes" / f"{ecr.id}-impact.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
    return report, md


def _plain(obj: Any, product: Product | None = None, removed: set[str] | None = None) -> Any:
    """Make an impact dict YAML-safe (S-215)."""
    if isinstance(obj, dict):
        return {_plain(str(k)): _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


def approve(
    product: Product,
    ecr_id: str,
    by: str,
    note: str | None = None,
    snapshot: bool = True,
) -> None:
    """Record the owner's approval after the impact report."""
    ecr = _require(product, ecr_id)
    if ecr.status == "draft":
        raise EcrError(
            f"{ecr.id} has no impact report yet; run `n2f ecr impact {ecr.id}` and read it first"
        )
    _transition(
        product,
        ecr,
        "approved",
        approval={"by": by, "at": dt.datetime.now().isoformat(timespec="seconds"), "note": note},
    )
    if snapshot:
        vcs = Vcs(product.root)
        if vcs.is_tracked() and vcs.is_repo_root():
            vcs.snapshot(f"Approve {ecr_id}")


def reject(product: Product, ecr_id: str, reason: str, snapshot: bool = True) -> None:
    """Close a change request without applying it."""
    ecr = _require(product, ecr_id)
    _transition(product, ecr, "rejected", rejected_reason=reason)
    if snapshot:
        vcs = Vcs(product.root)
        if vcs.is_tracked() and vcs.is_repo_root():
            vcs.snapshot(f"Reject {ecr_id}")


def close(product: Product, ecr_id: str) -> dict[str, Any]:
    """Close an applied change request: checks green, sign-offs current; revisions bump."""
    from napkin2factory.core.checks.stage import compute_stage
    from napkin2factory.core.graph.runner import run_build

    ecr = _require(product, ecr_id)
    if ecr.status != "applied":
        raise EcrError(f"{ecr.id} is {ecr.status}; only applied change requests are closed")
    vcs = Vcs(product.root)
    vcs.require_repo_root()
    run_build(product, target="checks", quiet=True)
    import json

    checks = json.loads(
        (product.paths.build / "checks" / "checks.json").read_text(encoding="utf-8")
    )
    _close_gate(ecr.id, checks["results"])
    before = (ecr.applied.model_dump() if ecr.applied else {}).get("before") or {}
    bumped = bump_revisions(product, dict(before), since=_snapshot_before(product, ecr))
    if bumped:
        run_build(load_product(product.root), target="checks", quiet=True)
    _append_changelog(product, ecr, bumped)
    fresh = load_product(product.root)
    _transition(fresh, fresh.ecrs[ecr.id], "closed")
    vcs.snapshot(f"Close {ecr.id}: {ecr.title}")
    # unpromoted concept cards never gate a release (N11), so the Napkin gate stays out of
    # the next step here (review gate A, C11)
    # ``stage`` keeps its v0.1 meaning (last gate passed) for scripts; ``current_stage`` is
    # the stage being worked in, the one `n2f status` and the report name (S-090)
    stage = compute_stage(load_product(product.root), napkin=False)
    next_step = "`n2f release vX.Y.Z`" if stage.current == "ready" else stage.next_step
    return {
        "bumped": {k: list(v) for k, v in bumped.items()},
        "stage": stage.stage,
        "current_stage": stage.current,
        "next_step": next_step,
    }


def ecr_table(product: Product) -> list[dict[str, Any]]:
    """Rows for ``n2f ecr list``."""
    return [
        {
            "id": e.id,
            "title": e.title,
            "kind": e.kind,
            "status": e.status,
            "released_in": e.released_in or "",
        }
        for e in product.ecrs.values()
    ]


__all__ = [
    "EcrError",
    "Uri",
    "_EMPTY_TREE",
    "_append_changelog",
    "_asm_order",
    "_changed_files",
    "_close_gate",
    "_coerce",
    "_ecr_path",
    "_edit_param_line",
    "_move_invalidated_signoffs",
    "_output_hashes",
    "_part_rel",
    "_require",
    "_set_in_yaml",
    "_snapshot_before",
    "_transition",
    "apply",
    "approve",
    "bump_revisions",
    "close",
    "ecr_table",
    "new_ecr",
    "next_ecr_id",
    "reject",
    "run_impact",
]
