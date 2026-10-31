"""Named checks behind ``concept-v0.yaml`` and their runner (NAPKIN_STAGE N5, S-022 pattern).

Concept rules screen a *card*, not a part: each check reads a :class:`ConceptFacts` (the
card, the screening's raw ``computed`` and ``estimate`` values, the composed massing) plus
the rule's YAML ``params`` and returns an :class:`Outcome`. :func:`run_concept_rules` turns
outcomes into :class:`~napkin2factory.core.model.concepts.RuleRow` rows with the pack's
wording. ``rulepacks.runner.run_rulepacks`` never runs this pack: it iterates product
parts, and no part has ``scope: concept``.

Values in ``computed`` and ``estimates`` are pint quantities (or words); a rule row records
which of the two labels it relied on, so a reader can tell geometry from estimate.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from napkin2factory.core.model.concepts import ConceptCard, RuleRow
from napkin2factory.core.units import Quantity, is_quantity
from napkin2factory.rulepacks.runner import RulePack, load_packs

if TYPE_CHECKING:
    from napkin2factory.concepts.massing import MassingPiece, MassingResult

Qty = Any
CONCEPT_SCOPE = "concept"
AXES: tuple[str, str, str] = ("width", "depth", "height")
#: Kit generators whose massing is a sheet cut flat and folded (rule blank-vs-stock-sheet).
SHEET_KITS: tuple[str, ...] = ("enclosure", "bracket_l", "panel", "plate")
HINGED = ("hinged-left", "hinged-right")
LIFT_ORDER: tuple[str, ...] = ("one-person", "two-person", "equipment")
LIFT_WORDS: dict[str, str] = {
    "one-person": "a one-person lift",
    "two-person": "a two-person lift",
    "equipment": "equipment handling (a trolley or lifting aid)",
}
_CIRCUIT_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*V\W*(\d+(?:\.\d+)?)\s*A\s*$", re.IGNORECASE)


@dataclass
class ConceptFacts:
    """What a concept check may read."""

    card: ConceptCard
    computed: dict[str, Any] = field(default_factory=dict)
    estimates: dict[str, Any] = field(default_factory=dict)
    massing: MassingResult | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Outcome:
    """A check's answer: ``violated`` takes the rule's severity; ``warn`` is always a warning."""

    status: Literal["pass", "violated", "warn", "skip"]
    values: dict[str, Any] = field(default_factory=dict)
    violations: list[dict[str, Any]] = field(default_factory=list)
    relies_on: list[str] = field(default_factory=list)
    message: str | None = None  # used as is (skip reasons, unknown-table notes)


CheckFn = Callable[[ConceptFacts, dict[str, Any]], Outcome]


# --- small helpers ------------------------------------------------------------------


def mm_text(value_mm: float) -> str:
    """``995 mm`` (whole millimetres)."""
    return f"{value_mm:.0f} mm"


def _q_mm(q: Qty) -> float:
    return float(q.to("mm").magnitude)


def _site_length(card: ConceptCard, key: str) -> Qty | None:
    v: Any = card.site.get(key)
    if is_quantity(v):
        try:
            v.to("mm")
        except Exception:  # pint DimensionalityError: not a length
            return None
        return v
    return None


def parse_circuit(text: str) -> tuple[Qty, Qty] | None:
    """``240V-13A`` → (240 V, 13 A); ``None`` when the text is not of that form."""
    m = _CIRCUIT_RE.match(text)
    if not m:
        return None
    return Quantity(float(m.group(1)), "V"), Quantity(float(m.group(2)), "A")


def door_swing_term(
    card: ConceptCard, massing: MassingResult | None, factor: float = 1.0
) -> tuple[float, str]:
    """Width an open hinged door adds beside its hinge side (mm) and how it was found.

    For ``layout.door`` ``hinged-left`` or ``hinged-right`` the open leaf stands beside the
    body on the hinge side, so the footprint grows by ``factor × door width`` (1.0 = the
    leaf swung right back, the conservative case). The door width is the world x-extent of
    the massing call named ``door``, else ``envelope.door_width``, else nothing is added
    and the basis says so. Any other door (none, sliding, lift-off, top lid) adds 0.
    """
    door = str(card.layout.get("door", "")).strip().lower()
    if door not in HINGED:
        return 0.0, f"door {door or 'not given'}: nothing swings beside the body"
    piece = massing.piece("door") if massing is not None else None
    if piece is not None:
        width = piece.size[0]
        basis = f"{door}: the {mm_text(width)} door leaf swung open beside the hinge"
    elif is_quantity(card.envelope.get("door_width")):
        width = _q_mm(card.envelope["door_width"])
        basis = f"{door}: envelope.door_width {mm_text(width)} swung open beside the hinge"
    else:
        return 0.0, (
            f"{door}, but no `door` massing call or envelope.door_width: the open door is "
            "not counted"
        )
    if factor != 1.0:
        basis += f", × {factor:g}"
    return factor * width, basis


def _fmt(template: str, values: dict[str, Any]) -> str:
    try:
        return template.format(**values)
    except (KeyError, IndexError, ValueError):
        return template


def _skip(message: str) -> Outcome:
    return Outcome("skip", message=message)


# --- the checks ---------------------------------------------------------------------


def fits_site_width(facts: ConceptFacts, params: dict[str, Any]) -> Outcome:
    """Footprint width plus the door-swing term fits ``site.alcove_width``.

    ``width + door_swing_factor × door_width ≤ alcove_width`` for a hinged door (see
    :func:`door_swing_term`); other doors add nothing.
    """
    limit = _site_length(facts.card, "alcove_width")
    if limit is None:
        return _skip("no alcove width on the card (site.alcove_width)")
    width = facts.computed.get("width")
    if width is None:
        return _skip("no massing to measure")
    term, basis = door_swing_term(
        facts.card, facts.massing, float(params.get("door_swing_factor", 1.0))
    )
    total = _q_mm(width) + term
    values = {
        "width": mm_text(_q_mm(width)),
        "door_term": mm_text(term),
        "door_basis": basis,
        "total": mm_text(total),
        "limit": mm_text(_q_mm(limit)),
    }
    status: Literal["pass", "violated"] = "pass" if total <= _q_mm(limit) + 1e-6 else "violated"
    return Outcome(status, values, [values] if status == "violated" else [], ["computed"])


def fits_site_extent(facts: ConceptFacts, params: dict[str, Any]) -> Outcome:
    """The massing's depth or height fits ``site.alcove_depth`` / ``site.alcove_height``."""
    axis = str(params.get("axis", "depth"))
    key = str(params.get("site_key", f"alcove_{axis}"))
    limit = _site_length(facts.card, key)
    if limit is None:
        return _skip(f"no {key.replace('_', ' ')} on the card (site.{key})")
    size = facts.computed.get(axis)
    if size is None:
        return _skip("no massing to measure")
    values = {"size": mm_text(_q_mm(size)), "limit": mm_text(_q_mm(limit))}
    ok = _q_mm(size) <= _q_mm(limit) + 1e-6
    return Outcome("pass" if ok else "violated", values, [] if ok else [values], ["computed"])


def circuit_available(facts: ConceptFacts, params: dict[str, Any]) -> Outcome:
    """The element current, with headroom, fits the site's circuit.

    An explicit ``site.circuit`` (``240V-13A``) is checked directly; otherwise the region
    table picks the smallest class (``calckit.power.circuit_for_power``). An unknown region
    is a warning, never a failure.
    """
    from napkin2factory.calckit import power as pw

    power = facts.extra.get("power")
    if power is None:
        return _skip(
            "no power to check: give envelope.power, or envelope.heat_up_time with the "
            "chamber and insulation"
        )
    headroom = float(params.get("headroom", pw.CIRCUIT_HEADROOM_MIN))
    relies = ["estimate"]
    circuit = facts.card.site.get("circuit")
    region = facts.card.site.get("region")
    parsed = parse_circuit(circuit) if isinstance(circuit, str) else None
    values: dict[str, Any] = {
        "power": _power_text(power),
        "margin": f"{(headroom - 1) * 100:.0f} %",
        "region": region,
    }
    if parsed is not None:
        volts, amps = parsed
        current = pw.element_current(power, volts)
        needed = headroom * float(current.to("A").magnitude)
        values.update(
            current=f"{float(current.to('A').magnitude):.1f} A at {volts.magnitude:g} V",
            needed=f"{needed:.1f} A",
            circuit=f"the {circuit} circuit on site",
        )
        if needed <= float(amps.to("A").magnitude) + 1e-9:
            values["circuit"] = f"fits the {circuit} circuit on site"
            return Outcome("pass", values, [], relies)
        return Outcome("violated", values, [values], relies)
    if not isinstance(region, str) or not region.strip():
        return _skip("no supply on the card (site.circuit like 240V-13A, or site.region)")
    verdict = pw.circuit_for_power(region, power, headroom=headroom)
    if verdict.status == "unknown_region":
        return Outcome("warn", values, [], relies)
    amps_now = float(verdict.current.to("A").magnitude)
    values.update(current=f"{amps_now:.1f} A", needed=f"{headroom * amps_now:.1f} A")
    if verdict.status == "ok":
        values["circuit"] = f"needs {_article(verdict.label)} {verdict.label}"
        return Outcome("pass", values, [], relies)
    values["circuit"] = f"any circuit on file for {region}"
    return Outcome("violated", values, [values], relies)


def mass_vs_lift_class(facts: ConceptFacts, params: dict[str, Any]) -> Outcome:
    """How the mass can be moved (HSE guideline classes, ``calckit.mass_cost.lift_class``).

    Against ``site.lift_class`` when the card names one; otherwise anything beyond a
    two-person lift is flagged.
    """
    from napkin2factory.calckit import mass_cost

    mass, label = facts.estimates.get("total_mass"), "estimate"
    if mass is None:
        mass, label = facts.computed.get("mass"), "computed"
    if mass is None:
        return _skip("no mass: give each massing call a material")
    verdict = mass_cost.lift_class(mass)
    kg = float(mass.to("kg").magnitude)
    values: dict[str, Any] = {
        "mass": f"{kg:.0f} kg",
        "handling": LIFT_WORDS.get(verdict.label, verdict.label),
        "lighter": "",
    }
    allowed = facts.card.site.get("lift_class")
    if isinstance(allowed, str) and allowed in LIFT_ORDER:
        limit = allowed
    else:
        limit = "two-person"
    over = (
        LIFT_ORDER.index(verdict.label) > LIFT_ORDER.index(limit)
        if verdict.label in LIFT_ORDER
        else False
    )
    if not over:
        return Outcome("pass", values, [], [label])
    values["lighter"] = LIFT_WORDS[limit].split(" (")[0].removeprefix("a ")
    return Outcome("violated", values, [values], [label])


def _material_class(material: str | None) -> str:
    name = (material or "").lower()
    if "stainless" in name:
        return "stainless-steel"
    if "alumin" in name:
        return "aluminium"
    return "mild-steel"


#: Reveal used for a ``fit_to`` panel or plate when neither the call nor the card's style
#: gives one (the kit's own default, ``style.yaml`` schema default).
DEFAULT_REVEAL_MM = 2.0


def _reveal_mm(args: Any, card_style: dict[str, Any] | None) -> float:
    """The reveal a ``fit_to`` call is cut with: its own, else the card's style, else 2 mm."""
    if getattr(args, "reveal", None) is not None:
        return float(args.reveal)
    raw = (card_style or {}).get("reveal")
    if raw is not None:
        from napkin2factory.core.units import parse_quantity

        try:
            return _q_mm(raw if is_quantity(raw) else parse_quantity(raw, "mm"))
        except Exception:  # noqa: S110 - an unreadable sketch value falls back to the default
            pass
    return DEFAULT_REVEAL_MM


def sheet_blank(
    piece: MassingPiece, card_style: dict[str, Any] | None = None
) -> tuple[float, float] | None:
    """Developed blank (mm) of a sheet-metal massing call, ``None`` for other kits.

    enclosure: ``(length + 2·height) × (width + 2·height)``; bracket_l:
    ``(length + height) × width``; plate: ``width × depth``; panel: ``width × height``.
    A plate or panel sized by ``fit_to`` (no width) is the opening less ``2 × reveal``
    (the call's ``reveal``, else the card's ``style.reveal``, else 2 mm). Bend allowances
    are ignored (envelope grade).
    """
    a = piece.args
    if piece.kit in ("plate", "panel") and getattr(a, "fit_to", None) is not None:
        r = _reveal_mm(a, card_style)
        return (a.fit_to.width - 2 * r, a.fit_to.height - 2 * r)
    if piece.kit == "enclosure":
        return (a.length + 2 * a.height, a.width + 2 * a.height)
    if piece.kit == "bracket_l":
        return (a.length + a.height, a.width)
    if piece.kit == "plate":
        return (a.width, a.depth)
    if piece.kit == "panel":
        return (a.width, a.height)
    return None


def blank_vs_stock_sheet(facts: ConceptFacts, params: dict[str, Any]) -> Outcome:
    """Every sheet-metal call's developed blank fits a stock sheet (``stock_sheet_fits``)."""
    from napkin2factory.calckit import load_table, mass_cost

    if facts.massing is None:
        return _skip("no massing to measure")
    violations: list[dict[str, Any]] = []
    fits: list[str] = []
    unknown: list[str] = []
    for piece in facts.massing.pieces:
        blank = sheet_blank(piece, facts.card.style)
        if blank is None:
            continue
        mclass = _material_class(piece.material)
        verdict = mass_cost.stock_sheet_fits(
            (Quantity(blank[0], "mm"), Quantity(blank[1], "mm")), mclass
        )
        size = f"{max(blank):.0f} × {min(blank):.0f} mm"
        if not verdict.known:
            unknown.append(f"{piece.name}: {verdict.message}")
        elif verdict.fits:
            fits.append(f"{piece.name} {size} on {verdict.sheet}")
        else:
            rows = [r for r in load_table("stock_sheets") if r["material_class"] == mclass]
            largest = max(rows, key=lambda r: float(r["width_mm"]) * float(r["length_mm"]))
            violations.append(
                {"call": piece.name, "blank": size, "material": mclass, "largest": largest["label"]}
            )
    if violations:
        return Outcome("violated", {}, violations, ["computed"])
    if unknown:
        return Outcome("warn", {}, [], ["computed"], message="; ".join(unknown))
    if not fits:
        return _skip("no sheet-metal massing calls (enclosure, bracket_l, panel, plate)")
    return Outcome("pass", {"detail": "; ".join(fits)}, [], ["computed"])


def walls_fit_envelope(facts: ConceptFacts, params: dict[str, Any]) -> Outcome:
    """``chamber + 2 × insulation ≤ body`` on each axis.

    The body is the massing call named ``body``, else the call with the largest bounding
    box; the insulation is every layer's clearance plus thickness, per side.
    """
    chamber = facts.extra.get("chamber")
    wall = facts.extra.get("wall")
    if chamber is None or wall is None:
        return _skip("no envelope.chamber with envelope.insulation on the card")
    if facts.massing is None or not facts.massing.pieces:
        return _skip("no massing to measure")
    body = facts.massing.piece("body") or max(
        facts.massing.pieces, key=lambda p: p.size[0] * p.size[1] * p.size[2]
    )
    wall_mm = _q_mm(wall)
    violations = []
    for i, axis in enumerate(AXES):
        c = _q_mm(chamber[i])
        needed, outer = c + 2 * wall_mm, body.size[i]
        if needed > outer + 1e-6:
            violations.append(
                {
                    "axis": axis,
                    "needed": mm_text(needed),
                    "chamber": mm_text(c),
                    "wall": mm_text(wall_mm),
                    "call": body.name,
                    "outer": mm_text(outer),
                }
            )
    if violations:
        return Outcome("violated", {}, violations, ["computed"])
    needed_txt = " × ".join(f"{_q_mm(chamber[i]) + 2 * wall_mm:.0f}" for i in range(3)) + " mm"
    outer_txt = " × ".join(f"{body.size[i]:.0f}" for i in range(3)) + " mm"
    values = {"wall": mm_text(wall_mm), "needed": needed_txt, "call": body.name, "outer": outer_txt}
    return Outcome("pass", values, [], ["computed"])


def _face(text: str, default: str = "") -> str:
    words = set(re.split(r"[\s\-_/]+", text.strip().lower()))
    for face in (
        "top",
        "above",
        "below",
        "under",
        "bottom",
        "front",
        "back",
        "rear",
        "left",
        "right",
    ):
        if face in words:
            return {"above": "top", "under": "below", "bottom": "below", "rear": "back"}.get(
                face, face
            )
    return default


def controls_not_adjacent_hot_face(facts: ConceptFacts, params: dict[str, Any]) -> Outcome:
    """Controls not on the top, nor on the door's face beside or above it.

    The door's face is ``layout.load`` (default front) for a hinged or front door, the top
    for a lid. Controls below the door are fine.
    """
    controls = str(facts.card.layout.get("controls", "")).strip()
    door = str(facts.card.layout.get("door", "")).strip()
    if not controls or not door:
        return _skip("no layout.controls and layout.door to compare")
    door_face = (
        "top"
        if _face(door) == "top" or "lid" in door.lower()
        else _face(str(facts.card.layout.get("load", "")), "front")
    )
    where = _face(controls)
    values = {"controls": controls, "door": door, "where": ""}
    if where == "top":
        values["where"] = "above"
    elif where == door_face and where != "below":
        values["where"] = "beside"
    if values["where"]:
        return Outcome("violated", values, [values], [])
    return Outcome("pass", values, [], [])


CONCEPT_CHECKS: dict[str, CheckFn] = {
    "fits_site_width": fits_site_width,
    "fits_site_extent": fits_site_extent,
    "circuit_available": circuit_available,
    "mass_vs_lift_class": mass_vs_lift_class,
    "blank_vs_stock_sheet": blank_vs_stock_sheet,
    "walls_fit_envelope": walls_fit_envelope,
    "controls_not_adjacent_hot_face": controls_not_adjacent_hot_face,
}


def _power_text(power: Qty) -> str:
    w = float(power.to("W").magnitude)
    return f"{w / 1000:.3g} kW" if w >= 1000 else f"{w:.0f} W"


def _article(label: str | None) -> str:
    return "an" if (label or "x")[0] in "8aeiouAEIOU" or (label or "").startswith("11") else "a"


def concept_packs(packs: list[RulePack] | None = None) -> list[RulePack]:
    """The shipped packs that apply to concept cards (``applies_to: {scope: concept}``)."""
    return [
        p
        for p in (packs if packs is not None else load_packs())
        if p.applies_to.get("scope") == CONCEPT_SCOPE
    ]


def rule_params(rule_id: str, packs: list[RulePack] | None = None) -> dict[str, Any]:
    """The YAML ``params`` of one concept rule (empty when the rule is absent)."""
    for pack in concept_packs(packs):
        for rule in pack.rules:
            if rule.get("id") == rule_id:
                return dict(rule.get("params") or {})
    return {}


def run_concept_rules(
    card: ConceptCard,
    computed: dict[str, Any],
    estimates: dict[str, Any],
    massing: MassingResult | None = None,
    extra: dict[str, Any] | None = None,
    packs: list[RulePack] | None = None,
) -> list[RuleRow]:
    """Evaluate every concept rule on one card; one :class:`RuleRow` per rule."""
    facts = ConceptFacts(card, computed, estimates, massing, dict(extra or {}))
    rows: list[RuleRow] = []
    for pack in concept_packs(packs):
        for rule in pack.rules:
            rid = str(rule["id"])
            title = str(rule.get("title", rid))
            severity: Literal["fail", "warn"] = (
                "warn" if str(rule.get("severity", "fail")) == "warn" else "fail"
            )
            fn = CONCEPT_CHECKS.get(str(rule.get("check")))
            if fn is None:
                rows.append(
                    RuleRow(
                        id=rid,
                        title=title,
                        severity=severity,
                        status="skip",
                        message=f"unknown check {rule.get('check')!r} in {pack.path.name}",
                    )
                )
                continue
            out = fn(facts, dict(rule.get("params") or {}))
            if out.status == "skip":
                status, message = "skip", out.message or "not checked"
            elif out.status == "violated":
                template = str(rule.get("message", rid))
                status = severity
                message = "; ".join(_fmt(template, v) for v in out.violations) or _fmt(
                    template, out.values
                )
            elif out.status == "warn":
                status = "warn"
                message = out.message or _fmt(
                    str(rule.get("warn_message", rule.get("message", rid))), out.values
                )
            else:
                status = "pass"
                message = out.message or _fmt(str(rule.get("pass_message", "ok")), out.values)
            relies = sorted({r for r in out.relies_on if r in ("computed", "estimate")})
            rows.append(
                RuleRow(
                    id=rid,
                    title=title,
                    severity=severity,
                    status=status,  # type: ignore[arg-type]
                    message=message,
                    relies_on=relies,  # type: ignore[arg-type]
                )
            )
    return rows


__all__ = [
    "CONCEPT_CHECKS",
    "ConceptFacts",
    "Outcome",
    "concept_packs",
    "door_swing_term",
    "parse_circuit",
    "rule_params",
    "run_concept_rules",
    "sheet_blank",
]
