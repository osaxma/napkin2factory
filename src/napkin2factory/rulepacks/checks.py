"""Named check functions behind the YAML rule packs.

Each takes the part model, its ``features.json`` dict, the rule's params, and the product
context, and returns a list of violation dicts (empty = pass).  Message templates in the
YAML are formatted with the violation dict.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from napkin2factory.core.loader import Product
from napkin2factory.core.model import Part

Violation = dict[str, Any]
CheckFn = Callable[[Part, dict[str, Any], dict[str, Any], Product], list[Violation]]


def _thickness(feats: dict[str, Any]) -> float | None:
    t = feats.get("thickness")
    return float(t) if t else None


def min_bend_radius(
    part: Part, feats: dict[str, Any], params: dict[str, Any], product: Product
) -> list[Violation]:
    """R ≥ factor × t for every bend."""
    t = _thickness(feats)
    if t is None:
        return []
    out = []
    for b in feats.get("bends", []):
        if float(b["radius"]) + 1e-6 < params.get("factor", 1.0) * t:
            out.append(
                {
                    "label": b.get("label") or "?",
                    "radius": b["radius"],
                    "min": params.get("factor", 1.0) * t,
                    "thickness": t,
                }
            )
    return out


def min_hole_diameter(
    part: Part, feats: dict[str, Any], params: dict[str, Any], product: Product
) -> list[Violation]:
    """D ≥ factor × t for every hole."""
    t = _thickness(feats)
    if t is None:
        return []
    return [
        {"label": h.get("label") or "?", "diameter": h["diameter"], "thickness": t}
        for h in feats.get("holes", [])
        if float(h["diameter"]) + 1e-6 < params.get("factor", 1.0) * t
    ]


def _dist_point_segment(p: list[float], a: list[float], b: list[float]) -> float:
    ab = [b[i] - a[i] for i in range(3)]
    ap = [p[i] - a[i] for i in range(3)]
    denom = sum(c * c for c in ab) or 1e-12
    t = max(0.0, min(1.0, sum(ap[i] * ab[i] for i in range(3)) / denom))
    q = [a[i] + t * ab[i] for i in range(3)]
    return math.sqrt(sum((p[i] - q[i]) ** 2 for i in range(3)))


def hole_to_bend(
    part: Part, feats: dict[str, Any], params: dict[str, Any], product: Product
) -> list[Violation]:
    """Hole centre to bend line ≥ factor_t × t + factor_r × r.

    Uses the generator's ``bend_distance`` when it recorded one.
    """
    t = _thickness(feats)
    bends = feats.get("bends", [])
    if t is None or not bends:
        return []
    out = []
    for h in feats.get("holes", []):
        if h.get("bend_distance") is not None:
            d = float(h["bend_distance"])
            r = min(float(b["radius"]) for b in bends)
        else:
            d, r = min(
                (_dist_point_segment(h["center"], b["start"], b["end"]), float(b["radius"]))
                for b in bends
            )
        need = params.get("factor_t", 2.0) * t + params.get("factor_r", 1.0) * r
        if d + 1e-6 < need:
            out.append(
                {"label": h.get("label") or "?", "distance": round(d, 2), "min": round(need, 2)}
            )
    return out


def min_flange(
    part: Part, feats: dict[str, Any], params: dict[str, Any], product: Product
) -> list[Violation]:
    """Flange flat height ≥ factor × t."""
    t = _thickness(feats)
    if t is None:
        return []
    return [
        {
            "label": f.get("label") or "?",
            "height": f["height"],
            "min": params.get("factor", 4.0) * t,
        }
        for f in feats.get("flanges", [])
        if float(f["height"]) + 1e-6 < params.get("factor", 4.0) * t
    ]


def relief_present(
    part: Part, feats: dict[str, Any], params: dict[str, Any], product: Product
) -> list[Violation]:
    """Two or more non-parallel bends (adjacent flanges) require declared reliefs."""
    bends = feats.get("bends", [])
    if len(bends) < 2:
        return []
    dirs = set()
    for b in bends:
        d = [b["end"][i] - b["start"][i] for i in range(3)]
        n = math.sqrt(sum(c * c for c in d)) or 1.0
        dirs.add(tuple(round(abs(c / n), 3) for c in d))
    if len(dirs) >= 2 and not feats.get("reliefs"):
        return [{"bends": len(bends)}]
    return []


def flat_pattern_present(
    part: Part, feats: dict[str, Any], params: dict[str, Any], product: Product
) -> list[Violation]:
    """Sheet-metal parts should carry a flat pattern."""
    return [] if feats.get("_has_flat_pattern") else [{"uri": part.uri}]


def custom_part_complete(
    part: Part, feats: dict[str, Any], params: dict[str, Any], product: Product
) -> list[Violation]:
    """process, material, finish, tolerance_class on custom parts."""
    if part.kind != "custom":
        return []
    missing = [
        k
        for k, v in (
            ("process", part.process != "none"),
            ("material", part.material is not None),
            ("finish", bool(part.finish)),
            ("tolerance_class", part.tolerance_class is not None),
        )
        if not v
    ]
    return [{"uri": part.uri, "missing": ", ".join(missing)}] if missing else []


def part_in_assembly(
    part: Part, feats: dict[str, Any], params: dict[str, Any], product: Product
) -> list[Violation]:
    """Orphan parts are flagged."""
    if not product.assemblies:
        return []
    used = {c.uri for a in product.assemblies.values() for c in a.children}
    return [] if part.uri in used else [{"uri": part.uri}]


def cots_has_source(
    part: Part, feats: dict[str, Any], params: dict[str, Any], product: Product
) -> list[Violation]:
    """COTS parts need vendor, mpn, url."""
    if part.kind != "cots":
        return []
    if part.source is None or not part.source.vendor or not part.source.mpn or not part.source.url:
        return [{"uri": part.uri}]
    return []


def cots_source_verified(
    part: Part, feats: dict[str, Any], params: dict[str, Any], product: Product
) -> list[Violation]:
    """Unverified vendor links warn."""
    if part.kind != "cots" or part.source is None:
        return []
    return [] if part.source.verified else [{"uri": part.uri}]


CHECKS: dict[str, CheckFn] = {
    "min_bend_radius": min_bend_radius,
    "min_hole_diameter": min_hole_diameter,
    "hole_to_bend": hole_to_bend,
    "min_flange": min_flange,
    "relief_present": relief_present,
    "flat_pattern_present": flat_pattern_present,
    "custom_part_complete": custom_part_complete,
    "part_in_assembly": part_in_assembly,
    "cots_has_source": cots_has_source,
    "cots_source_verified": cots_source_verified,
}
