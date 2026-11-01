"""The hinged door's swing: the parameters and terms the alcove requirements read (S-085)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from napkin2factory.concepts.promote.common import (
    _lv_quantity,
    _q_text,
    _slug,
)
from napkin2factory.concepts.screens import generic
from napkin2factory.core.model.concepts import ConceptCard
from napkin2factory.core.units import is_quantity


def _site_length(card: ConceptCard, field: Any) -> Any:
    v: Any = field.raw(card)
    if is_quantity(v):
        try:
            return v.to("mm")
        except Exception:  # pint DimensionalityError: not a length
            return None
    return None


#: Parameters promotion seeds for the alcove requirements (S-085): the leaf that swings
#: (unless the card gives ``envelope.door_width``, seeded under its own name) and the room it
#: takes beside the hinge, an expression over the leaf. The fits-the-space screen names them.
DOOR_LEAF_PARAM = generic.DOOR_LEAF_PARAM
DOOR_ROOM_PARAM = generic.DOOR_ROOM_PARAM
DOOR_ROW_TITLE = "The open door keeps to its room beside the hinge"
_SEED_WORDS = {
    DOOR_LEAF_PARAM: ": the width of the door that swings open; write it as an expression "
    "over the door's own parameters so the alcove requirements follow the designed door",
    DOOR_ROOM_PARAM: ": the room the open door takes beside the hinge",
}


@dataclass
class DoorSwing:
    """The open door beside the hinge, from the raw screening value and the card's angle."""

    leaf: Any  # the leaf width (mm), as screening measured it
    factor: float  # max(0, −cos θ), or the rule's factor when the card gives no angle
    angle: float | None  # degrees
    leaf_param: str  # the parameter the room is an expression over
    basis: str  # the screening's own words for it

    @property
    def factor_text(self) -> str:
        """The factor as written in the expression (6 significant digits)."""
        return f"{self.factor:.6g}"

    @property
    def expr(self) -> str:
        """``door-leaf-width * 0.34202`` (or the leaf alone when the factor is 1)."""
        if self.factor_text == "1":
            return self.leaf_param
        return f"{self.leaf_param} * {self.factor_text}"

    @property
    def term(self) -> Any:
        """The room beside the hinge, unrounded: what the expression evaluates to."""
        return (self.leaf * float(self.factor_text)).to("mm")

    @property
    def allowance(self) -> Any:
        """The room rounded *up* to 0.1 mm once, so the expression never exceeds it."""
        from napkin2factory.core.units import Quantity

        raw = float(self.term.magnitude)
        return Quantity(math.ceil(round(raw * 10, 6)) / 10, "mm")

    def words(self) -> str:
        """``702.4 mm × max(0, −cos 110°) = 240.235 mm``, for the rationale."""
        leaf, term = _q_text(self.leaf), _q_text(self.term)
        if self.angle is not None:
            return f"{leaf} × max(0, −cos {self.angle:g}°) = {term}"
        if self.factor_text == "1":
            return f"{leaf}, the leaf swung fully back (the card gives no opening angle)"
        return f"{leaf} × {self.factor_text} = {term} (the card gives no opening angle)"


def door_swing(card: ConceptCard) -> DoorSwing | None:
    """The hinged door's leaf (raw) and factor, ``None`` when there is nothing to seed.

    The leaf is the screening's ``door_leaf`` value (0.1 mm, the massing's precision), or
    the card's ``envelope.door_width``; cards screened before it was recorded have neither
    and fall back to :func:`door_swing_term`'s difference.
    """
    from napkin2factory.rulepacks.concept_checks import (
        HINGED,
        door_swing_angle,
        rule_params,
        swing_factor,
    )

    sc = card.screening
    door = str(card.layout.get("door", "") or "").strip().lower()
    if sc is None or door not in HINGED:
        return None
    leaf_param = DOOR_LEAF_PARAM
    leaf = _lv_quantity(sc.computed.get("door_leaf"))
    on_card = card.envelope.get("door_width")
    if is_quantity(on_card) and "door_width" in card.envelope:
        leaf, leaf_param = on_card, _slug(generic.DOOR_WIDTH.key)
    if leaf is None:
        return None
    try:
        leaf = leaf.to("mm")
    except Exception:  # pint DimensionalityError: not a length
        return None
    angle = door_swing_angle(card)
    default = float(rule_params("fits-site-width").get("door_swing_factor", 1.0))
    foot = sc.computed.get("footprint_with_door_swing")
    basis = (
        (foot.ref or foot.source).removeprefix("width + open door (").removesuffix(")")
        if foot is not None
        else "the door leaf"
    )
    return DoorSwing(leaf, swing_factor(angle, default), angle, leaf_param, basis)


def door_seeds(card: ConceptCard) -> list[tuple[str, Any, str, str | None]]:
    """``(name, quantity, source, expr)`` for the door parameters the alcove rows read.

    Only for a card with an alcove width and a hinged door that reaches past the hinge.
    """
    ds = door_swing(card)
    if ds is None or ds.factor <= 0 or _site_length(card, generic.SITE_WIDTH) is None:
        return []
    out: list[tuple[str, Any, str, str | None]] = []
    if ds.leaf_param == DOOR_LEAF_PARAM:
        out.append((DOOR_LEAF_PARAM, ds.leaf, "screening: the door that swings open", None))
    out.append((DOOR_ROOM_PARAM, ds.term, f"screening: {ds.words()}", ds.expr))
    return out


def door_swing_term(card: ConceptCard) -> tuple[Any, str]:
    """The screening's door-swing term (mm) and its basis.

    From the raw leaf and the card's angle (:func:`door_swing`) when the screening recorded
    the leaf (S-085: never the difference of two rounded values); otherwise, for cards
    screened before, ``footprint_with_door_swing − width`` from the card's computed values
    (0 when the door is not hinged). The basis is the footprint's engineering ``ref`` (its
    ``source`` on cards screened before review gate B).
    """
    from napkin2factory.core.units import Quantity

    sc = card.screening
    assert sc is not None
    ds = door_swing(card)
    if ds is not None:
        return ds.term, ds.basis
    foot = sc.computed.get("footprint_with_door_swing")
    width = _lv_quantity(sc.computed.get("width"))
    footq = _lv_quantity(foot)
    door = str(card.layout.get("door", "") or "").strip().lower()
    if foot is None and door in ("", "none"):
        return Quantity(0.0, "mm"), "no door on the card: nothing swings beside the body"
    if foot is None or width is None or footq is None:
        return Quantity(0.0, "mm"), "no footprint in the screening: no door swing counted"
    term = (footq - width).to("mm")
    basis = (foot.ref or foot.source).removeprefix("width + open door (").removesuffix(")")
    return term, basis
