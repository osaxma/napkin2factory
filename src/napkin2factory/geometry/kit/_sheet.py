"""Shared sheet-metal math for the bent kit generators (``bracket_l``, ``enclosure``).

Lengths are millimetres, angles degrees.  The flat-pattern helpers return plain 2D
polygons (lists of ``(x, y)``) that go straight into :class:`FlatPattern`.
"""

from __future__ import annotations

import math

from build123d import (
    BuildLine,
    BuildSketch,
    CenterArc,
    Line,
    Location,
    Plane,
    Solid,
    extrude,
    make_face,
)

from napkin2factory.geometry.features import Vec2

Vec3 = tuple[float, float, float]

# (upper bound of r/t, K) — first row whose bound exceeds r/t wins.
_K_TABLE: tuple[tuple[float, float], ...] = (
    (1.0, 0.33),
    (2.0, 0.40),
    (4.0, 0.44),
    (math.inf, 0.50),
)


def k_factor(inside_radius: float, thickness: float) -> float:
    """Nominal K-factor (neutral-axis position as a fraction of thickness) by r/t.

    Values follow the common air-bending K-factor table (Machinery's Handbook style):
    r/t < 1 → 0.33, 1–2 → 0.40, 2–4 → 0.44, ≥ 4 → 0.50.  It is a nominal table, not a
    material- or tooling-specific calibration; shops override it with measured values.

    Args:
        inside_radius: Inside bend radius, mm.
        thickness: Sheet thickness, mm.

    Returns:
        The K-factor, between 0.33 and 0.5.

    Raises:
        ValueError: If ``thickness`` is not positive or ``inside_radius`` is negative.
    """
    if thickness <= 0:
        raise ValueError(f"thickness must be positive, got {thickness}")
    if inside_radius < 0:
        raise ValueError(f"bend radius must not be negative, got {inside_radius}")
    ratio = inside_radius / thickness
    for bound, k in _K_TABLE:
        if ratio < bound:
            return k
    return _K_TABLE[-1][1]


def bend_allowance(
    inside_radius: float, thickness: float, angle_deg: float, k: float | None = None
) -> float:
    """Arc length of the neutral axis through a bend: ``angle_rad × (r + k·t)``.

    Args:
        inside_radius: Inside bend radius, mm.
        thickness: Sheet thickness, mm.
        angle_deg: Bend angle (the amount the sheet turns), degrees.
        k: K-factor; looked up with :func:`k_factor` when omitted.

    Returns:
        The bend allowance, mm.
    """
    if k is None:
        k = k_factor(inside_radius, thickness)
    return math.radians(angle_deg) * (inside_radius + k * thickness)


def bend_solid(inside_radius: float, thickness: float, angle_deg: float, length: float) -> Solid:
    """The bent zone of a sheet: an annular sector extruded along the bend axis.

    Local frame: the bend axis is the local Z axis through the origin.  The sector lies
    in the XY plane between radii ``r`` and ``r + t`` and sweeps counter-clockwise (seen
    from +Z) from the +X direction by ``angle_deg``; it is extruded from ``z = 0`` to
    ``z = length``.  So the end face at angle 0 is the strip ``x ∈ [r, r+t], y = 0`` and
    the other end face lies along the direction at ``angle_deg``.  Place it with
    :func:`place` (or ``.located(Location(...))``).

    Args:
        inside_radius: Inside radius ``r``, mm (may be 0 for a sharp bend: a wedge).
        thickness: Sheet thickness ``t``, mm.
        angle_deg: Swept angle, degrees, in (0, 180].
        length: Extrusion length along the bend axis, mm.

    Returns:
        The bend solid.

    Raises:
        ValueError: On a non-positive thickness/length or an angle outside (0, 180].
    """
    if thickness <= 0 or length <= 0:
        raise ValueError(f"bend needs positive thickness and length, got {thickness}, {length}")
    if not 0 < angle_deg <= 180:
        raise ValueError(f"bend angle must be in (0, 180] degrees, got {angle_deg}")
    r, ro = inside_radius, inside_radius + thickness
    a = math.radians(angle_deg)
    with BuildSketch() as sk:
        with BuildLine():
            Line((r, 0), (ro, 0))
            CenterArc((0, 0), ro, 0, angle_deg)
            Line((ro * math.cos(a), ro * math.sin(a)), (r * math.cos(a), r * math.sin(a)))
            if r > 0:
                CenterArc((0, 0), r, angle_deg, -angle_deg)
        make_face()
    return extrude(sk.sketch, amount=length).solids()[0]


def place(shape: Solid, origin: Vec3, x_dir: Vec3, z_dir: Vec3) -> Solid:
    """Move a solid built in its local frame so local X/Z map onto ``x_dir``/``z_dir``.

    Args:
        shape: Solid built at the identity location.
        origin: World point for the local origin.
        x_dir: World direction of local +X.
        z_dir: World direction of local +Z (local Y follows from the right-hand rule).

    Returns:
        The relocated solid.
    """
    return shape.located(Location(Plane(origin=origin, x_dir=x_dir, z_dir=z_dir)))


def developed_l(flat_a: float, ba: float, flat_b: float, width: float) -> tuple[list[Vec2], float]:
    """Developed outline of a single-bend L: a strip ``flat_a + ba + flat_b`` by ``width``.

    The strip runs along +X from ``x = 0`` (free end of leg A) and is centred on Y.

    Args:
        flat_a: Straight (unbent) length of the first leg, mm.
        ba: Bend allowance, mm.
        flat_b: Straight length of the second leg, mm.
        width: Width across the bend line, mm.

    Returns:
        ``(outline, bend_x)``: the rectangle and the X of the bend centre line.
    """
    total = flat_a + ba + flat_b
    hw = width / 2
    outline: list[Vec2] = [(0.0, -hw), (total, -hw), (total, hw), (0.0, hw)]
    return outline, flat_a + ba / 2


def developed_tray(
    base_length: float, base_width: float, span_x: float, span_y: float, flap: float
) -> list[Vec2]:
    """Cross-shaped developed outline of a four-wall tray, centred on the base.

    The base flat (between the bend tangent lines) is ``base_length × base_width``.  The
    front/back flaps are ``span_x`` long (along X) and the left/right flaps ``span_y``
    long (along Y); every flap extends ``flap`` outward from the base edge (bend
    allowances plus wall and lip flats).  Spans shorter than the base leave rectangular
    corner reliefs; equal spans give the plain cross.

    Args:
        base_length: Base flat along X, mm.
        base_width: Base flat along Y, mm.
        span_x: Length of the front/back flaps along X, mm (≤ ``base_length``).
        span_y: Length of the left/right flaps along Y, mm (≤ ``base_width``).
        flap: Outward extension of every flap, mm.

    Returns:
        The outline polygon, counter-clockwise, with no repeated vertices.
    """
    bx, by, ax, ay, e = base_length / 2, base_width / 2, span_x / 2, span_y / 2, flap
    pts: list[Vec2] = [
        (-bx, -by),
        (-ax, -by),
        (-ax, -by - e),
        (ax, -by - e),
        (ax, -by),
        (bx, -by),
        (bx, -ay),
        (bx + e, -ay),
        (bx + e, ay),
        (bx, ay),
        (bx, by),
        (ax, by),
        (ax, by + e),
        (-ax, by + e),
        (-ax, by),
        (-bx, by),
        (-bx, ay),
        (-bx - e, ay),
        (-bx - e, -ay),
        (-bx, -ay),
    ]
    out: list[Vec2] = []
    for p in pts:
        if not out or math.dist(out[-1], p) > 1e-9:
            out.append(p)
    if len(out) > 1 and math.dist(out[0], out[-1]) <= 1e-9:
        out.pop()
    return out


def rounded_rect(
    cx: float, cy: float, width: float, height: float, radius: float = 0.0, segments: int = 8
) -> list[Vec2]:
    """Polygon approximation of a (rounded) rectangle, for flat-pattern cutouts.

    Args:
        cx: Centre X, mm.
        cy: Centre Y, mm.
        width: Size along X, mm.
        height: Size along Y, mm.
        radius: Corner radius, mm (0 for sharp corners).
        segments: Straight segments per rounded corner.

    Returns:
        The polygon, counter-clockwise.
    """
    hw, hh = width / 2, height / 2
    if radius <= 0:
        return [(cx - hw, cy - hh), (cx + hw, cy - hh), (cx + hw, cy + hh), (cx - hw, cy + hh)]
    pts: list[Vec2] = []
    corners = (
        (hw - radius, -hh + radius, -90.0),
        (hw - radius, hh - radius, 0.0),
        (-hw + radius, hh - radius, 90.0),
        (-hw + radius, -hh + radius, 180.0),
    )
    for ox, oy, start in corners:
        for i in range(segments + 1):
            a = math.radians(start + 90.0 * i / segments)
            pts.append((cx + ox + radius * math.cos(a), cy + oy + radius * math.sin(a)))
    return pts


def rounded_rect_area(width: float, height: float, radius: float = 0.0) -> float:
    """Exact area of a rectangle with four corner radii ``radius``.

    Args:
        width: Size along X, mm.
        height: Size along Y, mm.
        radius: Corner radius, mm.

    Returns:
        Area, mm².
    """
    return width * height - (4.0 - math.pi) * radius * radius
