"""The product's vitals for a checkpoint: total mass and priced cost from a fresh build (v0.8 R3).

A checkpoint records them only when the parts list is up to date with the model; otherwise
both are None, which the owner reads as "not measured" (S-251). Nothing is built here.
"""

from __future__ import annotations

import json
from typing import Any

from napkin2factory.core.checkpoints import Vitals
from napkin2factory.core.loader import Product


def _fresh(product: Product) -> bool:
    """True when the parts-list rule would not run: its rollups match the model as it is."""
    from napkin2factory.core.graph.runner import explain_build

    # The last build may have rendered or not; the plan differs by that flag, so the parts
    # list is fresh if it is fresh under either (S-251).
    for render in (True, False):
        try:
            plan = explain_build(product, "all", render=render)
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
