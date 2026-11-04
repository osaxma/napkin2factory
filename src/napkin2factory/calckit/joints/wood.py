"""Across-grain wood movement with relative humidity (S-201, S-207)."""

from __future__ import annotations

from napkin2factory.calckit._tables import load_table
from napkin2factory.calckit.joints._units import Qty, _si
from napkin2factory.calckit.joints.moisture import DEFAULT_TEMPERATURE, equilibrium_moisture_content


def wood_movement(
    width: Qty,
    species: str,
    humidity_range: tuple[float | Qty, float | Qty] | float | Qty,
    *,
    grain_direction: str = "tangential",
    delta_mc: float | None = None,
    temperature: Qty = DEFAULT_TEMPERATURE,
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
            ``(30, 70)`` or ``(0.30, 0.70)``) or a single swing in RH, taken as centred on
            50 % RH.
        grain_direction: ``"tangential"`` (flat-sawn, default) or ``"radial"`` (quarter-sawn).
        delta_mc: explicit moisture content change in percentage points, if known.
        temperature: air temperature for the humidity-to-moisture conversion (Hailwood-
            Horrobin, FPL-GTR-190 Eq. 4-5; default 21 degC, about 70 degF).

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
        dm = abs(
            equilibrium_moisture_content(h2, temperature)
            - equilibrium_moisture_content(h1, temperature)
        )
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
        # a swing of delta_rh centred on 50 % RH (S-207)
        dm = abs(
            equilibrium_moisture_content(0.5 + delta_rh / 2.0, temperature)
            - equilibrium_moisture_content(0.5 - delta_rh / 2.0, temperature)
        )

    # Delta_W = width * C * Delta_M
    delta_w = width * (c_coeff * dm)
    return delta_w.to("mm")
