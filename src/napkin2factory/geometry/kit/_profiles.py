"""Cross-section and stock profile helpers for kit generators (S-202)."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Literal

from build123d import Cylinder, Pos, Rotation, Shape

from napkin2factory.geometry.kit._common import require_positive

if TYPE_CHECKING:
    from napkin2factory.geometry.kit.frame import MemberSpec

ProfileKind = Literal["square-tube", "angle", "rect-tube", "round-tube", "t-slot"]


def profile_name(m: MemberSpec) -> str:
    """Stock description used in members and the cut list, e.g. ``square-tube 25x25x2``."""
    if m.profile == "square-tube":
        return f"{m.profile} {m.size:g}x{m.size:g}x{m.wall:g}"
    if m.profile == "angle":
        return f"{m.profile} {m.size:g}x{m.size:g}x{m.wall:g}"
    if m.profile == "rect-tube":
        s2 = m.size2 if m.size2 is not None else m.size
        return f"{m.profile} {m.size:g}x{s2:g}x{m.wall:g}"
    if m.profile == "round-tube":
        return f"{m.profile} {m.size:g}x{m.wall:g}"
    return f"{m.profile} {m.size:g}x{m.size:g}"


def section_area(m: MemberSpec) -> float:
    """Cross-section area of the stock, mm²."""
    s, w = m.size, m.wall
    if m.profile == "square-tube":
        return s * s - (s - 2 * w) ** 2
    if m.profile == "angle":
        return 2 * s * w - w * w
    if m.profile == "rect-tube":
        s2 = m.size2 if m.size2 is not None else s
        return s * s2 - (s - 2 * w) * (s2 - 2 * w)
    if m.profile == "round-tube":
        return math.pi * w * (s - w)
    sw = m.slot_width or 0.0
    sd = m.slot_depth or 0.0
    return s * s - 4 * sw * sd


def validate_member(m: MemberSpec, role: str = "member") -> None:
    """Validate a member specification."""
    if m.profile == "t-slot":
        require_positive(**{f"{role}.size": m.size})
        if m.slot_width is None or m.slot_depth is None:
            raise ValueError(f"{role} t-slot requires slot_width and slot_depth")
        require_positive(**{f"{role}.slot_width": m.slot_width, f"{role}.slot_depth": m.slot_depth})
        if m.slot_width >= m.size:
            raise ValueError(f"{role} slot_width {m.slot_width:g} must be < size {m.size:g}")
        if 2 * m.slot_depth >= m.size:
            raise ValueError(f"{role} 2*slot_depth {2 * m.slot_depth:g} must be < size {m.size:g}")
        return
    require_positive(**{f"{role}.size": m.size, f"{role}.wall": m.wall})
    if m.profile == "rect-tube":
        if m.size2 is None:
            raise ValueError(f"{role} rect-tube requires size2")
        require_positive(**{f"{role}.size2": m.size2})
        if m.size < 2 * m.wall + 0.5 or m.size2 < 2 * m.wall + 0.5:
            raise ValueError(
                f"{role} size {m.size:g} and size2 {m.size2:g} "
                f"must be at least 2*wall + 0.5 (wall {m.wall:g})"
            )
        return
    if m.size < 2 * m.wall + 0.5:
        raise ValueError(f"{role} size {m.size:g} must be at least 2*wall + 0.5 (wall {m.wall:g})")


def round_tube_solid(
    axis: int, ext: float, s: float, w: float, center: tuple[float, float, float]
) -> Shape:
    """A round tube hollow cylinder along ``axis``."""
    r_out, r_in = s / 2, s / 2 - w
    if axis == 2:
        outer = Pos(*center) * Cylinder(radius=r_out, height=ext)
        inner = Pos(*center) * Cylinder(radius=r_in, height=ext + 2)
    elif axis == 0:
        outer = Pos(*center) * Rotation(0, 90, 0) * Cylinder(radius=r_out, height=ext)
        inner = Pos(*center) * Rotation(0, 90, 0) * Cylinder(radius=r_in, height=ext + 2)
    else:
        outer = Pos(*center) * Rotation(-90, 0, 0) * Cylinder(radius=r_out, height=ext)
        inner = Pos(*center) * Rotation(-90, 0, 0) * Cylinder(radius=r_in, height=ext + 2)
    return outer - inner


def t_slot_solid(
    axis: int,
    ext: float,
    s: float,
    sw: float,
    sd: float,
    center: tuple[float, float, float],
    box_fn: Any,
) -> Shape:
    """A square T-slot extrusion with four centered slot grooves along ``axis``."""
    outer = box_fn(axis, ext, s, s, center)
    cross = [i for i in range(3) if i != axis]
    g1_pos = list(center)
    g1_pos[cross[0]] += (s - sd) / 2
    g1 = box_fn(axis, ext + 2, sd, sw, (g1_pos[0], g1_pos[1], g1_pos[2]))
    g2_pos = list(center)
    g2_pos[cross[0]] -= (s - sd) / 2
    g2 = box_fn(axis, ext + 2, sd, sw, (g2_pos[0], g2_pos[1], g2_pos[2]))
    g3_pos = list(center)
    g3_pos[cross[1]] += (s - sd) / 2
    g3 = box_fn(axis, ext + 2, sw, sd, (g3_pos[0], g3_pos[1], g3_pos[2]))
    g4_pos = list(center)
    g4_pos[cross[1]] -= (s - sd) / 2
    g4 = box_fn(axis, ext + 2, sw, sd, (g4_pos[0], g4_pos[1], g4_pos[2]))
    return outer - g1 - g2 - g3 - g4
