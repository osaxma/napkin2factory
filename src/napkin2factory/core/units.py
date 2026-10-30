"""The unit registry (decision D21, D32).

pint everywhere in the model.  This module *defines* the non-stock units the model
relies on and pins the handling of the awkward ones:

* ``USD`` — currency as its own dimension (``[currency]``), so ``85 USD * 3`` rolls up
  and ``85 USD + 10 mm`` is a dimensionality error, never a silent number.
* ``d`` — day; pint's stock alias, asserted present at import so a registry change
  cannot drop it.
* ``degC`` — an affine (offset) unit.  Quantities are constructed with
  ``Quantity(magnitude, unit)`` (never ``magnitude * unit``) so pint does not raise
  ``OffsetUnitCalculusError``; comparisons between two ``degC`` values are fine, and
  arithmetic uses ``delta_degC`` or kelvin explicitly.

The parse/format pair round-trips ``"60 degC"``, ``"85 USD"``, ``"10 d"``, ``"1.5 mm"``.
"""

from __future__ import annotations

import re
from typing import Any

import pint

ureg = pint.UnitRegistry(autoconvert_offset_to_baseunit=False)
ureg.define("USD = [currency] = usd = dollar")
ureg.define("EUR = [currency_eur]")  # kept distinct on purpose: no silent FX
ureg.define("GBP = [currency_gbp]")
Quantity = ureg.Quantity
Unit = ureg.Unit

# Stock aliases we rely on: fail loudly at import if a pint upgrade changes them.
assert str(ureg.Unit("d")) == "day", "pint lost the 'd' alias for day"
assert str(ureg.Unit("degC")) == "degree_Celsius", "pint lost the 'degC' alias"

#: Canonical short spellings for formatting.  Anything else falls back to pint's ``~``.
_SHORT: dict[str, str] = {
    "degree_Celsius": "degC",
    "delta_degree_Celsius": "delta_degC",
    "day": "d",
    "dimensionless": "",
    "USD": "USD",
    "EUR": "EUR",
    "GBP": "GBP",
}

_QTY_RE = re.compile(r"^\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*(.*?)\s*$")


class UnitError(ValueError):
    """A string could not be parsed as a quantity, or units do not match."""


def parse_quantity(text: str | int | float, default_unit: str | None = None) -> Any:
    """Parse ``"60 degC"``, ``"85 USD"``, ``"10 d"``, ``"200"`` into a pint quantity.

    Args:
        text: the string (or a bare number, which takes ``default_unit`` or is dimensionless).
        default_unit: unit applied when ``text`` carries none.

    Raises:
        UnitError: on malformed input or an unknown unit.
    """
    if isinstance(text, bool):
        raise UnitError(f"{text!r} is not a quantity")
    if isinstance(text, (int, float)):
        return Quantity(text, default_unit or "dimensionless")
    m = _QTY_RE.match(str(text))
    if not m:
        raise UnitError(
            f"{text!r} is not a quantity; write a number followed by a unit, like '50 mm'"
        )
    mag_s, unit_s = m.group(1), m.group(2) or (default_unit or "")
    mag: float | int = float(mag_s)
    if mag == int(mag) and "." not in mag_s and "e" not in mag_s.lower():
        mag = int(mag)
    try:
        unit = ureg.Unit(unit_s) if unit_s else ureg.Unit("dimensionless")
    except Exception as exc:  # pint raises several unrelated classes
        raise UnitError(f"unknown unit {unit_s!r} in {text!r}: {exc}") from exc
    return Quantity(mag, unit)


def format_quantity(q: Any, precision: int = 6) -> str:
    """Format a quantity as ``"<magnitude> <unit>"`` in the canonical short spelling."""
    if not isinstance(q, Quantity):
        return str(q)
    mag = q.magnitude
    if isinstance(mag, float):
        if mag == int(mag) and abs(mag) < 1e15:
            mag_s = str(int(mag))
        else:
            mag_s = f"{mag:.{precision}g}"
    else:
        mag_s = str(mag)
    unit = unit_label(q.units)
    return f"{mag_s} {unit}".strip()


def unit_label(unit: Any) -> str:
    """Short label for a pint unit (``mm``, ``degC``, ``USD``, ``d``)."""
    long = str(unit)
    if long in _SHORT:
        return _SHORT[long]
    return f"{unit:~}".replace("°C", "degC").replace("Δ°C", "delta_degC")


def is_quantity(obj: object) -> bool:
    """True for pint quantities from this registry."""
    return isinstance(obj, Quantity)


def to_unit(q: Any, unit: str) -> Any:
    """Convert, raising :class:`UnitError` with a readable message on mismatch."""
    try:
        return q.to(unit)
    except pint.DimensionalityError as exc:
        raise UnitError(f"cannot convert {format_quantity(q)} to {unit}: {exc}") from exc


def magnitude_in(q: Any, unit: str) -> float:
    """Magnitude of ``q`` expressed in ``unit`` as a float."""
    return float(to_unit(q, unit).magnitude)


def same_dimension(a: Any, b: Any) -> bool:
    """True when two quantities can be compared."""
    return bool(a.dimensionality == b.dimensionality)


def compare(a: Any, op: str, b: Any) -> bool:
    """Evaluate ``a <op> b`` for quantities with ``op`` in ``< <= == != >= >``.

    Raises:
        UnitError: if the dimensions differ or the operator is unknown.
    """
    if not same_dimension(a, b):
        raise UnitError(f"cannot compare {format_quantity(a)} with {format_quantity(b)}")
    bb = b.to(a.units)
    x, y = a.magnitude, bb.magnitude
    ops = {
        "<": x < y,
        "<=": x <= y,
        "==": abs(x - y) <= 1e-9 * max(1.0, abs(x), abs(y)),
        "!=": abs(x - y) > 1e-9 * max(1.0, abs(x), abs(y)),
        ">=": x >= y,
        ">": x > y,
    }
    if op not in ops:
        raise UnitError(f"unknown comparison operator {op!r}; use one of {sorted(ops)}")
    return bool(ops[op])


def mm(q: Any) -> float:
    """Magnitude in millimetres (the geometry boundary helper, D21)."""
    if isinstance(q, (int, float)):
        return float(q)
    return magnitude_in(q, "mm")
