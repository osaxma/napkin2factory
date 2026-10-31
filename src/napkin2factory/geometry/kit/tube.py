"""``tube``: a round or square hollow section, or a solid bar.

The section is solid when ``wall`` is 0 or at least half the outer size.  Origin at the
centre of one end; the tube extends along ``+axis``.
"""

from __future__ import annotations

from typing import Any, Literal

from build123d import (
    Align,
    Axis,
    Box,
    BuildPart,
    BuildSketch,
    Circle,
    Cylinder,
    Mode,
    Rectangle,
    RectangleRounded,
    extrude,
)

from napkin2factory.geometry.features import CutItem, Dim, Features, PartResult, Vec3
from napkin2factory.geometry.kit import KitArgs, KitContext
from napkin2factory.geometry.kit._common import Length, massing_result, require_positive


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


def _validate(a: Args) -> None:
    """Raise ``ValueError`` on non-positive sizes or a corner radius that does not fit."""
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


def _orient(shape: Any, axis: str) -> Any:
    """Turn a solid built along +Z so it runs along ``+axis`` (origin fixed)."""
    if axis == "x":
        return shape.rotate(Axis.Y, 90)
    if axis == "y":
        return shape.rotate(Axis.X, -90)
    return shape


def _end_and_across(a: Args) -> tuple[Vec3, Vec3, Vec3, Vec3]:
    """End point of the axis, a unit vector across the section, and the size callout ends."""
    ax = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}[a.axis]
    end = (ax[0] * a.length, ax[1] * a.length, ax[2] * a.length)
    # a direction across the section, perpendicular to the axis
    across = (0.0, 0.0, 1.0) if a.axis != "z" else (1.0, 0.0, 0.0)
    r = a.size / 2
    p1 = (-across[0] * r, -across[1] * r, -across[2] * r)
    p2 = (across[0] * r, across[1] * r, across[2] * r)
    return end, across, p1, p2


def _overall_dims(a: Args) -> list[Dim]:
    end, _, p1, p2 = _end_and_across(a)
    return [
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


def massing(a: Args, ctx: KitContext) -> PartResult:
    """Silhouette (N3): the outer solid along ``+axis`` with no bore and sharp corners."""
    _validate(a)
    align = (Align.CENTER, Align.CENTER, Align.MIN)
    if a.shape == "round":
        solid: Any = Cylinder(a.size / 2, a.length, align=align)
    else:
        solid = Box(a.size, a.size, a.length, align=align)
    return massing_result(_orient(solid, a.axis), a.process, _overall_dims(a), ctx)


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
    _validate(a)
    solid = is_solid(a)
    wall = 0.0 if solid else a.wall
    with BuildPart() as bp:
        with BuildSketch():
            _section(a, a.size, a.corner_radius, Mode.ADD)
            if not solid:
                _section(a, a.size - 2 * wall, max(a.corner_radius - wall, 0.0), Mode.SUBTRACT)
        extrude(amount=a.length)
    shape = _orient(bp.part, a.axis)
    shape.label = ctx.uri

    profile = profile_name(a)
    feats = Features(
        process=a.process, extra={"profile": profile, "outer": a.size, "wall": wall, "solid": solid}
    )
    _, across, _, p2 = _end_and_across(a)
    dims = _overall_dims(a)
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
