"""``plate``: a flat rectangular sheet with optional holes and corner radius.

Reference implementation for the generator protocol: validated args, a build123d
solid, declared features (holes with edge distances), dimension callouts, and a flat
pattern (the plate is its own flat pattern) with a developed-area check.
"""

from __future__ import annotations

from build123d import (
    Align,
    Axis,
    Box,
    BuildPart,
    BuildSketch,
    Circle,
    Locations,
    Rectangle,
    extrude,
    fillet,
)

from napkin2factory.geometry.features import (
    Dim,
    Features,
    FlatPattern,
    Hole,
    PartResult,
    polygon_area,
)
from napkin2factory.geometry.kit import KitArgs, KitContext
from napkin2factory.geometry.kit._common import Count, Length, massing_result, require_positive


class HoleSpec(KitArgs):
    """Holes on a rectangular grid centred on the plate."""

    diameter: Length
    count_x: Count = 2
    count_y: Count = 2
    spacing_x: Length | None = None
    spacing_y: Length | None = None
    inset: Length = 15.0  # distance from the plate edge when spacing is not given


class Args(KitArgs):
    """``plate`` arguments (lengths in any unit; converted to mm)."""

    width: Length
    depth: Length
    thickness: Length
    corner_radius: Length = 0.0
    holes: HoleSpec | None = None
    process: str = "cut-sheet"


ARGS = Args


def hole_centers(a: Args) -> list[tuple[float, float]]:
    """Grid of hole centres in plate coordinates (origin at the plate centre)."""
    if a.holes is None or a.holes.count_x * a.holes.count_y == 0:
        return []
    h = a.holes
    sx = h.spacing_x if h.spacing_x is not None else (a.width - 2 * h.inset)
    sy = h.spacing_y if h.spacing_y is not None else (a.depth - 2 * h.inset)
    xs = [0.0] if h.count_x == 1 else [-sx / 2 + sx * i / (h.count_x - 1) for i in range(h.count_x)]
    ys = [0.0] if h.count_y == 1 else [-sy / 2 + sy * i / (h.count_y - 1) for i in range(h.count_y)]
    return [(x, y) for y in ys for x in xs]


def _validate(a: Args) -> list[tuple[float, float]]:
    """Check sizes and that every hole clears the plate edge; return the hole centres."""
    require_positive(width=a.width, depth=a.depth, thickness=a.thickness)
    centers = hole_centers(a)
    if a.holes is not None:
        for x, y in centers:
            edge = min(a.width / 2 - abs(x), a.depth / 2 - abs(y)) - a.holes.diameter / 2
            if edge <= 0:
                raise ValueError(f"hole at ({x:.1f}, {y:.1f}) breaks the plate edge")
    return centers


def _overall_dims(a: Args) -> list[Dim]:
    hw, hd = a.width / 2, a.depth / 2
    return [
        Dim("width", a.width, (-hw, -hd, 0), (hw, -hd, 0), view="top"),
        Dim("depth", a.depth, (hw, -hd, 0), (hw, hd, 0), view="top"),
        Dim("thickness", a.thickness, (hw, -hd, 0), (hw, -hd, a.thickness), view="front"),
    ]


def massing(a: Args, ctx: KitContext) -> PartResult:
    """Silhouette (N3): a box of the outer size, no holes and no corner radius."""
    _validate(a)
    shape = Box(a.width, a.depth, a.thickness, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return massing_result(shape, a.process, _overall_dims(a), ctx)


def generate(a: Args, ctx: KitContext) -> PartResult:
    """Build the plate. Origin at the plate centre, Z up through the thickness."""
    centers = _validate(a)
    with BuildPart() as bp:
        with BuildSketch():
            Rectangle(a.width, a.depth)
        extrude(amount=a.thickness)
        if a.corner_radius > 0.01:
            fillet(bp.edges().filter_by(Axis.Z), radius=a.corner_radius)
        if a.holes is not None and centers:
            with BuildSketch():
                with Locations(*centers):
                    Circle(a.holes.diameter / 2)
            extrude(amount=a.thickness, mode=__import__("build123d").Mode.SUBTRACT)
    shape = bp.part
    shape.label = ctx.uri

    feats = Features(process=a.process, thickness=a.thickness)
    for i, (x, y) in enumerate(centers):
        d = a.holes.diameter if a.holes else 0.0
        feats.holes.append(
            Hole(
                center=(x, y, 0.0),
                diameter=d,
                edge_distance=min(a.width / 2 - abs(x), a.depth / 2 - abs(y)) - d / 2,
                label=f"H{i + 1}",
            )
        )
    hw, hd = a.width / 2, a.depth / 2
    outline = [(-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)]
    flat = FlatPattern(
        outline=outline,
        holes=[((x, y), a.holes.diameter) for x, y in centers] if a.holes else [],
        thickness=a.thickness,
    )
    flat.area = polygon_area(outline) - sum(3.141592653589793 * (d / 2) ** 2 for _, d in flat.holes)
    dims = _overall_dims(a)
    if a.holes and centers:
        dims.append(
            Dim(
                "hole",
                a.holes.diameter,
                (centers[0][0], centers[0][1], 0),
                (centers[0][0], centers[0][1], 0),
                view="top",
                kind="diameter",
            )
        )
    return PartResult(
        shape=shape,
        features=feats,
        dims=dims,
        flat_pattern=flat,
        props={"developed_area": flat.area},
        flat_map=lambda p: (p[0], p[1]) if -hw <= p[0] <= hw and -hd <= p[1] <= hd else None,
    )
