"""The ``structure`` verify kind: the napkin stage's structural screen on the built model (S-336).

``verify: {kind: structure, target: asm://<top>#props.<measure>, op, value}``. The measures are the
screen's own computed values: ``deflection`` (the sag), ``yield_factor``, ``buckling_factor`` and
``tip_over_factor``. The evaluator rebuilds the screen's pieces from the built assembly's
instances (``build/assemblies/<top>/instances.json``) and their parts' kits, arguments and
materials, takes the loads from the parameters promotion seeded from the card's site, and runs
:func:`napkin2factory.concepts.screens.structural.run` unchanged. A construction the screen
does not cover is never a pass: the requirement is left for a person, with the screen's words.
"""

from __future__ import annotations

import json
from typing import Any

from napkin2factory.core.checks.evaluators import EvalContext
from napkin2factory.core.checks.evidence import evidence_key
from napkin2factory.core.checks.results import CheckResult
from napkin2factory.core.model import Requirement
from napkin2factory.core.units import compare, format_quantity, parse_quantity

#: The measures a ``structure`` target may select (the screening's computed names).
MEASURES: tuple[str, ...] = ("deflection", "yield_factor", "buckling_factor", "tip_over_factor")


def check_structure(verify: Any) -> None:
    """A ``structure`` target selects a measure: ``asm://top#props.deflection``.

    The ``props.`` prefix is what the loader accepts for a value the build or a check computes
    (it looks up any other selector among the assembly's declared fields).
    """
    sel = verify.target.selector
    if len(sel) != 2 or sel[0] != "props" or sel[1] not in MEASURES:
        raise ValueError(
            "structure targets select one measure of an assembly, e.g. "
            f"asm://top#props.deflection; the measures are {', '.join(MEASURES)}"
        )


def _location(translation: list[float], quaternion: list[float]) -> Any:
    """A build123d ``Location`` from ``instances.json``'s translation and xyzw quaternion."""
    from build123d import Location
    from OCP.gp import gp_Quaternion, gp_Trsf, gp_Vec

    trsf = gp_Trsf()
    trsf.SetRotation(gp_Quaternion(*(float(v) for v in quaternion)))
    trsf.SetTranslationPart(gp_Vec(*(float(v) for v in translation)))
    return Location(trsf)


def _pieces(ctx: EvalContext, top: str) -> list[Any] | str:
    """The built assembly's instances as the screen's pieces, else why there are none."""
    from napkin2factory.concepts.massing import build_piece_at
    from napkin2factory.core.model.concepts import MassingCall
    from napkin2factory.core.model.parts import KitGeometry
    from napkin2factory.geometry.accessors import make_accessors
    from napkin2factory.geometry.build_part import resolve_args

    path = ctx.build_dir / "assemblies" / top / "instances.json"
    if not path.is_file():
        return f"asm://{top} has not been built"
    records = json.loads(path.read_text(encoding="utf-8"))
    P, I, _log = make_accessors(ctx.product)  # noqa: N806, E741 — the accessors' usual names
    pieces: list[Any] = []
    for rec in records:
        pid = str(rec["uri"]).removeprefix("part://")
        part = ctx.product.parts.get(pid)
        if part is None or not isinstance(part.geometry, KitGeometry):
            return f"part://{pid} is not drawn by a kit, so the structure cannot be read from it"
        args = resolve_args(part.geometry.args, P, I)
        name = rec.get("label") or str(rec["node"])
        call = MassingCall.model_validate(
            {
                "kit": part.geometry.kit,
                "as": name,
                "args": args,
                "material": part.material.name if part.material else None,
                "process_class": part.process,
                "role": part.role,
            }
        )
        piece = build_piece_at(
            f"{top}/{name}", str(rec["node"]), call, _location(rec["translation"], rec["rotation"])
        )
        pieces.append(piece)
    return pieces or f"asm://{top} has no parts yet, so there is nothing to check"


def _card(ctx: EvalContext, top: str) -> tuple[Any, list[str]]:
    """A card carrying the loads the model holds: ``site`` read from the seeded parameters."""
    from napkin2factory.concepts.promote.loads import seed_name
    from napkin2factory.concepts.screens.structural_base import FIELDS
    from napkin2factory.core.model.concepts import ConceptCard

    site: dict[str, str] = {}
    read: list[str] = []
    for f in FIELDS:
        name = seed_name(f.key, f.param)
        if name in ctx.product.parameters:
            site[f.key] = format_quantity(ctx.product.parameter_value(name))
            read.append(f"param://{name}")
    return ConceptCard.model_validate({"id": "C-000", "title": top, "site": site}), read


def screen_asm(ctx: EvalContext, top: str) -> dict[str, Any]:
    """Run the structural screen on a built assembly (once per check run).

    Returns ``{"rows": [...], "computed": {name: raw}, "read": [uris]}`` or ``{"why": text}``
    when the assembly cannot be read.
    """
    cache: dict[str, dict[str, Any]] = ctx.__dict__.setdefault("_structure", {})
    if top in cache:
        return cache[top]
    from napkin2factory.concepts.massing import MassingResult
    from napkin2factory.concepts.screens.base import ScreenValues
    from napkin2factory.concepts.screens.structural import run

    pieces = _pieces(ctx, top)
    if isinstance(pieces, str):
        out: dict[str, Any] = {"why": pieces}
    else:
        card, read = _card(ctx, top)
        if not card.site:
            out = {
                "why": "the model holds no load parameters (point-load, distributed-load or "
                "edge-load), so there is nothing to check"
            }
        else:
            values = ScreenValues()
            massing = MassingResult(card.id, pieces, [], {})
            rows = run(card, massing, values)
            out = {"rows": rows, "computed": dict(values.computed.raw), "read": read}
    cache[top] = out
    return out


def eval_structure(
    ctx: EvalContext, req: Requirement, res: CheckResult, evidence: dict[str, str]
) -> str | None:
    """``structure``: one measure of the structural screen, run on the built assembly."""
    v = req.verify
    assert v is not None and v.target is not None and v.op and v.value is not None
    top = str(v.target.base).removeprefix("asm://")
    measure = v.target.selector[1]
    screened = screen_asm(ctx, top)
    if "why" in screened:
        res.message = screened["why"]
        return "skip" if "not been built" in screened["why"] else None
    value = screened["computed"].get(measure)
    if value is None:
        # not covered, or an input missing: the screen says which, never a pass
        rows = [r for r in screened["rows"] if r.status == "skip"]
        res.message = (
            rows[0].message if rows else f"the structural check computed no {measure} here"
        )
        return None
    quantity = value if hasattr(value, "magnitude") and hasattr(value, "units") else None
    if quantity is None:
        quantity = parse_quantity(float(value))
    ok = compare(quantity, v.op, v.value)
    res.message = f"{measure} = {format_quantity(quantity)} {v.op} {format_quantity(v.value)}"
    evidence[f"asm://{top}"] = evidence_key(ctx.product, ctx.build_dir, f"asm://{top}")
    for uri in screened["read"]:
        evidence[uri] = evidence_key(ctx.product, ctx.build_dir, uri)
    return "pass" if ok else "fail"
