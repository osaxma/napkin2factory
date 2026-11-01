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
            rep.status, rep.message = "skip", f"{party} has not been built"
            return rep
        feats = json.loads(feats_path.read_text(encoding="utf-8"))
        frame = iface.frame_for(str(party))
        if iface.kind == "bolt-pattern":
            pats = [p for p in feats.get("patterns", []) if p.get("interface") == iface.uri]
            if not pats:
                rep.status, rep.message = (
                    "fail",
                    f"{party} did not place the pattern for iface://{iface.id}",
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
                    f"{party} did not record the mating face for iface://{iface.id}",
                )
                rep.parties[str(party)] = {"status": "fail", "why": "no mating face recorded"}
            else:
                rep.parties[str(party)] = {"status": "pass", "face": faces[0]}
    if rep.status == "fail":
        return rep
    if iface.kind == "bolt-pattern" and len(patterns) == 2:
        (ua, a), (ub, b) = patterns.items()
        if not _match(a["local"], b["local"], TOLERANCE_MM):
            rep.status = "fail"
            rep.message = (
                f"hole patterns differ between {ua} and {ub} (tolerance {TOLERANCE_MM} mm): "
                f"{a['local']} vs {b['local']}"
            )
        elif abs(float(a["diameter"]) - float(b["diameter"])) > TOLERANCE_MM:
            rep.status = "fail"
            rep.message = f"hole diameters differ: {a['diameter']} vs {b['diameter']}"
        else:
            spec = iface.spec
            n = spec.count if isinstance(spec, BoltPatternSpec) else len(a["local"])
            rep.message = f"{n} holes agree within {TOLERANCE_MM} mm on both parties"
    elif iface.kind == "mating-face":
        rep.message = (
            "both parties record the mating face; contact is allowed in the interference "
            "check (D29)"
        )
    if rep.status == "pass":
        rep.alignment = check_alignment(product, iface, build_dir)
        if rep.alignment["status"] == "fail":
            rep.status = "fail"
            rep.message = rep.alignment["message"]
        elif rep.alignment["status"] == "pass":
            rep.message += "; " + rep.alignment["message"]
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


def _miss_words(m: dict[str, float]) -> str:
    parts = []
    if m["distance_mm"] > ALIGN_MM:
        parts.append(f"their frames are {m['distance_mm']:.1f} mm apart")
    if m["normal_deg"] > ALIGN_DEG:
        parts.append(f"their faces are turned {m['normal_deg']:.1f}° from each other")
    if m["x_axis_deg"] > ALIGN_DEG:
        parts.append(f"their patterns are rotated {m['x_axis_deg']:.1f}° from each other")
    return " and ".join(parts) or "they meet"


def check_alignment(product: Product, iface: Interface, build_dir: Path) -> dict[str, Any]:
    """Stage 2 (P3): every occurrence of each party has a partner whose frame meets its own.

    ``iface`` must be resolved (``resolve_interface``).  Checked in each lowest assembly that
    contains both parties, from its ``instances.json`` (leaves in that assembly's frame,
    nested ones included).  Only interfaces that give each party its own frame (``frames:``)
    are checked: the shared fallback ``frame`` is in nobody's coordinates in particular.

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
    fa, fb = iface.frame_for(a), iface.frame_for(b)
    out: dict[str, Any] = {
        "status": "pass",
        "tolerance": {"distance_mm": ALIGN_MM, "angle_deg": ALIGN_DEG},
        "offset_mm": float(iface.offset),
        "assemblies": {},
    }
    failures: list[str] = []
    worst = 0.0
    for aid in asms:
        path = build_dir / "assemblies" / aid / "instances.json"
        if not path.is_file():
            out["assemblies"][aid] = {"status": "skip", "why": "not built"}
            continue
        instances: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
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
        lonely: list[dict[str, Any]] = []
        for node in [n for n, _ in occ_a] + [n for n, _ in occ_b]:
            mine = [p for p in pairs if node in p["occurrences"]]
            if mine and not any(p["meets"] for p in mine):
                nearest = min(mine, key=lambda p: (p["distance_mm"], p["normal_deg"]))
                if nearest not in lonely:
                    lonely.append(nearest)
        for p in pairs:
            if p["meets"]:
                worst = max(worst, p["distance_mm"])
        for p in lonely:
            na, nb = p["occurrences"]
            failures.append(f"{na} and {nb} do not meet in asm://{aid}: {_miss_words(p)}")
        out["assemblies"][aid] = {
            "status": "fail" if lonely else "pass",
            "pairs": pairs,
        }
    checked = [v for v in out["assemblies"].values() if v["status"] != "skip"]
    if failures:
        out["status"] = "fail"
        out["message"] = (
            "; ".join(failures)
            + f" (allowed: {ALIGN_MM} mm and {ALIGN_DEG}°, offset {float(iface.offset):g} mm)"
        )
    elif not checked:
        out["status"] = "skip"
        out["message"] = "where the parts meet is not checked: the assembly is not built"
    else:
        where = ", ".join(f"asm://{aid}" for aid in asms)
        out["message"] = f"placed, the parts meet in {where} (worst {worst:.2f} mm)"
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
