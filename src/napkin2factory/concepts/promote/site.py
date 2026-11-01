"""Step 3: the card's site constraints become requirements on the top assembly (N8)."""

from __future__ import annotations

import math
from typing import Any

from napkin2factory.concepts.promote.common import (
    SeededParam,
    _q_text,
)
from napkin2factory.concepts.promote.door import (
    DOOR_ROOM_PARAM,
    DOOR_ROW_TITLE,
    _site_length,
    door_swing,
    door_swing_term,
)
from napkin2factory.concepts.screens import generic
from napkin2factory.core.model.concepts import ConceptCard
from napkin2factory.core.units import is_quantity
from napkin2factory.rulepacks.concept_checks import circuit_headroom, parse_circuit

#: The envelope key whose seeded parameter the supply requirement bounds.
POWER_KEY = "power"


def site_requirements(
    card: ConceptCard,
    seeded: list[SeededParam],
    top: str | None,
    notes: list[str],
) -> list[tuple[str, dict[str, Any]]]:
    """``(about, requirement fields)`` for each site constraint on the card."""
    from napkin2factory.core.units import Quantity

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
        # S-085): the closed width gets the alcove less the door's allowance, and a second
        # row holds the door to that allowance, so a wider or further-opening door fails
        allowance = ds.allowance
        limit = (width - allowance).to("mm")
        room = f"param://{DOOR_ROOM_PARAM}"
        leaf_uri = f"param://{ds.leaf_param}"
        out.append(
            (
                "alcove",
                {
                    "title": "Fits the alcove with the door open",
                    "statement": f"The closed width plus the {_q_text(allowance)} the open door "
                    f"takes beside the hinge stays within the {_q_text(width)} alcove.",
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
                "alcove",
                {
                    "title": DOOR_ROW_TITLE,
                    "statement": f"The open door takes at most {_q_text(allowance)} beside the "
                    "hinge, the room the alcove leaves it.",
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
    elif width is not None:
        term, basis = door_swing_term(card)
        if ds is None and float(term.magnitude) > 0:
            notes.append(
                "the screening does not record the door's width (it predates that): the "
                "alcove bound holds the door swing as a number — rebuild the card "
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
                "alcove",
                {
                    "title": "Fits the alcove with the door open",
                    "statement": f"The closed width plus {swing} stays within the "
                    f"{_q_text(width)} alcove.",
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
                "alcove",
                {
                    "title": f"Fits the alcove {site_field.key}",
                    "statement": f"The assembled product is at most {_q_text(limit)} {word}.",
                    "category": "geometry",
                    "verify": geometry(axis, "<=", limit),
                    "rationale": f"site.{site_field.written(card)} on {card.id}.",
                },
            )
        )
    circuit = card.site.get("circuit")
    if circuit is not None:
        parsed = parse_circuit(circuit) if isinstance(circuit, str) else None
        power = next((p for p in seeded if p.source == f"envelope.{POWER_KEY}"), None)
        if parsed is None:
            notes.append(
                f"site.circuit {circuit!r} is not like 240V-13A: no supply requirement written"
            )
        elif power is None:
            notes.append(
                "no power on the card (envelope.power): no supply requirement written — "
                "add one once the element power is known"
            )
        else:
            volts, amps = parsed
            # One margin for the napkin and the factory (review gate A, B1): the bound is
            # read from rule circuit-available's `headroom`, the number screening used, so a
            # green circuit row cannot become a failing requirement on the same inputs.
            headroom = circuit_headroom()
            raw = float((volts * amps).to("W").magnitude) / headroom
            # rounded *up* to 0.1 W so a card exactly at the screening limit still passes
            limit = Quantity(math.ceil(round(raw * 10, 6)) / 10, "W")
            out.append(
                (
                    "supply",
                    {
                        "title": "Runs on the site circuit",
                        "statement": f"The element power is at most {_q_text(limit)}, so the "
                        f"{circuit} site circuit keeps a {headroom:g} headroom.",
                        "category": "performance",
                        "verify": {
                            "kind": "param_bound",
                            "target": f"param://{power.name}",
                            "op": "<=",
                            "value": _q_text(limit),
                        },
                        "allocation": [f"param://{power.name}"] + ([f"asm://{top}"] if top else []),
                        "rationale": f"{_q_text(volts)} × {_q_text(amps)} / {headroom:g}: the "
                        f"same {headroom:g} headroom screening used (rule circuit-available); "
                        "the NEC 210.20 continuous-load factor 1.25 is stricter [verify].",
                    },
                )
            )
    elif card.site.get("region") is not None and any(
        p.source == f"envelope.{POWER_KEY}" for p in seeded
    ):
        notes.append(
            f"site.region {card.site['region']} but no site.circuit: no supply requirement "
            "written — add site.circuit (e.g. 230V-16A) once the socket is known"
        )
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
