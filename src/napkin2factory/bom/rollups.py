"""BOM structure and rollups (D18): quantities through sub-assemblies, cost, mass, counts.

Every declared value is read through recording selectors so the ``bom`` rule's
dependencies are exact (``part://x#cost.unit``, ``asm://y#children``, ``part://x#props.mass``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from napkin2factory.core.loader import Product
from napkin2factory.core.model import Part
from napkin2factory.core.units import format_quantity, parse_quantity
from napkin2factory.geometry.accessors import ReadLog


@dataclass
class BomLine:
    """One indented BOM row."""

    level: int
    uri: str
    id: str
    name: str
    kind: str
    qty: int  # quantity at this position (per parent)
    total_qty: int  # rolled-up quantity in the top assembly
    process: str = ""
    material: str = ""
    finish: str = ""
    tolerance_class: str = ""
    unit_cost: float | None = None
    cost_basis: str = ""
    lead_time_days: float | None = None
    mass_kg: float | None = None
    mass_source: str = ""
    source: str = ""
    sourcing_status: str = ""
    manufacturer: str = ""
    rev: str = ""
    children: list[BomLine] = field(default_factory=list)

    @property
    def ext_cost(self) -> float | None:
        """Extended cost (unit × total quantity)."""
        return None if self.unit_cost is None else self.unit_cost * self.total_qty


def _props_mass(build_dir: Path | None, part: Part) -> tuple[float | None, str]:
    if part.mass is not None:
        return float(part.mass.to("kg").magnitude), "declared"
    if build_dir is None:
        return None, "not built"
    p = build_dir / "parts" / part.id / "props.json"
    if not p.is_file():
        return None, "not built"
    import json

    data = json.loads(p.read_text(encoding="utf-8"))
    return float(data["mass"]), str(data.get("mass_source", "computed"))


def manufacturer_column(part: Part, qty: int) -> str:
    """The "what to tell the manufacturer" text for a row."""
    if part.kind == "reference":
        return f"supplied by the owner / already exists: {part.name} ({qty}×); not quoted"
    if part.kind == "cots":
        src = part.source
        return f"buy {qty}× {part.name}" + (f" ({src.vendor} {src.mpn})" if src else "")
    bits = [part.process]
    if part.material:
        bits.append(part.material.spec or part.material.name)
    if part.finish:
        bits.append(part.finish)
    if part.tolerance_class:
        bits.append(part.tolerance_class)
    bits.append(f"qty {qty}")
    if part.manufacturer_notes:
        bits.append(part.manufacturer_notes)
    return "; ".join(b for b in bits if b)


def sourcing_status(part: Part) -> str:
    """Complete | unverified | missing — before the URL/catalog tiers run (M4 refines)."""
    if part.kind == "reference":
        return "reference"
    if part.kind != "cots":
        return "custom"
    if part.source is None:
        return "missing"
    if not part.source.url:
        return "no-url"
    return "verified" if part.source.verified else "unverified"


def build_lines(
    product: Product,
    asm_id: str,
    log: ReadLog,
    build_dir: Path | None,
    level: int = 0,
    multiplier: int = 1,
) -> list[BomLine]:
    """Indented lines for one assembly, recursing into sub-assemblies."""
    asm = product.assemblies[asm_id]
    log.add(f"asm://{asm_id}#children")
    lines: list[BomLine] = []
    for child in asm.children:
        if child.part is not None:
            part = product.parts[child.part.id]
            for sel in (
                "name",
                "kind",
                "process",
                "material",
                "finish",
                "tolerance_class",
                "cost",
                "lead_time",
                "source",
                "rev",
                "mass",
                "manufacturer_notes",
            ):
                log.add(f"{part.uri}#{sel}")
            mass, mass_src = _props_mass(build_dir, part)
            log.add(f"{part.uri}#geometry")
            if part.mass is None and part.has_geometry:
                log.add(f"{part.uri}#props.mass")
            lines.append(
                BomLine(
                    level=level,
                    uri=part.uri,
                    id=part.id,
                    name=part.name,
                    kind=part.kind,
                    qty=child.qty,
                    total_qty=child.qty * multiplier,
                    process=part.process,
                    material=(part.material.spec or part.material.name) if part.material else "",
                    finish=part.finish or "",
                    tolerance_class=part.tolerance_class or "",
                    unit_cost=float(part.cost.unit.to("USD").magnitude) if part.cost else None,
                    cost_basis=part.cost.basis if part.cost else "",
                    lead_time_days=float(part.lead_time.to("day").magnitude)
                    if part.lead_time
                    else None,
                    mass_kg=mass,
                    mass_source=mass_src,
                    source=f"{part.source.vendor} {part.source.mpn}" if part.source else "",
                    sourcing_status=sourcing_status(part),
                    manufacturer=manufacturer_column(part, child.qty * multiplier),
                    rev=part.rev,
                )
            )
        elif child.asm is not None:
            sub = product.assemblies[child.asm.id]
            log.add(f"{sub.uri}#name")
            log.add(f"{sub.uri}#rev")
            line = BomLine(
                level=level,
                uri=sub.uri,
                id=sub.id,
                name=sub.name,
                kind="assembly",
                qty=child.qty,
                total_qty=child.qty * multiplier,
                rev=sub.rev,
            )
            line.children = build_lines(
                product, sub.id, log, build_dir, level + 1, multiplier * child.qty
            )
            lines.append(line)
    return lines


def flatten_lines(lines: list[BomLine]) -> list[BomLine]:
    """Depth-first list including nested children."""
    out: list[BomLine] = []
    for ln in lines:
        out.append(ln)
        out.extend(flatten_lines(ln.children))
    return out


def top_assemblies(product: Product) -> list[str]:
    """Assemblies no other assembly contains."""
    used = {c.asm.id for a in product.assemblies.values() for c in a.children if c.asm is not None}
    return sorted(a for a in product.assemblies if a not in used)


def compute_rollups(
    product: Product, build_dir: Path | None = None, log: ReadLog | None = None
) -> dict[str, Any]:
    """The ``rollups.json`` payload: lines per top assembly plus totals."""
    log = log if log is not None else ReadLog()
    log.add("set://parts")
    log.add("set://asms")
    tops = top_assemblies(product)
    per_part: dict[str, dict[str, Any]] = {}
    structure: dict[str, list[dict[str, Any]]] = {}
    for top in tops:
        lines = build_lines(product, top, log, build_dir)
        structure[f"asm://{top}"] = [line_to_dict(ln) for ln in lines]
        for ln in flatten_lines(lines):
            if ln.kind == "assembly":
                continue
            agg = per_part.setdefault(
                ln.uri,
                {
                    "uri": ln.uri,
                    "name": ln.name,
                    "kind": ln.kind,
                    "total_qty": 0,
                    "unit_cost": ln.unit_cost,
                    "lead_time_days": ln.lead_time_days,
                    "mass_kg": ln.mass_kg,
                    "sourcing_status": ln.sourcing_status,
                },
            )
            agg["total_qty"] += ln.total_qty
    total_cost = 0.0
    cost_known = True
    total_mass = 0.0
    mass_known = True
    max_lead = 0.0
    custom = 0
    part_count = 0
    for agg in per_part.values():
        part_count += agg["total_qty"]
        if agg["kind"] == "custom":
            custom += agg["total_qty"]
        if agg["kind"] == "reference":
            pass  # not bought, not made: contributes mass but no cost
        elif agg["unit_cost"] is None:
            cost_known = False
        else:
            total_cost += agg["unit_cost"] * agg["total_qty"]
        if agg["mass_kg"] is None:
            mass_known = False
        else:
            total_mass += agg["mass_kg"] * agg["total_qty"]
        if agg["lead_time_days"] is not None:
            max_lead = max(max_lead, agg["lead_time_days"])
    # Parts in no assembly still count for sourcing but not for totals.
    orphans = sorted(p.uri for p in product.parts.values() if p.uri not in per_part)
    return {
        "top_assemblies": [f"asm://{t}" for t in tops],
        "structure": structure,
        "parts": dict(sorted(per_part.items())),
        "orphans": orphans,
        "total_cost": round(total_cost, 2),
        "total_cost_unit": "USD",
        "cost_complete": cost_known,
        "total_mass": round(total_mass, 4),
        "total_mass_unit": "kg",
        "mass_complete": mass_known,
        "part_count": part_count,
        "distinct_parts": len(per_part),
        "custom_count": custom,
        "custom_ratio": round(custom / part_count, 4) if part_count else 0.0,
        "max_lead_time": max_lead,
        "max_lead_time_unit": "d",
        "reads": log.keys,
    }


def line_to_dict(ln: BomLine) -> dict[str, Any]:
    """JSON form of a line (recursive)."""
    d = {k: v for k, v in ln.__dict__.items() if k != "children"}
    d["ext_cost"] = ln.ext_cost
    d["children"] = [line_to_dict(c) for c in ln.children]
    return d


def rollup_value(rollups: dict[str, Any], selector: str) -> Any:
    """``bom://rollups#total_cost`` → a pint quantity (or plain number) for the checks."""
    units = {"total_cost": "USD", "total_mass": "kg", "max_lead_time": "d"}
    if selector not in rollups:
        raise KeyError(
            f"bom://rollups has no {selector!r}; available: total_cost, total_mass, "
            "part_count, custom_ratio, max_lead_time"
        )
    val = rollups[selector]
    return parse_quantity(val, units.get(selector)) if isinstance(val, (int, float)) else val


__all__ = [
    "BomLine",
    "compute_rollups",
    "flatten_lines",
    "format_quantity",
    "rollup_value",
    "top_assemblies",
]
