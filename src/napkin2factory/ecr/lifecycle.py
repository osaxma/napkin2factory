"""ECR state machine and mechanical application (decisions D7, D22, D23).

``new`` → ``impact`` → ``approve`` → ``apply`` → ``close`` (or ``reject``).  Parametric
change requests carry ``edits`` applied in place with ruamel (comments and order kept);
design change requests carry ``tasks`` for the designer and may carry a ``patch`` (a
unified diff over ``model/``) that ``apply`` applies.  Every step that changes the model
takes a snapshot through the vcs wrapper (D31) and is worded for the operator.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any

from napkin2factory.core.errors import GateBlocked, N2FError
from napkin2factory.core.graph.impact import (
    ImpactReport,
    compute_impact,
    next_rev,
    parse_set,
    summarize,
)
from napkin2factory.core.loader import Product, load_product
from napkin2factory.core.model import TRANSITIONS, Ecr, Edit
from napkin2factory.core.units import UnitError, format_quantity, parse_quantity
from napkin2factory.core.uris import Uri
from napkin2factory.core.vcs import Vcs
from napkin2factory.core.yamlio import dump_roundtrip, load_roundtrip, write_yaml


class EcrError(N2FError):
    """A change request cannot take this step; the message says why and what to do."""

    exit_code = 3


def _ecr_path(product: Product, ecr_id: str) -> Path:
    return product.paths.changes / f"{ecr_id}.yaml"


def _require(product: Product, ecr_id: str) -> Ecr:
    ecr_id = ecr_id.replace("ecr://", "")
    if ecr_id not in product.ecrs:
        known = ", ".join(sorted(product.ecrs)) or "none yet"
        raise EcrError(
            f"change request {ecr_id} does not exist (known: {known}); `n2f ecr new` creates one"
        )
    return product.ecrs[ecr_id]


def _transition(product: Product, ecr: Ecr, to: str, **fields: Any) -> None:
    if not ecr.can_transition(to):
        allowed = ", ".join(TRANSITIONS[ecr.status]) or "nothing (it is final)"
        raise EcrError(f"{ecr.id} is {ecr.status}; from there it can only go to: {allowed}")
    path = _ecr_path(product, ecr.id)
    data = load_roundtrip(path)
    data["status"] = to
    for k, v in fields.items():
        data[k] = v
    dump_roundtrip(path, data)


def next_ecr_id(product: Product) -> str:
    """``ECR-001``, or one past the highest existing id."""
    nums = [int(m.group(1)) for e in product.ecrs for m in [re.match(r"ECR-(\d{3})", e)] if m]
    return f"ECR-{(max(nums) + 1) if nums else 1:03d}"


def new_ecr(
    product: Product,
    title: str,
    kind: str = "parametric",
    reason: str | None = None,
    sets: list[str] | None = None,
    tasks: list[str] | None = None,
    patch: str | None = None,
    requested_by: str = "human",
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
    return ecr


def run_impact(product: Product, ecr_id: str, write: bool = True) -> tuple[ImpactReport, str]:
    """Compute impact, store the structured block in the ECR, write the Markdown summary."""
    ecr = _require(product, ecr_id)
    if ecr.status not in ("draft", "impact"):
        raise EcrError(f"{ecr.id} is {ecr.status}; impact is assessed on draft change requests")
    report = compute_impact(product, list(ecr.edits), kind=ecr.kind, tasks=list(ecr.tasks))
    md = summarize(report, product)
    if write:
        _transition(product, ecr, "impact", impact=_plain(report.to_dict()))
        out = product.paths.build / "changes" / f"{ecr.id}-impact.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
    return report, md


def _plain(obj: Any) -> Any:
    """Make an impact dict YAML-safe (no tuples, no Uri objects)."""
    if isinstance(obj, dict):
        return {str(k): _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


def approve(product: Product, ecr_id: str, by: str, note: str | None = None) -> None:
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


def reject(product: Product, ecr_id: str, reason: str) -> None:
    """Close a change request without applying it."""
    ecr = _require(product, ecr_id)
    _transition(product, ecr, "rejected", rejected_reason=reason)


# ---- apply ---------------------------------------------------------------------------


def _set_in_yaml(product: Product, edit: Edit) -> str:
    """Apply one edit to the right YAML file in place; return a human line."""
    u = edit.set
    if u.scheme == "param":
        path = product.paths.parameters
        data = load_roundtrip(path)
        params = data.setdefault("parameters", {})
        if u.id not in params:
            raise EcrError(f"param://{u.id} does not exist")
        entry = params[u.id]
        unit = entry.get("unit", "") or None
        try:
            q = parse_quantity(str(edit.to), unit)
            value: Any = q.to(unit).magnitude if unit else q.magnitude
        except Exception as exc:
            raise EcrError(f"cannot set param://{u.id} to {edit.to!r}: {exc}") from exc
        if "expr" in entry:
            raise EcrError(
                f"param://{u.id} is an expression ({entry['expr']}); "
                "set the parameters it depends on instead"
            )
        old = entry.get("value")
        new_value = int(value) if float(value).is_integer() else float(value)
        if not _edit_param_line(path, u.id, new_value):
            entry["value"] = new_value
            dump_roundtrip(path, data)
        return f"param://{u.id}: {old} → {new_value} {unit or ''}".strip()
    # selector edits on requirements, parts, assemblies, interfaces, decisions
    if u.scheme == "req":
        path = product.paths.requirements
        data = load_roundtrip(path)
        target = next((r for r in data.get("requirements", []) if r.get("id") == u.id), None)
    elif u.scheme == "dec":
        path = product.paths.decisions
        data = load_roundtrip(path)
        target = next((d for d in data.get("decisions", []) if d.get("id") == u.id), None)
    elif u.scheme in ("part", "asm", "iface"):
        folder = {
            "part": product.paths.parts,
            "asm": product.paths.assemblies,
            "iface": product.paths.interfaces,
        }[u.scheme]
        path = folder / f"{u.id}.yaml"
        data = load_roundtrip(path)
        target = data
    else:
        raise EcrError(
            f"edits cannot target {u.scheme}:// ({u}); supported: param, req, part, asm, iface, dec"
        )
    if target is None:
        raise EcrError(f"{u.base} does not exist")
    cur: Any = target
    for key in u.selector[:-1]:
        if key not in cur or cur[key] is None:
            cur[key] = {}
        cur = cur[key]
    last = u.selector[-1]
    old = cur.get(last) if isinstance(cur, dict) else None
    cur[last] = _coerce(edit.to, old)
    dump_roundtrip(path, data)
    return f"{u}: {old!r} → {cur[last]!r}"


def _edit_param_line(path: Path, slug: str, value: Any) -> bool:
    """Change ``value:`` on the parameter's own line, touching nothing else (one-line diff).

    Works for the flow-mapping style ``n2f init`` writes (``slug: {value: 1, unit: mm}``);
    returns False when the parameter is written in block style, so the caller falls back
    to a ruamel round-trip.
    """
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    pat = re.compile(
        rf"^(\s*{re.escape(slug)}\s*:\s*\{{.*?)(value\s*:\s*)([-+0-9.eE]+)(.*)$", re.DOTALL
    )
    for i, line in enumerate(lines):
        m = pat.match(line)
        if m:
            lines[i] = f"{m.group(1)}{m.group(2)}{value}{m.group(4)}"
            path.write_text("".join(lines), encoding="utf-8")
            return True
    return False


def _coerce(value: Any, old: Any) -> Any:
    """Keep the field's type where obvious: numbers stay numbers, quantities stay strings."""
    if isinstance(old, bool):
        return str(value).lower() in ("true", "yes", "1")
    if isinstance(old, (int, float)) and not isinstance(value, (int, float)):
        try:
            f = float(str(value).split()[0])
            return int(f) if f.is_integer() and isinstance(old, int) else f
        except ValueError:
            return value
    if isinstance(value, str):
        try:
            q = parse_quantity(value)
            return format_quantity(q) if not q.dimensionless else value
        except UnitError:
            return value
    return value


def apply(product: Product, ecr_id: str, snapshot: bool = True) -> list[str]:
    """Apply an approved change request to the model and take a snapshot."""
    ecr = _require(product, ecr_id)
    if ecr.status != "approved":
        raise EcrError(
            f"{ecr.id} is {ecr.status}; only approved change requests are applied "
            f"(`n2f ecr approve {ecr.id} --by <name>`)"
        )
    vcs = Vcs(product.root)
    vcs.require_repo_root()
    lines: list[str] = []
    before = _output_hashes(product)
    for e in ecr.edits:
        lines.append(_set_in_yaml(product, e))
    if ecr.kind == "design":
        if ecr.patch:
            patch_path = product.root / ecr.patch
            if not patch_path.is_file():
                raise EcrError(f"{ecr.id}: patch file {ecr.patch} not found")
            vcs.apply_patch(patch_path)
            lines.append(f"applied patch {ecr.patch}")
        for t in ecr.tasks:
            lines.append(f"task for the designer: {t}")
    # validate the result before snapshotting
    fresh = load_product(product.root)
    sha = vcs.snapshot(f"Apply {ecr.id}: {ecr.title}") if snapshot else (vcs.head() or "")
    _transition(
        fresh,
        fresh.ecrs[ecr.id],
        "applied",
        applied={
            "snapshot": sha,
            "at": dt.datetime.now().isoformat(timespec="seconds"),
            "before": before,
        },
    )
    if snapshot:
        vcs.snapshot(f"Record {ecr.id} as applied")
    return lines


def _output_hashes(product: Product) -> dict[str, str]:
    """Current part/assembly output hashes (for revision bumps at close)."""
    from napkin2factory.core.graph.manifest import Manifest

    m = Manifest.load(product.paths.build)
    return {rid: e.output_hash for rid, e in m.entries.items() if rid.startswith(("part:", "asm:"))}


# ---- close ---------------------------------------------------------------------------


def bump_revisions(product: Product, before: dict[str, str]) -> dict[str, tuple[str, str]]:
    """Bump revs of changed parts, then of assemblies whose children changed.

    Returns ``{uri: (old, new)}``.
    """
    after = _output_hashes(product)
    bumped: dict[str, tuple[str, str]] = {}
    for part in product.parts.values():
        rid = f"part:{part.id}"
        changed = before.get(rid) != after.get(rid) if (rid in before or rid in after) else False
        if changed or _declared_changed(product, part.uri):
            path = product.paths.parts / f"{part.id}.yaml"
            data = load_roundtrip(path)
            old = str(data.get("rev", "A"))
            data["rev"] = next_rev(old)
            dump_roundtrip(path, data)
            bumped[part.uri] = (old, data["rev"])
    for aid in _asm_order(product):
        asm = product.assemblies[aid]
        child_bumped = any(c.uri in bumped for c in asm.children)
        rid = f"asm:{aid}"
        changed = before.get(rid) != after.get(rid) if (rid in before or rid in after) else False
        if child_bumped or changed:
            path = product.paths.assemblies / f"{aid}.yaml"
            data = load_roundtrip(path)
            old = str(data.get("rev", "A"))
            data["rev"] = next_rev(old)
            dump_roundtrip(path, data)
            bumped[asm.uri] = (old, data["rev"])
    return bumped


def _asm_order(product: Product) -> list[str]:
    from napkin2factory.geometry.build import assembly_order

    return assembly_order(product)


def _declared_changed(product: Product, uri: str) -> bool:
    """Did this part's YAML change since the applied snapshot's parent? (vcs diff)."""
    rel = f"model/parts/{uri.split('://')[1]}.yaml"
    return rel in Vcs(product.root).changed_in_last_snapshot()


def _close_gate(ecr_id: str, results: list[dict[str, Any]]) -> None:
    """Refuse to close while a check fails or a requirement waits for a human sign-off.

    Example sign-offs (``signed`` rows flagged ``example``) do not block: the release gate
    weighs those.  Failing checks are listed first; the sign-off wording matches the stage
    blockers (``core/checks/stage.py``) so ``n2f status`` and ``n2f ecr close`` agree.
    """
    fails = [r["id"] for r in results if r["status"] == "fail"]
    human = [r for r in results if r["status"] == "needs-human"]
    if not fails and not human:
        return
    reasons: list[str] = []
    if fails:
        reasons.append(f"{len(fails)} check(s) fail ({', '.join(fails[:5])})")
    for r in human:
        rid = r["id"].split("://")[-1]
        why = r.get("message") or "needs a human sign-off"
        reasons.append(
            f"{rid} needs a human sign-off ({why}) — "
            f'`n2f signoff {rid} --by <name> --statement "…"`'
        )
    if not human:
        tail = "fix them, rebuild, and close again"
    elif not fails:
        tail = f"sign {'it' if len(human) == 1 else 'them'} off, then close again"
    else:
        tail = "fix the failing checks, rebuild, sign off what needs it, and close again"
    raise GateBlocked(f"{ecr_id} cannot close: {'; '.join(reasons)}; {tail}")


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
    bumped = bump_revisions(product, dict(before))
    if bumped:
        run_build(load_product(product.root), target="checks", quiet=True)
    _append_changelog(product, ecr, bumped)
    fresh = load_product(product.root)
    _transition(fresh, fresh.ecrs[ecr.id], "closed")
    vcs.snapshot(f"Close {ecr.id}: {ecr.title}")
    stage = compute_stage(load_product(product.root))
    next_step = "`n2f release vX.Y.Z`" if stage.stage == "verify" else stage.next_step
    return {
        "bumped": {k: list(v) for k, v in bumped.items()},
        "stage": stage.stage,
        "next_step": next_step,
    }


def _append_changelog(product: Product, ecr: Ecr, bumped: dict[str, tuple[str, str]]) -> None:
    path = product.paths.changelog
    text = path.read_text(encoding="utf-8") if path.is_file() else "# Changelog\n"
    lines = [
        f"\n## {ecr.id} — {ecr.title} ({dt.date.today().isoformat()})\n",
        f"Kind: {ecr.kind}. {ecr.reason or ''}".strip() + "\n",
    ]
    for e in ecr.edits:
        lines.append(f"- set `{e.set}` to `{e.to}`\n")
    for t in ecr.tasks:
        lines.append(f"- design task: {t}\n")
    for uri, (old, new) in bumped.items():
        lines.append(f"- {uri}: rev {old} → {new}\n")
    if ecr.impact and ecr.impact.get("cost_delta"):
        lines.append(f"- cost delta: {ecr.impact['cost_delta']:+.2f} USD per unit\n")
    path.write_text(text.rstrip("\n") + "\n" + "".join(lines), encoding="utf-8")


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
