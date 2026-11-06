"""Live change requests: ``start``, ``impact``, ``approve``, ``close``, ``abort``, ``quick``.

A live request (one with a ``baseline``, v0.8 R6) is edited in place: ``start`` saves the
folder's checkpoint as the baseline, the agent edits ``model/`` files, and every later step
reads the folder against that baseline (:mod:`live_impact`). There is no patch and no
``apply``. At most one request is open (``draft`` or ``approved``) at a time (S-254); an
approval is bound to the hash of the model it approved (R7); every state change leaves a
checkpoint (R4, ``cli/checkpointing.py``).

The start checkpoint rule, shared with ``undo`` (M1b): the first checkpoint after the
baseline is the one ``start`` records, and nothing is recorded between them, so ``undo``
stops there and ``abort`` can find where the request began.
"""

from __future__ import annotations

import datetime as dt
import shutil
import tempfile
from pathlib import Path
from typing import Any

from napkin2factory.cli.checkpointing import checkpoint, save_edits_first, stale_after_restore
from napkin2factory.core import checkpoints
from napkin2factory.core.checkpoints import Checkpoint
from napkin2factory.core.graph.impact import parse_set
from napkin2factory.core.loader import Product, load_product
from napkin2factory.core.model import Ecr
from napkin2factory.core.vcs import Vcs
from napkin2factory.core.vitals import current_vitals
from napkin2factory.core.yamlio import dump_roundtrip, load_roundtrip, write_yaml
from napkin2factory.ecr import live_impact
from napkin2factory.ecr.apply import _set_in_yaml
from napkin2factory.ecr.live_text import summarize_live
from napkin2factory.ecr.revisions import _append_changelog, _close_gate, bump_revisions
from napkin2factory.ecr.state import EcrError, _ecr_path, _require, next_ecr_id

#: Statuses of a request that is still being worked on.
OPEN = ("draft", "approved")
#: What a scratch copy for a trial leaves out (the build, the history).
_NOT_COPIED = frozenset({"build", ".git", ".worktrees", "__pycache__"})


def is_live(ecr: Ecr) -> bool:
    """True for a request started with ``ecr start`` (it has a baseline)."""
    return ecr.baseline is not None


def open_request(product: Product) -> Ecr | None:
    """The one live request still open (draft or approved), if any.

    A request filed before v0.8 (no baseline) follows the old steps and does not count: it
    cannot hold the folder, and M2c migrates it (B-0263).
    """
    for e in product.ecrs.values():
        if is_live(e) and e.status in OPEN:
            return e
    return None


def resolve(product: Product, ecr_id: str | None) -> Ecr:
    """The request named, else the open one; raises with the next step when there is none."""
    if ecr_id:
        return _require(product, ecr_id)
    ecr = open_request(product)
    if ecr is None:
        raise EcrError("no change request is open; `n2f ecr start --title …` opens one")
    return ecr


def _update(product: Product, ecr: Ecr, to: str | None = None, **fields: Any) -> None:
    """Write fields (and a new status, if the state machine allows it) into the request's file."""
    if to is not None and to != ecr.status and not ecr.can_transition(to):
        raise EcrError(f"{ecr.id} is {ecr.status}; it cannot become {to}")
    path = _ecr_path(product, ecr.id)
    data = load_roundtrip(path)
    if to is not None:
        data["status"] = to
    for key, value in fields.items():
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
    dump_roundtrip(path, data)


def _refuse_if_open(product: Product) -> None:
    other = open_request(product)
    if other is not None:
        raise EcrError(
            f"{other.id} ({other.title}) is still open; only one change request is open at "
            f"a time. Finish it with `n2f ecr close {other.id}` or drop it with "
            f"`n2f ecr abort {other.id}`"
        )


def _try_sets(product: Product, sets: list[str]) -> None:
    """Try the edits on a scratch copy, so a fault shows before ``start`` changes anything."""
    edits = [parse_set(s) for s in sets]
    for e in edits:
        if not product.exists(e.set.base):
            raise EcrError(f"{e.set} does not exist in the model; check the id")
    root = product.root.resolve()
    with tempfile.TemporaryDirectory(prefix="n2f-sets-") as tmp:
        copy = Path(tmp) / root.name
        shutil.copytree(
            root,
            copy,
            ignore=lambda d, names: [n for n in names if n in _NOT_COPIED],
        )
        trial = load_product(copy)
        for e in edits:
            _set_in_yaml(trial, e)
        load_product(copy)


def start(
    product: Product,
    title: str,
    kind: str = "parametric",
    reason: str | None = None,
    sets: list[str] | None = None,
    tasks: list[str] | None = None,
    requested_by: str = "human",
) -> dict[str, Any]:
    """Open a live change request: save unsaved edits, record the baseline and the start.

    Returns ``{"ecr", "baseline", "started", "checkpoint", "edits"}``: the request id, the
    baseline's id, the start checkpoint, the newest checkpoint (the edits', if there were any)
    and the line of each ``--set`` applied.
    """
    vcs = Vcs(product.root)
    vcs.require_repo_root()
    _refuse_if_open(product)
    if sets:
        _try_sets(product, sets)
    save_edits_first(product)  # never counted as part of the request (R6)
    newest = checkpoints.read(vcs, limit=1)
    base = newest[0] if newest else checkpoint(product, "Start")
    ecr_id = next_ecr_id(product)
    edits = [parse_set(s) for s in (sets or [])]
    vitals = current_vitals(product)
    ecr = Ecr.model_validate(
        {
            "id": ecr_id,
            "title": title,
            "kind": kind,
            "reason": reason,
            "edits": edits,
            "tasks": list(tasks or []),
            "requested_by": requested_by,
            "created": dt.date.today(),
            "baseline": {"checkpoint": base.id, "mass": vitals.mass, "cost": vitals.cost},
        }
    )
    payload = ecr.model_dump(mode="json", exclude_none=True)
    payload["edits"] = [{"set": str(e.set), "to": e.to} for e in edits]
    product.paths.changes.mkdir(parents=True, exist_ok=True)
    write_yaml(_ecr_path(product, ecr_id), payload)
    vcs.set_ref(f"ecr/{ecr_id}/baseline", base.id)
    started = checkpoint(product, f"Started {ecr_id}: {title}")
    latest = started
    lines: list[str] = []
    if edits:
        lines = [_set_in_yaml(product, e) for e in edits]
        words = ", ".join(f"{e.set.id} to {e.to}" for e in edits)
        latest = checkpoint(load_product(product.root), f"{ecr_id}: set {words}")
    return {
        "ecr": ecr_id,
        "baseline": base.id,
        "started": started,
        "checkpoint": latest,
        "edits": lines,
    }


def impact(product: Product, ecr_id: str | None = None) -> tuple[Ecr, dict[str, Any], str]:
    """Compute and store the impact of the open (or named) live request; returns its report text.

    An approved request goes back to draft: an approval belongs to the impact report it
    read, and this is a new one (R7).
    """
    ecr = resolve(product, ecr_id)
    if not is_live(ecr):
        raise EcrError(f"{ecr.id} was filed the old way; use its own steps")
    if ecr.status not in OPEN:
        raise EcrError(f"{ecr.id} is {ecr.status}; impact is assessed on open change requests")
    block = live_impact.compute(product, ecr)
    text = summarize_live(block, product, ecr.title, ecr.id)
    if ecr.status == "approved":
        _update(product, ecr, "draft", impact=block, approval=None)
    else:
        _update(product, ecr, impact=block)
    out = live_impact.cache_dir(product, ecr.id).parent / f"{ecr.id}-impact.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return ecr, block, text


def approve(product: Product, ecr_id: str | None, by: str, note: str | None = None) -> Checkpoint:
    """Record the owner's approval, bound to the model the impact report was computed on (R7)."""
    ecr = resolve(product, ecr_id)
    if not is_live(ecr):
        raise EcrError(f"{ecr.id} was filed the old way; use its own steps")
    if ecr.status != "draft":
        raise EcrError(f"{ecr.id} is {ecr.status}; only an open, unapproved request is approved")
    if not ecr.impact or not ecr.impact.get("model_hash"):
        raise EcrError(
            f"{ecr.id} has no impact report yet; run `n2f ecr impact {ecr.id}` and read it first"
        )
    vcs = Vcs(product.root)
    now = live_impact.model_hash(vcs)
    if ecr.impact["model_hash"] != now:
        raise EcrError(
            f"the model changed since the impact of {ecr.id} was computed; "
            f"run `n2f ecr impact {ecr.id}` again and read it before approving"
        )
    approval = {
        "by": by,
        "at": dt.datetime.now().isoformat(timespec="seconds"),
        "note": note,
        "model_hash": now,
    }
    _update(product, ecr, "approved", approval={k: v for k, v in approval.items() if v})
    return checkpoint(product, f"Approved {ecr.id} by {by}")


def close(product: Product, ecr_id: str | None = None) -> dict[str, Any]:
    """Close an approved live request: the model is the one approved, build and checks green."""
    from napkin2factory.core.checks.stage import compute_stage

    ecr = resolve(product, ecr_id)
    if not is_live(ecr):
        raise EcrError(f"{ecr.id} was filed the old way; use its own steps")
    if ecr.status != "approved" or ecr.approval is None:
        raise EcrError(
            f"{ecr.id} is {ecr.status}; approve it first: `n2f ecr impact {ecr.id}`, "
            f"then `n2f ecr approve {ecr.id} --by <name>`"
        )
    vcs = Vcs(product.root)
    vcs.require_repo_root()
    if ecr.approval.model_hash and ecr.approval.model_hash != live_impact.model_hash(vcs):
        raise EcrError(
            f"the model changed since {ecr.id} was approved; review the new impact: "
            f"`n2f ecr impact {ecr.id}`, then `n2f ecr approve {ecr.id} --by <name>` again"
        )
    save_edits_first(product)  # the approved model, saved, so the revision diff sees it
    results = _build_and_check(product)
    _close_gate(ecr.id, results)
    assert ecr.baseline is not None
    render = live_impact.render_flag(product)
    with live_impact.baseline_copy(vcs, ecr.baseline.checkpoint) as scratch:
        base = live_impact.baseline_figures(product, ecr, scratch, render)
    bumped = bump_revisions(
        product,
        dict(base["outputs"]),
        since=ecr.baseline.checkpoint,
        new=_created_since(vcs, product, ecr.baseline.checkpoint),
    )
    if bumped:
        _build_and_check(load_product(product.root))
    _append_changelog(product, ecr, bumped)
    fresh = load_product(product.root)
    _update(fresh, fresh.ecrs[ecr.id], "closed")
    cp = checkpoint(load_product(product.root), f"Closed {ecr.id}: {ecr.title}")
    stage = compute_stage(load_product(product.root), napkin=False)
    next_step = "`n2f release vX.Y.Z`" if stage.current == "ready" else stage.next_step
    return {
        "bumped": {k: list(v) for k, v in bumped.items()},
        "stage": stage.stage,
        "current_stage": stage.current,
        "next_step": next_step,
        "checkpoint": cp,
    }


def _created_since(vcs: Vcs, product: Product, checkpoint: str) -> frozenset[str]:
    """URIs of the parts and assemblies whose file did not exist at ``checkpoint``."""
    new: set[str] = set()
    for uri in (
        *(p.uri for p in product.parts.values()),
        *(a.uri for a in product.assemblies.values()),
    ):
        rel = product.files[uri].relative_to(product.paths.root).as_posix()
        if vcs.read_file(checkpoint, rel) is None:
            new.add(uri)
    return frozenset(new)


def _build_and_check(product: Product) -> list[dict[str, Any]]:
    """Build up to the checks (incremental) and return the check results."""
    import json

    from napkin2factory.core.graph.runner import run_build

    run_build(
        product, target=live_impact.TARGET, quiet=True, render=live_impact.render_flag(product)
    )
    data = json.loads((product.paths.build / "checks" / "checks.json").read_text(encoding="utf-8"))
    results: list[dict[str, Any]] = data["results"]
    return results


def start_checkpoint(vcs: Vcs, ecr: Ecr) -> Checkpoint:
    """The checkpoint ``start`` recorded: the first one after the baseline."""
    if ecr.baseline is None:
        raise EcrError(f"{ecr.id} has no baseline")
    cps = sorted(checkpoints.read(vcs), key=lambda c: c.number)
    for i, cp in enumerate(cps):
        if cp.id == ecr.baseline.checkpoint and i + 1 < len(cps):
            return cps[i + 1]
    raise EcrError(f"the history {ecr.id} started from is not in this folder; it cannot be undone")


def abort(product: Product, ecr_id: str | None = None, reason: str | None = None) -> dict[str, Any]:
    """Drop an open request: save the work as a checkpoint, return to where it started.

    The aborted work stays reachable as a checkpoint, so the abort itself can be undone (R2).
    """
    ecr = resolve(product, ecr_id)
    if not is_live(ecr):
        raise EcrError(f"{ecr.id} was filed the old way; `n2f ecr reject {ecr.id} --reason …`")
    if ecr.status not in OPEN:
        raise EcrError(f"{ecr.id} is {ecr.status}; only an open change request is aborted")
    vcs = Vcs(product.root)
    vcs.require_repo_root()
    start_cp = start_checkpoint(vcs, ecr)
    saved = save_edits_first(product)
    vcs.restore(start_cp.id)
    path = _ecr_path(product, ecr.id)
    data = load_roundtrip(path)
    data["status"] = "aborted"
    if reason:
        data["aborted_reason"] = reason
    dump_roundtrip(path, data)
    cp = checkpoint(
        load_product(product.root),
        f"Aborted {ecr.id}: {ecr.title}",
        restores=start_cp.id,
    )
    return {
        "checkpoint": cp,
        "restored": start_cp,
        "saved": saved,
        "stale": stale_after_restore(load_product(product.root)),
    }


def quick(
    product: Product,
    sets: list[str],
    reason: str | None = None,
    title: str | None = None,
    requested_by: str = "human",
) -> dict[str, Any]:
    """``start`` with the edits, then the impact: the whole small change in one step."""
    if not sets:
        raise EcrError("`n2f ecr quick` needs at least one `--set param://x=value`")
    words = ", ".join(f"{parse_set(s).set.id} to {parse_set(s).to}" for s in sets)
    started = start(
        product,
        title or f"Set {words}",
        reason=reason,
        sets=sets,
        requested_by=requested_by,
    )
    ecr, block, text = impact(load_product(product.root), started["ecr"])
    return {**started, "impact": block, "text": text, "title": ecr.title}
