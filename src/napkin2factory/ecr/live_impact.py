"""The live impact of a change request: the working folder against its baseline (v0.8 R6).

``compute`` diffs the folder against the baseline checkpoint (``Vcs.diff_working``, without
``changes/``), classifies the changes into objects, rebuilds the current tree incrementally
(the normal build runner, up to the checks) and compares what that build measured with what
the baseline measured. The baseline's figures are built once, in a scratch copy of the
baseline, and kept in ``build/changes/<id>/baseline.json``: the baseline never changes, so
the file never needs to (it is rebuilt if it is missing or belongs to another baseline).

The figures are computed from builds, never estimated: mass, priced cost (the parts with no
price named, so a cost delta is never a silent zero), the envelope of each top assembly, the
status of every check, and the key of every rule so "what rebuilt" is what moved since the
baseline, not what happened to run during this command.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from napkin2factory.core.errors import N2FError
from napkin2factory.core.graph.impact import _impact, _patch_keys
from napkin2factory.core.graph.impact_live import live_diff
from napkin2factory.core.graph.manifest import Manifest
from napkin2factory.core.graph.runner import explain_build, run_build
from napkin2factory.core.loader import Product, load_product
from napkin2factory.core.model import Ecr
from napkin2factory.core.vcs import Vcs
from napkin2factory.ecr import stale_text
from napkin2factory.ecr.checkpointing import APPROVAL_HASH_EXCLUDE

#: The folder whose files are not part of a change (its own record, S-252).
RECORDS = "changes/"
BASELINE_FILE = "baseline.json"
#: Bump when ``figures`` changes shape: a kept baseline of another format is built again.
FORMAT = 2
#: The build target a live impact (and a close) rebuilds: everything the checks read.
TARGET = "checks"


def cache_dir(product: Product, ecr_id: str) -> Path:
    """``build/changes/<id>/``: what is kept about a request outside the model."""
    return product.paths.build / "changes" / ecr_id


def model_hash(vcs: Vcs) -> str:
    """The hash an impact report and an approval are bound to: the model, without records."""
    return vcs.working_hash(exclude=APPROVAL_HASH_EXCLUDE)


def figures(product: Product, build_dir: Path) -> dict[str, Any]:
    """What a finished build measured, in the plain form kept for before/after comparison."""
    from napkin2factory.bom.rollups import cost_basis_of, top_assemblies

    out: dict[str, Any] = {
        "mass": None,
        "mass_unit": "kg",
        "mass_complete": True,
        "cost": None,
        "cost_unit": "USD",
        "cost_complete": True,
        "cost_basis": "estimate",
        "unit_costs": {},
        "unpriced": [],
        "orphans": [],
        "envelope": {},
        "checks": {},
        "messages": {},
        "req_messages": {},
        "rules": {},
        "outputs": {},
    }
    rollups = _read_json(build_dir / "bom" / "rollups.json")
    if rollups:
        out["mass"] = rollups.get("total_mass")
        out["mass_unit"] = rollups.get("total_mass_unit", "kg")
        out["mass_complete"] = bool(rollups.get("mass_complete", True))
        out["cost"] = rollups.get("total_cost")
        out["cost_unit"] = rollups.get("total_cost_unit", "USD")
        out["cost_complete"] = bool(rollups.get("cost_complete", True))
        parts = rollups.get("parts", {})
        out["cost_basis"] = cost_basis_of(rollups)
        out["unit_costs"] = {u: row.get("unit_cost") for u, row in parts.items()}
        out["unpriced"] = sorted(u for u, row in parts.items() if row.get("unit_cost") is None)
        out["orphans"] = sorted(rollups.get("orphans", []))
    for aid in top_assemblies(product):
        bbox = (_read_json(build_dir / "assemblies" / aid / "props.json") or {}).get("bbox")
        if isinstance(bbox, dict) and all(k in bbox for k in "xyz"):
            out["envelope"][f"asm://{aid}"] = [round(float(bbox[k]), 1) for k in "xyz"]
    checks = _read_json(build_dir / "checks" / "checks.json") or {}
    out["checks"] = {str(r["id"]): str(r["status"]) for r in checks.get("results", []) if "id" in r}
    out["messages"] = {
        str(r["id"]): str(r.get("persona_message") or r.get("message") or "")
        for r in checks.get("results", [])
        if r.get("status") == "fail" and "id" in r
    }
    out["req_messages"] = {
        str(r["id"]): str(r.get("persona_message") or r.get("message") or "")
        for r in checks.get("results", [])
        if str(r.get("id", "")).startswith("req://")
    }
    manifest = Manifest.load(build_dir)
    out["rules"] = {rid: e.key for rid, e in manifest.entries.items()}
    out["outputs"] = {
        rid: e.output_hash
        for rid, e in manifest.entries.items()
        if rid.startswith(("part:", "asm:"))
    }
    return out


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def render_flag(product: Product) -> bool:
    """Whether the folder's last build had renders, read from the build's own record.

    A build with renders and one without are different builds (the flag is an input of the
    part rules); building with the other one would redo every part. A folder never built
    is built without renders, which is faster and changes no number.
    """
    for entry in Manifest.load(product.paths.build).entries.values():
        flag = entry.inputs.get("render")
        if flag is not None:
            return flag == "render"
    return False


@contextmanager
def baseline_copy(vcs: Vcs, checkpoint: str) -> Iterator[Path]:
    """The model as it stood at ``checkpoint``, in a scratch folder removed afterwards."""
    with tempfile.TemporaryDirectory(prefix="n2f-baseline-") as tmp:
        wt = Path(tmp) / "baseline"
        vcs.worktree_add(checkpoint, wt)
        try:
            _read_as_current(wt)
            yield wt
        finally:
            vcs.worktree_remove(wt)
            shutil.rmtree(wt, ignore_errors=True)


def _read_as_current(scratch: Path) -> None:
    """Read a baseline saved before the schema 2 upgrade as the current format.

    Only the change-request records and the ``schema:`` line differ between the formats; the
    records are not part of the model being compared, so the copy drops them (S-261).
    """
    from napkin2factory.core.model import migrate

    if migrate.schema_of(scratch) < migrate.CURRENT:
        migrate.write_schema(scratch, migrate.CURRENT)
        shutil.rmtree(scratch / "changes", ignore_errors=True)


def baseline_figures(
    product: Product, ecr: Ecr, scratch: Path, render: bool, refresh: bool = False
) -> dict[str, Any]:
    """The baseline's figures: from ``baseline.json``, else built in the ``scratch`` copy.

    The copy starts with this folder's ``build/`` so the build only does what differs; the
    result is kept, since a baseline never changes. ``refresh`` rebuilds even when kept.
    """
    assert ecr.baseline is not None
    path = cache_dir(product, ecr.id) / BASELINE_FILE
    kept = None if refresh else _read_json(path)
    if (
        kept is not None
        and kept.get("checkpoint") == ecr.baseline.checkpoint
        and kept.get("format") == FORMAT
    ):
        return kept
    if product.paths.build.is_dir():
        shutil.copytree(
            product.paths.build,
            scratch / "build",
            symlinks=True,
            dirs_exist_ok=True,
        )
    other = load_product(scratch)
    run_build(other, target=TARGET, quiet=True, render=render, build_dir=scratch / "build")
    data = figures(other, scratch / "build")
    data["checkpoint"] = ecr.baseline.checkpoint
    data["format"] = FORMAT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
    return data


_SCHEMA_LINE = re.compile(r"^schema:[^\n#]*", re.MULTILINE)


def _only_schema_moved(vcs: Vcs, checkpoint: str) -> bool:
    """True when ``n2f.yaml`` differs from the baseline's only by its ``schema:`` line."""
    then = vcs.read_file(checkpoint, "n2f.yaml")
    try:
        now = (vcs.root / "n2f.yaml").read_text(encoding="utf-8")
    except OSError:
        return False
    if then is None:
        return False
    old = _SCHEMA_LINE.sub("schema:", then.decode("utf-8", errors="replace"), count=1)
    return old == _SCHEMA_LINE.sub("schema:", now, count=1)


def _files(vcs: Vcs, checkpoint: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"added": [], "changed": [], "removed": []}
    for c in vcs.diff_working(checkpoint):
        if c.path.startswith(RECORDS):
            continue
        if c.path == "n2f.yaml" and _only_schema_moved(vcs, checkpoint):
            continue  # the upgrade moved the format number, not the design
        out[c.status].append(c.path)
    return out


def _delta(before: Any, after: Any) -> float | None:
    if isinstance(before, (int, float)) and isinstance(after, (int, float)):
        return round(float(after) - float(before), 4)
    return None


def compute(product: Product, ecr: Ecr) -> dict[str, Any]:
    """The stored ``impact:`` block for a live request; rebuilds the current tree as it goes.

    Raises :class:`N2FError` when the baseline checkpoint is gone from the history. A build
    that fails (a broken part script) raises its own error: fix the model, run it again.
    """
    if ecr.baseline is None:
        raise N2FError(f"{ecr.id} has no baseline; it is not a live change request")
    vcs = Vcs(product.root)
    vcs.require_repo_root()
    base_id = ecr.baseline.checkpoint
    if not vcs.ref_exists(base_id):
        raise N2FError(
            f"{ecr.id} started from a saved state that is no longer in this folder's history "
            f"({base_id[:8]}); abort it with `n2f ecr abort {ecr.id}`"
        )
    files = _files(vcs, base_id)
    model_at = model_hash(vcs)
    render = render_flag(product)
    with baseline_copy(vcs, base_id) as scratch:
        before = load_product(scratch)
        base = baseline_figures(product, ecr, scratch, render)
    found, params = live_diff(before, product, files)
    plan = explain_build(product, TARGET, render=render)
    seeded = {rid: why for rid, run, why in plan if run and rid != "validate"}
    report = _impact(
        product,
        [],
        product.paths.build,
        ecr.kind,
        list(ecr.tasks),
        _patch_keys(before, product, found),
        seeded,
        patch=found,
    )
    run_build(product, target=TARGET, quiet=True, render=render)
    now = figures(product, product.paths.build)
    return _block(ecr, product, report, found, params, base, now, files, model_at)


def _block(
    ecr: Ecr,
    product: Product,
    report: Any,
    found: Any,
    params: list[dict[str, Any]],
    base: dict[str, Any],
    now: dict[str, Any],
    files: dict[str, list[str]],
    model_at: str,
) -> dict[str, Any]:
    """Assemble the stored impact: the diff, the before → after figures, rebuilds, sign-offs."""
    rebuilt = {
        rid: report.rule_reasons.get(rid, "its inputs changed")
        for rid in sorted(set(base["rules"]) | set(now["rules"]))
        if base["rules"].get(rid) != now["rules"].get(rid)
    }
    mass = {
        "before": base["mass"],
        "after": now["mass"],
        "delta": _delta(base["mass"], now["mass"]),
        "unit": now["mass_unit"],
        "complete": now["mass_complete"],
        "basis": "computed",
    }
    # A part rebuilt with the same declared unit cost: its shape may have moved, but the
    # price was not re-quoted, so the cost delta does not speak for it (S-274).
    not_requoted = sorted(
        pid
        for rid in rebuilt
        if rid.startswith("part:")
        for pid in [rid.removeprefix("part:")]
        if f"part://{pid}" in now["unit_costs"]
        and base.get("unit_costs", {}).get(f"part://{pid}", "")
        == now["unit_costs"][f"part://{pid}"]
    )
    cost = {
        "before": base["cost"],
        "after": now["cost"],
        "delta": _delta(base["cost"], now["cost"]),
        "unit": now["cost_unit"],
        "complete": now["cost_complete"],
        "basis": now["cost_basis"],
        "shape_changed_not_requoted": not_requoted,
        "unpriced": now["unpriced"],
        "newly_unpriced": [u for u in now["unpriced"] if u not in base["unpriced"]],
        "not_in_an_assembly": [u for u in now["orphans"] if u not in base["orphans"]],
        "note": report.cost_note if not report.cost_complete else "",
    }
    envelope = {
        asm: {
            "before": base["envelope"].get(asm),
            "after": now["envelope"].get(asm),
            "basis": "computed",
        }
        for asm in sorted(set(base["envelope"]) | set(now["envelope"]))
    }
    affected = {r.id: r for r in report.requirements}
    moved = {
        cid.removeprefix("req://")
        for cid in set(base["checks"]) | set(now["checks"])
        if cid.startswith("req://") and base["checks"].get(cid) != now["checks"].get(cid)
    }
    requirements = []
    for rid in sorted(set(affected) | moved):
        req = product.requirements.get(rid)
        requirements.append(
            {
                "id": rid,
                "title": req.title if req is not None else "",
                "why": affected[rid].why if rid in affected else "its result moved",
                "before": base["checks"].get(f"req://{rid}"),
                "after": now["checks"].get(f"req://{rid}"),
                "safety": bool(req.safety) if req is not None else False,
                # the figures behind a verdict, as the check wrote them (gate L, S-281)
                "before_message": base.get("req_messages", {}).get(f"req://{rid}", ""),
                "after_message": now.get("req_messages", {}).get(f"req://{rid}", ""),
            }
        )
    other_checks = [
        {
            "id": cid,
            "before": base["checks"].get(cid),
            "after": now["checks"].get(cid),
            "message": now["messages"].get(cid, ""),
        }
        for cid in sorted(set(base["checks"]) | set(now["checks"]))
        if not cid.startswith("req://") and base["checks"].get(cid) != now["checks"].get(cid)
    ]
    # One source for both sign-off lists: the state the check computes (gate L, S-281).
    redo = sorted(
        c.removeprefix("req://")
        for c, status in now["checks"].items()
        if c.startswith("req://")
        and status == "needs-human"
        and base["checks"].get(c) in ("signed", "pass")
    )
    waiting = sorted(
        c.removeprefix("req://")
        for c, status in now["checks"].items()
        if c.startswith("req://") and status == "needs-human"
    )
    return {
        "live": True,
        "baseline": ecr.baseline.checkpoint if ecr.baseline else None,
        "model_hash": model_at,
        "computed_at": dt.datetime.now().isoformat(timespec="seconds"),
        "files": files,
        "objects": found.objects,
        "revs": found.revs,
        "parameters": params,
        "scope": found.scope,
        "mass": mass,
        "cost": cost,
        "cost_delta": cost["delta"] or 0.0,
        "envelope": envelope,
        "rules": sorted(rebuilt),
        "rebuilt": rebuilt,
        "requirements": requirements,
        "other_checks": other_checks,
        "signoffs_invalidated": redo,
        "signoffs_waiting": waiting,
        "stale_text": stale_text.find(product, params),
        "signoffs_removed": found.signoffs_removed,
        "interfaces": report.interfaces,
        "ports": report.ports,
        "kind": ecr.kind,
        "tasks": list(ecr.tasks),
    }
