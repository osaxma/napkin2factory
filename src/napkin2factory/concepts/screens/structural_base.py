"""What the structural screen's shape cases share: its card fields, titles and check rows (W4).

The fields are ``site`` fields of the card (the package's own words); the rows are the sag,
yield, buckling and tip-over rows, each with the formula and the source in its message and the
factor under a stable name in the screening's computed values (docs/napkin.md, "The structural
screen"). The shape cases are in :mod:`~napkin2factory.concepts.screens.structural_top` (a top
on a stand) and :mod:`~napkin2factory.concepts.screens.structural` (a column with an arm).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from napkin2factory.calckit import joints, structural
from napkin2factory.concepts.screens.base import CardField, ScreenValues, fmt, sig
from napkin2factory.core.model.concepts import ConceptCard, RuleRow
from napkin2factory.core.units import Quantity

Qty = Any


def _site(key: str, unit: str, kind: str, example: str, words: str) -> CardField:
    # ``hint=False``: a new card's skeleton names these only when the card gives one, so a
    # product with no loads is never asked about them
    return CardField("site", key, unit, kind, example, words, hint=False)


POINT_LOAD = _site("point_load", "N", "a force", "1471.5 N", "the load at the centre of the top")
DISTRIBUTED_LOAD = _site("distributed_load", "N", "a force", "800 N", "the load spread over it")
EDGE_LOAD = _site("edge_load", "N", "a force", "490.5 N", "the downward load at an edge")
EDGE_OFFSET = _site(
    "edge_offset", "mm", "a length", "150 mm", "how far beyond the support the edge load acts"
)
MAX_DEFLECTION = _site("max_deflection", "mm", "a length", "2.5 mm", "the most it may sag")
CYCLES = _site("cycles", "", "a count", "100000", "how many times the load is applied")
FIELDS = (POINT_LOAD, DISTRIBUTED_LOAD, EDGE_LOAD, EDGE_OFFSET, MAX_DEFLECTION, CYCLES)

TITLES = {
    "structural-deflection": "Sag stays within the limit",
    "structural-yield": "Stress stays under yield",
    "structural-buckling": "Legs or column do not buckle",
    "structural-tip-over": "It does not tip over",
    "structural-cross-member": "The cross member carries the centre load",
    "structural-support": "The massing shows what carries the load",
}
#: Effective length factors: unbraced frame legs sway laterally (AISC Table C-A-7.1 case f,
#: K = 2.0, SPEC §4); a column with an arm is a cantilever (case e, design K = 2.1).
LEG_ENDS, COLUMN_ENDS = 2.0, "fixed-free"


@dataclass
class Ctx:
    """What one screening hands every check: the card, the shapes, the loads and the limit."""

    card: ConceptCard
    massing: Any
    values: ScreenValues
    loads: dict[str, Qty | None]
    limit: Qty | None
    kind: str


@dataclass(frozen=True)
class Stock:
    """A material's stiffness, strength and density from the shared table, with its source."""

    E: Qty
    yield_strength: Qty
    ref: str
    density: float  # kg/m^3


def mm(v: float) -> Qty:
    """A length in millimetres."""
    return Quantity(v, "mm")


def length_text(q: Qty) -> str:
    """A length with three significant figures (``fmt`` rounds a length to whole millimetres)."""
    return f"{sig(float(q.to('mm').magnitude))} mm"


def rule_row(rid: str, status: Any, message: str) -> RuleRow:
    """One structural row with its owner-worded title."""
    relies: Any = [] if status == "skip" else ["computed"]
    return RuleRow(id=rid, title=TITLES[rid], status=status, message=message, relies_on=relies)


def skip_row(rid: str, why: str) -> RuleRow:
    """A check that was not run, with the reason."""
    return rule_row(rid, "skip", f"not run: {why}")


def stock_of(piece: Any) -> Stock | str:
    """E, yield strength and density of a piece's material from the shared table, else why not."""
    # the same keyword match the massing densities use (calckit/data/materials.yaml, W2)
    from napkin2factory.geometry.materials import material_row

    if piece.material is None:
        return f"the {piece.name} has no material"
    row = material_row(piece.material)
    if row is None or row.get("youngs_modulus") is None or row.get("yield_strength") is None:
        return f"no stiffness and strength on file for {piece.material}"
    return Stock(
        Quantity(float(row["youngs_modulus"]), "Pa"),
        Quantity(float(row["yield_strength"]), "Pa"),
        f"{row['name']} in calckit/data/materials.yaml [verify]",
        float(row.get("density") or 0.0),
    )


def tube_section(shape: str, size: float, wall: float, size2: float | None = None) -> Any | str:
    """The section of a tube (round, square or rectangular), else why it has none."""
    if shape in ("round", "round-tube"):
        if wall <= 0 or wall >= size / 2:
            return "no section properties for a solid round bar"
        return structural.round_tube_section(mm(size), mm(wall))
    if shape not in ("square", "square-tube", "rect-tube"):
        return f"no section properties for a {shape}"
    if wall <= 0 or wall >= min(size, size2 or size) / 2:
        return structural.rect_section(mm(size2 or size), mm(size))
    return structural.rect_tube_section(mm(size2 or size), mm(size), mm(wall))


def piece_section(piece: Any, depth: int, across: int) -> Any | str:
    """Section of a tube or block piece bending with its ``depth`` axis in the plane."""
    a = piece.args
    if piece.kit == "tube":
        return tube_section(a.shape, a.size, a.wall)
    if piece.kit == "block":
        return structural.rect_section(mm(piece.size[across]), mm(piece.size[depth]))
    return f"no section properties for a {piece.kit} call"


def total_kg(ctx: Ctx) -> float:
    """The rough shapes' mass plus what other screens added to it (the hardware, S-221)."""
    kg = float(ctx.massing.mass or 0.0)
    return kg + sum(float(q.to("kg").magnitude) for q, _words, _ref in ctx.values.mass_items)


def factor_row(
    rid: str,
    ctx: Ctx,
    got: float,
    need: float,
    subject: str,
    how: str,
    case: str = "",
    name: str = "",
) -> RuleRow:
    """A factor against the factor it needs: one row, the value, the formula and the source.

    The factor is a computed value of the screening under ``name`` (default: the row's id
    without ``structural-``, hyphens as underscores, plus ``_factor``).
    """
    ok = got >= need
    name = name or rid.removeprefix("structural-").replace("-", "_") + "_factor"
    ctx.values.computed.add(name, got, sig(got), "computed from the card and the massing", how)
    return rule_row(
        rid,
        "pass" if ok else "fail",
        f"{subject}: factor {sig(got)} (computed), {'at least' if ok else 'below'} the "
        f"{sig(need)} needed ({case or ctx.kind} case) — {how}",
    )


def deflection_row(ctx: Ctx, d: Qty, what: str, how: str) -> RuleRow:
    """The sag against the card's limit; ``d`` is the screening's ``deflection``."""
    text = length_text(d)
    ctx.values.computed.add("deflection", d, text, "computed from the card and the massing", how)
    if ctx.limit is None:
        msg = f"{what} {text} (computed), not judged: no max_deflection on the card — {how}"
        return rule_row("structural-deflection", "skip", msg)
    need = joints.factor_of_safety("deflection", ctx.kind)
    margin = float((ctx.limit / d).to("").magnitude) if float(d.magnitude) else math.inf
    ok = margin >= need
    return rule_row(
        "structural-deflection",
        "pass" if ok else "fail",
        f"{what} {text} (computed), {'within' if ok else 'beyond'} the "
        f"{length_text(ctx.limit)} limit on the card (limit ÷ sag is {sig(margin)}, "
        f"{sig(need)} needed, {ctx.kind} case) — {how}",
    )


def column_row(
    ctx: Ctx,
    sec: Any,
    stock: Stock,
    length_mm: float,
    load: Qty,
    ends: str | float,
    who: str,
    share: str = "",
) -> RuleRow:
    """Buckling of one column by Euler or Johnson depending on slenderness (S-207, S-211).

    ``share`` (words) says what makes up a leg's load: the subject is then "the worst-loaded
    leg, taking <share>".
    """
    i_min, length = min(sec.Ix, sec.Iy), mm(length_mm)
    res = structural.column_buckling_load(
        stock.E, i_min, sec.A, stock.yield_strength, length, ends, load=load
    )
    got = res.safety_factor or math.inf
    if isinstance(ends, (int, float)):
        k, ends_label = float(ends), "sway"
    else:
        k, ends_label = structural.K_FACTORS[ends], ends
    need = joints.factor_of_safety("buckling", ctx.kind)
    method_name = res.method.capitalize()
    formula_text = f"{method_name} ({res.formula})"
    how = f"{formula_text}; slenderness {sig(res.slenderness or 0)}, K {k:g} ({ends_label}); "
    how += f"{res.source}; {stock.ref}"
    if share:
        subject = (
            f"the worst-loaded leg, taking {share} ({fmt(load, 'N')}), over {length_text(length)}"
        )
    else:
        subject = f"{who} under {fmt(load, 'N')} over {length_text(length)}"
    return factor_row("structural-buckling", ctx, got, need, subject, how)


def yield_row(
    ctx: Ctx,
    moment_nm: float,
    z: Qty,
    stock: Stock,
    who: str,
    how: str,
    rid: str = "structural-yield",
    name: str = "",
) -> RuleRow:
    """Bending stress against yield for one member."""
    res = structural.beam_bending_stress(Quantity(moment_nm, "N*m"), z, stock.yield_strength)
    got = res.yield_factor or math.inf
    need = joints.factor_of_safety("yield", ctx.kind)
    stress = fmt(res.stress.to("MPa"), "MPa")
    subject = f"{who} carries {stress} of bending stress ({sig(moment_nm)} N·m)"
    detail = f"{how}; {res.formula}; {res.source}; {stock.ref}"
    return factor_row(rid, ctx, got, need, subject, detail, name=name)
