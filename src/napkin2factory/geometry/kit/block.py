"""``block``: a rectangular solid (bricks, slabs, fibre boards, COTS boxes).

Origin at the centre of the base; the block spans ``z`` from 0 to ``height``.  Optional
vertical-edge fillet or all-edge chamfer (not both).
"""

from __future__ import annotations

from build123d import Axis, BuildPart, BuildSketch, Rectangle, chamfer, extrude, fillet

from napkin2factory.geometry.features import CutItem, Dim, Features, PartResult
from napkin2factory.geometry.kit import KitArgs, KitContext
from napkin2factory.geometry.kit._common import Length, require_positive


class Args(KitArgs):
    """``block`` arguments (lengths in any unit; converted to mm)."""

    length: Length
    width: Length
    height: Length
    fillet: Length = 0.0  # vertical edges only
    chamfer: Length = 0.0  # all edges
    process: str = "cut-block"


ARGS = Args


def generate(a: Args, ctx: KitContext) -> PartResult:
    """Build the block. Origin at the centre of the base, Z up through the height.

    Args:
        a: validated arguments.
        ctx: generator context (labels the shape with ``ctx.uri``).

    Returns:
        The solid with process, cut size, dimension callouts and a one-line cut list.

    Raises:
        ValueError: on non-positive sizes or a fillet/chamfer too large for the block.
    """
    require_positive(length=a.length, width=a.width, height=a.height)
    if a.fillet < 0 or a.chamfer < 0:
        raise ValueError("fillet and chamfer must not be negative")
    if a.fillet > 0 and a.chamfer > 0:
        raise ValueError("block takes a vertical-edge fillet or an all-edge chamfer, not both")
    if a.fillet > 0 and a.fillet >= min(a.length, a.width) / 2:
        raise ValueError(
            f"fillet {a.fillet} must be smaller than half the smaller side "
            f"({min(a.length, a.width) / 2})"
        )
    if a.chamfer > 0 and a.chamfer >= min(a.length, a.width, a.height) / 2:
        raise ValueError(
            f"chamfer {a.chamfer} must be smaller than half the smallest side "
            f"({min(a.length, a.width, a.height) / 2})"
        )
    with BuildPart() as bp:
        with BuildSketch():
            Rectangle(a.length, a.width)
        extrude(amount=a.height)
        if a.fillet > 0:
            fillet(bp.edges().filter_by(Axis.Z), radius=a.fillet)
        if a.chamfer > 0:
            chamfer(bp.edges(), length=a.chamfer)
    shape = bp.part
    shape.label = ctx.uri

    feats = Features(process=a.process, extra={"cut_size": [a.length, a.width, a.height]})
    hl, hw = a.length / 2, a.width / 2
    dims = [
        Dim("length", a.length, (-hl, -hw, 0), (hl, -hw, 0), view="top"),
        Dim("width", a.width, (hl, -hw, 0), (hl, hw, 0), view="top"),
        Dim("height", a.height, (hl, -hw, 0), (hl, -hw, a.height), view="front"),
    ]
    cut = CutItem(
        description=f"{a.length:g}×{a.width:g}×{a.height:g} block",
        length=a.length,
        width=a.width,
        thickness=a.height,
        qty=1,
    )
    return PartResult(shape=shape, features=feats, dims=dims, cut_list=[cut])
