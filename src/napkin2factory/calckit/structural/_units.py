"""Private unit helpers: every calc takes pint quantities and computes in SI floats."""

from __future__ import annotations

from typing import Any

from napkin2factory.core.units import Quantity, UnitError

#: A pint quantity from the shared registry (pint is untyped for mypy).
Qty = Any


#: Standard acceleration of gravity, m/s² (ISO 80000-3; CODATA).
STANDARD_GRAVITY = Quantity(9.80665, "m/s**2")


_G_SI = 9.80665


# --- unit conversion and boundary checks ---------------------------------------------


def _si(q: Qty, unit: str, example: str) -> float:
    """``q`` in ``unit`` as a float; bare number or wrong dimension raises UnitError."""
    if not hasattr(q, "to"):
        raise UnitError(
            f"structural expects a quantity like {example!r}, got the bare number {q!r}"
        )
    try:
        return float(q.to(unit).magnitude)
    except Exception as exc:
        raise UnitError(f"structural expects a quantity in {unit} ({example}): {exc}") from exc


def _m(q: Qty, name: str = "length") -> float:
    return _si(q, "m", f"{name}=100 mm")


def _m2(q: Qty, name: str = "area") -> float:
    return _si(q, "m**2", f"{name}=50 mm**2")


def _m3(q: Qty, name: str = "section modulus") -> float:
    return _si(q, "m**3", f"{name}=10000 mm**3")


def _m4(q: Qty, name: str = "moment of inertia") -> float:
    return _si(q, "m**4", f"{name}=1e6 mm**4")


def _n(q: Qty, name: str = "force") -> float:
    return _si(q, "N", f"{name}=1000 N")


def _nm(q: Qty, name: str = "moment") -> float:
    return _si(q, "N*m", f"{name}=150 N*m")


def _pa(q: Qty, name: str = "stress/modulus") -> float:
    return _si(q, "Pa", f"{name}=200 GPa")


def _kg(q: Qty, name: str = "mass") -> float:
    return _si(q, "kg", f"{name}=25 kg")


def _dimless(q: Qty, name: str = "dimensionless") -> float:
    return _si(q, "dimensionless", f"{name}=Quantity(1.0, '')")
