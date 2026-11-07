"""The product's vitals for a checkpoint: total mass and priced cost from a fresh build (v0.8 R3).

A checkpoint records them only when the parts list is up to date with the model; otherwise
both are None, which the owner reads as "not measured" (S-251). Nothing is built here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from napkin2factory.core import checkpoints as cps
from napkin2factory.core.checkpoints import Vitals
from napkin2factory.core.loader import Product, load_product
from napkin2factory.core.vcs import Vcs

#: How many of the newest checkpoints are compared with the folder for an identical design.
_SAME_DESIGN_SCAN = 12

#: Files that record decisions, requirements, sign-offs, concepts or change requests without
#: changing the parts or parameters that determine mass and cost (B-0294).
_RECORD_ONLY_PREFIXES = (
    "changes/",
    "concepts/",
    "model/signoffs/",
    "model/decisions.yaml",
    "model/requirements.yaml",
    "model/docs/",
)


def _fresh(product: Product) -> bool:
    """True when the parts-list rule would not run: its rollups match the model as it is."""
    from napkin2factory.core.graph.runner import explain_build

    # The last build may have rendered or not; the plan differs by that flag, so the parts
    # list is fresh if it is fresh under either (S-251).
    for render in (True, False):
        try:
            plan = explain_build(product, "bom", render=render)
        except Exception:  # an unloadable model has no measurable vitals; the command says why
            return False
        if any(rid == "bom" and not run for rid, run, _ in plan):
            return True
    return False


def _mass(data: dict[str, Any]) -> str | None:
    value = data.get("total_mass")
    if not isinstance(value, (int, float)):
        return None
    text = f"{value:.1f} {data.get('total_mass_unit', 'kg')}"
    return text if data.get("mass_complete", True) else f"{text} (some parts without a mass)"


def _cost(data: dict[str, Any]) -> str | None:
    value = data.get("total_cost")
    if not isinstance(value, (int, float)):
        return None
    text = f"{value:,.0f} {data.get('total_cost_unit', 'USD')}"
    return text if data.get("cost_complete", True) else f"{text} (some parts without a price)"


def current_vitals(product: Product) -> Vitals:
    """Mass and priced cost from the last build when fresh, else ``Vitals()`` (not measured)."""
    path = product.paths.build / "bom" / "rollups.json"
    if not path.is_file() or not _fresh(product):
        return Vitals()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Vitals()
    if not isinstance(data, dict):
        return Vitals()
    return Vitals(mass=_mass(data), cost=_cost(data))


def _same_design(vcs: Vcs, ref: str) -> bool:
    """True when the working folder's design files match ``ref`` (record-only files aside)."""
    try:
        changes = vcs.diff_working(ref)
    except Exception:
        return False
    return not [c for c in changes if not c.path.startswith(_RECORD_ONLY_PREFIXES)]


def recorded_vitals(product: Product | Path, restores: str | None = None) -> Vitals:
    """Vitals for a checkpoint that may restore an earlier recorded state (B-0294).

    When ``restores`` names an earlier checkpoint (or another checkpoint shares the restored
    design state), its recorded vitals are reused so the same state keeps the same figures.
    Otherwise falls back to :func:`current_vitals` (not measured when the build is stale).
    """
    root = product.root if isinstance(product, Product) else Path(product)
    loaded: Product | None = product if isinstance(product, Product) else None
    if loaded is None:
        try:
            loaded = load_product(root)
        except Exception:
            loaded = None
    vcs = Vcs(root)
    if vcs.is_tracked() and vcs.is_repo_root():
        log = cps.read(vcs)
        if restores is not None:
            for cp in log:
                if cp.id == restores and cp.vitals:
                    return cp.vitals
            for cp in log:
                if cp.restores == restores and cp.vitals:
                    return cp.vitals
        for cp in log[:_SAME_DESIGN_SCAN]:  # newest first; each test is one diff
            if cp.vitals and _same_design(vcs, cp.id):
                return cp.vitals
    return current_vitals(loaded) if loaded is not None else Vitals()
