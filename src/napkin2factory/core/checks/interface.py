"""Interface conformance (D16): both parties recorded the same pattern in the interface frame."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from napkin2factory.core.loader import Product
from napkin2factory.core.model import BoltPatternSpec, Interface

TOLERANCE_MM = 0.5


@dataclass
class InterfaceReport:
    """Outcome and evidence of one interface check."""

    status: str = "pass"
    message: str = ""
    parties: dict[str, Any] = field(default_factory=dict)

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
    rep = InterfaceReport()
    patterns: dict[str, Any] = {}
    for party in iface.parties:
        pid = party.id
        if party.scheme != "part":
            rep.parties[str(party)] = {
                "status": "skip",
                "why": "assemblies are not checked as parties in v0.1",
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
    return rep
