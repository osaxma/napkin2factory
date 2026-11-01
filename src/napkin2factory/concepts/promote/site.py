"""Step 3: the card's site constraints become requirements on the top assembly (N8)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from napkin2factory.concepts.promote.common import (
    SeededParam,
    _q_text,
)
from napkin2factory.concepts.promote.packs import pack_requirements
from napkin2factory.concepts.promote.swing import (
    DOOR_ROOM_PARAM,
    DOOR_ROW_TITLE,
    _site_length,
    door_swing,
    door_swing_term,
)
from napkin2factory.concepts.screens import SPACE_WORDS, generic
from napkin2factory.core.model.concepts import ConceptCard
from napkin2factory.core.units import is_quantity

#: The ``about`` of the rows that hold the product to the space it must fit (``--json``).
SPACE_ABOUT = "space"


def site_requirements(
    card: ConceptCard,
    seeded: list[SeededParam],
    top: str | None,
    notes: list[str],
    root: Path | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    """``(about, requirement fields)`` for each site constraint on the card.

    The space it must fit, then what the product's own screens seed (``root``'s
    ``model/screens/``, :mod:`.packs`), then the weight. The rows name the space in the
    product's own word (``WORDS`` of its screens, else "space"), and name a door only when
    the card names a hinged one (gate F, S-137).
    """
    from napkin2factory.core.packs import product_words
    from napkin2factory.core.units import Quantity
    from napkin2factory.rulepacks.concept_checks import HINGED

    space = product_words(root).get("space", SPACE_WORDS)
    door = str(card.layout.get("door", "") or "").strip().lower()

    src = f"concept {card.id} site constraint"
    allocation: Any = [f"asm://{top}"] if top else "unallocated"
    out: list[tuple[str, dict[str, Any]]] = []

    def geometry(axis: str, op: str, value: Any) -> dict[str, Any]:
        if top is None:
            return {
                "kind": "manual",
                "note": "there is no assembly yet: check this against the built product, "
                "or re-target it at the top assembly once it exists",
            }
        return {
            "kind": "geometry_prop",
            "target": f"asm://{top}#props.{axis}",
            "op": op,
            "value": _q_text(value),
        }

    width = _site_length(card, generic.SITE_WIDTH)
    seeded_names = {p.name for p in seeded}
    ds = door_swing(card)
    if width is not None and ds is not None and DOOR_ROOM_PARAM in seeded_names:
        # the door is a parameter, not a number frozen in the bound (review gate A, C8;
        # S-085): the closed width gets the space less the door's allowance, and a second
        # row holds the door to that allowance, so a wider or further-opening door fails
        allowance = ds.allowance
        limit = (width - allowance).to("mm")
        room = f"param://{DOOR_ROOM_PARAM}"
        leaf_uri = f"param://{ds.leaf_param}"
        out.append(
            (
                SPACE_ABOUT,
                {
                    "title": f"Fits the {space} with the door open",
                    "statement": f"The closed width plus the {_q_text(allowance)} the open door "
                    f"takes beside the hinge stays within the {_q_text(width)} {space}.",
                    "category": "geometry",
                    "verify": geometry("bbox.x", "<=", limit),
                    "allocation": [f"asm://{top}", room] if top else "unallocated",
                    "rationale": f"{_q_text(width)} − {_q_text(allowance)} = {_q_text(limit)} "
                    f"for the closed width. The open door's room is {DOOR_ROOM_PARAM}: "
                    f"{ds.words()}, held to {_q_text(allowance)} by the requirement "
                    f'"{DOOR_ROW_TITLE}".',
                },
            )
        )
        out.append(
            (
                SPACE_ABOUT,
                {
                    "title": DOOR_ROW_TITLE,
                    "statement": f"The open door takes at most {_q_text(allowance)} beside the "
                    f"hinge, the room the {space} leaves it.",
                    "category": "geometry",
                    "verify": {
                        "kind": "param_bound",
                        "target": room,
                        "op": "<=",
                        "value": _q_text(allowance),
                    },
                    "allocation": [room, leaf_uri],
                    "rationale": f"{DOOR_ROOM_PARAM} is the expression {ds.expr}, so a wider "
                    f"door ({ds.leaf_param}) or a wider opening fails here instead of "
                    "passing unseen; write "
                    f"{ds.leaf_param} as an expression over the designed door's parameters "
                    "so the check follows it.",
                },
            )
        )
    elif width is not None and door not in HINGED:
        # no door that swings beside the body: the width alone, no door words (gate F)
        out.append(
            (
                SPACE_ABOUT,
                {
                    "title": f"Fits the {space} width",
                    "statement": f"The assembled product is at most {_q_text(width)} wide.",
                    "category": "geometry",
                    "verify": geometry("bbox.x", "<=", width),
                    "rationale": f"site.{generic.SITE_WIDTH.written(card)} on {card.id}.",
                },
            )
        )
    elif width is not None:
        term, basis = door_swing_term(card)
        if ds is None and float(term.magnitude) > 0:
            notes.append(
                f"the screening does not record the door's width (it predates that): the "
                f"{space} bound holds the door swing as a number — rebuild the card "
                f"(`n2f concept build {card.id}`) and promote again to make it a parameter"
            )
        limit = (width - term).to("mm")
        term_mm = float(term.magnitude)
        swing = (
            f"the door swing of {_q_text(term)}"
            if term_mm > 0
            else "no door swing (the door does not open sideways)"
        )
        out.append(
            (
                SPACE_ABOUT,
                {
                    "title": f"Fits the {space} with the door open",
                    "statement": f"The closed width plus {swing} stays within the "
                    f"{_q_text(width)} {space}.",
                    "category": "geometry",
                    "verify": geometry("bbox.x", "<=", limit),
                    "rationale": f"Door-swing term {_q_text(term)} (computed by screening: "
                    f"{basis}); {_q_text(width)} − {_q_text(term)} = {_q_text(limit)} for the "
                    "closed width.",
                },
            )
        )
    for site_field, axis, word in (
        (generic.SITE_DEPTH, "bbox.y", "deep"),
        (generic.SITE_HEIGHT, "bbox.z", "tall"),
    ):
        limit = _site_length(card, site_field)
        if limit is None:
            continue
        out.append(
            (
                SPACE_ABOUT,
                {
                    "title": f"Fits the {space} {site_field.key}",
                    "statement": f"The assembled product is at most {_q_text(limit)} {word}.",
                    "category": "geometry",
                    "verify": geometry(axis, "<=", limit),
                    "rationale": f"site.{site_field.written(card)} on {card.id}.",
                },
            )
        )
    # what only the product's own screens know (a heated box's supply, B-0086)
    out += pack_requirements(root, card, seeded, top, notes)
    mass_limit: Any = card.site.get("mass_limit")
    basis = f"site.mass_limit on {card.id}"
    if not is_quantity(mass_limit) and isinstance(card.site.get("lift_class"), str):
        from napkin2factory.calckit import load_table

        row = next(
            (r for r in load_table("lift_classes") if r["label"] == card.site["lift_class"]),
            None,
        )
        if row is not None and row.get("max_kg") is not None:
            mass_limit = Quantity(float(row["max_kg"]), "kg")
            basis = f"site.lift_class {row['label']} (HSE guideline weight) [verify]"
    if is_quantity(mass_limit):
        try:
            kg = mass_limit.to("kg")
        except Exception:  # pint DimensionalityError
            notes.append(f"site.mass_limit {mass_limit} is not a mass: no weight requirement")
        else:
            out.append(
                (
                    "weight",
                    {
                        "title": "Light enough to move as planned",
                        "statement": f"The assembled product weighs less than {_q_text(kg)}.",
                        "category": "mass",
                        "verify": geometry("mass", "<", kg),
                        "rationale": basis + ".",
                    },
                )
            )
    for _, data in out:
        data.setdefault("allocation", allocation)
        data["source"] = src
    if top is None and out:
        notes.append(
            "the product has no assembly yet: site requirements are allocated `unallocated` "
            "and checked by a person until an assembly exists"
        )
    return out
