"""Private unit helpers for the joint calcs: pint quantities in, SI floats inside."""

from __future__ import annotations

from typing import Any

from napkin2factory.core.units import UnitError

#: A pint quantity from the shared registry.
Qty = Any


# --- Unit conversion helpers --------------------------------------------------------


def _si(q: Qty, unit: str, example: str) -> float:
    """Return ``q`` in ``unit`` as a float; a bare number or wrong dimension raises UnitError.

    One exception type, the same as the structural pack (gate I, S-227).
    """
    if not hasattr(q, "to"):
        raise UnitError(f"joints expects a quantity like {example!r}, got the bare number {q!r}")
    try:
        return float(q.to(unit).magnitude)
    except Exception as exc:
        raise UnitError(f"joints expects a quantity in {unit} ({example}): {exc}") from exc


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
