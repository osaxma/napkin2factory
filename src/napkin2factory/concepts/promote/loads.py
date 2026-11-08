"""What the card says it must carry and cost: loads, sag limit and budget (B-0230).

A promotion that drops these leaves a product whose model has no trace of the owner's loads.
So every ``site`` number the screens read as a load (the fields in their "when it carries a
load" group) becomes a parameter, owner ``napkin``; the sag limit and the budget also become
requirements bounded by them. A value that is not a number of the right kind is listed in the
promotion's notes, never dropped silently.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from napkin2factory.concepts.promote.common import _q_text, _shown, display_units
from napkin2factory.core import concepts as cm
from napkin2factory.core.model.concepts import ConceptCard
from napkin2factory.core.units import is_quantity

#: The ``site`` key of the sag limit and of the budget (the generic and structural screens').
SAG_KEY, BUDGET_KEY = "max_deflection", "budget"


def seed_name(key: str, param: str | None = None) -> str:
    """The parameter a ``site`` key seeds: the field's declared name, else the key with hyphens."""
    return param or key.replace("_", "-")


def _fields(root: Path | None) -> list[Any]:
    """The ``site`` fields promotion keeps: the loads group (screens') and the budget."""
    return [
        f
        for f in cm.screen_fields(root)
        if f.section == "site" and (f.group or f.key == BUDGET_KEY)
    ]


def load_seeds(
    card: ConceptCard, root: Path | None, notes: list[str]
) -> list[tuple[str, Any, str, str | None]]:
    """``(parameter name, quantity, source, None)`` for each load, limit and budget on the card."""
    out: list[tuple[str, Any, str, str | None]] = []
    for f in _fields(root):
        written = f.written(card)
        if written is None:
            continue
        value = card.site.get(written)
        if not is_quantity(value) or f.wrong_kind(value) is not None:
            notes.append(
                f"site.{written}: {value!r} is not {f.kind} (for example {f.example}); "
                "not seeded, so the model has no trace of it"
            )
            continue
        out.append((seed_name(f.key, f.param), value, f"site.{written}", None))
    return out


#: The structural checks a seeded model re-runs (S-336): the screening's computed value, the
#: ``structure`` measure it becomes, the factor-of-safety check, the load case that sets the
#: factor it needs, the ``about`` of its requirement and the owner's words for it.
STRUCTURE_FACTORS: tuple[tuple[str, str, str, str, str], ...] = (
    ("yield_factor", "yield", "load", "yield", "its bending stress stays under yield"),
    ("buckling_factor", "buckling", "load", "buckling", "its legs or column do not buckle"),
    ("tip_over_factor", "tip_over", "edge_load", "tip-over", "it does not tip over"),
)


def _load_kind(card: ConceptCard) -> str:
    """``cyclic`` once the card gives a cycle count, else ``static`` (as the screen reads it)."""
    from napkin2factory.concepts.screens.structural_base import CYCLES

    cycles = CYCLES.quantity(card)
    return "cyclic" if cycles is not None and float(cycles.magnitude) > 0 else "static"


def _structure_factors(card: ConceptCard, top: str, under: str) -> list[tuple[str, dict[str, Any]]]:
    """One requirement per factor the card's screening computed, at the screen's own minimum.

    The minimum is ``calckit.joints.factor_of_safety`` for the load case the screen used, so
    the requirement and the screening agree (S-336).
    """
    from napkin2factory.calckit import joints

    if card.screening is None:
        return []
    out: list[tuple[str, dict[str, Any]]] = []
    for name, measure, case, about, words in STRUCTURE_FACTORS:
        if name not in card.screening.computed:
            continue
        need = joints.factor_of_safety(measure, _load_kind(card) if case == "load" else case)
        text = f"{need:g}"
        out.append(
            (
                about,
                {
                    "title": f"The structure holds: {words}",
                    "statement": f"{under} {words}, with a safety factor of at least {text}.",
                    "category": "performance",
                    "verify": {
                        "kind": "structure",
                        "target": f"asm://{top}#props.{name}",
                        "op": ">=",
                        "value": text,
                    },
                    "allocation": [f"asm://{top}"],
                    "rationale": f"The structural screening of {card.id} computed this factor; "
                    "the check runs the same screen on the built model (S-336).",
                },
            )
        )
    return out


def limit_requirements(
    card: ConceptCard,
    top: str | None,
    root: Path | None,
    structure: bool = False,
) -> list[tuple[str, dict[str, Any]]]:
    """The sag limit and the budget as requirements, in the product's display units.

    With ``structure`` (a seeded model that builds, S-336) the sag limit is checked by the
    ``structure`` verify kind on the top assembly instead of being left for a person, and each
    factor the card's screening computed becomes a requirement too.
    """
    units = display_units(root)
    fields = {f.key: f for f in _fields(root)}
    out: list[tuple[str, dict[str, Any]]] = []
    # allocated to the top assembly only: a seeded parameter can go away again when
    # `concept switch` brings a parked direction back, and a requirement must not point at it
    allocation: Any = [f"asm://{top}"] if top else "unallocated"

    sag = card.site.get(SAG_KEY)
    if SAG_KEY in fields and is_quantity(sag) and fields[SAG_KEY].wrong_kind(sag) is None:
        loads = [
            f"{_shown(card.site[k], units)}, {f.said()}"
            for k, f in fields.items()
            if f.group
            and k not in (SAG_KEY, "cycles")
            and is_quantity(card.site.get(k))
            and k not in ("edge_offset",)
        ]
        under = f"Under the loads on {card.id} ({'; '.join(loads)}), the" if loads else "The"
        if structure and top:
            verify: dict[str, Any] = {
                "kind": "structure",
                "target": f"asm://{top}#props.deflection",
                "op": "<=",
                "value": _q_text(sag),
            }
        else:
            verify = {
                "kind": "manual",
                "note": "no sag calculation is in the model yet: check it by hand, "
                "or add a calc and point this requirement at it",
            }
        out.append(
            (
                "sag",
                {
                    "title": "Sag stays within the limit",
                    "statement": f"{under} sag is at most {_shown(sag, units)}.",
                    "category": "performance",
                    "verify": verify,
                    "allocation": allocation,
                    "rationale": f"site.{SAG_KEY} on {card.id}.",
                },
            )
        )
    budget = card.site.get(BUDGET_KEY)
    if (
        BUDGET_KEY in fields
        and is_quantity(budget)
        and fields[BUDGET_KEY].wrong_kind(budget) is None
    ):
        out.append(
            (
                "cost",
                {
                    "title": "Within the budget",
                    "statement": f"The bill of materials totals at most {_shown(budget, units)}.",
                    "category": "cost",
                    "verify": {
                        "kind": "bom_rollup",
                        "target": "bom://rollups#total_cost",
                        "op": "<=",
                        "value": _q_text(budget),
                    },
                    "allocation": allocation,
                    "rationale": f"site.{BUDGET_KEY} on {card.id}.",
                },
            )
        )
    if structure and top:
        loads_said = [
            f"{_shown(card.site[k], units)}, {f.said()}"
            for k, f in fields.items()
            if f.group
            and k not in (SAG_KEY, "cycles", "edge_offset")
            and is_quantity(card.site.get(k))
        ]
        said = (
            f"Under the loads on {card.id} ({'; '.join(loads_said)})," if loads_said else "Loaded,"
        )
        out += _structure_factors(card, top, said)
    src = f"concept {card.id} site constraint"
    for _, data in out:
        data["source"] = src
    return out
