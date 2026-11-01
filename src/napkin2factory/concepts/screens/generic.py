"""The system's generic screens (F8): what any product's card can be screened for.

* **fits-the-space** — the rough shapes' size, volume and mass, and the width a hinged door
  takes beside its hinge when the card names one (``layout.door``, a massing call named
  ``door`` or ``envelope.door_width``); its rules (``fits-site-*``) hold them against
  ``site.width``, ``site.depth`` and ``site.height`` (the space it must fit; ``alcove_*``
  read as aliases for one version, F16). A card with no door gets no door words (S-137).
* **total mass** — the rough shapes plus what other screens add (``values.mass_items``).
* **cost band** — the rough shapes and other screens' ``cost_items`` priced per process.
* **mass-vs-lift** — how the total can be lifted and moved (``site.lift_class``).
* **blank-vs-stock-sheet** — every folded sheet's flat blank on a stock sheet (a rule only).
* **walls-fit-envelope** — an inner size plus two walls inside the body, when a screen of
  the product gives them (``values.shared["inner_size"]``, ``["wall"]``; a rule only).

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
from napkin2factory.core.domain import Screen
from napkin2factory.core.model.concepts import ConceptCard, RuleRow
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
MASS_LIMIT = CardField("site", "mass_limit", "kg", "a mass", "40 kg", "the weight limit")
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


@reads(phase="total")
def cost_band(card: ConceptCard, massing: Any, values: ScreenValues) -> list[RuleRow]:
    """A rough cost range: every rough shape and ``cost_items`` entry priced per process."""
    from napkin2factory.calckit import mass_cost

    notes = values.notes
    low = high = 0.0
    counted: list[str] = []
    priced: list[str] = []
    unpriced: list[str] = []
    no_material: list[str] = []
    no_band: list[str] = []
    items: list[tuple[str, str, float | None]] = []
    if massing is not None:
        items += [(p.name, p.process_class, p.mass) for p in massing.pieces]
    items += values.cost_items
    for name, pclass, kg in items:
        try:
            c = mass_cost.cost_estimate(pclass, mass=None if kg is None else Quantity(kg, "kg"))
        except ValueError:
            no_material.append(name)
            unpriced.append(name)
            continue
        if not c.known or c.low is None or c.high is None:
            no_band.append(name)
            unpriced.append(name)
            continue
        low += float(c.low.to("USD").magnitude)
        high += float(c.high.to("USD").magnitude)
        counted.append(f"{name}: {pclass}")
        priced.append(name)
    if no_material:
        notes.append(
            f"the cost leaves out {the(owner_names(no_material))}: no material, so no mass to price"
        )
    if no_band:
        notes.append(
            f"the cost leaves out {the(owner_names(no_band))}: no price range on file for "
            "how it is made"
        )
    if not counted:
        return []
    ref = "mass_cost.cost_estimate (" + "; ".join(counted) + ") [verify]"
    words = f"rough cost of the {and_(owner_names(priced))} from cost bands per process"
    if unpriced:
        left = owner_names(unpriced)
        verb = "is" if len(left) == 1 else "are"
        names = " and the ".join(left) if len(left) < 3 else and_(left)
        words += f"; the {names} {verb} not counted"
    words += f"; {TO_CHECK}"
    values.estimate.add(
        "cost_low", Quantity(low, "USD"), fmt(Quantity(low, "USD"), "USD"), words, ref
    )
    values.estimate.add(
        "cost_high", Quantity(high, "USD"), fmt(Quantity(high, "USD"), "USD"), words, ref
    )
    return []


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
    Screen("blank-vs-stock-sheet", blank_vs_stock_sheet, title="Sheets fit stock sizes"),
    Screen("walls-fit-envelope", walls_fit_envelope, title="Walls fit the body"),
)

__all__ = [
    "DOOR_LEAF_PARAM",
    "DOOR_ROOM_PARAM",
    "DOOR_SWING",
    "DOOR_WIDTH",
    "GENERIC_SCREENS",
    "SITE_DEPTH",
    "SITE_HEIGHT",
    "SITE_WIDTH",
    "site_length",
]
