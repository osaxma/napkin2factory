"""The generic ``rough-shapes-overlap`` screen: do shapes share material? (S-336, S-343).

Promotion keeps the rough shapes as drawn, so two pieces that overlap on the card become two
parts that overlap in the model, and ``n2f check`` fails them under "parts do not overlap".
This screen finds them at the napkin, where moving one is cheap. It runs the model check's own
test (:mod:`napkin2factory.core.checks.interference`: bounding boxes first, then the common
volume, more than its threshold is an overlap) on the placed silhouettes.

Only silhouettes that are the real shape are compared: blocks, plates and solid bars. A frame's
members are tested one by one from its layout (:func:`napkin2factory.geometry.kit.frame.pieces`,
B-0323), so a piece standing in the open space between members passes while a cross member
running through a leg or rail fails. A hollow tube or an enclosure is drawn as a solid in the
massing, so it is skipped. A card with no overlap gets no row at all, so a card that never
overlapped is screened exactly as before.

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


def _edge_joint(a: Any, b: Any) -> bool:
    """The pieces cross only along an edge, by the thinner one's thickness (S-336).

    Two panels meeting at a corner are drawn overlapping there (a sketch's butt joint): their
    common box is no thicker than the thinner piece on two axes. Members that cross through
    each other (a joist through a bearer) share a box thicker than that on two axes.
    """
    thin = min(*a.size, *b.size) + 0.5
    common = [
        min(a.bbox_max[i], b.bbox_max[i]) - max(a.bbox_min[i], b.bbox_min[i]) for i in range(3)
    ]
    return sum(1 for d in common if d <= thin) >= 2


def _frame_boxes(piece: Any) -> list[tuple[str, Any]]:
    """Each member's ``(label, shape)`` in the card's coordinates (B-0323)."""
    from napkin2factory.geometry.kit import frame

    args = (
        piece.args if isinstance(piece.args, frame.Args) else frame.ARGS.model_validate(piece.args)
    )
    hb = frame.validate(args)
    layout = frame.pieces(args, hb)
    boxes: list[tuple[str, Any]] = []
    for p in layout:
        ext, center = frame._solid_span(p)
        pm = p.member or args.member
        s = pm.size
        s2 = pm.size2 if pm.profile == "rect-tube" and pm.size2 is not None else s
        u = s2 if p.kind != "leg" else s
        v = s if p.kind != "leg" else s2
        local_box = frame._box(p.axis, ext, u, v, center)
        boxes.append((p.label, local_box.moved(piece.location)))
    return boxes


def overlaps(pieces: list[Any]) -> list[tuple[str, str, float]]:
    """``(a, b, mm³)`` for each pair of exact silhouettes over the model's threshold."""
    from napkin2factory.core.checks.interference import (
        THRESHOLD_MM3,
        _bbox_overlap,
        _common_volume,
    )

    exact_shapes: dict[int, Any] = {}
    frame_boxes: dict[int, list[tuple[str, Any]]] = {}

    for i, p in enumerate(pieces):
        if _exact(p):
            exact_shapes[i] = p.built.result.shape.moved(p.location)
        elif p.kit == "frame":
            frame_boxes[i] = _frame_boxes(p)

    found: list[tuple[str, str, float]] = []
    for i, pa in enumerate(pieces):
        for j in range(i + 1, len(pieces)):
            pb = pieces[j]
            if i in exact_shapes and j in exact_shapes:
                sa, sb = exact_shapes[i], exact_shapes[j]
                if not _bbox_overlap(sa, sb) or _edge_joint(pa, pb):
                    continue
                volume = _common_volume(sa, sb)
                if volume > THRESHOLD_MM3:
                    found.append((pa.name, pb.name, volume))
            elif i in exact_shapes and j in frame_boxes:
                sa = exact_shapes[i]
                for mb_label, mb_shape in frame_boxes[j]:
                    if not _bbox_overlap(sa, mb_shape):
                        continue
                    volume = _common_volume(sa, mb_shape)
                    if volume > THRESHOLD_MM3:
                        found.append((pa.name, f"{pb.name}'s {mb_label}", volume))
            elif i in frame_boxes and j in exact_shapes:
                sb = exact_shapes[j]
                for ma_label, ma_shape in frame_boxes[i]:
                    if not _bbox_overlap(ma_shape, sb):
                        continue
                    volume = _common_volume(ma_shape, sb)
                    if volume > THRESHOLD_MM3:
                        found.append((f"{pa.name}'s {ma_label}", pb.name, volume))
            elif i in frame_boxes and j in frame_boxes:
                for ma_label, ma_shape in frame_boxes[i]:
                    for mb_label, mb_shape in frame_boxes[j]:
                        if not _bbox_overlap(ma_shape, mb_shape):
                            continue
                        volume = _common_volume(ma_shape, mb_shape)
                        if volume > THRESHOLD_MM3:
                            found.append(
                                (f"{pa.name}'s {ma_label}", f"{pb.name}'s {mb_label}", volume)
                            )
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
