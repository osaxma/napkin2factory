"""Assemblies: placements, instance counting, GLB with named nodes, renders (D13, D18).

An assembly module exposes ``build(P, I, parts) -> AssemblyResult`` and places built
parts by their interfaces with :func:`place_by` (P1), or by coordinates with :func:`place`
when a part has no interface with anything already placed.  The checker later verifies that
the instance count per part equals the YAML quantities and that every interface's frames
meet (P3).
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


COORDINATES = "coordinates"


@dataclass
class Placement:
    """One placed occurrence of a part or sub-assembly.

    ``via`` says how it was placed: ``"coordinates"`` (:func:`place`) or ``"iface://<id>"``
    (:func:`place_by`).  It is kept in ``instances.json`` so ``n2f check`` can warn about a
    part placed by coordinates although an interface could place it (P1, S-106).
    """

    uri: str
    built: Any  # BuiltPart or BuiltAssembly
    location: Any  # build123d Location
    label: str | None = None
    via: str = COORDINATES

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


@dataclass
class _Occurrence:
    """A party's occurrence that ``place_by`` can use: its location and the labels naming it."""

    location: Any  # in the frame of the assembly being built (or of the sub-assembly moved)
    labels: tuple[str | None, ...]  # the placement's label, then the leaf's inside a sub-assembly

    @property
    def name(self) -> str:
        """The labels joined for an error message (``'door/left'``)."""
        return "/".join(lab for lab in self.labels if lab is not None) or "no label"


def _leaf_occurrences(
    built: Any, uri: str, outer: Any = None, label: str | None = None
) -> list[_Occurrence]:
    """Occurrences of part ``uri`` among a built sub-assembly's leaves (its own frame).

    ``outer`` (the sub-assembly's placement location) moves them into the parent's frame.
    A stand-in without ``leaves`` has none.
    """
    out = []
    for leaf in getattr(built, "leaves", None) or []:
        if leaf.uri == uri:
            loc = outer * leaf.location if outer is not None else leaf.location
            labels = (label, leaf.label) if outer is not None else (leaf.label,)
            out.append(_Occurrence(loc, labels))
    return out


def _pick(
    found: list[_Occurrence], label: str | None, what: str, keyword: str, where: str
) -> _Occurrence:
    """The one occurrence named by ``label`` (any of its labels), or a ``GeometryError``."""
    from napkin2factory.geometry.build import GeometryError

    chosen = [o for o in found if label in o.labels] if label is not None else found
    names = ", ".join(repr(o.name) for o in found) or "none"
    if not chosen:
        raise GeometryError(
            f"place_by: no occurrence of {what} is labelled {label!r}; its labels: {names}"
        )
    if len(chosen) > 1:
        raise GeometryError(
            f"place_by: {what} is placed {len(chosen)} times{where}; pick one with "
            f"{keyword}=<label> (its labels: {names})"
        )
    return chosen[0]


def place_by(
    I: Any,  # noqa: N803 — the recording interface accessor of the assembly module
    res: AssemblyResult,
    iface_id: str,
    uri: str,
    built: Any,
    *,
    onto: str | None = None,
    label: str | None = None,
    inner: str | None = None,
) -> Placement:
    """Place a part, or a sub-assembly by one of its ports, so the interface's frames meet (P1, P4).

    The other party must already be placed in ``res``, directly or as a leaf of a
    sub-assembly placed in ``res`` (two modules joined by a port each side).  The child is
    rotated so its frame's normal and ``x_axis`` point the same way as the placed party's
    frame, and moved so its frame origin sits ``offset`` along that normal from the placed
    party's origin: ``+offset`` when the placed party is the interface's first party,
    ``-offset`` when the child is (``offset`` runs from the first party to the second, P2).
    The basis is :func:`napkin2factory.core.frames.frame_basis`, the one the holes are cut
    with.

    When ``uri`` is a sub-assembly (``"asm://door"``), the party being placed is the
    interface's party found among its leaves (``built.leaves``, in the sub-assembly's own
    frame, also when it was reloaded from disk, S-049); the whole sub-assembly moves with it.

    Args:
        I: the ``I`` accessor passed to ``build(P, I, parts)`` (records the interface read).
        res: the assembly result holding the placed party.
        iface_id: the interface id (without ``iface://``).
        uri: the part to place (one of the parties), or the sub-assembly holding one.
        built: the built part or sub-assembly (``parts["lid"]``, ``parts["door"]``).
        onto: the label of the occurrence to place onto, when the other party is placed
            more than once; inside a placed sub-assembly, either its label or the leaf's.
        label: this occurrence's label.
        inner: for a sub-assembly, the label of the party's leaf inside it, when the party
            occurs there more than once.

    Returns:
        The placement (not yet added: wrap it in ``res.add(...)``).

    Raises:
        GeometryError: when ``uri`` is not a party (nor holds exactly one), the other party
            is absent or ambiguous in ``res``, or a frame used has no ``x_axis``; each
            message says the fix.
    """
    from napkin2factory.core.frames import frame_basis
    from napkin2factory.geometry.build import GeometryError

    iface = I[iface_id]
    where = f"iface://{iface_id}"
    parties = [str(p) for p in iface.parties]
    for party in parties:
        if not party.startswith("part://"):
            raise GeometryError(
                f"place_by: {where} names {party}; an interface joins two parts, and a "
                "sub-assembly exports a joint of one of its parts under `ports:`"
            )
    inner_loc: Any = None
    if uri.startswith("asm://"):
        inside = [p for p in parties if _leaf_occurrences(built, p)]
        if len(inside) != 1:
            why = "both of its parties are" if inside else "neither of its parties is"
            raise GeometryError(
                f"place_by: {uri} cannot be placed by {where}: {why} inside it; place a "
                "sub-assembly by a port, a joint between one of its parts and a part outside it"
            )
        party = inside[0]
        leaf = _pick(_leaf_occurrences(built, party), inner, party, "inner", f" inside {uri}")
        inner_loc = leaf.location
    elif uri in parties:
        party = uri
    else:
        raise GeometryError(
            f"place_by: {uri} is not a party of {where} (its parties are {', '.join(parties)}); "
            "place it with the interface that joins it, or with place(...)"
        )
    other = parties[1] if parties[0] == party else parties[0]
    found: list[_Occurrence] = []
    for p in res.instances:
        if p.uri == other:
            found.append(_Occurrence(p.location, (p.label,)))
        elif p.is_assembly:
            found.extend(_leaf_occurrences(p.built, other, p.location, p.label))
    if not found:
        raise GeometryError(
            f"place_by: {party} joins {other} through {where}, but {other} is not placed yet; "
            f"place {other} first (placement order matters)"
        )
    anchor = _pick(found, onto, other, "onto", "")
    frames = {}
    for pty in (party, other):
        frame = iface.frame_for(pty)
        if frame.x_axis is None:
            _, x, _, _ = frame_basis(frame)
            hint = [round(c, 6) + 0.0 for c in x]
            raise GeometryError(
                f"place_by: the frame of {pty} in {where} has no x_axis, so its rotation "
                f"about the normal is undefined; add `x_axis: {hint}` to that frame in "
                f"model/interfaces/{iface_id}.yaml (the axis its holes are cut along today)"
            )
        frames[pty] = frame_basis(frame)
    sign = 1.0 if parties[0] == other else -1.0
    offset = sign * float(iface.offset)
    o_a, x_a, y_a, z_a = frames[other]
    o_b, x_b, y_b, z_b = frames[party]
    m_anchor = _matrix(anchor.location)
    r_anchor, t_anchor = m_anchor[:3, :3], m_anchor[:3, 3]
    basis_a = r_anchor @ np.column_stack([x_a, y_a, z_a])  # the placed frame, assembly coords
    origin_a = r_anchor @ np.asarray(o_a) + t_anchor
    rot = basis_a @ np.column_stack([x_b, y_b, z_b]).T
    target = origin_a + offset * basis_a[:, 2]
    trans = target - rot @ np.asarray(o_b)
    if inner_loc is not None:
        # the party's leaf sits at inner_loc in the sub-assembly: place the sub-assembly so
        # that leaf lands where the party must go (sub = party · inner⁻¹)
        m = np.eye(4)
        m[:3, :3], m[:3, 3] = rot, trans
        m = m @ np.linalg.inv(_matrix(inner_loc))
        rot, trans = m[:3, :3], m[:3, 3]
    return Placement(
        uri=uri, built=built, location=_from_matrix(rot, trans), label=label, via=where
    )


def _matrix(location: Any) -> NDArray[np.float64]:
    """4×4 homogeneous matrix of a build123d Location."""
    trsf = location.wrapped.Transformation()
    m = np.eye(4)
    for r in range(3):
        for c in range(4):
            m[r, c] = trsf.Value(r + 1, c + 1)
    return m


def _from_matrix(rot: NDArray[np.float64], trans: NDArray[np.float64]) -> Any:
    """A build123d Location from a rotation matrix and a translation.

    Rotation entries within 1e-12 of 0 or ±1 and translations within 1e-9 mm of 0 are
    snapped (no ``-0.0``), so a placement computed through the frames writes the same
    ``instances.json`` as the same rotation and offset typed by hand (S-106).
    """
    from build123d import Location
    from OCP.gp import gp_Mat, gp_Quaternion, gp_Trsf, gp_Vec

    r = np.where(np.abs(rot) < 1e-12, 0.0, rot)
    r = np.where(np.abs(np.abs(r) - 1.0) < 1e-12, np.sign(r), r)
    trsf = gp_Trsf()
    trsf.SetRotation(gp_Quaternion(gp_Mat(*(float(v) for v in r.reshape(-1)))))
    t = np.where(np.abs(trans) < 1e-9, 0.0, trans)
    trsf.SetTranslationPart(gp_Vec(*(float(v) for v in t)))
    return Location(trsf)


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
    m = _matrix(location)
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
    label: str | None = None
    via: str = COORDINATES  # how it was placed (P1); a nested leaf keeps its own


def flatten(result: AssemblyResult, top_uri: str) -> tuple[list[FlatInstance], list[GlbGroup]]:
    """Resolve nested placements into world-space leaf instances and group nodes.

    Instance numbering is global per part URI within the top-level assembly
    (``part://brick#1`` … ``part://brick#26``), which is what the viewer and the BOM use.
    """
    counters: Counter[str] = Counter()
    pending: list[tuple[str, Any, str | None, Any, Placement]] = []
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
                pending.append((p.uri, world, parent_node, p.built, p))

    walk(result, None, None)

    # Stable numbering (gate-1 B5): by label when given, else by rounded world transform,
    # so reordering the placement code does not renumber physical occurrences.
    def sort_key(item: tuple[str, Any, str | None, Any, Placement]) -> tuple[Any, ...]:
        uri, world, parent, _built, placement = item
        label = placement.label
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
    for uri, world, parent, built, placement in sorted(pending, key=sort_key):
        leaf_counter[uri] += 1
        leaves.append(
            FlatInstance(
                f"{uri}#{leaf_counter[uri]}",
                uri,
                world,
                parent,
                built,
                label=placement.label,
                via=placement.via,
            )
        )
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


def exploded_scene(
    leaves: list[FlatInstance], groups: list[GlbGroup], axis: str, spacing: float
) -> Scene:
    """The assembly pulled apart as the report's viewer does at full explode (P8 sheets).

    Each top-level occurrence (a part, or a whole sub-assembly) moves along ``axis`` by
    ``spacing`` times its rank, ranked by its position along that axis, so the picture on an
    assembly sheet matches what the owner sees with the viewer's slider at its end.
    """
    k = "xyz".index(axis)
    parent_of = {g.name: g.parent for g in groups}
    base: dict[str, float] = {g.name: g.translation[k] for g in groups if g.parent is None}

    def top_of(leaf: FlatInstance) -> str:
        node = leaf.parent
        if node is None:
            return leaf.node
        while parent_of.get(node) is not None:
            node = parent_of[node] or node
        return node

    for leaf in leaves:
        if leaf.parent is None:
            base[leaf.node] = location_to_trs(leaf.location)[0][k]
    rank = {name: i for i, name in enumerate(sorted(base, key=lambda n: (base[n], n)))}
    scene = Scene()
    for leaf in leaves:
        v, t = leaf.built.tess
        pts = transform_points(v, leaf.location)
        shift = np.zeros(3)
        shift[k] = spacing * rank.get(top_of(leaf), 0)
        scene.meshes.append(Mesh(pts + shift, t, color_for(leaf.uri), leaf.node))
    return scene


def assembly_props(leaves: list[FlatInstance]) -> dict[str, Any]:
    """bbox, mass, volume, centroid and instance counts over all leaves."""
    if not leaves:
        # an empty stub seeded by promotion (P10, S-112) builds with the same keys as any
        # other assembly; `instances: 0` is what the checks read as "nothing to measure yet"
        return {
            "bbox": {"x": 0, "y": 0, "z": 0, "min": [0, 0, 0], "max": [0, 0, 0]},
            "mass": 0.0,
            "volume": 0.0,
            "centroid": {"x": 0.0, "y": 0.0, "z": 0.0},
            "instance_counts": {},
            "instances": 0,
            "units": {"length": "mm", "volume": "mm**3", "mass": "kg"},
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
