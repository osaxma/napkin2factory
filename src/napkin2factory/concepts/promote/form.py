"""Step 4: style and layout choices become requirements verified by the form rule pack."""

from __future__ import annotations

from typing import Any

from napkin2factory.concepts.promote.common import (
    _and,
    _q_text,
)
from napkin2factory.core.model.concepts import ConceptCard
from napkin2factory.core.model.style import StyleFile

#: The rule pack the form requirements point at.
FORM_PACK = "form-v0"


def form_requirements(
    card: ConceptCard, style: StyleFile, top: str | None, notes: list[str]
) -> list[tuple[str, dict[str, Any]]]:
    """Form requirements from the merged style and the card's layout (the template library)."""
    src = f"concept {card.id} style"
    allocation: Any = [f"asm://{top}"] if top else "unallocated"
    out: list[tuple[str, dict[str, Any]]] = []

    def rule(rule_id: str) -> dict[str, Any]:
        return {"kind": "rule", "target": f"rule://{FORM_PACK}/{rule_id}"}

    radius = style.corner_radius
    if float(radius.to("mm").magnitude) > 0:
        out.append(
            (
                "form",
                {
                    "title": "Rounded exposed corners",
                    "statement": "Exposed bends and corners of the body, door, stand, controls "
                    f"and trim have a radius of at least {_q_text(radius)}.",
                    "category": "geometry",
                    "verify": rule("form-corner-radius"),
                    "rationale": f"Chosen with {card.id} (style corner_radius "
                    f"{_q_text(radius)}); the threshold lives in style.yaml.",
                },
            )
        )
    if style.fastener_visibility == "hidden-front":
        out.append(
            (
                "form",
                {
                    "title": "No visible fasteners on the front",
                    "statement": "No fastener holes show on the front face of the body or "
                    "the door.",
                    "category": "usability",
                    "verify": rule("form-fasteners-hidden-front"),
                    "rationale": f"Chosen with {card.id} (style fastener_visibility hidden-front).",
                },
            )
        )
    controls = str(card.layout.get("controls", "")).strip()
    if controls:
        out.append(
            (
                "form",
                {
                    "title": "Controls where they were sketched",
                    "statement": f"The controls sit {controls.replace('-', ' ')} on the "
                    f"product, as on {card.id}.",
                    "category": "usability",
                    "priority": "should",
                    "verify": rule("form-controls-placement"),
                    "rationale": f"Layout chosen with {card.id} (layout.controls {controls}); "
                    "a misplaced control is a warning, never a failure.",
                },
            )
        )
    if len(out) == 1:  # none at all needs no note: the summary says so (gate B, B4)
        why = []
        if float(radius.to("mm").magnitude) <= 0:
            why.append("no corner radius")
        if style.fastener_visibility != "hidden-front":
            why.append(f"fasteners {str(style.fastener_visibility).replace('-', ' ')}")
        if not controls:
            why.append("no place for the controls in the layout")
        notes.append(
            f"1 form requirement applies: the style chose {_and(why)} — give the card's style "
            "a corner radius or hidden front fasteners for more"
        )
    for _, data in out:
        data["allocation"] = allocation
        data["source"] = src
    return out
