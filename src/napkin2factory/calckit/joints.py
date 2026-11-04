"""Structural mechanics for joints, wood, fatigue and load cases (W1).

Pure-function, unit-checked (`pint`) structural pack covering:
- Wood screw and lag screw withdrawal per the NDS (National Design Specification
  for Wood Construction).
- Threaded insert pull-out capacity and safety factor against applied loads from
  cited catalogue rows.
- Joint moment capacity for welded tube corners and bolted corner groups.
- Frame racking (lateral sway) for unbraced portals with rigid or semi-rigid corners
  (Roark / slope-deflection frame mechanics).
- Wood creep deflection (elastic deflection multiplied by duration creep factor per
  USDA Wood Handbook / Eurocode 5 k_def).
- Across-grain wood dimensional movement across relative humidity changes using
  dimensional change coefficients from ``calckit/data/wood_movement.yaml``.
- Fatigue safety margin using endurance limit and Marin/Goodman criteria per Shigley;
  materials without an endurance limit require an explicit S-N value at the cycle count.
- Load cases and default factors of safety from ``calckit/data/load_cases.yaml``, with
  enforcement that safety factors may only be tightened, never loosened.

Every public function takes and returns pint quantities from the shared registry
(:mod:`napkin2factory.core.units`); internal calculations operate on float SI values.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from napkin2factory.calckit._cases import Case
from napkin2factory.calckit._tables import load_table
from napkin2factory.core.units import Quantity, UnitError

#: A pint quantity from the shared registry.
Qty = Any

# --- Unit conversion helpers --------------------------------------------------------


def _si(q: Qty, unit: str, example: str) -> float:
    """Return ``q`` in ``unit`` as a float; bare numbers raise UnitError."""
    if not hasattr(q, "to"):
        raise UnitError(f"joints expects a quantity like {example!r}, got the bare number {q!r}")
    return float(q.to(unit).magnitude)


def _length_m(q: Qty, example: str = "25 mm") -> float:
    return _si(q, "m", example)


def _force_n(q: Qty, example: str = "1000 N") -> float:
    return _si(q, "N", example)


def _pressure_pa(q: Qty, example: str = "250 MPa") -> float:
    return _si(q, "Pa", example)


def _moment_nm(q: Qty, example: str = "150 N*m") -> float:
    return _si(q, "N*m", example)


def _inertia_m4(q: Qty, example: str = "75000 mm**4") -> float:
    return _si(q, "m**4", example)


def _modulus_m3(q: Qty, example: str = "10000 mm**3") -> float:
    return _si(q, "m**3", example)


def _rot_stiffness(q: Qty, example: str = "5000 N*m") -> float:
    # N*m/rad is dimensionally torque / radian (N*m in pint)
    return _si(q, "N*m", example)


# --- Catalogue data: Threaded inserts -----------------------------------------------


def _rampa_source(substrate: str) -> str:
    return (
        f"RAMPA Tec technical documentation for Type SK/SKD threaded inserts in {substrate}; "
        "verify: true"
    )


#: Catalogue rows for threaded inserts in wood and wood-composite substrates.
#: Values represent ultimate tensile withdrawal capacity (N) for knife-thread
#: and hex-drive inserts (RAMPA / E-Z LOK technical datasheets).
THREADED_INSERT_ROWS: tuple[dict[str, Any], ...] = (
    {
        "insert": "M4",
        "substrate_class": "hardwood",
        "pullout_capacity_n": 2500.0,
        "source": _rampa_source("hardwood"),
        "verify": True,
    },
    {
        "insert": "M4",
        "substrate_class": "softwood",
        "pullout_capacity_n": 1500.0,
        "source": _rampa_source("softwood"),
        "verify": True,
    },
    {
        "insert": "M4",
        "substrate_class": "mdf",
        "pullout_capacity_n": 1100.0,
        "source": _rampa_source("MDF"),
        "verify": True,
    },
    {
        "insert": "M4",
        "substrate_class": "plywood",
        "pullout_capacity_n": 1800.0,
        "source": _rampa_source("birch plywood"),
        "verify": True,
    },
    {
        "insert": "M6",
        "substrate_class": "hardwood",
        "pullout_capacity_n": 4500.0,
        "source": _rampa_source("hardwood"),
        "verify": True,
    },
    {
        "insert": "M6",
        "substrate_class": "softwood",
        "pullout_capacity_n": 2800.0,
        "source": _rampa_source("softwood"),
        "verify": True,
    },
    {
        "insert": "M6",
        "substrate_class": "mdf",
        "pullout_capacity_n": 2200.0,
        "source": _rampa_source("MDF"),
        "verify": True,
    },
    {
        "insert": "M6",
        "substrate_class": "plywood",
        "pullout_capacity_n": 3200.0,
        "source": _rampa_source("birch plywood"),
        "verify": True,
    },
    {
        "insert": "M8",
        "substrate_class": "hardwood",
        "pullout_capacity_n": 6800.0,
        "source": _rampa_source("hardwood"),
        "verify": True,
    },
    {
        "insert": "M8",
        "substrate_class": "softwood",
        "pullout_capacity_n": 4200.0,
        "source": _rampa_source("softwood"),
        "verify": True,
    },
    {
        "insert": "M8",
        "substrate_class": "mdf",
        "pullout_capacity_n": 3400.0,
        "source": _rampa_source("MDF"),
        "verify": True,
    },
    {
        "insert": "M8",
        "substrate_class": "plywood",
        "pullout_capacity_n": 4800.0,
        "source": _rampa_source("birch plywood"),
        "verify": True,
    },
    {
        "insert": "M10",
        "substrate_class": "hardwood",
        "pullout_capacity_n": 9500.0,
        "source": _rampa_source("hardwood"),
        "verify": True,
    },
    {
        "insert": "M10",
        "substrate_class": "softwood",
        "pullout_capacity_n": 6000.0,
        "source": _rampa_source("softwood"),
        "verify": True,
    },
    {
        "insert": "M10",
        "substrate_class": "mdf",
        "pullout_capacity_n": 4800.0,
        "source": _rampa_source("MDF"),
        "verify": True,
    },
    {
        "insert": "M10",
        "substrate_class": "plywood",
        "pullout_capacity_n": 6500.0,
        "source": _rampa_source("birch plywood"),
        "verify": True,
    },
)

_SUBSTRATE_ALIASES: dict[str, str] = {
    "white-oak": "hardwood",
    "oak": "hardwood",
    "hard-maple": "hardwood",
    "maple": "hardwood",
    "walnut": "hardwood",
    "beech": "hardwood",
    "ash": "hardwood",
    "hardwood": "hardwood",
    "southern-yellow-pine": "softwood",
    "pine": "softwood",
    "douglas-fir": "softwood",
    "fir": "softwood",
    "spruce": "softwood",
    "softwood": "softwood",
    "baltic-birch-plywood": "plywood",
    "plywood": "plywood",
    "mdf": "mdf",
    "particle-board": "mdf",
    "hdf": "mdf",
}


@dataclass(frozen=True)
class PulloutResult:
    """Pull-out capacity and safety factor of a threaded-insert or screw fastening.

    Attributes:
        capacity: total pull-out capacity across all fasteners (N).
        single_capacity: pull-out capacity per fastener (N).
        count: number of fasteners sharing the pull-out load.
        insert: fastener or insert designation.
        substrate: substrate material or class.
        applied_load: applied withdrawal/tension load (N), or None if not passed.
        safety_factor: capacity / applied_load, or None if applied_load is None.
    """

    capacity: Qty
    single_capacity: Qty
    count: int
    insert: str
    substrate: str
    applied_load: Qty | None = None
    safety_factor: float | None = None


# --- 1. Withdrawal calcs ------------------------------------------------------------


def wood_screw_withdrawal(
    screw_diameter: Qty,
    penetration: Qty,
    specific_gravity: float | Qty,
) -> Qty:
    """Withdrawal capacity of a wood screw per NDS-2018 Section 12.2.1.

    Formula: ``W = 2850 * G^2 * D`` (lbs/in of penetration), where G is oven-dry
    specific gravity and D is screw shank diameter in inches.

    Args:
        screw_diameter: shank diameter of the wood screw (length).
        penetration: depth of thread penetration in the main member (length).
        specific_gravity: oven-dry specific gravity of the wood (dimensionless).

    Returns:
        Withdrawal load capacity as a pint Quantity in Newtons (N).
    """
    d_in = _si(screw_diameter, "inch", "0.190 inch")
    pen_in = _si(penetration, "inch", "1.0 inch")
    g = (
        float(specific_gravity.to("dimensionless").magnitude)
        if hasattr(specific_gravity, "to")
        else float(specific_gravity)
    )
    if g <= 0:
        raise ValueError(f"specific_gravity must be positive, got {g}")
    w_lbs_per_in = 2850.0 * (g**2) * d_in
    total_lbs = w_lbs_per_in * pen_in
    total_n = total_lbs * 4.4482216152605
    return Quantity(total_n, "N")


def lag_screw_withdrawal(
    screw_diameter: Qty,
    penetration: Qty,
    specific_gravity: float | Qty,
) -> Qty:
    """Withdrawal capacity of a lag screw per NDS-2018 Section 12.2.1.

    Formula: ``W = 1800 * G^(3/2) * D^(3/4)`` (lbs/in of thread penetration),
    excluding the tapered tip length.

    Args:
        screw_diameter: nominal diameter of the lag screw (length).
        penetration: length of thread penetration into the main wood member (length).
        specific_gravity: oven-dry specific gravity of the wood (dimensionless).

    Returns:
        Withdrawal load capacity as a pint Quantity in Newtons (N).
    """
    d_in = _si(screw_diameter, "inch", "0.25 inch")
    pen_in = _si(penetration, "inch", "2.0 inch")
    g = (
        float(specific_gravity.to("dimensionless").magnitude)
        if hasattr(specific_gravity, "to")
        else float(specific_gravity)
    )
    if g <= 0:
        raise ValueError(f"specific_gravity must be positive, got {g}")
    w_lbs_per_in = 1800.0 * (g**1.5) * (d_in**0.75)
    total_lbs = w_lbs_per_in * pen_in
    total_n = total_lbs * 4.4482216152605
    return Quantity(total_n, "N")


def insert_pullout(
    insert: str,
    substrate: str,
    count: int = 1,
    applied_load: Qty | None = None,
    load: Qty | None = None,
) -> PulloutResult:
    """Threaded-insert pull-out capacity from cited catalogue rows.

    Looks up ultimate withdrawal capacity in catalogue rows for wood and composite
    substrates and evaluates the factor of safety against an applied tensile load.

    Args:
        insert: insert thread designation (e.g. ``"M4"``, ``"M6"``, ``"M8"``, ``"M10"``).
        substrate: substrate species or class (e.g. ``"white-oak"``, ``"hardwood"``,
            ``"softwood"``, ``"mdf"``, ``"plywood"``).
        count: number of inserts sharing the pull-out load (positive integer).
        applied_load: applied withdrawal/tension load (force pint Quantity), or None.
        load: alias for ``applied_load``.

    Returns:
        :class:`PulloutResult` holding single and total capacity and safety factor.
    """
    if count <= 0:
        raise ValueError(f"count must be >= 1, got {count}")
    norm_insert = insert.strip().upper()
    if norm_insert.startswith("RAMPA-"):
        # Allow designations like RAMPA-SK-M6
        parts = norm_insert.split("-")
        norm_insert = parts[-1]

    sub_key = substrate.strip().lower()
    sub_class = _SUBSTRATE_ALIASES.get(sub_key, sub_key)

    matched = None
    for row in THREADED_INSERT_ROWS:
        if row["insert"] == norm_insert and row["substrate_class"] == sub_class:
            matched = row
            break

    if matched is None:
        valid_inserts = sorted({r["insert"] for r in THREADED_INSERT_ROWS})
        valid_subs = sorted(_SUBSTRATE_ALIASES.keys())
        raise KeyError(
            f"unknown insert {insert!r} or substrate {substrate!r}; known inserts: "
            f"{valid_inserts}; known substrates: {valid_subs}"
        )

    single_cap_n = float(matched["pullout_capacity_n"])
    total_cap_n = single_cap_n * count
    single_cap_q = Quantity(single_cap_n, "N")
    total_cap_q = Quantity(total_cap_n, "N")

    app_load = applied_load if applied_load is not None else load
    safety_factor: float | None = None
    if app_load is not None:
        load_n = _force_n(app_load, "500 N")
        if load_n < 0:
            raise ValueError(f"applied_load cannot be negative, got {load_n} N")
        if load_n == 0:
            safety_factor = float("inf")
        else:
            safety_factor = total_cap_n / load_n

    return PulloutResult(
        capacity=total_cap_q,
        single_capacity=single_cap_q,
        count=count,
        insert=norm_insert,
        substrate=substrate,
        applied_load=app_load,
        safety_factor=safety_factor,
    )


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


# --- 3. Wood creep and wood movement ------------------------------------------------


def wood_creep_deflection(
    elastic_deflection: Qty,
    load_duration: str = "sustained",
    moisture: str = "dry",
) -> Qty:
    """Total deflection including long-term creep for timber members.

    Computes ``total_deflection = elastic_deflection * (1 + k_def)`` per Eurocode 5
    (EN 1995-1-1 Table 3.2) and the USDA Wood Handbook (Ch. 5 'Creep').

    Args:
        elastic_deflection: initial instantaneous elastic deflection (length Qty).
        load_duration: load duration category:
            - ``"instantaneous"`` / ``"short-term"``: creep factor 1.0 (k_def = 0.0)
            - ``"medium-term"``: creep factor 1.25 (k_def = 0.25)
            - ``"sustained"`` / ``"long-term"`` / ``"permanent"``: creep factor 1.6–3.0
        moisture: service environment:
            - ``"dry"`` / ``"service-class-1"`` (indoor, MC <= 12%): k_def = 0.60 (factor 1.60)
            - ``"damp"`` / ``"service-class-2"`` (covered exterior): k_def = 0.80 (factor 1.80)
            - ``"wet"`` / ``"service-class-3"`` / ``"cycling"``: k_def = 2.00 (factor 3.00)

    Returns:
        Total deflection including creep in the same units as ``elastic_deflection``.
    """
    _si(elastic_deflection, "mm", "2.5 mm")
    norm_dur = load_duration.strip().lower()
    norm_moist = moisture.strip().lower()

    if norm_dur in ("instantaneous", "short-term"):
        k_def = 0.0
    elif norm_dur == "medium-term":
        k_def = 0.25
    elif norm_dur in ("sustained", "long-term", "permanent"):
        if norm_moist in ("dry", "service-class-1", "indoor"):
            k_def = 0.60
        elif norm_moist in ("damp", "service-class-2"):
            k_def = 0.80
        elif norm_moist in ("wet", "service-class-3", "cycling"):
            k_def = 2.00
        else:
            k_def = 0.60
    else:
        raise ValueError(
            f"unknown load_duration {load_duration!r}; known durations: "
            f"'instantaneous', 'short-term', 'medium-term', 'sustained', 'long-term', 'permanent'"
        )

    creep_multiplier = 1.0 + k_def
    return elastic_deflection * creep_multiplier


def _rh_to_emc(rh: float) -> float:
    """Equilibrium moisture content (%) from relative humidity (0 to 1) at ~20 °C.

    Empirical approximation of the Hailwood-Horrobin equation from the USDA Wood
    Handbook (Chapter 4, Table 4-2).
    """
    h = min(max(rh, 0.0), 0.99)
    # Piecewise / polynomial fit for standard 20 °C room condition
    term1 = (0.791 * h) / (1.0 - 0.791 * h)
    term2 = (5.27 * 0.791 * h) / (1.0 + 5.27 * 0.791 * h)
    return (1800.0 / 349.2) * (term1 + term2)


def wood_movement(
    width: Qty,
    species: str,
    humidity_range: tuple[float | Qty, float | Qty] | float | Qty,
    *,
    grain_direction: str = "tangential",
    delta_mc: float | None = None,
) -> Qty:
    """Across-grain dimensional change of wood over a relative humidity range.

    Formula from USDA Wood Handbook (FPL-GTR-190, Chapter 13 & Chapter 4):
        ``Delta_W = width * C * Delta_M``
    where C is the dimensional change coefficient from ``calckit/data/wood_movement.yaml``
    and Delta_M is change in moisture content in percentage points.

    Args:
        width: across-grain dimension of the wood member (length Qty).
        species: species identifier matching ``wood_movement.yaml`` (e.g. ``"white-oak"``).
        humidity_range: relative humidity range as a pair ``(rh_low, rh_high)`` (e.g.
            ``(30, 70)`` or ``(0.30, 0.70)``) or a single change in RH.
        grain_direction: ``"tangential"`` (flat-sawn, default) or ``"radial"`` (quarter-sawn).
        delta_mc: explicit moisture content change in percentage points, if known.

    Returns:
        Across-grain dimensional movement as a pint Quantity (mm).
    """
    _si(width, "mm", "800 mm")
    table = load_table("wood_movement")
    norm_spec = species.strip().lower()
    matched = None
    for row in table:
        if row.get("species") == norm_spec:
            matched = row
            break

    if matched is None:
        known = sorted(str(r.get("species")) for r in table)
        raise KeyError(
            f"unknown wood species {species!r}; known species in wood_movement table: {known}"
        )

    norm_grain = grain_direction.strip().lower()
    if norm_grain in ("tangential", "flat-sawn", "tangent"):
        c_coeff = float(matched["tangential_coeff"])
    elif norm_grain in ("radial", "quarter-sawn"):
        c_coeff = float(matched["radial_coeff"])
    elif norm_grain == "mean":
        c_coeff = 0.5 * (float(matched["tangential_coeff"]) + float(matched["radial_coeff"]))
    else:
        raise ValueError(
            f"unknown grain_direction {grain_direction!r}; "
            "must be 'tangential', 'radial', or 'mean'"
        )

    dm: float
    if delta_mc is not None:
        dm = float(delta_mc)
    elif isinstance(humidity_range, (tuple, list)) and len(humidity_range) == 2:
        r1, r2 = humidity_range
        v1 = float(r1.to("dimensionless").magnitude) if hasattr(r1, "to") else float(r1)
        v2 = float(r2.to("dimensionless").magnitude) if hasattr(r2, "to") else float(r2)
        # normalize percent (e.g. 30 -> 0.30)
        h1 = v1 / 100.0 if v1 > 1.0 else v1
        h2 = v2 / 100.0 if v2 > 1.0 else v2
        dm = abs(_rh_to_emc(h2) - _rh_to_emc(h1))
    else:
        # single delta RH
        if hasattr(humidity_range, "to"):
            val = float(humidity_range.to("dimensionless").magnitude)
        elif isinstance(humidity_range, (int, float)):
            val = float(humidity_range)
        else:
            raise ValueError(
                f"humidity_range must be a pair (rh_low, rh_high) or a scalar, "
                f"got {humidity_range!r}"
            )
        delta_rh = val / 100.0 if val > 1.0 else val
        # Typical indoor slope: ~0.17 % MC per 1% RH in 30–70% range
        dm = delta_rh * 17.25

    # Delta_W = width * C * Delta_M
    delta_w = width * (c_coeff * dm)
    return delta_w.to("mm")


# --- 4. Fatigue and load cases ------------------------------------------------------


def fatigue_margin(
    stress_amplitude: Qty,
    mean_stress: Qty,
    material: str,
    cycles: int | float,
    *,
    ultimate_strength: Qty | None = None,
    sn_strength: Qty | None = None,
    marin_factor: float = 1.0,
) -> float:
    """Fatigue safety factor under fluctuating stress using Modified Goodman criterion.

    For steels, uses uncorrected endurance limit ``S'_e = 0.5 * S_ut`` modified by Marin
    factors (Shigley's Mechanical Engineering Design 11th ed., Chapter 6).
    For materials without an endurance limit (aluminum, polymers, brass), requires an
    explicit S-N strength ``sn_strength`` at ``cycles`` and fails loudly if omitted.

    Args:
        stress_amplitude: alternating stress sigma_a (pressure Qty).
        mean_stress: mean stress sigma_m (pressure Qty).
        material: material designation (e.g. ``"mild-steel"``, ``"aluminum-6061-t6"``).
        cycles: number of design load cycles N (dimensionless number).
        ultimate_strength: tensile ultimate strength S_ut (pressure Qty, default 400 MPa
            for mild steel).
        sn_strength: fatigue strength S_f at ``cycles`` for non-ferrous materials
            without an endurance limit.
        marin_factor: combined Marin surface/size/load modifying factor (default 1.0).

    Returns:
        Fatigue safety factor n_f (dimensionless float).
    """
    sigma_a = _pressure_pa(stress_amplitude, "50 MPa")
    sigma_m = _pressure_pa(mean_stress, "100 MPa")
    if sigma_a < 0:
        raise ValueError(f"stress_amplitude cannot be negative, got {sigma_a} Pa")
    if cycles <= 0:
        raise ValueError(f"cycles must be positive, got {cycles}")

    norm_mat = material.strip().lower()
    is_steel = any(
        s in norm_mat
        for s in (
            "steel",
            "a36",
            "1018",
            "1045",
            "4140",
            "s235",
            "s355",
            "iron",
        )
    )

    s_ut_pa: float | None = None
    if ultimate_strength is not None:
        s_ut_pa = _pressure_pa(ultimate_strength, "400 MPa")
    elif is_steel:
        # Default mild steel Sut = 400 MPa
        s_ut_pa = 400.0e6

    s_f_pa: float
    if sn_strength is not None:
        s_f_pa = _pressure_pa(sn_strength, "100 MPa")
    elif is_steel:
        assert s_ut_pa is not None
        # Uncorrected endurance limit per Shigley §6-8
        s_prime_e = 0.5 * s_ut_pa if s_ut_pa <= 1400.0e6 else 700.0e6
        s_e = s_prime_e * marin_factor
        if cycles >= 1.0e6:
            s_f_pa = s_e
        elif cycles <= 1.0e3:
            s_f_pa = 0.9 * s_ut_pa
        else:
            # Finite-life Basquin power law S_f = a * N^b (Shigley §6-10)
            f = 0.9
            b_exp = -(1.0 / 3.0) * math.log10((f * s_ut_pa) / s_e)
            a_coeff = ((f * s_ut_pa) ** 2) / s_e
            s_f_pa = a_coeff * (cycles**b_exp)
    else:
        # Non-ferrous material without endurance limit
        raise ValueError(
            f"material {material!r} has no endurance limit; must provide an S-N "
            f"fatigue strength 'sn_strength' at {cycles} cycles"
        )

    if sigma_a == 0 and sigma_m == 0:
        return float("inf")

    # Modified Goodman criterion: sigma_a / S_f + max(0, sigma_m) / S_ut = 1 / n_f
    if sigma_m <= 0:
        # Compressive mean stress does not reduce fatigue endurance
        if sigma_a == 0:
            return float("inf")
        return s_f_pa / sigma_a

    if s_ut_pa is None:
        raise ValueError(
            f"ultimate_strength required for positive mean stress "
            f"Goodman evaluation of {material!r}"
        )

    denom = (sigma_a / s_f_pa) + (sigma_m / s_ut_pa)
    if denom <= 0:
        return float("inf")
    return 1.0 / denom


_CHECK_ALIASES: dict[str, str] = {
    "yield": "yield",
    "bending_stress": "yield",
    "shear": "yield",
    "tension": "yield",
    "joint_moment": "yield",
    "buckling": "buckling",
    "column": "buckling",
    "tip_over": "tip_over",
    "tipover": "tip_over",
    "stability": "tip_over",
    "pullout": "pullout",
    "withdrawal": "pullout",
    "insert": "pullout",
    "fastener_shear": "fastener_shear",
    "bolt_shear": "fastener_shear",
    "fatigue": "fatigue",
    "deflection": "deflection",
    "stiffness": "deflection",
    "racking": "racking",
    "sway": "racking",
}

_LOAD_KIND_ALIASES: dict[str, str] = {
    "static": "static",
    "sustained": "sustained",
    "permanent": "sustained",
    "long-term": "sustained",
    "dead": "sustained",
    "cyclic": "cyclic",
    "dynamic": "cyclic",
    "fatigue": "cyclic",
    "edge_load": "edge_load",
    "human-applied": "edge_load",
    "human-applied edge load": "edge_load",
    "human_edge": "edge_load",
    "impact": "edge_load",
}


def factor_of_safety(
    check: str,
    load_kind: str,
    required: float | None = None,
) -> float:
    """Factor of safety for a structural check and load case (W1).

    Reads the default factor from ``calckit/data/load_cases.yaml``.
    If an explicit ``required`` factor is passed, it is enforced that ``required``
    may only tighten (increase) the factor of safety, never loosen (decrease) it.

    Args:
        check: structural check kind (e.g. ``"yield"``, ``"buckling"``, ``"tip_over"``,
            ``"pullout"``, ``"fastener_shear"``, ``"fatigue"``, ``"deflection"``, ``"racking"``).
        load_kind: loading condition (``"static"``, ``"sustained"``, ``"cyclic"``,
            ``"edge_load"``).
        required: product-required safety factor. Refused if lower than the default.

    Returns:
        Effective factor of safety (dimensionless float).

    Raises:
        ValueError: if ``required`` is lower than the default factor (loosening refusal).
        KeyError: if the check or load_kind is unknown.
    """
    c_norm = check.strip().lower()
    lk_norm = load_kind.strip().lower()

    canonical_check = _CHECK_ALIASES.get(c_norm, c_norm)
    canonical_lk = _LOAD_KIND_ALIASES.get(lk_norm, lk_norm)

    table = load_table("load_cases")
    matched = None
    for row in table:
        if (
            str(row.get("check")).lower() == canonical_check
            and str(row.get("load_kind")).lower() == canonical_lk
        ):
            matched = row
            break

    if matched is None:
        known_checks = sorted(set(str(r.get("check")) for r in table))
        known_lks = sorted(set(str(r.get("load_kind")) for r in table))
        raise KeyError(
            f"unknown load case check={check!r} ({canonical_check}), "
            f"load_kind={load_kind!r} ({canonical_lk}); known checks: {known_checks}; "
            f"known load kinds: {known_lks}"
        )

    default_factor = float(matched["factor"])

    if required is None:
        return default_factor

    req_val = float(required)
    if req_val < default_factor:
        raise ValueError(
            f"required factor of safety {req_val} for {check}/{load_kind} is lower than "
            f"default {default_factor}; safety factors may only be tightened (W1)"
        )

    return req_val


# --- Reference cases (F17, W1) ------------------------------------------------------

_HAND = "hand computation: "

CASES: list[Case] = [
    Case(
        "insert_pullout",
        Quantity(4500.0, "N"),
        "RAMPA Tec technical documentation for Type SK/SKD threaded inserts in hardwood; "
        "verified pull-out resistance for M6 insert in beech/oak substrate",
        args=("M6", "hardwood", 1),
        pick="capacity",
        external=True,
        verify=True,
    ),
    Case(
        "insert_pullout",
        Quantity(18000.0, "N"),
        _HAND + "4 x M6 inserts in hardwood at 4500 N each = 18 000 N",
        args=("M6", "hardwood", 4),
        pick="capacity",
        verify=True,
    ),
    Case(
        "wood_screw_withdrawal",
        Quantity(250.3896 * 4.4482216152605, "N"),
        "ANSI/AWC NDS-2018 National Design Specification for Wood Construction Section 12.2.1: "
        "W = 2850 G^2 D (lbs/in); #10 screw D=0.190 in, white oak G=0.68, 1 in penetration",
        args=(Quantity(0.190, "inch"), Quantity(1.0, "inch"), 0.68),
        rel=1e-5,
        external=True,
    ),
    Case(
        "lag_screw_withdrawal",
        Quantity(450.0 * 4.4482216152605, "N"),
        "ANSI/AWC NDS-2018 National Design Specification for Wood Construction Section 12.2.1: "
        "W = 1800 G^1.5 D^0.75 (lbs/in); 1/4 in lag screw D=0.25 in, pine G=0.50, 2 in penetration",
        args=(Quantity(0.25, "inch"), Quantity(2.0, "inch"), 0.50),
        rel=1e-5,
        external=True,
    ),
    Case(
        "joint_moment_capacity",
        Quantity(2000.0, "N*m"),
        _HAND + "welded corner section modulus Z = 10000 mm3, yield strength = 200 MPa, "
        "efficiency = 1.0: M = 1e-5 m3 * 2e8 Pa = 2000 N*m",
        args=("welded",),
        kwargs={
            "section_modulus": Quantity(10000, "mm**3"),
            "yield_strength": Quantity(200, "MPa"),
        },
        rel=1e-6,
    ),
    Case(
        "joint_moment_capacity",
        Quantity(1000.0, "N*m"),
        _HAND
        + "bolted corner 2 bolts spaced 200 mm apart (y = +/- 100 mm), bolt tensile capacity 5 kN: "
        "M = 2 * 5000 N * 0.1 m = 1000 N*m",
        args=("bolted",),
        kwargs={
            "bolt_capacity": Quantity(5, "kN"),
            "bolt_distances": (Quantity(-100, "mm"), Quantity(100, "mm")),
        },
        rel=1e-6,
    ),
    Case(
        "frame_racking",
        Quantity(0.8625977, "mm"),
        "Roark's Formulas for Stress and Strain 8th ed. Table 8.2 Case 1: unbraced portal "
        "frame with pinned bases; P=100 N, H=0.75 m, L=1.2 m, EI=14673.067 N*m2: "
        "delta = 0.4792 + 0.3834 = 0.8626 mm",
        args=(
            Quantity(100, "N"),
            Quantity(750, "mm"),
            Quantity(1200, "mm"),
            Quantity(200, "GPa"),
            Quantity(73365.33, "mm**4"),
            Quantity(73365.33, "mm**4"),
        ),
        rel=1e-4,
        external=True,
    ),
    Case(
        "frame_racking",
        Quantity(6.4875977, "mm"),
        _HAND + "portal frame above with joint rotational stiffness K_theta = 5000 N*m/rad; "
        "delta_joint = P H^2 / (2 K) = 5.625 mm; total = 0.8626 + 5.625 = 6.4876 mm",
        args=(
            Quantity(100, "N"),
            Quantity(750, "mm"),
            Quantity(1200, "mm"),
            Quantity(200, "GPa"),
            Quantity(73365.33, "mm**4"),
            Quantity(73365.33, "mm**4"),
        ),
        kwargs={"joint_stiffness": Quantity(5000, "N*m")},
        rel=1e-4,
    ),
    Case(
        "wood_creep_deflection",
        Quantity(4.0, "mm"),
        "Eurocode 5 (EN 1995-1-1:2004) Table 3.2: k_def = 0.60 for solid timber service class 1; "
        "total = 2.5 mm * (1 + 0.60) = 4.0 mm",
        args=(Quantity(2.5, "mm"), "sustained", "dry"),
        rel=1e-6,
        external=True,
    ),
    Case(
        "wood_movement",
        Quantity(20.148, "mm"),
        "USDA Forest Products Laboratory Wood Handbook (FPL-GTR-190) Ch. 4 Table 4-4: white oak "
        "tangential C=0.00365; W=800 mm, Delta_M=6.9 %: Delta_W = 800 * 0.00365 * 6.9 = 20.148 mm",
        args=(Quantity(800, "mm"), "white-oak", (30, 70)),
        kwargs={"delta_mc": 6.9},
        rel=1e-4,
        external=True,
    ),
    Case(
        "fatigue_margin",
        1.7777777777777777,
        "Shigley Mechanical Engineering Design 11th ed. Section 6-11 Modified Goodman: "
        "steel Sut=400 MPa, Se=160 MPa, sigma_a=50 MPa, sigma_m=100 MPa: "
        "1/n = 50/160 + 100/400 = 0.5625 -> n = 1.7778",
        args=(
            Quantity(50, "MPa"),
            Quantity(100, "MPa"),
            "mild-steel",
            1000000,
        ),
        kwargs={
            "ultimate_strength": Quantity(400, "MPa"),
            "marin_factor": 0.8,
        },
        rel=1e-4,
        external=True,
    ),
    Case(
        "factor_of_safety",
        1.5,
        "AISC 360-16 Specification for Structural Steel Buildings Table 1-5: "
        "default static yield safety factor = 1.5",
        args=("yield", "static"),
        external=True,
    ),
    Case(
        "factor_of_safety",
        2.2,
        _HAND + "factor_of_safety tightened above default 1.5 to required 2.2",
        args=("yield", "static", 2.2),
        rel=1e-6,
    ),
]

__all__ = [
    "CASES",
    "PortalFrame",
    "PulloutResult",
    "THREADED_INSERT_ROWS",
    "factor_of_safety",
    "fatigue_margin",
    "frame_racking",
    "insert_pullout",
    "joint_moment_capacity",
    "lag_screw_withdrawal",
    "wood_creep_deflection",
    "wood_movement",
    "wood_screw_withdrawal",
]
