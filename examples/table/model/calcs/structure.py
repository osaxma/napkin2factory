"""The table's structural calcs: SPEC.md section 4.1, worked from the model's parameters.

Every function takes ``P`` and gives a number or a quantity a requirement is held against.
Sections, beams, columns and tip-over come from ``calckit.structural``; creep, racking, corners,
insert pull-out and wood movement from ``calckit.joints``; densities, stiffness and strength
from the one materials table (``calckit/data/materials.yaml``). Nothing here is typed in twice:
the geometry is the parameters the parts are built from.

The model (the spec's own choices, SPEC.md section 4.0):

* the top and the two long rails bend together as one simply supported beam between the leg
  centres; their stiffnesses add (the slotted fixings carry no shear); the whole 800 mm of the
  top acts; the self weight is the top and the two long rails;
* each glide is a pin at the floor, its 20 mm stem rigid; a leg is the full floor-to-top-underside
  length of the one tube;
* the weld efficiency is the spec's choice, a parameter marked [verify].
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from napkin2factory.calckit import joints, mass_cost, structural
from napkin2factory.core.units import Quantity
from napkin2factory.geometry.materials import material_row

G = 9.80665  # m/s^2, the value calckit.structural uses (SPEC.md conventions)
TOP = "white-oak"
STEEL = "mild steel"


@dataclass(frozen=True)
class Model:
    """Everything the calcs share, read once from the parameters (each read is recorded)."""

    span: Quantity  # leg centre to leg centre along the length
    ei_top: Quantity
    ei_rails: Quantity
    e_top: Quantity
    e_steel: Quantity
    strength_top: Quantity
    strength_steel: Quantity
    i_top: Quantity
    z_top: Quantity
    tube: Any  # RectTubeSection
    top_kg: float
    rails_kg: float  # the two long rails
    frame_kg: float  # all tube and tabs
    hardware_kg: float
    glides_kg: float
    screws_kg: float
    height: Quantity  # floor to the underside of the top
    rail_height: Quantity  # floor to the rail centre line

    @property
    def table_kg(self) -> float:
        """Whole table: top, frame, hardware."""
        return self.top_kg + self.frame_kg + self.hardware_kg

    @property
    def table_n(self) -> float:
        """Weight of the whole table, N."""
        return self.table_kg * G


def _factor(x: float | None) -> Quantity:
    """A factor as a dimensionless quantity, which is what a requirement compares."""
    if x is None:
        raise ValueError("the calc kit gave no factor (no load to compare against)")
    return Quantity(float(x), "dimensionless")


def _row(name: str) -> dict[str, Any]:
    row = material_row(name)
    if row is None:
        raise ValueError(f"no row for {name} in calckit/data/materials.yaml")
    return row


def _model(P: Any) -> Model:  # noqa: N803
    top, steel = _row(TOP), _row(STEEL)
    rho_top = float(mass_cost.density(TOP)[0].to("kg/m**3").magnitude)
    rho_steel = float(mass_cost.density(STEEL)[0].to("kg/m**3").magnitude)
    e_top, e_steel = (
        Quantity(float(top["youngs_modulus"]), "Pa"),
        Quantity(float(steel["youngs_modulus"]), "Pa"),
    )
    mm = Quantity
    width, length = mm(P.mm("table-width"), "mm"), mm(P.mm("table-length"), "mm")
    thick, size, wall = (mm(P.mm(n), "mm") for n in ("top-thickness", "tube-size", "tube-wall"))
    sec_top = structural.rect_section(width, thick)
    tube = structural.rect_tube_section(size, size, wall)
    a_tube = float(tube.A.to("m**2").magnitude)
    h_leg, l_frame, w_frame = (
        P.mm(n) / 1000 for n in ("frame-height", "frame-length", "frame-width")
    )
    s = size.to("m").magnitude
    long_rail, short_rail = l_frame - 2 * s, w_frame - 2 * s  # between the legs
    tube_m = 4 * h_leg + 2 * long_rail + 2 * short_rail
    tab = P.mm("tab-size") / 1000
    tabs_m3 = 8 * tab * tab * (P.mm("tab-thickness") / 1000)  # slots are not subtracted (SPEC 4.0)
    top_kg = (
        float(length.to("m").magnitude * width.to("m").magnitude * thick.to("m").magnitude)
        * rho_top
    )
    glides, inserts, screws = (
        float(P[n].to("kg").magnitude) for n in ("glide-mass", "insert-mass", "screw-mass")
    )
    hardware = 4 * glides + 8 * inserts + 8 * screws
    return Model(
        span=mm(P.mm("leg-pitch-x"), "mm"),
        ei_top=(e_top * sec_top.I).to("N*mm**2"),
        ei_rails=(2 * e_steel * tube.Ix).to("N*mm**2"),
        e_top=e_top,
        e_steel=e_steel,
        strength_top=Quantity(float(top["yield_strength"]), "Pa"),
        strength_steel=Quantity(float(steel["yield_strength"]), "Pa"),
        i_top=sec_top.I,
        z_top=sec_top.Z,
        tube=tube,
        top_kg=top_kg,
        rails_kg=2 * long_rail * a_tube * rho_steel,
        frame_kg=(tube_m * a_tube + tabs_m3) * rho_steel,
        hardware_kg=hardware,
        glides_kg=4 * glides,
        screws_kg=8 * screws,
        height=mm(P.mm("table-height") - P.mm("top-thickness"), "mm"),
        rail_height=mm(P.mm("table-height") - P.mm("top-thickness") - P.mm("tube-size") / 2, "mm"),
    )


def _sag(m: Model, point: Quantity, weight: Quantity) -> Quantity:
    """Mid-span sag of the top and long rails together under a point load and a uniform weight."""
    ei = m.ei_top + m.ei_rails
    i_eq = (ei / m.e_top).to("mm**4")  # one beam of oak stiffness with the combined E*I
    dp = structural.beam_deflection_simply_supported(point, m.span, m.e_top, i_eq)
    dw = structural.beam_deflection_simply_supported(weight, m.span, m.e_top, i_eq, "uniform")
    return (dp.deflection + dw.deflection).to("mm")


def _span_weight(m: Model) -> Quantity:
    """Top plus the two long rails, spread over the span."""
    return Quantity((m.top_kg + m.rails_kg) * G, "N")


def _moment(m: Model, point: Quantity) -> Quantity:
    """M = F L / 4 + W L / 8 under the centre load and the self weight (Roark Table 8.1)."""
    w = _span_weight(m)
    return (point * m.span / 4 + w * m.span / 8).to("N*mm")


def centre_load_sag(P: Any) -> Quantity:  # noqa: N803
    """Mid-span sag under the 150 kg centre load plus the spanning members' weight (SPEC 4.1)."""
    m = _model(P)
    return _sag(m, P["centre-load"], _span_weight(m))


def long_term_sag(P: Any) -> Quantity:  # noqa: N803
    """Final sag under the sustained load plus self weight, timber creep included (SPEC 4.1).

    EN 1995-1-1 section 2.3.2.2 through ``joints.composite_creep_deflection``: only the oak's
    stiffness falls by 1 / (1 + k_def); the steel does not creep.
    """
    m = _model(P)
    elastic = _sag(m, P["sustained-load"], _span_weight(m))
    return joints.composite_creep_deflection(elastic, [(m.ei_top, True), (m.ei_rails, False)]).to(
        "mm"
    )


def top_yield_factor(P: Any) -> Quantity:  # noqa: N803
    """Stress limit of the oak top over its bending stress, under the centre load (SPEC 4.1).

    The moment shares out by stiffness, so the top carries ``M * EI_top / (EI_top + EI_rails)``.
    The limit is the proportional-limit stress of the materials table row.
    """
    m = _model(P)
    share = m.ei_top / (m.ei_top + m.ei_rails)
    res = structural.beam_bending_stress(
        _moment(m, P["centre-load"]) * share, m.z_top, m.strength_top
    )
    return _factor(res.yield_factor)


def rail_yield_factor(P: Any) -> Quantity:  # noqa: N803
    """Yield factor of the steel long rails together under the centre load (SPEC 4.1)."""
    m = _model(P)
    share = m.ei_rails / (m.ei_top + m.ei_rails)
    z_rails = 2 * m.tube.Zx
    res = structural.beam_bending_stress(
        _moment(m, P["centre-load"]) * share, z_rails, m.strength_steel
    )
    return _factor(res.yield_factor)


def member_yield_factor(P: Any) -> Quantity:  # noqa: N803
    """The lowest yield factor of the spanning members, the top and the rails (SPEC req. 4)."""
    return min(top_yield_factor(P), rail_yield_factor(P))


def leg_buckling_factor(P: Any) -> Quantity:  # noqa: N803
    """Buckling factor of one leg carrying the whole centre load and a quarter of the table.

    The glide is a pin and the top fixes the leg's rotation but lets it sway: K = 2.0 over the
    floor-to-top-underside length. The slenderness is below the Euler limit, so the calc kit
    picks the Johnson parabola (Shigley, intermediate columns); ``euler_buckling_load`` would
    refuse this column (SPEC 4.1).
    """
    m = _model(P)
    load = P["centre-load"] + Quantity(m.table_n / 4, "N")
    res = structural.column_buckling_load(
        m.e_steel, m.tube.Ix, m.tube.A, m.strength_steel, m.height, 2.0, load=load
    )
    return _factor(res.safety_factor)


def tip_over_factor(P: Any) -> Quantity:  # noqa: N803
    """Tip-over factor under the edge load at the middle of the worst edge, empty table.

    The tipping edge is the line through the glide centres; the centre of gravity is at the plan
    centre (the frame is symmetric under the top). The front edge, across the width, governs
    (SPEC 4.1); the end edge is worked too and the lower factor is returned.
    """
    m = _model(P)
    mass = Quantity(m.table_kg, "kg")
    factors = []
    for glide_half, edge_half in (
        (P.mm("leg-pitch-y") / 2, P.mm("table-width") / 2),
        (P.mm("leg-pitch-x") / 2, P.mm("table-length") / 2),
    ):
        res = structural.tip_over_safety_factor(
            mass, Quantity(glide_half, "mm"), P["edge-load"], Quantity(edge_half - glide_half, "mm")
        )
        factors.append(res.safety_factor)
    return _factor(min(factors))


def _sway(m: Model, push: Quantity, span: Quantity, i_beam: Quantity) -> Quantity:
    return joints.frame_racking(
        lateral_load=push,
        height=m.rail_height,
        span=span,
        e_modulus=m.e_steel,
        i_column=m.tube.Ix,
        i_beam=i_beam,
        base_fixity="pinned",
    ).to("mm")


def racking_sway(P: Any) -> Quantity:  # noqa: N803
    """Sway at top level under the racking factor times the lateral push (SPEC 4.1).

    Each of the two frames the push runs along carries half of it; the glides are pins and the
    welded corners are rigid; the top's stiffening is ignored. The push along the length and
    across the width are both worked and the larger sway is returned.
    """
    m = _model(P)
    factor = joints.factor_of_safety("racking", "edge_load")
    per_frame = P["lateral-push"] * factor / 2
    along = _sway(m, per_frame, Quantity(P.mm("leg-pitch-x"), "mm"), m.tube.Ix)
    across = _sway(m, per_frame, Quantity(P.mm("leg-pitch-y"), "mm"), m.tube.Ix)
    return max(along, across)


def corner_moment_factor(P: Any) -> Quantity:  # noqa: N803
    """Welded corner capacity over the moment one leg takes from the lateral push (SPEC 4.1).

    Capacity is ``Z * sigma_y * eta`` of the tube (``joints.joint_moment_capacity``); each of
    the four legs takes a quarter of the push as shear over the rail-centre height.
    """
    m = _model(P)
    cap = joints.joint_moment_capacity(
        kind="welded",
        section_modulus=m.tube.Zx,
        yield_strength=m.strength_steel,
        weld_efficiency=float(P["weld-efficiency"].to("").magnitude),
    )
    applied = (P["lateral-push"] / 4 * m.rail_height).to("N*m")
    return _factor(float((cap / applied).to("").magnitude))


def insert_pullout_factor(P: Any) -> Quantity:  # noqa: N803
    """Pull-out factor when the assembled table is lifted by its top (SPEC 4.1).

    The base hangs from the inserts; a warped base hangs on two, so two inserts carry the
    whole base: the frame, the glides and the screws.
    """
    m = _model(P)
    base_n = Quantity((m.frame_kg + m.glides_kg + m.screws_kg) * G, "N")
    return _factor(
        joints.insert_pullout("M8", "hardwood", count=2, applied_load=base_n).safety_factor
    )


def wood_movement_at_slot(P: Any) -> Quantity:  # noqa: N803
    """Across-grain movement of the top at a long-rail fixing over the year's humidity range.

    The fixing is half the row spacing from the top's fixed centreline. The moisture swing is
    the Hailwood-Horrobin equilibrium difference (FPL-GTR-190 Eq. 4-5); passing it as
    ``delta_mc`` keeps the figure the spec's (SPEC 4.1 note).
    """
    low, high = (float(P[n].to("percent").magnitude) for n in ("humidity-low", "humidity-high"))
    swing = joints.equilibrium_moisture_content(high) - joints.equilibrium_moisture_content(low)
    distance = Quantity(P.mm("tab-row-spacing") / 2, "mm")
    return joints.wood_movement(distance, TOP, (low, high), delta_mc=swing).to("mm")


def slot_clearance(P: Any) -> Quantity:  # noqa: N803
    """Free travel of a slotted fixing less the movement there; at least 0 mm keeps the top free.

    The travel is taken as the slot length less the slot width (the screw's clearance hole), the
    spec's conservative reading (SPEC 4.1).
    """
    travel = Quantity(P.mm("slot-length") - P.mm("insert-hole"), "mm")
    return (travel - wood_movement_at_slot(P)).to("mm")
