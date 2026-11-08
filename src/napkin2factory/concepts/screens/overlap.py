"""The generic ``rough-shapes-overlap`` screen: do the card's pieces share material? (S-336).

Promotion keeps the rough shapes as drawn, so two pieces that overlap on the card become two
parts that overlap in the model, and ``n2f check`` fails them under "parts do not overlap".
This screen finds them at the napkin, where moving one is cheap. It runs the model check's own
test (:mod:`napkin2factory.core.checks.interference`: bounding boxes first, then the common
volume, more than its threshold is an overlap) on the placed silhouettes.

Only silhouettes that are the real shape are compared: blocks, plates and solid bars. A frame,
a hollow tube or an enclosure is drawn as a solid in the massing, so a part standing inside it
would read as an overlap that is not one. A card with no overlap gets no row at all, so a card
that never overlapped is screened exactly as before.

It runs on cards that carry a load (``site`` gives a point, distributed or edge load, or a sag
limit): there the pieces are the members of a built structure and must meet face to face. On
any other card a block may stand for a hollow body with its door inside it, so overlap is how
it is drawn (the kiln's body and door), and nothing is said.
"""

from __future__ import annotations

from typing import Any

from napkin2factory.concepts.screens.base import ScreenValues, reads
from napkin2factory.core.domain import Screen
from napkin2factory.core.model.concepts import ConceptCard, RuleRow

#: The kits whose massing silhouette is the real shape.
EXACT_KITS = ("block", "plate", "tube")
#: The ``site`` keys that make a card a loaded structure (as ``empty_massing_example`` reads them).
LOAD_KEYS = ("point_load", "distributed_load", "edge_load", "max_deflection")
TITLE = "Rough shapes do not overlap"
#: How many pairs the message names.
SHOWN = 3


def _exact(piece: Any) -> bool:
    """Whether the piece's silhouette is the shape itself (a hollow tube is a solid one)."""
    return bool(piece.kit in EXACT_KITS and piece.material_volume is None)


def overlaps(pieces: list[Any]) -> list[tuple[str, str, float]]:
    """``(a, b, mm³)`` for each pair of exact silhouettes over the model's threshold."""
    from napkin2factory.core.checks.interference import (
        THRESHOLD_MM3,
        _bbox_overlap,
        _common_volume,
    )

    placed = [(p, p.built.result.shape.moved(p.location)) for p in pieces if _exact(p)]
    found: list[tuple[str, str, float]] = []
    for i, (pa, sa) in enumerate(placed):
        for pb, sb in placed[i + 1 :]:
            if not _bbox_overlap(sa, sb):
                continue
            volume = _common_volume(sa, sb)
            if volume > THRESHOLD_MM3:
                found.append((pa.name, pb.name, volume))
    return found


@reads(phase="check")
def rough_shapes_overlap(card: ConceptCard, massing: Any, values: ScreenValues) -> list[RuleRow]:
    """A failing row naming the overlapping pairs and the fix; no row when nothing overlaps."""
    if massing is None or not any(k in card.site for k in LOAD_KEYS):
        return []
    found = overlaps(massing.pieces)
    if not found:
        return []
    named = "; ".join(
        f"{a} and {b} by {v / 1000:.0f} cm³"
        for a, b, v in sorted(found, key=lambda t: -t[2])[:SHOWN]
    )
    more = f" (and {len(found) - SHOWN} more pairs)" if len(found) > SHOWN else ""
    return [
        RuleRow(
            id="rough-shapes-overlap",
            title=TITLE,
            status="fail",
            message=f"{len(found)} pair(s) of rough shapes share material: {named}{more}. "
            "Move one so they meet face to face, or make one shorter",
            relies_on=["computed"],
        )
    ]


OVERLAP_SCREEN = Screen("rough-shapes-overlap", rough_shapes_overlap, title=TITLE)

__all__ = ["OVERLAP_SCREEN", "overlaps"]
