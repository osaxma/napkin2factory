"""``tube``: a round or square hollow section, or a solid bar.

The section is solid when ``wall`` is 0 or at least half the outer size.  Origin at the
centre of one end; the tube extends along ``+axis``.
"""

from __future__ import annotations

from typing import Literal

from build123d import (
    Axis,
    BuildPart,
    BuildSketch,
    Circle,
    Mode,
    Rectangle,
    RectangleRounded,
    extrude,
)

from napkin2factory.geometry.features import CutItem, Dim, Features, PartResult
from napkin2factory.geometry.kit import KitArgs, KitContext
from napkin2factory.geometry.kit._common import Length, require_positive


class Args(KitArgs):
    """``tube`` arguments (lengths in any unit; converted to mm)."""

    shape: Literal["round", "square"] = "round"
    size: Length  # outer diameter, or outer side of the square
    wall: Length = 0.0  # 0 (or >= size/2) → solid bar
    length: Length
    axis: Literal["x", "y", "z"] = "z"
    corner_radius: Length = 0.0  # square only, outer corners
    process: str = "machining"


ARGS = Args


def is_solid(a: Args) -> bool:
    """Whether the arguments describe a solid bar rather than a hollow section."""
    return a.wall <= 0 or a.wall >= a.size / 2


def profile_name(a: Args) -> str:
    """Cut-list profile string, e.g. ``"round 25x2"`` or ``"square 20 solid"``."""
    if is_solid(a):
        return f"{a.shape} {a.size:g} solid"
    return f"{a.shape} {a.size:g}x{a.wall:g}"


def _section(a: Args, size: float, radius: float, mode: Mode) -> None:
    if a.shape == "round":
        Circle(size / 2, mode=mode)
    elif radius > 0.01:
        RectangleRounded(size, size, radius, mode=mode)
    else:
        Rectangle(size, size, mode=mode)


def generate(a: Args, ctx: KitContext) -> PartResult:
    """Build the tube along ``+axis`` from the origin (centre of one end).

    Args:
        a: validated arguments.
        ctx: generator context (labels the shape with ``ctx.uri``).

    Returns:
        The solid with its profile in ``features.extra``, dims and a one-line cut list.

    Raises:
        ValueError: on non-positive sizes or a corner radius that does not fit.
    """
    require_positive(size=a.size, length=a.length)
    if a.wall < 0:
        raise ValueError(f"wall must not be negative, got {a.wall}")
    if a.corner_radius < 0:
        raise ValueError(f"corner_radius must not be negative, got {a.corner_radius}")
    if a.shape == "round" and a.corner_radius > 0:
        raise ValueError("corner_radius applies to square tubes only")
    if a.shape == "square" and a.corner_radius >= a.size / 2:
        raise ValueError(
            f"corner_radius {a.corner_radius} must be smaller than half the size ({a.size / 2})"
        )
    solid = is_solid(a)
    wall = 0.0 if solid else a.wall
    with BuildPart() as bp:
        with BuildSketch():
            _section(a, a.size, a.corner_radius, Mode.ADD)
            if not solid:
                _section(a, a.size - 2 * wall, max(a.corner_radius - wall, 0.0), Mode.SUBTRACT)
        extrude(amount=a.length)
    shape = bp.part
    if a.axis == "x":
        shape = shape.rotate(Axis.Y, 90)
    elif a.axis == "y":
        shape = shape.rotate(Axis.X, -90)
    shape.label = ctx.uri

    profile = profile_name(a)
    feats = Features(
        process=a.process, extra={"profile": profile, "outer": a.size, "wall": wall, "solid": solid}
    )
    ax = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}[a.axis]
    end = (ax[0] * a.length, ax[1] * a.length, ax[2] * a.length)
    # a direction across the section, perpendicular to the axis
    across = (0.0, 0.0, 1.0) if a.axis != "z" else (1.0, 0.0, 0.0)
    r = a.size / 2
    p1 = (-across[0] * r, -across[1] * r, -across[2] * r)
    p2 = (across[0] * r, across[1] * r, across[2] * r)
    dims = [
        Dim(
            "size",
            a.size,
            p1,
            p2,
            view="front",
            kind="diameter" if a.shape == "round" else "linear",
        ),
        Dim("length", a.length, (0.0, 0.0, 0.0), end, view="front"),
    ]
    if not solid:
        dims.append(
            Dim(
                "wall",
                wall,
                p2,
                (p2[0] - across[0] * wall, p2[1] - across[1] * wall, p2[2] - across[2] * wall),
                view="front",
            )
        )
    cut = CutItem(description=f"{profile} × {a.length:g}", length=a.length, qty=1, profile=profile)
    return PartResult(shape=shape, features=feats, dims=dims, cut_list=[cut])
