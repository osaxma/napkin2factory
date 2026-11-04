"""Wood screw, lag screw and threaded-insert pull-out capacity and safety factor."""

from __future__ import annotations

from dataclasses import dataclass

from napkin2factory.calckit.joints._units import Qty, _force_n, _si
from napkin2factory.calckit.joints.inserts import _SUBSTRATE_ALIASES, THREADED_INSERT_ROWS
from napkin2factory.core.units import Quantity


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
