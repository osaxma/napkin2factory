"""Named checks behind ``concept-v0.yaml`` and their runner (NAPKIN_STAGE N5, S-022 pattern).

Concept rules screen a *card*, not a part: each check reads a :class:`ConceptFacts` (the
card, the screening's raw ``computed`` and ``estimate`` values, the composed massing, what
screens shared) plus the rule's YAML ``params`` and returns an :class:`Outcome`.
:func:`rule_rows` turns outcomes into :class:`~napkin2factory.core.model.concepts.RuleRow`
rows with the rule's wording; a product's own screen (``model/screens/``, F10) uses it for
its rules too. ``rulepacks.runner.run_rulepacks`` never runs this pack: it iterates
product parts, and no part has ``scope: concept``. The checks here are the generic
screens' (F8): the space, the lift, the sheets, the walls.

Values in ``computed`` and ``estimates`` are pint quantities (or words); a rule row records
which of the two labels it relied on, so a reader can tell geometry from estimate.
"""

from __future__ import annotations

import math
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
    #: Raw values screens hand each other (``ScreenValues.shared``).
    shared: dict[str, Any] = field(default_factory=dict)


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


def kg_text(kg: float) -> str:
    """A mass for the owner: one decimal below 10 kg (``0.4 kg``), else whole (``23 kg``)."""
    return f"{kg:.1f} kg" if abs(kg) < 10 else f"{kg:.0f} kg"


def _q_mm(q: Qty) -> float:
    return float(q.to("mm").magnitude)


def parse_circuit(text: str) -> tuple[Qty, Qty] | None:
    """``240V-13A`` → (240 V, 13 A); ``None`` when the text is not of that form."""
    m = _CIRCUIT_RE.match(text)
    if not m:
        return None
    return Quantity(float(m.group(1)), "V"), Quantity(float(m.group(2)), "A")


def door_swing_angle(card: ConceptCard) -> float | None:
    """The card's door opening angle in degrees (``envelope.door_swing``), else ``None``.

    Only an angle above 0° counts; a missing, unreadable or non-angle value is ``None``, and
    the screen then counts the leaf swung fully back (the widest case).
    """
    v: Any = card.envelope.get("door_swing")
    if not is_quantity(v):
        return None
    try:
        deg = float(v.to("degree").magnitude)
    except Exception:  # pint DimensionalityError: not an angle
        return None
    return deg if deg > 0 else None


def swing_factor(angle_deg: float | None, default: float = 1.0) -> float:
    """Share of the leaf that stands beside the hinge when the door is open.

    A leaf opened by θ about a vertical hinge on the body's edge reaches ``leaf × −cos θ``
    past the hinge side: nothing up to 90°, the whole leaf at 180°. On its way to an angle
    beyond 180° the leaf passes 180°, so the largest reach is counted:
    ``max(0, −cos(min(θ, 180°)))``. With no angle the ``default`` applies (1.0: the leaf
    swung fully back, the conservative case).
    """
    if angle_deg is None:
        return default
    return max(0.0, -math.cos(math.radians(min(angle_deg, 180.0))))


def door_leaf(card: ConceptCard, massing: MassingResult | None) -> tuple[float, str] | None:
    """The width of the leaf that swings (mm) and its words, else ``None``.

    The world x-extent of the massing call named ``door``, else ``envelope.door_width``.
    """
    piece = massing.piece("door") if massing is not None else None
    if piece is not None:
        return piece.size[0], f"the {mm_text(piece.size[0])} door leaf"
    if is_quantity(card.envelope.get("door_width")):
        width = _q_mm(card.envelope["door_width"])
        return width, f"the {mm_text(width)} door (its width on the card)"
    return None


def door_swing_term(
    card: ConceptCard, massing: MassingResult | None, factor: float = 1.0
) -> tuple[float, str]:
    """Width an open hinged door adds beside its hinge side (mm) and how it was found.

    For ``layout.door`` ``hinged-left`` or ``hinged-right`` the open leaf reaches past the
    body on the hinge side by ``leaf × max(0, −cos θ)`` for the card's opening angle θ
    (``envelope.door_swing``, :func:`swing_factor`); a card with no angle counts
    ``factor × leaf`` (1.0 = the leaf swung right back, the conservative case). The leaf
    is the world x-extent of the massing call named ``door``, else ``envelope.door_width``,
    else nothing is added and the basis says so. Any other door (none, sliding, lift-off,
    top lid) adds 0. The basis is in the owner's words (it ends up in rule messages).
    """
    door = str(card.layout.get("door", "")).strip().lower()
    if door not in HINGED:
        return 0.0, f"a {door.replace('-', ' ') or 'missing'} door: nothing swings beside the body"
    found = door_leaf(card, massing)
    if found is None:
        return 0.0, ("the card gives no door shape or door width, so the open door is not counted")
    width, leaf = found
    angle = door_swing_angle(card)
    if angle is not None:
        basis = f"{leaf} opened to {angle:g}°"
        return swing_factor(angle) * width, basis
    basis = f"{leaf} swung fully back; the card does not say how far it opens"
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
    """Footprint width plus the door-swing term fits ``site.width`` (the space's width).

    ``width + door leaf × max(0, −cos θ) ≤ site.width`` for a hinged door opening to θ,
    ``width + door_swing_factor × door leaf`` when the card gives no angle (see
    :func:`door_swing_term`); other doors add nothing.
    """
    from napkin2factory.concepts.screens.generic import SITE_WIDTH

    limit = SITE_WIDTH.quantity(facts.card)
    if limit is None:
        return _skip("no alcove width on the card")
    width = facts.computed.get("width")
    if width is None:
        return _skip("no rough shapes to measure")
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
    door = str(facts.card.layout.get("door", "") or "").strip().lower()
    if status == "pass" and door in ("", "none"):  # no door: say it plainly (gate B, C11)
        msg = f"{values['width']} wide fits the {values['limit']} alcove"
        return Outcome("pass", values, [], ["computed"], message=msg)
    return Outcome(status, values, [values] if status == "violated" else [], ["computed"])


def fits_site_extent(facts: ConceptFacts, params: dict[str, Any]) -> Outcome:
    """The massing's depth or height fits ``site.depth`` / ``site.height``."""
    from napkin2factory.concepts.screens.generic import SITE_DEPTH, SITE_HEIGHT

    axis = str(params.get("axis", "depth"))
    limit = (SITE_HEIGHT if axis == "height" else SITE_DEPTH).quantity(facts.card)
    if limit is None:
        return _skip(f"no alcove {axis} on the card")
    size = facts.computed.get(axis)
    if size is None:
        return _skip("no rough shapes to measure")
    values = {"size": mm_text(_q_mm(size)), "limit": mm_text(_q_mm(limit))}
    ok = _q_mm(size) <= _q_mm(limit) + 1e-6
    return Outcome("pass" if ok else "violated", values, [] if ok else [values], ["computed"])


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
        return _skip("no mass: give each rough shape a material")
    verdict = mass_cost.lift_class(mass)
    kg = float(mass.to("kg").magnitude)
    values: dict[str, Any] = {
        "mass": kg_text(kg),
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
        return _skip("no rough shapes to measure")
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
        return _skip("no folded sheet-metal shapes on the card")
    return Outcome("pass", {"detail": "; ".join(fits)}, [], ["computed"])


def walls_fit_envelope(facts: ConceptFacts, params: dict[str, Any]) -> Outcome:
    """``inner size + 2 × wall ≤ body`` on each axis.

    The inner size (three lengths) and the wall (per side) are what a screen of the product
    shares as ``inner_size`` and ``wall``; without them the rule skips. The body is the
    massing call named ``body``, else the call with the largest bounding box.
    """
    chamber = facts.shared.get("inner_size")
    wall = facts.shared.get("wall")
    if chamber is None or wall is None:
        return _skip("no chamber and insulation on the card")
    if facts.massing is None or not facts.massing.pieces:
        return _skip("no rough shapes to measure")
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


CONCEPT_CHECKS: dict[str, CheckFn] = {
    "fits_site_width": fits_site_width,
    "fits_site_extent": fits_site_extent,
    "mass_vs_lift_class": mass_vs_lift_class,
    "blank_vs_stock_sheet": blank_vs_stock_sheet,
    "walls_fit_envelope": walls_fit_envelope,
}


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


def circuit_headroom(packs: list[RulePack] | None = None) -> float:
    """``headroom`` of a concept rule ``circuit-available`` (``rating ≥ headroom × current``).

    The one supply margin of the napkin stage: a product's supply screen checks it and
    promotion writes the supply requirement as ``power ≤ V·I / headroom`` from the same
    number (review gate A, B1). No shipped pack has the rule (it is a product's, F10), so this
    is :data:`calckit.power.CIRCUIT_HEADROOM_MIN`, the constant a product's screen should
    read too, unless a concept pack passed in says otherwise.
    """
    from napkin2factory.calckit import power as pw

    params = rule_params("circuit-available", packs)
    return float(params.get("headroom", pw.CIRCUIT_HEADROOM_MIN))


def rule_rows(
    rules: list[dict[str, Any]],
    checks: dict[str, CheckFn],
    facts: ConceptFacts,
    source: str = "the pack",
) -> list[RuleRow]:
    """One :class:`RuleRow` per rule, each evaluated by its named check in ``checks``.

    ``rules`` are pack-shaped dicts (id, title, severity, check, params, message,
    pass_message, warn_message). A product's own screen (F10) states its rules the same way
    and calls this.
    """
    rows: list[RuleRow] = []
    for rule in rules:
        rid = str(rule["id"])
        title = str(rule.get("title", rid))
        severity: Literal["fail", "warn"] = (
            "warn" if str(rule.get("severity", "fail")) == "warn" else "fail"
        )
        fn = checks.get(str(rule.get("check")))
        if fn is None:
            rows.append(
                RuleRow(
                    id=rid,
                    title=title,
                    severity=severity,
                    status="skip",
                    message=f"unknown check {rule.get('check')!r} in {source}",
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
        relies = sorted({r for r in out.relies_on if r in ("computed", "estimate", "given")})
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


def run_concept_rules(
    card: ConceptCard,
    computed: dict[str, Any],
    estimates: dict[str, Any],
    massing: MassingResult | None = None,
    shared: dict[str, Any] | None = None,
    packs: list[RulePack] | None = None,
) -> list[RuleRow]:
    """Evaluate every concept pack's rules on one card; one :class:`RuleRow` per rule."""
    facts = ConceptFacts(card, computed, estimates, massing, dict(shared or {}))
    rows: list[RuleRow] = []
    for pack in concept_packs(packs):
        rows += rule_rows(pack.rules, CONCEPT_CHECKS, facts, pack.path.name)
    return rows


__all__ = [
    "CONCEPT_CHECKS",
    "ConceptFacts",
    "Outcome",
    "concept_packs",
    "door_leaf",
    "door_swing_angle",
    "door_swing_term",
    "kg_text",
    "parse_circuit",
    "rule_params",
    "rule_rows",
    "run_concept_rules",
    "sheet_blank",
    "swing_factor",
]
