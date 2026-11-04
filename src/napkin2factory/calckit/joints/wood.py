"""Wood creep deflection and across-grain wood movement with relative humidity."""

from __future__ import annotations

from napkin2factory.calckit._tables import load_table
from napkin2factory.calckit.joints._units import Qty, _si

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
