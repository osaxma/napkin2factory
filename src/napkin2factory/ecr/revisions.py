"""Revision bumping, output hash tracking, snapshot diffs and close gates.

Split from lifecycle.py (S-248).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from napkin2factory.core.errors import GateBlocked
from napkin2factory.core.graph.impact import next_rev
from napkin2factory.core.loader import Product
from napkin2factory.core.model import Ecr
from napkin2factory.core.vcs import Vcs
from napkin2factory.core.yamlio import dump_roundtrip, load_roundtrip


def _output_hashes(product: Product) -> dict[str, str]:
    """Current part/assembly output hashes (for revision bumps at close)."""
    from napkin2factory.core.graph.manifest import Manifest

    m = Manifest.load(product.paths.build)
    return {rid: e.output_hash for rid, e in m.entries.items() if rid.startswith(("part:", "asm:"))}


def bump_revisions(
    product: Product, before: dict[str, str], since: str | None = None
) -> dict[str, tuple[str, str]]:
    """Bump revs of changed parts, then of assemblies whose children changed.

    A part changed when its output hash moved (``before`` → now) or its YAML differs
    between the snapshot ``since`` and the latest one (declared fields: finish, material,
    cost... that leave the geometry alone).  ``since`` is the snapshot before the change
    request was applied (:func:`_snapshot_before`); without it only the latest snapshot
    is diffed.  Returns ``{uri: (old, new)}``.
    """
    after = _output_hashes(product)
    declared = _changed_files(product, since)
    bumped: dict[str, tuple[str, str]] = {}
    for part in product.parts.values():
        rid = f"part:{part.id}"
        changed = before.get(rid) != after.get(rid) if (rid in before or rid in after) else False
        if changed or _part_rel(product, part.id) in declared:
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


#: git's empty tree: what a change request applied in the very first snapshot diffs against.
_EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def _snapshot_before(product: Product, ecr: Ecr) -> str | None:
    """The snapshot just before ``ecr`` was applied (S-089).

    ``apply`` records the snapshot that holds the change; its parent is the model as it
    stood before.  Later snapshots (a sign-off, the designer's own work) are all inside
    the span from there to the latest snapshot.
    """
    snap = ecr.applied.snapshot if ecr.applied else ""
    if not snap:
        return None
    vcs = Vcs(product.root)
    if not vcs.ref_exists(snap):
        return None
    parent = f"{snap}~1"
    return parent if vcs.ref_exists(parent) else _EMPTY_TREE


def _changed_files(product: Product, since: str | None) -> set[str]:
    """Files that differ between ``since`` and the latest snapshot (or in the latest one)."""
    vcs = Vcs(product.root)
    if since is None:
        return set(vcs.changed_in_last_snapshot())
    return set(vcs.diff_names(since, vcs.head() or since))


def _part_rel(product: Product, part_id: str) -> str:
    """A part's YAML path as the vcs diff names it (relative to the product root)."""
    return (product.paths.parts / f"{part_id}.yaml").relative_to(product.paths.root).as_posix()


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


__all__ = [
    "_EMPTY_TREE",
    "_append_changelog",
    "_asm_order",
    "_changed_files",
    "_close_gate",
    "_output_hashes",
    "_part_rel",
    "_snapshot_before",
    "bump_revisions",
]
