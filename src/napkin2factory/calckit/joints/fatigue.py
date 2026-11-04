"""Fatigue margin (endurance limit, Marin and Goodman) and factors of safety."""

from __future__ import annotations

import math

from napkin2factory.calckit._tables import load_table
from napkin2factory.calckit.joints._units import Qty, _pressure_pa

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
