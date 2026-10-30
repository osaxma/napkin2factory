"""Pairwise interference check on an assembly (D29).

For every pair of placed instances: bbox prefilter, COTS-to-COTS pairs skipped, pairs
joined by a declared ``mating-face`` interface skipped and recorded as ``allowed-contact``,
then the boolean common volume; more than 1 mm³ is an interference.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from napkin2factory.core.loader import Product

THRESHOLD_MM3 = 1.0


@dataclass
class InterferenceReport:
    """Outcome plus the evidence rows."""

    pairs_checked: int = 0
    pairs_skipped_bbox: int = 0
    pairs_skipped_cots: int = 0
    allowed_contacts: list[str] = field(default_factory=list)
    interferences: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when no pair overlaps beyond the threshold."""
        return not self.interferences

    def to_dict(self) -> dict[str, Any]:
        """JSON form."""
        return dict(self.__dict__)


def _location(tr: list[float], q: list[float]) -> Any:
    from build123d import Location
    from OCP.gp import gp_Quaternion, gp_Trsf, gp_Vec

    trsf = gp_Trsf()
    trsf.SetRotation(gp_Quaternion(q[0], q[1], q[2], q[3]))
    trsf.SetTranslationPart(gp_Vec(tr[0], tr[1], tr[2]))
    return Location(trsf)


def _bbox(shape: Any) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    bb = shape.bounding_box()
    return (bb.min.X, bb.min.Y, bb.min.Z), (bb.max.X, bb.max.Y, bb.max.Z)


def _bbox_overlap(a: Any, b: Any, tol: float = 0.01) -> bool:
    (a0, a1), (b0, b1) = _bbox(a), _bbox(b)
    return all(a1[i] > b0[i] + tol and b1[i] > a0[i] + tol for i in range(3))


def _volume(common: Any) -> float:
    """Volume of a boolean result (a shape, or a ShapeList in build123d ≥ 0.12)."""
    if common is None:
        return 0.0
    if hasattr(common, "volume"):
        return float(common.volume)
    return float(sum(getattr(s, "volume", 0.0) for s in common))


def check_interference(product: Product, asm_id: str, build_dir: Path) -> InterferenceReport:
    """Run the check against ``build/assemblies/<id>/instances.json`` and the parts' STEP files."""
    from build123d import import_step

    report = InterferenceReport()
    inst_path = build_dir / "assemblies" / asm_id / "instances.json"
    if not inst_path.is_file():
        report.notes.append(f"asm://{asm_id} has not been built")
        return report
    instances = json.loads(inst_path.read_text(encoding="utf-8"))
    shapes: dict[str, Any] = {}
    placed: list[tuple[str, str, Any]] = []
    for inst in instances:
        uri = inst["uri"]
        pid = uri.replace("part://", "")
        if uri not in shapes:
            step = build_dir / "parts" / pid / "model.step"
            if not step.is_file():
                report.notes.append(f"{uri} has no STEP; skipped")
                continue
            shapes[uri] = import_step(str(step))
        placed.append(
            (inst["node"], uri, shapes[uri].moved(_location(inst["translation"], inst["rotation"])))
        )
    mating_pairs: set[frozenset[str]] = set()
    for iface in product.interfaces.values():
        if iface.kind == "mating-face":
            mating_pairs.add(frozenset(str(p) for p in iface.parties))
    iface_by_pair = {
        frozenset(str(p) for p in i.parties): i.id
        for i in product.interfaces.values()
        if i.kind == "mating-face"
    }
    for i in range(len(placed)):
        for j in range(i + 1, len(placed)):
            node_a, uri_a, shape_a = placed[i]
            node_b, uri_b, shape_b = placed[j]
            part_a, part_b = (
                product.parts[uri_a.replace("part://", "")],
                product.parts[uri_b.replace("part://", "")],
            )
            if part_a.kind == "cots" and part_b.kind == "cots":
                report.pairs_skipped_cots += 1
                continue
            pair = frozenset({uri_a, uri_b})
            if not _bbox_overlap(shape_a, shape_b):
                report.pairs_skipped_bbox += 1
                continue
            if pair in mating_pairs:
                report.allowed_contacts.append(
                    f"{node_a} ~ {node_b}: allowed-contact: iface://{iface_by_pair[pair]}"
                )
                continue
            report.pairs_checked += 1
            try:
                common = shape_a & shape_b
                vol = _volume(common)
            except Exception as exc:  # OCCT boolean failures are reported, not hidden
                report.interferences.append(
                    {
                        "a": node_a,
                        "b": node_b,
                        "volume": None,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                continue
            if vol > THRESHOLD_MM3:
                report.interferences.append({"a": node_a, "b": node_b, "volume": round(vol, 3)})
    return report
