"""Single explode resolver for the 3D viewer and the assembly sheets (v0.9 M1, Q2, S-290).

Every top-level unit of an assembly (a part occurrence or a sub-assembly group placed in
the top assembly) gets one :class:`ExplodeMove`: a unit direction vector (or ``(0, 0, 0)``
when declared to stay put), a full-explode distance in mm, and the name of the rule that
chose the direction.

Three architectural seams live here:
1. **Where a new direction rule goes:** :data:`RULES` lists ``(source, fn)`` pairs in
   :data:`SOURCES` priority order; the first rule that returns a vector wins.
2. **Where an un-modelled fastener enters:** :func:`units_of` builds an :class:`ExplodeUnit`
   for every top-level occurrence; a unit with ``has_geometry=False`` passes through
   :func:`resolve` (receiving its direction and the step after the last modelled unit on
   that line without taking a step from modelled units) and is skipped only at drawing time.
3. **One resolver for every output:** ``build_asm`` calls :func:`resolve` once and hands the
   same map to ``export_assembly_glb`` (which writes ``n2f_explode`` on each top-level GLB
   node for the viewer) and to ``exploded_scene`` (which draws the assembly sheet's picture).
   Nothing else computes an explode direction.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from napkin2factory.geometry.assembly import FlatInstance
    from napkin2factory.geometry.glb import GlbGroup

Vec = tuple[float, float, float]

SOURCES: tuple[str, ...] = ("declared", "interface", "fallback")
"""Priority order of direction rules; the first rule in :data:`RULES` that answers wins."""


@dataclass(frozen=True)
class ExplodeUnit:
    """One top-level occurrence in an assembly to be resolved for the exploded view."""

    node: str
    uri: str
    label: str | None = None
    away: Vec | None = None
    centre: Vec | None = None
    has_geometry: bool = True


@dataclass(frozen=True)
class ExplodeMove:
    """Resolved explode motion of one top-level unit at slider factor 1."""

    direction: Vec
    distance: float
    source: str


@dataclass(frozen=True)
class ExplodeContext:
    """Assembly-wide inputs shared across the direction rules."""

    assembly_centre: Vec = (0.0, 0.0, 0.0)
    declared: Mapping[str, Sequence[float]] = field(default_factory=dict)


def _clean_zero(x: float) -> float:
    return 0.0 if abs(x) < 1e-12 else float(x)


def _normalize(v: Sequence[float]) -> Vec | None:
    """Return ``v`` as a unit :data:`Vec`, or ``None`` if its length is near zero."""
    x, y, z = float(v[0]), float(v[1]), float(v[2])
    norm = math.hypot(x, y, z)
    if norm < 1e-12:
        return None
    return (_clean_zero(x / norm), _clean_zero(y / norm), _clean_zero(z / norm))


def _round_vec(v: Vec) -> Vec:
    """Round a direction to 6 decimal places (without ``-0.0``) for direction-line grouping."""
    return (
        round(_clean_zero(v[0]), 6) + 0.0,
        round(_clean_zero(v[1]), 6) + 0.0,
        round(_clean_zero(v[2]), 6) + 0.0,
    )


def _is_zero(v: Vec) -> bool:
    return math.hypot(v[0], v[1], v[2]) < 1e-12


def _rule_declared(unit: ExplodeUnit, ctx: ExplodeContext) -> Vec | None:
    """Owner-declared direction by occurrence label first, then by part/assembly URI."""
    raw: Sequence[float] | None = None
    if unit.label is not None and unit.label in ctx.declared:
        raw = ctx.declared[unit.label]
    elif unit.uri in ctx.declared:
        raw = ctx.declared[unit.uri]
    if raw is None:
        return None
    normed = _normalize(raw)
    return (0.0, 0.0, 0.0) if normed is None else normed


def _rule_interface(unit: ExplodeUnit, _ctx: ExplodeContext) -> Vec | None:
    """Direction the unit was pushed into place by ``place_by``, normalised."""
    if unit.away is None:
        return None
    return _normalize(unit.away)


def _rule_fallback(unit: ExplodeUnit, ctx: ExplodeContext) -> Vec:
    """Outward along the dominant axis of ``centre - assembly_centre`` (+Z when centred/absent)."""
    if unit.centre is None:
        return (0.0, 0.0, 1.0)
    diffs = (
        unit.centre[0] - ctx.assembly_centre[0],
        unit.centre[1] - ctx.assembly_centre[1],
        unit.centre[2] - ctx.assembly_centre[2],
    )
    k = max(range(3), key=lambda i: abs(diffs[i]))
    if abs(diffs[k]) < 1e-6:
        return (0.0, 0.0, 1.0)
    sign = 1.0 if diffs[k] >= 0.0 else -1.0
    out = [0.0, 0.0, 0.0]
    out[k] = sign
    return (out[0], out[1], out[2])


Rule = Callable[[ExplodeUnit, ExplodeContext], Vec | None]

RULES: tuple[tuple[str, Rule], ...] = (
    ("declared", _rule_declared),
    ("interface", _rule_interface),
    ("fallback", _rule_fallback),
)
"""Ordered ``(source, rule)`` table evaluated by :func:`resolve`."""


def _projection(unit: ExplodeUnit, assembly_centre: Vec, direction: Vec) -> float:
    """Position of ``unit.centre`` along ``direction`` relative to ``assembly_centre``."""
    if unit.centre is None:
        return 0.0
    return round(
        (unit.centre[0] - assembly_centre[0]) * direction[0]
        + (unit.centre[1] - assembly_centre[1]) * direction[1]
        + (unit.centre[2] - assembly_centre[2]) * direction[2],
        6,
    )


def resolve(
    units: Sequence[ExplodeUnit],
    assembly_centre: Vec = (0.0, 0.0, 0.0),
    spacing_mm: float = 80.0,
    declared: Mapping[str, Sequence[float]] | None = None,
) -> dict[str, ExplodeMove]:
    """Resolve the explode direction, distance and source for every top-level unit.

    Every unit receives a move, including units with ``has_geometry=False``.  Units with
    geometry that share the same rounded direction are ordered along that direction (nearest
    to ``assembly_centre`` first) and assigned steps ``1, 2, …`` with
    ``distance = spacing_mm * step``.  A zero direction stays put (``distance = 0.0``) and
    takes no step; a geometry-less unit takes no step from modelled units and receives the
    step it would have after the last modelled unit on its direction line.
    """
    ctx = ExplodeContext(assembly_centre=assembly_centre, declared=declared or {})
    picked: list[tuple[ExplodeUnit, Vec, str]] = []
    geom_by_dir: dict[Vec, list[ExplodeUnit]] = defaultdict(list)

    for unit in units:
        chosen_dir: Vec = (0.0, 0.0, 1.0)
        chosen_source = "fallback"
        for source, rule in RULES:
            ans = rule(unit, ctx)
            if ans is not None:
                chosen_dir = ans
                chosen_source = source
                break
        picked.append((unit, chosen_dir, chosen_source))
        if unit.has_geometry and not _is_zero(chosen_dir):
            geom_by_dir[_round_vec(chosen_dir)].append(unit)

    step_of: dict[str, int] = {}
    for dir_key, group in geom_by_dir.items():
        ordered = sorted(group, key=lambda u: _projection(u, assembly_centre, dir_key))
        for idx, u in enumerate(ordered, start=1):
            step_of[u.node] = idx

    moves: dict[str, ExplodeMove] = {}
    for unit, chosen_dir, chosen_source in picked:
        if _is_zero(chosen_dir):
            dist = 0.0
        elif unit.has_geometry:
            dist = float(spacing_mm) * step_of[unit.node]
        else:
            after_last = len(geom_by_dir.get(_round_vec(chosen_dir), ())) + 1
            dist = float(spacing_mm) * after_last
        moves[unit.node] = ExplodeMove(
            direction=chosen_dir,
            distance=dist,
            source=chosen_source,
        )
    return moves


def _leaf_points(leaf: FlatInstance) -> np.ndarray | None:
    """World-space vertices of ``leaf``, or ``None`` when the leaf has no geometry."""
    from napkin2factory.geometry.assembly import transform_points

    tess = getattr(leaf.built, "tess", None)
    if tess is None or len(tess[0]) == 0:
        return None
    return transform_points(tess[0], leaf.location)


def _bbox_centre(pts: np.ndarray) -> Vec:
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    c = (lo + hi) / 2.0
    return (float(c[0]), float(c[1]), float(c[2]))


def assembly_centre(leaves: Sequence[FlatInstance]) -> Vec:
    """Centre of the bounding box over all leaves with geometry, or ``(0, 0, 0)``."""
    arrays = [pts for leaf in leaves if (pts := _leaf_points(leaf)) is not None]
    if not arrays:
        return (0.0, 0.0, 0.0)
    return _bbox_centre(np.vstack(arrays))


def units_of(
    leaves: Sequence[FlatInstance],
    groups: Sequence[GlbGroup] = (),
) -> list[ExplodeUnit]:
    """Build :class:`ExplodeUnit` records for the top-level occurrences of ``flatten()``."""
    parent_of = {g.name: g.parent for g in groups}

    def top_of(leaf: FlatInstance) -> str:
        node = leaf.parent
        if node is None:
            return leaf.node
        while parent_of.get(node) is not None:
            node = parent_of[node] or node
        return node

    group_pts: dict[str, list[np.ndarray]] = defaultdict(list)
    for leaf in leaves:
        if leaf.parent is not None:
            pts = _leaf_points(leaf)
            if pts is not None:
                group_pts[top_of(leaf)].append(pts)

    out: list[ExplodeUnit] = []
    for g in groups:
        if g.parent is not None:
            continue
        arrays = group_pts.get(g.name, [])
        has_geom = bool(arrays)
        centre = _bbox_centre(np.vstack(arrays)) if has_geom else None
        out.append(
            ExplodeUnit(
                node=g.name,
                uri=g.name.split("#")[0],
                label=g.label,
                away=g.away,
                centre=centre,
                has_geometry=has_geom,
            )
        )
    for leaf in leaves:
        if leaf.parent is not None:
            continue
        pts = _leaf_points(leaf)
        has_geom = pts is not None
        centre = _bbox_centre(pts) if pts is not None else None
        out.append(
            ExplodeUnit(
                node=leaf.node,
                uri=leaf.uri,
                label=leaf.label,
                away=leaf.away,
                centre=centre,
                has_geometry=has_geom,
            )
        )
    return out


__all__ = [
    "ExplodeContext",
    "ExplodeMove",
    "ExplodeUnit",
    "RULES",
    "SOURCES",
    "Vec",
    "assembly_centre",
    "resolve",
    "units_of",
]
