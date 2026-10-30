"""Assemblies: placements, instance counting, GLB with named nodes, renders (D13, D18).

An assembly module exposes ``build(P, I, parts) -> AssemblyResult`` and places built
parts (and built sub-assemblies) with :func:`place`.  The checker later verifies that
the instance count per part equals the YAML quantities.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from napkin2factory.geometry.glb import GlbGroup, GlbInstance, GlbMesh, write_glb
from napkin2factory.geometry.render import Mesh, Scene, color_for

Vec3 = tuple[float, float, float]
Quat = tuple[float, float, float, float]


@dataclass
class Placement:
    """One placed occurrence of a part or sub-assembly."""

    uri: str
    built: Any  # BuiltPart or BuiltAssembly
    location: Any  # build123d Location
    label: str | None = None

    @property
    def is_assembly(self) -> bool:
        """True for a sub-assembly placement."""
        return self.uri.startswith("asm://")


@dataclass
class AssemblyResult:
    """What an assembly module returns: placements in the assembly frame."""

    instances: list[Placement] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def add(self, placement: Placement) -> Placement:
        """Append and return a placement (fluent helper)."""
        self.instances.append(placement)
        return placement


def _location(
    location: Any = None, translate: Vec3 | None = None, rotate: Vec3 | None = None
) -> Any:
    from build123d import Location

    if location is not None:
        return location
    t = translate or (0.0, 0.0, 0.0)
    r = rotate or (0.0, 0.0, 0.0)
    return Location(t, r)


def place(
    uri: str,
    built: Any,
    location: Any = None,
    *,
    translate: Vec3 | None = None,
    rotate: Vec3 | None = None,
    label: str | None = None,
) -> Placement:
    """Place ``built`` (a BuiltPart or BuiltAssembly) at a build123d ``Location``.

    Either pass ``location`` or ``translate=(x, y, z)`` with an optional ``rotate``
    (Euler XYZ, degrees).
    """
    return Placement(
        uri=uri, built=built, location=_location(location, translate, rotate), label=label
    )


def grid(
    uri: str,
    built: Any,
    origin: Vec3,
    step: Vec3,
    counts: tuple[int, int, int],
    rotate: Vec3 | None = None,
) -> list[Placement]:
    """Place a rectangular grid of instances (brick courses, fastener rows)."""
    out: list[Placement] = []
    for i in range(counts[0]):
        for j in range(counts[1]):
            for k in range(counts[2]):
                t = (origin[0] + step[0] * i, origin[1] + step[1] * j, origin[2] + step[2] * k)
                out.append(place(uri, built, translate=t, rotate=rotate))
    return out


def location_to_trs(location: Any) -> tuple[Vec3, Quat]:
    """build123d Location → (translation, quaternion xyzw)."""
    trsf = location.wrapped.Transformation()
    t = trsf.TranslationPart()
    q = trsf.GetRotation()
    return (float(t.X()), float(t.Y()), float(t.Z())), (
        float(q.X()),
        float(q.Y()),
        float(q.Z()),
        float(q.W()),
    )


def transform_points(points: NDArray[np.float64], location: Any) -> NDArray[np.float64]:
    """Apply a build123d Location to an (n,3) array."""
    trsf = location.wrapped.Transformation()
    m = np.eye(4)
    for r in range(3):
        for c in range(4):
            m[r, c] = trsf.Value(r + 1, c + 1)
    homo = np.hstack([points, np.ones((len(points), 1))])
    return (homo @ m.T)[:, :3]


@dataclass
class FlatInstance:
    """A leaf occurrence with its world transform, used for GLB, renders and checks."""

    node: str  # part://x#n
    uri: str  # part://x
    location: Any  # world Location
    parent: str | None  # asm://y#m group node, or None at the top level
    built: Any


def flatten(result: AssemblyResult, top_uri: str) -> tuple[list[FlatInstance], list[GlbGroup]]:
    """Resolve nested placements into world-space leaf instances and group nodes.

    Instance numbering is global per part URI within the top-level assembly
    (``part://brick#1`` … ``part://brick#26``), which is what the viewer and the BOM use.
    """
    counters: Counter[str] = Counter()
    pending: list[
        tuple[str, Any, str | None, Any, str | None]
    ] = []  # uri, world, parent, built, label
    groups: list[GlbGroup] = []

    def walk(res: AssemblyResult, parent_loc: Any, parent_node: str | None) -> None:
        for p in res.instances:
            world = parent_loc * p.location if parent_loc is not None else p.location
            if p.is_assembly:
                counters[p.uri] += 1
                node = f"{p.uri}#{counters[p.uri]}"
                t, q = location_to_trs(p.location)
                groups.append(GlbGroup(name=node, translation=t, rotation=q, parent=parent_node))
                walk(p.built.result, world, node)
            else:
                pending.append((p.uri, world, parent_node, p.built, p.label))

    walk(result, None, None)

    # Stable numbering (gate-1 B5): by label when given, else by rounded world transform,
    # so reordering the placement code does not renumber physical occurrences.
    def sort_key(item: tuple[str, Any, str | None, Any, str | None]) -> tuple[Any, ...]:
        uri, world, parent, _built, label = item
        t, q = location_to_trs(world)
        return (
            uri,
            label or "~",
            tuple(round(v, 3) for v in t),
            tuple(round(v, 4) for v in q),
            parent or "",
        )

    leaves: list[FlatInstance] = []
    leaf_counter: Counter[str] = Counter()
    for uri, world, parent, built, _label in sorted(pending, key=sort_key):
        leaf_counter[uri] += 1
        leaves.append(FlatInstance(f"{uri}#{leaf_counter[uri]}", uri, world, parent, built))
    return leaves, groups


def instance_counts(leaves: list[FlatInstance]) -> dict[str, int]:
    """Occurrences per part URI."""
    return dict(sorted(Counter(leaf.uri for leaf in leaves).items()))


def export_assembly_glb(
    top_uri: str, leaves: list[FlatInstance], groups: list[GlbGroup], path: Path
) -> Path:
    """One mesh per part URI, one node per occurrence with its *local* transform (D13)."""
    meshes: dict[str, GlbMesh] = {}
    instances: list[GlbInstance] = []
    # Local transform relative to the parent group: recompute from placements by walking
    # again would need the tree; instead store world transforms and put every leaf under the
    # root group of its parent chain with the parent's inverse applied.
    group_world: dict[str, Any] = {}
    from build123d import Location

    for g in groups:
        loc = Location(g.translation, (0, 0, 0))
        # rotation from quaternion
        from OCP.gp import gp_Quaternion, gp_Trsf, gp_Vec

        trsf = gp_Trsf()
        trsf.SetRotation(gp_Quaternion(*g.rotation))
        trsf.SetTranslationPart(gp_Vec(*g.translation))
        loc = Location(trsf)
        parent_world = group_world.get(g.parent) if g.parent else None
        group_world[g.name] = parent_world * loc if parent_world is not None else loc
    for leaf in leaves:
        if leaf.uri not in meshes:
            v, t = leaf.built.tess
            meshes[leaf.uri] = GlbMesh(
                leaf.uri, v.astype(np.float32), t.astype(np.uint32), color_for(leaf.uri)
            )
        local = leaf.location
        if leaf.parent is not None:
            local = group_world[leaf.parent].inverse() * leaf.location
        tr, q = location_to_trs(local)
        instances.append(
            GlbInstance(leaf.node, leaf.uri, translation=tr, rotation=q, parent=leaf.parent)
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(write_glb(list(meshes.values()), instances, groups, scene_name=top_uri))
    return path


def scene_for_assembly(leaves: list[FlatInstance]) -> Scene:
    """World-space meshes coloured per part URI."""
    scene = Scene()
    for leaf in leaves:
        v, t = leaf.built.tess
        scene.meshes.append(
            Mesh(transform_points(v, leaf.location), t, color_for(leaf.uri), leaf.node)
        )
    return scene


def assembly_props(leaves: list[FlatInstance]) -> dict[str, Any]:
    """bbox, mass, volume, centroid and instance counts over all leaves."""
    if not leaves:
        return {
            "bbox": {"x": 0, "y": 0, "z": 0, "min": [0, 0, 0], "max": [0, 0, 0]},
            "mass": 0.0,
            "volume": 0.0,
            "instance_counts": {},
            "instances": 0,
        }
    pts = np.vstack([transform_points(leaf.built.tess[0], leaf.location) for leaf in leaves])
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    mass = 0.0
    volume = 0.0
    cx = np.zeros(3)
    for leaf in leaves:
        m = float(leaf.built.props["mass"])
        c = leaf.built.props["centroid"]
        wc = transform_points(np.asarray([[c["x"], c["y"], c["z"]]]), leaf.location)[0]
        mass += m
        volume += float(leaf.built.props["volume"])
        cx += m * wc
    centroid = (cx / mass) if mass > 0 else (lo + hi) / 2
    return {
        "bbox": {
            "x": round(float(hi[0] - lo[0]), 4),
            "y": round(float(hi[1] - lo[1]), 4),
            "z": round(float(hi[2] - lo[2]), 4),
            "min": [round(float(x), 4) for x in lo],
            "max": [round(float(x), 4) for x in hi],
        },
        "mass": round(mass, 6),
        "volume": round(volume, 3),
        "centroid": {
            "x": round(float(centroid[0]), 4),
            "y": round(float(centroid[1]), 4),
            "z": round(float(centroid[2]), 4),
        },
        "instance_counts": instance_counts(leaves),
        "instances": len(leaves),
        "units": {"length": "mm", "volume": "mm**3", "mass": "kg"},
    }
