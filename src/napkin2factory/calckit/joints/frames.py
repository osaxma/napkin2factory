"""Joint moment capacity of welded and bolted corners, and frame racking of portals."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from napkin2factory.calckit.joints._units import (
    Qty,
    _force_n,
    _inertia_m4,
    _length_m,
    _modulus_m3,
    _pressure_pa,
    _rot_stiffness,
)
from napkin2factory.core.units import Quantity

# --- 2. Joint moment capacity and frame racking -------------------------------------


def joint_moment_capacity(
    joint: str | Mapping[str, Any] | None = None,
    section: Mapping[str, Any] | Qty | None = None,
    *,
    kind: str | None = None,
    section_modulus: Qty | None = None,
    yield_strength: Qty | None = None,
    weld_efficiency: float = 1.0,
    bolt_capacity: Qty | None = None,
    bolt_distances: Sequence[Qty] | None = None,
    bolt_spacing: Qty | None = None,
    bolt_count: int | None = None,
) -> Qty:
    """Moment capacity of a welded or bolted corner before yield.

    For welded corners: ``M = Z * sigma_y * eta``, where Z is section modulus,
    sigma_y is material yield strength, and eta is weld efficiency (default 1.0).
    For bolted corners: ``M = (F_bolt / max(|y_i|)) * sum(y_i^2)`` per Shigley
    §8-5 / AISC bolt group elastic analysis.

    Args:
        joint: joint kind string (``"welded"`` or ``"bolted"``) or mapping holding
            joint parameters.
        section: section modulus (Qty) or mapping holding section properties.
        kind: explicit joint kind override (``"welded"`` or ``"bolted"``).
        section_modulus: section modulus of the welded tube or weld group (volume Qty).
        yield_strength: material yield strength (pressure Qty).
        weld_efficiency: weld efficiency factor (dimensionless float, default 1.0).
        bolt_capacity: allowable tensile or shear load per bolt (force Qty).
        bolt_distances: distances y_i of bolts from neutral axis/pivot (sequence of length Qty).
        bolt_spacing: distance d between a pair of bolts (length Qty).
        bolt_count: bolt count when using standard spacing (integer).

    Returns:
        Moment capacity before yield as a pint Quantity in Newton-meters (N*m).
    """
    # Determine joint kind
    determined_kind = kind
    if determined_kind is None:
        if isinstance(joint, str):
            determined_kind = joint
        elif isinstance(joint, Mapping) and "kind" in joint:
            determined_kind = str(joint["kind"])
        elif section_modulus is not None or (
            isinstance(section, (Quantity, Mapping))
            and not (bolt_capacity or bolt_distances or bolt_spacing)
        ):
            determined_kind = "welded"
        elif bolt_capacity is not None or bolt_distances is not None:
            determined_kind = "bolted"
        else:
            determined_kind = "welded"

    norm_kind = determined_kind.strip().lower()

    if norm_kind == "welded":
        # Resolve section modulus Z
        z_q = section_modulus
        if z_q is None:
            if isinstance(section, Mapping):
                z_q = section.get("section_modulus", section.get("Z"))
            elif hasattr(section, "to"):
                z_q = section
            elif isinstance(joint, Mapping):
                z_q = joint.get("section_modulus", joint.get("Z"))
        if z_q is None:
            raise ValueError(
                "joint_moment_capacity(welded) requires 'section_modulus' (e.g. 10000 mm**3)"
            )

        # Resolve yield strength
        ys_q = yield_strength
        if ys_q is None:
            if isinstance(section, Mapping):
                ys_q = section.get("yield_strength", section.get("sigma_y"))
            elif isinstance(joint, Mapping):
                ys_q = joint.get("yield_strength", joint.get("sigma_y"))
        if ys_q is None:
            raise ValueError(
                "joint_moment_capacity(welded) requires 'yield_strength' (e.g. 250 MPa)"
            )

        eff = weld_efficiency
        if isinstance(joint, Mapping) and "weld_efficiency" in joint:
            eff = float(joint["weld_efficiency"])
        if eff <= 0:
            raise ValueError(f"weld_efficiency must be positive, got {eff}")

        z_m3 = _modulus_m3(z_q, "10000 mm**3")
        ys_pa = _pressure_pa(ys_q, "250 MPa")
        moment_nm = z_m3 * ys_pa * eff
        return Quantity(moment_nm, "N*m")

    if norm_kind == "bolted":
        f_bolt_q = bolt_capacity
        if f_bolt_q is None and isinstance(joint, Mapping):
            f_bolt_q = joint.get("bolt_capacity")
        if f_bolt_q is None:
            raise ValueError(
                "joint_moment_capacity(bolted) requires 'bolt_capacity' (force Qty, e.g. 5 kN)"
            )
        f_bolt_n = _force_n(f_bolt_q, "5 kN")

        distances: list[float] = []
        dists_input = bolt_distances
        if dists_input is None and isinstance(joint, Mapping):
            dists_input = joint.get("bolt_distances")

        if dists_input is not None:
            for d in dists_input:
                distances.append(_length_m(d, "50 mm"))
        else:
            spacing_q = bolt_spacing
            if spacing_q is None and isinstance(joint, Mapping):
                spacing_q = joint.get("bolt_spacing")
            if spacing_q is not None:
                spacing_m = _length_m(spacing_q, "100 mm")
                count = (
                    bolt_count
                    if bolt_count is not None
                    else (joint.get("bolt_count", 2) if isinstance(joint, Mapping) else 2)
                )
                if count == 2:
                    distances = [-spacing_m / 2.0, spacing_m / 2.0]
                else:
                    # symmetric rows spaced evenly across spacing_m
                    n_rows = count // 2 if count >= 4 else 2
                    step = spacing_m / (n_rows - 1) if n_rows > 1 else spacing_m
                    half = spacing_m / 2.0
                    for r in range(n_rows):
                        y = -half + r * step
                        distances.extend([y, y])  # 2 bolts per row
            else:
                raise ValueError(
                    "joint_moment_capacity(bolted) requires either "
                    "'bolt_distances' or 'bolt_spacing'"
                )

        if not distances:
            raise ValueError("bolt_distances cannot be empty")

        max_y = max(abs(y) for y in distances)
        if max_y <= 0:
            raise ValueError("bolts cannot all be located at neutral axis (y=0)")

        sum_y2 = sum(y**2 for y in distances)
        # Elastic moment resistance: M = (F_bolt / max_y) * sum(y_i^2)
        moment_nm = (f_bolt_n / max_y) * sum_y2
        return Quantity(moment_nm, "N*m")

    raise ValueError(f"unknown joint kind {determined_kind!r}; must be 'welded' or 'bolted'")


@dataclass(frozen=True)
class PortalFrame:
    """Dimensions and material properties of an unbraced portal frame.

    Attributes:
        height: column height H (length).
        span: horizontal beam span L (length).
        e_modulus: Young's modulus E (pressure).
        i_column: column second moment of area I_c (second moment of area).
        i_beam: beam second moment of area I_b (second moment of area).
        joint_stiffness: rotational spring stiffness K_theta of the two corners
            (torque/radian, e.g. N*m/rad). None implies perfectly rigid corners.
        base_fixity: column base condition: ``"pinned"`` (default) or ``"fixed"``.
    """

    height: Qty
    span: Qty
    e_modulus: Qty
    i_column: Qty
    i_beam: Qty
    joint_stiffness: Qty | None = None
    base_fixity: str = "pinned"


def frame_racking(
    *args: Any,
    frame: PortalFrame | Mapping[str, Any] | None = None,
    lateral_load: Qty | None = None,
    height: Qty | None = None,
    span: Qty | None = None,
    e_modulus: Qty | None = None,
    i_column: Qty | None = None,
    i_beam: Qty | None = None,
    joint_stiffness: Qty | None = None,
    base_fixity: str = "pinned",
) -> Qty:
    """Lateral sway of an unbraced portal frame under a horizontal racking load.

    Uses Roark's Formulas for Stress and Strain (Table 8.2 rectangular portal frame)
    and semi-rigid slope-deflection frame mechanics.
    For pinned bases:
        ``delta = (P * H^3)/(6 * E * I_c) + (P * H^2 * L)/(12 * E * I_b) + (P * H^2)/(2 * K_theta)``
    where K_theta is the rotational stiffness of the corner joints.

    Supports calling as:
    - ``frame_racking(frame, lateral_load)``
    - ``frame_racking(lateral_load, height, span, e_modulus, i_column, i_beam)``
    - ``frame_racking(frame=..., lateral_load=...)``

    Args:
        args: positional arguments (frame + load, or 6 member parameters).
        frame: :class:`PortalFrame` or mapping holding frame geometry and properties.
        lateral_load: lateral horizontal force (force Qty).
        height: column height H (length Qty).
        span: crosshead beam span L (length Qty).
        e_modulus: Young's modulus E of frame members (pressure Qty).
        i_column: moment of inertia of the two columns (length^4 Qty).
        i_beam: moment of inertia of the top beam (length^4 Qty).
        joint_stiffness: corner rotational spring stiffness (torque Qty, e.g. N*m/rad);
            None means rigid corners.
        base_fixity: ``"pinned"`` (default) or ``"fixed"``.

    Returns:
        Horizontal sway displacement at top corners as a pint Quantity (mm).
    """
    p_q: Qty = lateral_load
    h_q: Qty = height
    l_q: Qty = span
    e_q: Qty = e_modulus
    ic_q: Qty = i_column
    ib_q: Qty = i_beam
    k_theta_q: Qty = joint_stiffness
    fixity: str = base_fixity

    if len(args) == 6:
        p_q, h_q, l_q, e_q, ic_q, ib_q = args
    elif len(args) == 2:
        if isinstance(args[0], (PortalFrame, Mapping)):
            frame_obj = args[0]
            p_q = args[1]
            if isinstance(frame_obj, PortalFrame):
                h_q, l_q, e_q, ic_q, ib_q = (
                    frame_obj.height,
                    frame_obj.span,
                    frame_obj.e_modulus,
                    frame_obj.i_column,
                    frame_obj.i_beam,
                )
                if k_theta_q is None:
                    k_theta_q = frame_obj.joint_stiffness
                fixity = frame_obj.base_fixity
            else:
                h_q = frame_obj.get("height", h_q)
                l_q = frame_obj.get("span", l_q)
                e_q = frame_obj.get("e_modulus", e_q)
                ic_q = frame_obj.get("i_column", ic_q)
                ib_q = frame_obj.get("i_beam", ib_q)
                k_theta_q = frame_obj.get("joint_stiffness", k_theta_q)
                fixity = frame_obj.get("base_fixity", fixity)
        else:
            p_q, h_q = args
    elif len(args) == 1:
        if isinstance(args[0], (PortalFrame, Mapping)):
            frame_obj = args[0]
            if isinstance(frame_obj, PortalFrame):
                h_q, l_q, e_q, ic_q, ib_q = (
                    frame_obj.height,
                    frame_obj.span,
                    frame_obj.e_modulus,
                    frame_obj.i_column,
                    frame_obj.i_beam,
                )
                if k_theta_q is None:
                    k_theta_q = frame_obj.joint_stiffness
                fixity = frame_obj.base_fixity
            else:
                h_q = frame_obj.get("height", h_q)
                l_q = frame_obj.get("span", l_q)
                e_q = frame_obj.get("e_modulus", e_q)
                ic_q = frame_obj.get("i_column", ic_q)
                ib_q = frame_obj.get("i_beam", ib_q)
                k_theta_q = frame_obj.get("joint_stiffness", k_theta_q)
                fixity = frame_obj.get("base_fixity", fixity)
        else:
            p_q = args[0]
    elif frame is not None:
        if isinstance(frame, PortalFrame):
            h_q, l_q, e_q, ic_q, ib_q = (
                frame.height,
                frame.span,
                frame.e_modulus,
                frame.i_column,
                frame.i_beam,
            )
            if k_theta_q is None:
                k_theta_q = frame.joint_stiffness
            fixity = frame.base_fixity
        else:
            h_q = frame.get("height", h_q)
            l_q = frame.get("span", l_q)
            e_q = frame.get("e_modulus", e_q)
            ic_q = frame.get("i_column", ic_q)
            ib_q = frame.get("i_beam", ib_q)
            k_theta_q = frame.get("joint_stiffness", k_theta_q)
            fixity = frame.get("base_fixity", fixity)

    if p_q is None or h_q is None or l_q is None or e_q is None or ic_q is None or ib_q is None:
        raise ValueError(
            "frame_racking requires lateral_load, height, span, e_modulus, i_column, and i_beam"
        )

    p_n = _force_n(p_q, "100 N")
    h_m = _length_m(h_q, "750 mm")
    l_m = _length_m(l_q, "1200 mm")
    e_pa = _pressure_pa(e_q, "200 GPa")
    ic_m4 = _inertia_m4(ic_q, "75000 mm**4")
    ib_m4 = _inertia_m4(ib_q, "75000 mm**4")

    if fixity == "pinned":
        # Column bending contribution: 2 columns in parallel, shear P/2 each
        delta_col = (p_n * (h_m**3)) / (6.0 * e_pa * ic_m4)
        # Beam bending contribution: corner rotation theta_beam = M * L / (6 * E * I_b), M = P*H/2
        delta_beam = (p_n * (h_m**2) * l_m) / (12.0 * e_pa * ib_m4)
        # Semi-rigid corner rotation contribution: delta_theta = M / K_theta = (P*H/2) / K_theta
        delta_joint = 0.0
        if k_theta_q is not None:
            k_nm = _rot_stiffness(k_theta_q, "5000 N*m")
            if k_nm <= 0:
                raise ValueError(f"joint_stiffness must be positive, got {k_nm}")
            delta_joint = (p_n * (h_m**2)) / (2.0 * k_nm)
        total_delta_m = delta_col + delta_beam + delta_joint
    elif fixity == "fixed":
        # Roark Table 8.2 Case 2: portal frame with fixed bases
        k_ratio = (ib_m4 / l_m) / (ic_m4 / h_m)
        delta_rigid = ((p_n * (h_m**3)) / (12.0 * e_pa * ic_m4)) * (
            (k_ratio + 2.0) / (6.0 * k_ratio + 1.0)
        )
        delta_joint = 0.0
        if k_theta_q is not None:
            k_nm = _rot_stiffness(k_theta_q, "5000 N*m")
            if k_nm <= 0:
                raise ValueError(f"joint_stiffness must be positive, got {k_nm}")
            delta_joint = (p_n * (h_m**2)) / (4.0 * k_nm)
        total_delta_m = delta_rigid + delta_joint
    else:
        raise ValueError(f"unknown base_fixity {fixity!r}; must be 'pinned' or 'fixed'")

    return Quantity(total_delta_m * 1000.0, "mm")
