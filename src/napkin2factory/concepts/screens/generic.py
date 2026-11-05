"""The system's generic screens (F8): what any product's card can be screened for.

* **fits-the-space** — the rough shapes' size, volume and mass, and the width a hinged door
  takes beside its hinge when the card names one (``layout.door``, a massing call named
  ``door`` or ``envelope.door_width``); its rules (``fits-site-*``) hold them against
  ``site.width``, ``site.depth`` and ``site.height`` (the space it must fit; ``alcove_*``
  read as aliases for one version, F16). A card with no door gets no door words (S-137).
* **total mass** — the rough shapes plus what other screens add (``values.mass_items``).
* **cost band** — the rough shapes and other screens' ``cost_items`` priced per process
  (per kilogram, per metre of the longest side, per square metre of the biggest face, or per
  item), held against ``site.budget`` when the card gives one (S-207, B-0211).
* **mass-vs-lift** — how the total can be lifted and moved (``site.lift_class``).
* **mass-limit** — the total mass held against ``site.mass_limit``: a failing row over it,
  amber within 10 % of it (:mod:`.mass_limit`, S-233).
* **blank-vs-stock-sheet** — every folded sheet's flat blank on a stock sheet (a rule only).
* **walls-fit-envelope** — an inner size plus two walls inside the body, when a screen of
  the product gives them (``values.shared["inner_size"]``, ``["wall"]``; a rule only).
* **structural** — sag, yield, buckling and tip-over under the loads a card gives on its
  ``site`` (:mod:`.structural`; W4).

Their rule rows are the ``concept-v0`` pack's (``rulepacks/concept-v0.yaml``). A screen
only a product needs lives in that product's ``model/screens/`` (F10).
"""

from __future__ import annotations

from typing import Any

from napkin2factory.concepts.screens.base import (
    TO_CHECK,
    CardField,
    ScreenValues,
    and_,
    fmt,
    owner_names,
    reads,
    the,
)
from napkin2factory.concepts.screens.mass_limit import MASS_LIMIT, MASS_LIMIT_SCREEN
from napkin2factory.concepts.screens.structural import STRUCTURAL
from napkin2factory.core.domain import Screen
from napkin2factory.core.model.concepts import ConceptCard, Label, RuleRow
from napkin2factory.core.units import Quantity

#: The space it must fit (F8); ``alcove_*`` are the v0.4 keys, read for one version. Their
#: words say ``{space}``: "the space", or the product's own word for it (S-137).
SITE_WIDTH = CardField(
    "site", "width", "mm", "a length", "800 mm", "the {space} width", ("alcove_width",)
)
SITE_DEPTH = CardField(
    "site", "depth", "mm", "a length", "600 mm", "the {space} depth", ("alcove_depth",)
)
SITE_HEIGHT = CardField(
    "site", "height", "mm", "a length", "1400 mm", "the {space} height", ("alcove_height",)
)
#: The door-swing term's fields: read when the card names a door, never suggested on a new
#: card (``hint=False``), so a product without a door is not asked about one (S-137).
DOOR_LAYOUT = CardField(
    "layout",
    "door",
    None,
    "words",
    "hinged-left",
    "how the door opens (hinged-left, sliding…)",
    hint=False,
)
DOOR_SWING = CardField(
    "envelope",
    "door_swing",
    "degree",
    "an angle",
    "110 degree",
    "how far the door opens",
    hint=False,
)
DOOR_WIDTH = CardField(
    "envelope", "door_width", "mm", "a length", "600 mm", "the door width", hint=False
)
LIFT_CLASS = CardField(
    "site", "lift_class", None, "words", "two-person", "how it may be lifted (one-person…)"
)
#: What the owner will spend; the cost band is held against it (S-207).
BUDGET = CardField("site", "budget", "USD", "a money amount", "1600 USD", "the budget")
#: Parameters the door term seeds at promotion (S-085): the leaf that swings and the room it
#: takes beside the hinge (``door_width`` seeds ``door-width`` the usual way).
DOOR_LEAF_PARAM = "door-leaf-width"
DOOR_ROOM_PARAM = "door-swing-clearance"


def site_length(card: ConceptCard, field: CardField) -> Any | None:
    """The card's length for ``field`` (or its alias) in mm units, else None."""
    return field.quantity(card)


def _door_words(door: str, basis: str, term: float, angle: float | None) -> str:
    """Where the width with the door open comes from, in the owner's words."""
    if door not in ("hinged-left", "hinged-right"):
        return f"the body only: a {door.replace('-', ' ')} door swings nothing beside it"
    leaf = "the door (its width on the card)" if "on the card" in basis else "the door leaf"
    if angle is not None:
        if term <= 0:
            return f"the body only: {leaf} opens to {angle:g}°, so it stays in front of the body"
        return f"the body plus what {leaf}, opened to {angle:g}°, reaches past the hinge"
    if term <= 0:
        return (
            "the body only: the card gives no door shape or door width, so the open door "
            "is not counted"
        )
    return f"the body plus {leaf} swung fully back beside the hinge"


@reads(SITE_WIDTH, SITE_DEPTH, SITE_HEIGHT, DOOR_LAYOUT, DOOR_SWING, DOOR_WIDTH, phase="measure")
def fits_the_space(card: ConceptCard, massing: Any, values: ScreenValues) -> list[RuleRow]:
    """Size, volume and mass of the rough shapes, and the open door's width beside them."""
    from napkin2factory.rulepacks.concept_checks import (
        HINGED,
        door_leaf,
        door_swing_angle,
        door_swing_term,
        rule_params,
    )

    if massing is None or not massing.pieces:
        return []
    comp, notes = values.computed, values.notes
    w, d, h = massing.size
    for name, value, axis in (("width", w, "x"), ("depth", d, "y"), ("height", h, "z")):
        comp.add(
            name,
            Quantity(value, "mm"),
            fmt(Quantity(value, "mm"), "mm"),
            "measured across the rough shapes",
            f"massing bounding box ({axis})",
        )
    vol = Quantity(massing.volume, "mm**3")
    comp.add(
        "volume",
        vol,
        fmt(vol, "L"),
        "the space the rough shapes fill",
        "sum of the massing silhouettes",
    )
    if massing.mass is not None:
        m = Quantity(massing.mass, "kg")
        comp.add(
            "mass",
            m,
            fmt(m, "kg"),
            "from the rough shapes and their materials",
            "silhouette volume × density per call; frames and tubes by member section "
            "× cut length (geometry/materials.py)",
        )
    else:
        shapes = owner_names(list(massing.without_material))
        verb = "has" if len(shapes) == 1 else "have"
        notes.append(
            f"{the(shapes)} {verb} no material yet, so the rough shapes have no mass: "
            "give them a material to weigh them"
        )
    guessed = [
        p.name for p in massing.pieces if (p.density_source or "").startswith("unknown material")
    ]
    if guessed:  # the massing weighs an unlisted material as mild steel (S-186, S-233)
        from napkin2factory.geometry.materials import known_material_names

        shapes = owner_names(guessed)
        verb = "has" if len(shapes) == 1 else "have"
        notes.append(
            f"{the(shapes)} {verb} a material the tool does not know, so "
            f"{'it is' if len(shapes) == 1 else 'they are'} weighed as mild steel; "
            f"known materials: {', '.join(known_material_names())}"
        )
    door = str(card.layout.get("door", "") or "").strip().lower()
    if not door or door == "none":  # no door on the card: no door row (review gate B, C11)
        return []
    factor = float(rule_params("fits-site-width").get("door_swing_factor", 1.0))
    term, basis = door_swing_term(card, massing, factor)
    angle = door_swing_angle(card)
    foot = Quantity(w + term, "mm")
    comp.add(
        "footprint_with_door_swing",
        foot,
        fmt(foot, "mm"),
        _door_words(door, basis, term, angle),
        f"width + open door ({basis})",
    )
    leaf = door_leaf(card, massing) if door in HINGED else None
    if leaf is not None:
        # the leaf to 0.1 mm (the precision of the massing), so promotion bounds the space
        # with the raw numbers, not the difference of two rounded ones (S-085)
        comp.add(
            "door_leaf",
            Quantity(leaf[0], "mm"),
            f"{leaf[0]:.1f} mm",
            "the width of the door that swings open",
            "massing call `door`, x-extent"
            if "on the card" not in leaf[1]
            else "envelope.door_width",
        )
    if door in HINGED and angle is None and term > 0:
        notes.append(
            "the card does not say how far the door opens, so the open door is "
            "counted swung fully back against the wall (the widest case); give its "
            "opening angle (like 110 degree) to count only what it really needs"
        )
    return []


@reads(phase="total")
def total_mass(card: ConceptCard, massing: Any, values: ScreenValues) -> list[RuleRow]:
    """The rough shapes' mass plus every ``mass_items`` entry other screens added."""
    mass = values.computed.raw.get("mass")
    if mass is None or not values.mass_items:
        return []
    total = mass
    for kg, _words, _ref in values.mass_items:
        total = total + kg
    total = total.to("kg")
    values.estimate.add(
        "total_mass",
        total,
        fmt(total, "kg"),
        "the rough shapes plus " + and_([w for _, w, _ in values.mass_items]),
        "massing mass + " + " + ".join(r for _, _, r in values.mass_items),
    )
    return []


def piece_extent(piece: Any) -> tuple[float, float]:
    """A rough shape's longest side (mm) and the area of its biggest face (mm²).

    What a band per metre (``per_m``) or per square metre (``per_m2``) multiplies: the length
    of a bought-by-the-metre tube or extrusion, the face of a routed or cut sheet (B-0211,
    S-230). The bounding box stands in for the shape, so a slanted member counts a little
    short and an L-shaped sheet its box; the band is a range already.
    """
    a, b, _ = sorted(piece.size, reverse=True)
    return a, a * b


def cost_region(card: ConceptCard, values: ScreenValues) -> tuple[str | None, str | None]:
    """The region the cost bands are read for, and a sentence when a declared one has none.

    The card's own ``site.region`` wins over the product's region, which the runner puts in
    ``values.shared["region"]`` (gate I, B2, S-227). A region the cost bands have no rows
    for at all (a supply region such as ``SA``) is not guessed at: the next declared one is
    used, else ``None`` (the US bands, named as such), and the sentence says so. ``(None,
    None)``: nobody declared a region.
    """
    from napkin2factory.calckit import mass_cost

    on_file = mass_cost.band_regions()
    own = card.site.get("region")
    declared = [
        str(r).strip().upper()
        for r in (own if isinstance(own, str) else None, values.shared.get("region"))
        if r and str(r).strip()
    ]
    skipped = [r for r in declared if r not in on_file]
    usable = [r for r in declared if r in on_file]
    note = None
    if skipped:
        used = f"the {usable[0]} bands" if usable else f"the {mass_cost.DEFAULT_REGION} bands"
        note = (
            f"there are no cost bands for the region {skipped[0]} ({', '.join(on_file)} have "
            f"them), so the cost reads {used}"
        )
    return (usable[0] if usable else None), note


@reads(BUDGET, phase="total")
def cost_band(card: ConceptCard, massing: Any, values: ScreenValues) -> list[RuleRow]:
    """A rough cost range: every rough shape and ``cost_items`` entry priced per process.

    Bands are read for the card's or product's region (:func:`cost_region`); with none
    declared the US bands are read and the line says so. Amounts stay in the band's own
    currency: nothing is converted, and a card whose bands mix currencies is not summed.
    With ``site.budget`` on the card it also returns the ``cost-vs-budget`` row: pass when the
    band's high end is within the budget, fail when its low end is over it, otherwise a
    warning that the budget sits inside the band (S-207).
    """
    from napkin2factory.calckit import mass_cost

    notes = values.notes
    region, region_note = cost_region(card, values)
    if region_note:
        notes.append(region_note)
    shown = region or mass_cost.DEFAULT_REGION
    totals: dict[str, list[float]] = {}
    counted: list[str] = []
    priced: list[str] = []
    unpriced: list[str] = []
    no_material: list[str] = []
    no_band: list[str] = []
    no_band_classes: list[str] = []
    items: list[tuple[str, str, float | None, tuple[float, float] | None]] = []
    bands: list[mass_cost.CostBand] = []
    if massing is not None:
        items += [(p.name, p.process_class, p.mass, piece_extent(p)) for p in massing.pieces]
    items += [(name, pclass, kg, None) for name, pclass, kg in values.cost_items]
    no_size: list[str] = []
    for name, pclass, kg, extent in items:
        try:
            b = mass_cost.cost_band(pclass, region=region)
            c = mass_cost.cost_estimate(
                pclass,
                mass=None if kg is None else Quantity(kg, "kg"),
                length=None if extent is None else Quantity(extent[0], "mm"),
                area=None if extent is None else Quantity(extent[1], "mm**2"),
                region=region,
            )
        except ValueError as exc:
            if "pass mass=" in str(exc):
                no_material.append(name)
            elif any(k in str(exc) for k in ("pass area=", "pass length=")):
                no_size.append(name)
            else:
                raise
            unpriced.append(name)
            continue
        if not c.known or c.low is None or c.high is None:
            no_band.append(name)
            unpriced.append(name)
            if pclass not in no_band_classes:
                no_band_classes.append(pclass)
            continue
        cur = b.currency
        lo_hi = totals.setdefault(cur, [0.0, 0.0])
        lo_hi[0] += float(c.low.to(cur).magnitude)
        lo_hi[1] += float(c.high.to(cur).magnitude)
        counted.append(f"{name}: {pclass}")
        priced.append(name)
        if b.known:
            bands.append(b)
    if no_material:
        notes.append(
            f"the cost leaves out {the(owner_names(no_material))}: no material, so no mass to price"
        )
    if no_size:
        notes.append(
            f"the cost leaves out {the(owner_names(no_size))}: it is bought by the metre or the "
            "square metre and has no rough shape to measure"
        )
    if no_band:
        notes.append(
            f"the cost leaves out {the(owner_names(no_band))}: the {shown} cost bands have no "
            f"price range for how {'it is' if len(no_band) == 1 else 'they are'} made "
            f"({', '.join(no_band_classes)})"
        )
    budget = BUDGET.quantity(card)
    if not counted:
        if budget is not None:
            notes.append("the budget is not checked: nothing could be priced yet")
        return []
    if len(totals) > 1:
        notes.append(
            f"the cost is not added up: its bands are in {and_(sorted(totals))}, and nothing "
            "is converted between currencies"
        )
        return []
    ((currency, (low, high)),) = totals.items()
    basis = mass_cost.bands_words(bands, declared=region is not None)
    values.shared["cost_basis"] = basis
    ref = "mass_cost.cost_estimate (" + "; ".join(counted) + ") [verify]"
    words = f"rough cost of the {and_(owner_names(priced))} from the {basis}"
    if unpriced:
        left = owner_names(unpriced)
        verb = "is" if len(left) == 1 else "are"
        names = " and the ".join(left) if len(left) < 3 else and_(left)
        words += f"; the {names} {verb} not counted"
    words += f"; {TO_CHECK}"
    q_low, q_high = Quantity(low, currency), Quantity(high, currency)
    values.estimate.add("cost_low", q_low, fmt(q_low, currency), words, ref)
    values.estimate.add("cost_high", q_high, fmt(q_high, currency), words, ref)
    if budget is None:
        return []
    if currency != "USD":
        notes.append(
            f"the budget is not checked: it is in USD and the {shown} bands are in {currency} "
            "(nothing is converted)"
        )
        return []
    values.given.add("budget", budget, fmt(budget, "USD"), "on the card", "site.budget")
    return [_budget_row(low, high, float(budget.to("USD").magnitude))]


def _budget_row(low: float, high: float, budget: float) -> RuleRow:
    """The ``cost-vs-budget`` row: the cost band held against the budget (S-207)."""
    lo, hi, bud = (fmt(Quantity(x, "USD"), "USD") for x in (low, high, budget))
    title = "Within the budget"
    relies: list[Label] = ["given", "estimate"]
    if high <= budget:
        msg = f"the cost, {lo} to {hi}, is within the {bud} budget"
        return RuleRow(
            id="cost-vs-budget", title=title, severity="fail", status="pass",
            message=msg, relies_on=relies,
        )  # fmt: skip
    if low > budget:
        msg = f"even the low end of the cost, {lo}, is over the {bud} budget"
        return RuleRow(
            id="cost-vs-budget", title=title, severity="fail", status="fail",
            message=msg, relies_on=relies,
        )  # fmt: skip
    msg = f"the {bud} budget sits inside the cost band, {lo} to {hi}"
    return RuleRow(
        id="cost-vs-budget", title=title, severity="warn", status="warn",
        message=msg, relies_on=relies,
    )  # fmt: skip


@reads(LIFT_CLASS, MASS_LIMIT, phase="total")
def mass_vs_lift(card: ConceptCard, massing: Any, values: ScreenValues) -> list[RuleRow]:
    """How the total (else the rough shapes') mass can be lifted (HSE guideline classes)."""
    from napkin2factory.calckit import mass_cost

    lift_mass = values.estimate.raw.get("total_mass", values.computed.raw.get("mass"))
    if lift_mass is None:
        return []
    verdict = mass_cost.lift_class(lift_mass)
    values.estimate.add(
        "lift_class",
        verdict.label,
        verdict.label,
        f"from the mass and the lifting limits; {TO_CHECK}",
        "mass_cost.lift_class (HSE guideline weights) [verify]",
    )
    return []


@reads(phase="check")
def blank_vs_stock_sheet(card: ConceptCard, massing: Any, values: ScreenValues) -> list[RuleRow]:
    """Reads only the rough shapes; its row is the pack's ``blank-vs-stock-sheet``."""
    return []


@reads(phase="check")
def walls_fit_envelope(card: ConceptCard, massing: Any, values: ScreenValues) -> list[RuleRow]:
    """Reads what another screen shares; its row is the pack's ``walls-fit-envelope``."""
    return []


#: The generic screens, in the order they run within a phase.
GENERIC_SCREENS: tuple[Screen, ...] = (
    Screen("fits-the-space", fits_the_space, title="Fits the space"),
    Screen("total-mass", total_mass, title="Total mass"),
    Screen("cost-band", cost_band, title="Cost band"),
    Screen("mass-vs-lift", mass_vs_lift, title="How it can be lifted"),
    MASS_LIMIT_SCREEN,
    Screen("blank-vs-stock-sheet", blank_vs_stock_sheet, title="Sheets fit stock sizes"),
    Screen("walls-fit-envelope", walls_fit_envelope, title="Walls fit the body"),
    STRUCTURAL,
)

__all__ = [
    "DOOR_LEAF_PARAM",
    "DOOR_ROOM_PARAM",
    "DOOR_SWING",
    "DOOR_WIDTH",
    "GENERIC_SCREENS",
    "MASS_LIMIT",
    "SITE_DEPTH",
    "SITE_HEIGHT",
    "SITE_WIDTH",
    "site_length",
]
