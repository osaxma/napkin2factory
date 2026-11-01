"""Interface conformance (D16) in two stages, plus the coordinate-placement warning (P1).

1. **Patterns**: both parties recorded the same pattern in their own interface frames.
2. **Alignment** (P3): placed in the lowest assembly that contains both parties, the two
   frames meet: origin plus ``offset`` along the normal, the same normal and the same
   ``x_axis``.  Without it a part moved 10 mm in the assembly code passed stage 1.

The world frames use :func:`napkin2factory.core.frames.frame_basis`, the basis the holes
are cut with and ``place_by`` places with.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from napkin2factory.core.checks.results import CheckResult
from napkin2factory.core.frames import WorldFrame, add_scaled, angle_deg, length, sub, world_frame
from napkin2factory.core.loader import Product
from napkin2factory.core.model import BoltPatternSpec, Interface
from napkin2factory.core.tree import AssemblyTree

TOLERANCE_MM = 0.5
# P3 alignment tolerances: a design choice (PRODUCT_STRUCTURE.md P3, S-106), not a measured
# fit. Loose enough for float noise and rounded instance transforms, tight enough that a part
# moved by a few millimetres or turned by a degree fails.
ALIGN_MM = 0.5
ALIGN_DEG = 0.5


@dataclass
class InterfaceReport:
    """Outcome and evidence of one interface check."""

    status: str = "pass"
    message: str = ""
    parties: dict[str, Any] = field(default_factory=dict)
    alignment: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """JSON form."""
        return dict(self.__dict__)


def _basis(
    normal: list[float], x_axis: list[float] | None
) -> tuple[list[float], list[float], list[float]]:
    n = _norm(normal)
    if x_axis is not None:
        x = _norm(x_axis)
    else:
        ref = [1.0, 0.0, 0.0] if abs(n[0]) < 0.9 else [0.0, 1.0, 0.0]
        x = _norm(_cross(ref, n))
        x = _norm(_cross(n, x))  # deterministic in-plane axis
    y = _cross(n, x)
    return x, y, n


def _norm(v: list[float]) -> list[float]:
    m = math.sqrt(sum(c * c for c in v)) or 1.0
    return [c / m for c in v]


def _cross(a: list[float], b: list[float]) -> list[float]:
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _local_2d(
    centers: list[list[float]], origin: list[float], normal: list[float], x_axis: list[float] | None
) -> list[tuple[float, float]]:
    x, y, _ = _basis(normal, x_axis)
    out = []
    for c in centers:
        d = [c[i] - origin[i] for i in range(3)]
        out.append(
            (
                round(sum(d[i] * x[i] for i in range(3)), 3),
                round(sum(d[i] * y[i] for i in range(3)), 3),
            )
        )
    return sorted(out)


def _match(a: list[tuple[float, float]], b: list[tuple[float, float]], tol: float) -> bool:
    if len(a) != len(b):
        return False
    remaining = list(b)
    for p in a:
        hit = next(
            (q for q in remaining if abs(p[0] - q[0]) <= tol and abs(p[1] - q[1]) <= tol), None
        )
        if hit is None:
            return False
        remaining.remove(hit)
    return True


# ---- owner words (N5, D17; gate D, S-118) ----------------------------------------------
# The message is what an owner reads in `n2f check`, `n2f status` and the report: parts by
# name, the joint by its name, distances with what is allowed and what to do.  Ids, angles,
# offsets and coordinates stay in the row's detail (``--json``).


def _name(product: Product, uri: str) -> str:
    """A part or assembly by name (the uri when unknown)."""
    if uri.startswith("asm://"):
        asm = product.assemblies.get(uri.removeprefix("asm://"))
        return asm.name if asm is not None else uri
    part = product.parts.get(uri.removeprefix("part://").split("#", 1)[0])
    return part.name if part is not None else uri


def lower_name(name: str) -> str:
    """A name inside a sentence: "Mini electric test kiln" → "mini electric test kiln".

    An acronym or a mixed-case word ("PID controller") keeps its capitals.
    """
    if len(name) > 1 and name[0].isupper() and not name[1].isupper():
        return name[0].lower() + name[1:]
    return name


def _joint_at(iface: Interface) -> str:
    """Where two parts meet, said: 'at their joint "Shell to guard, top wall"'."""
    return f'at their joint "{iface.name}"' if iface.name else "at their joint"


def _assembled(product: Product, aids: list[str]) -> str:
    """Say "the assembled mini electric test kiln" (several: joined with "and")."""
    names = [lower_name(_name(product, f"asm://{a}")) for a in aids]
    return "the assembled " + (
        names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    )


def _within(worst: float) -> str:
    """The worst miss rounded up to 0.01 mm, never below it: "within 0.01 mm"."""
    return f"within {max(math.ceil(round(worst * 100, 6)) / 100, 0.01):.2f} mm"


def check_interface(product: Product, iface: Interface, build_dir: Path) -> InterfaceReport:
    """Compare the parties' recorded patterns (bolt-pattern) or face records (mating-face)."""
    from napkin2factory.geometry.accessors import resolve_interface

    iface = resolve_interface(product, iface)
    rep = InterfaceReport()
    patterns: dict[str, Any] = {}
    for party in iface.parties:
        pid = party.id
        if party.scheme != "part":
            # the loader refuses an asm:// party (P4, S-107); kept for a partial load
            rep.parties[str(party)] = {
                "status": "skip",
                "why": "an assembly is not a party: its joints are ports",
            }
            continue
        part = product.parts.get(pid)
        if part is None or not part.has_geometry:
            rep.parties[str(party)] = {"status": "skip", "why": "no geometry (BOM-only part)"}
            continue
        feats_path = build_dir / "parts" / pid / "features.json"
        if not feats_path.is_file():
            rep.status, rep.message = "skip", f"{part.name} has not been built yet"
            return rep
        feats = json.loads(feats_path.read_text(encoding="utf-8"))
        frame = iface.frame_for(str(party))
        if iface.kind == "bolt-pattern":
            pats = [p for p in feats.get("patterns", []) if p.get("interface") == iface.uri]
            if not pats:
                rep.status, rep.message = (
                    "fail",
                    f"{part.name} does not cut the holes {_joint_at(iface)}: its geometry "
                    "must place them from the joint",
                )
                rep.parties[str(party)] = {"status": "fail", "why": "no pattern recorded"}
                continue
            local = _local_2d(pats[0]["centers"], frame.origin, frame.normal, frame.x_axis)
            patterns[str(party)] = {"local": local, "diameter": pats[0]["diameter"]}
            rep.parties[str(party)] = {
                "status": "pass",
                "holes": local,
                "diameter": pats[0]["diameter"],
            }
        else:
            faces = [
                f
                for f in feats.get("extra", {}).get("mating_faces", [])
                if f.get("interface") == iface.uri
            ]
            if not faces:
                rep.status, rep.message = (
                    "fail",
                    f"{part.name} does not record its face {_joint_at(iface)}: its geometry "
                    "must place it from the joint",
                )
                rep.parties[str(party)] = {"status": "fail", "why": "no mating face recorded"}
            else:
                rep.parties[str(party)] = {"status": "pass", "face": faces[0]}
    if rep.status == "fail":
        return rep
    if iface.kind == "bolt-pattern" and len(patterns) == 2:
        (ua, a), (ub, b) = patterns.items()
        na, nb = _name(product, ua), _name(product, ub)
        if not _match(a["local"], b["local"], TOLERANCE_MM):
            # the hole positions of each party are in ``parties`` (``--json``)
            rep.status = "fail"
            rep.message = (
                f"the holes on {na} and {nb} do not match {_joint_at(iface)} "
                f"({TOLERANCE_MM:g} mm allowed): cut both from the joint's pattern"
            )
        elif abs(float(a["diameter"]) - float(b["diameter"])) > TOLERANCE_MM:
            rep.status = "fail"
            rep.message = (
                f"the holes on {na} ({float(a['diameter']):g} mm) and {nb} "
                f"({float(b['diameter']):g} mm) are not the same size {_joint_at(iface)}: "
                "cut both from the joint's pattern"
            )
        else:
            spec = iface.spec
            n = spec.count if isinstance(spec, BoltPatternSpec) else len(a["local"])
            rep.message = f"the {n} holes line up on both parts"
    elif iface.kind == "mating-face":
        # contact between the two is allowed in the interference check (D29)
        rep.message = "the faces touch by design" + (
            "" if iface.hardware_items() else " (no loose fixings)"
        )
    if rep.status == "pass":
        rep.alignment = check_alignment(product, iface, build_dir)
        if rep.alignment["status"] == "fail":
            rep.status = "fail"
            rep.message = rep.alignment["message"]
        elif rep.alignment["status"] == "pass":
            joiner = ", and in " if iface.kind == "bolt-pattern" else "; they meet in "
            rep.message += joiner + rep.alignment["message"]
    return rep


# ---- stage 2: alignment in the assembly (P3) ---------------------------------------------


def lowest_common_assemblies(product: Product, a: str, b: str) -> list[str]:
    """Assemblies containing both parts with no sub-assembly that also contains both (P3).

    Across levels too: a part of the kiln and a part inside its door meet in the kiln, whose
    ``instances.json`` holds the door's leaves in the kiln's frame (S-107).
    """
    return AssemblyTree(product.assemblies).lowest_containing(a, b)


def _occurrences(instances: list[dict[str, Any]], uri: str) -> list[dict[str, Any]]:
    return [i for i in instances if i.get("uri") == uri]


def _compare(iface: Interface, wa: WorldFrame, wb: WorldFrame) -> dict[str, float]:
    """How far the second party's frame is from where the first party's says it should be."""
    target = add_scaled(wa.origin, wa.normal, float(iface.offset))
    return {
        "distance_mm": round(length(sub(wb.origin, target)), 3) + 0.0,
        "normal_deg": round(angle_deg(wa.normal, wb.normal), 2) + 0.0,
        "x_axis_deg": round(angle_deg(wa.x_axis, wb.x_axis), 2) + 0.0,
    }


def _ok(m: dict[str, float]) -> bool:
    return (
        m["distance_mm"] <= ALIGN_MM
        and m["normal_deg"] <= ALIGN_DEG
        and m["x_axis_deg"] <= (ALIGN_DEG)
    )


def _miss_words(m: dict[str, float], kind: str) -> str:
    """How far off, in owner words, each with what is allowed."""
    what = "holes" if kind == "bolt-pattern" else "faces"
    parts = []
    if m["distance_mm"] > ALIGN_MM:
        parts.append(f"their {what} are {m['distance_mm']:.1f} mm apart ({ALIGN_MM:g} mm allowed)")
    if m["normal_deg"] > ALIGN_DEG:
        parts.append(
            f"their faces are turned {m['normal_deg']:.1f}° from each other "
            f"({ALIGN_DEG:g}° allowed)"
        )
    if m["x_axis_deg"] > ALIGN_DEG:
        parts.append(
            f"one is turned {m['x_axis_deg']:.1f}° against the other on the face "
            f"({ALIGN_DEG:g}° allowed)"
        )
    return " and ".join(parts) or "they meet"


def _occurrence_name(product: Product, node: str, instances: list[dict[str, Any]]) -> str:
    """A placed part by name; "no. 2" only when the part is placed more than once there."""
    uri = node.split("#", 1)[0]
    name = _name(product, uri)
    if "#" in node and len(_occurrences(instances, uri)) > 1:
        name += f" no. {node.split('#', 1)[1]}"
    return name


def _siblings(product: Product, iface: Interface) -> list[Interface]:
    """Other interfaces joining the same two parts, resolved (two hinges on one post)."""
    from napkin2factory.geometry.accessors import resolve_interface

    pair = {str(p) for p in iface.parties}
    return [
        resolve_interface(product, other)
        for oid, other in sorted(product.interfaces.items())
        if oid != iface.id
        and {str(p) for p in other.parties} == pair
        and all(str(p) in other.frames for p in other.parties)
    ]


def _pairs(
    iface: Interface, instances: list[dict[str, Any]], a: str, b: str
) -> list[dict[str, Any]]:
    """Every occurrence pair of the two parties, with how far their frames are apart."""
    fa, fb = iface.frame_for(a), iface.frame_for(b)
    occ_a = [
        (i["node"], world_frame(fa, i["translation"], i["rotation"]))
        for i in _occurrences(instances, a)
    ]
    occ_b = [
        (i["node"], world_frame(fb, i["translation"], i["rotation"]))
        for i in _occurrences(instances, b)
    ]
    pairs: list[dict[str, Any]] = []
    for na, wa in occ_a:
        for nb, wb in occ_b:
            m = _compare(iface, wa, wb)
            pairs.append(
                {
                    "occurrences": [na, nb],
                    **m,
                    "meets": _ok(m),
                    "world": {na: wa.to_dict(), nb: wb.to_dict()},
                }
            )
    return pairs


def check_alignment(product: Product, iface: Interface, build_dir: Path) -> dict[str, Any]:
    """Stage 2 (P3): every occurrence of each party has a partner whose frame meets its own.

    ``iface`` must be resolved (``resolve_interface``).  Checked in each lowest assembly that
    contains both parties, from its ``instances.json`` (leaves in that assembly's frame,
    nested ones included).  Only interfaces that give each party its own frame (``frames:``)
    are checked: the shared fallback ``frame`` is in nobody's coordinates in particular.

    A part joined to another at several places (two hinges on one hinge post) has one
    interface per place, each naming the same two parts (S-113).  Then an occurrence that
    meets another of those interfaces is that interface's business, not a miss here; but each
    interface still needs at least one pair that meets, so a missing hinge still fails.

    Returns:
        ``{status: pass|fail|skip, message, ...}`` with the world frames as evidence.
    """
    a, b = (str(p) for p in iface.parties)
    if not (a.startswith("part://") and b.startswith("part://")):
        return {"status": "skip", "message": "an assembly is not a party: its joints are ports"}
    if a not in iface.frames or b not in iface.frames:
        return {
            "status": "skip",
            "message": "where the parts meet is not checked: give each party its own frame "
            "under frames:",
        }
    asms = lowest_common_assemblies(product, a, b)
    if not asms:
        return {"status": "skip", "message": "the two parts are not in one assembly"}
    siblings = _siblings(product, iface)
    out: dict[str, Any] = {
        "status": "pass",
        "tolerance": {"distance_mm": ALIGN_MM, "angle_deg": ALIGN_DEG},
        "offset_mm": float(iface.offset),
        "assemblies": {},
    }
    if siblings:
        out["shared_with"] = [s.uri for s in siblings]
    failures: list[str] = []
    worst = 0.0
    for aid in asms:
        path = build_dir / "assemblies" / aid / "instances.json"
        if not path.is_file():
            out["assemblies"][aid] = {"status": "skip", "why": "not built"}
            continue
        instances: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
        pairs = _pairs(iface, instances, a, b)
        elsewhere = {
            node
            for sib in siblings
            for p in _pairs(sib, instances, str(sib.parties[0]), str(sib.parties[1]))
            if p["meets"]
            for node in p["occurrences"]
        }
        nodes = list(dict.fromkeys(n for p in pairs for n in p["occurrences"]))
        lonely: list[dict[str, Any]] = []
        for node in nodes:
            mine = [p for p in pairs if node in p["occurrences"]]
            if not any(p["meets"] for p in mine) and node not in elsewhere:
                nearest = min(mine, key=lambda p: (p["distance_mm"], p["normal_deg"]))
                if nearest not in lonely:
                    lonely.append(nearest)
        if pairs and not lonely and not any(p["meets"] for p in pairs):
            lonely.append(min(pairs, key=lambda p: (p["distance_mm"], p["normal_deg"])))
        for p in pairs:
            if p["meets"]:
                worst = max(worst, p["distance_mm"])
        for p in lonely:
            na, nb = p["occurrences"]
            where = f" in {_assembled(product, [aid])}" if len(asms) > 1 else ""
            failures.append(
                f"{_occurrence_name(product, na, instances)} and "
                f"{_occurrence_name(product, nb, instances)} do not line up "
                f"{_joint_at(iface)}{where}: {_miss_words(p, iface.kind)}"
            )
            out.setdefault("failures", []).append(
                {
                    "assembly": f"asm://{aid}",
                    "occurrences": [na, nb],
                    "distance_mm": p["distance_mm"],
                    "normal_deg": p["normal_deg"],
                    "x_axis_deg": p["x_axis_deg"],
                }
            )
        out["assemblies"][aid] = {
            "status": "fail" if lonely else "pass",
            "pairs": pairs,
        }
    checked = [v for v in out["assemblies"].values() if v["status"] != "skip"]
    if failures:
        out["status"] = "fail"
        what = "holes" if iface.kind == "bolt-pattern" else "faces"
        out["message"] = "; ".join(failures) + f". Move the {what} or the parts so they meet."
        # the offset, the ids and the world frames are evidence, not owner text (gate D)
        out["fix"] = (
            f"the second party's frame must sit {float(iface.offset):g} mm along the first "
            f"party's normal from it; correct the frames of {iface.uri} or the placement code"
        )
    elif not checked:
        out["status"] = "skip"
        out["message"] = "where the parts meet is not checked: the assembly is not built"
    else:
        out["worst_mm"] = worst
        out["message"] = f"{_assembled(product, asms)} ({_within(worst)})"
    return out


# ---- the coordinate-placement warning (P1) ----------------------------------------------


def coordinate_placement_warnings(product: Product, build_dir: Path) -> list[CheckResult]:
    """Warn when a joint was closed by typed-in coordinates although an interface could (P1).

    In each assembly, take every pair of parts placed directly in it that an interface joins.
    When neither part has an occurrence placed through an interface joining the two, both
    positions were typed in and can drift apart: one ``warn`` row per such joint, suggesting
    ``place_by``.  When one side was placed by the joint (the guard onto the stand), the other
    side's coordinates are the anchor and nothing is said.  The rule needs no placement
    order, so reordering the placement code changes nothing (S-030, S-106).  Joints through
    ports (P4) are not looked at yet: a sub-assembly's own placement is not in
    ``instances.json`` (B-0064).  A product built before v0.4 has no ``via``
    in ``instances.json`` and never warns.
    """
    out: list[CheckResult] = []
    for aid in sorted(product.assemblies):
        path = build_dir / "assemblies" / aid / "instances.json"
        if not path.is_file():
            continue
        instances: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
        via_by_uri: dict[str, set[str]] = {}
        nodes: dict[str, list[str]] = {}
        for inst in instances:
            if inst.get("parent") is None and "via" in inst:
                via_by_uri.setdefault(str(inst["uri"]), set()).add(str(inst["via"]))
                nodes.setdefault(str(inst["uri"]), []).append(str(inst["node"]))
        joints: dict[tuple[str, str], list[str]] = {}
        for iface in product.interfaces.values():
            a, b = (str(p) for p in iface.parties)
            if a != b and a in via_by_uri and b in via_by_uri:
                joints.setdefault((a, b) if a < b else (b, a), []).append(iface.uri)
        for (a, b), ifaces in sorted(joints.items()):
            if (via_by_uri[a] | via_by_uri[b]) & set(ifaces):
                continue  # one side was placed by the joint: the other side is the anchor
            name_a, name_b = (product.parts[u.removeprefix("part://")].name for u in (a, b))
            iface = product.interfaces[ifaces[0].removeprefix("iface://")]
            child = str(iface.parties[1])
            cid = child.removeprefix("part://")
            out.append(
                CheckResult(
                    id=f"placement://{aid}@{a.removeprefix('part://')}+{b.removeprefix('part://')}",
                    subject=child,
                    status="warn",
                    kind="interface",
                    title=f"{name_a} and {name_b}: placed by their joint",
                    message=(
                        f"{name_a} and {name_b} are both placed by typed-in coordinates, "
                        "although a joint between them could place one onto the other; placed "
                        "by the joint, the two cannot drift apart"
                    ),
                    detail={
                        "assembly": f"asm://{aid}",
                        "occurrences": nodes[a] + nodes[b],
                        "interfaces": ifaces,
                        "fix": f'place_by(I, res, "{iface.id}", "{child}", parts["{cid}"])',
                    },
                )
            )
    return out
