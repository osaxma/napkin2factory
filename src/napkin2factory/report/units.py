"""Display units helper for owner-facing reports and napkin board (W8, S-219).

When a product sets ``units: imperial`` in ``n2f.yaml``, quantities show the owner's unit
first and the standard engineering metric unit in brackets:
``31.5 in (800 mm)``, ``119 lb (54.1 kg)``, ``142 °F (61 degC)``.
Metric products (the default) show standard metric units unchanged: ``800 mm``.
Drawings and exported manufacturing files stay in mm.
"""

from __future__ import annotations

import re
from typing import Any

from napkin2factory.core.units import (
    UnitError,
    format_quantity,
    is_quantity,
    parse_quantity,
    ureg,
)

LENGTH_DIM = ureg("mm").dimensionality
MASS_DIM = ureg("kg").dimensionality
FORCE_DIM = ureg("N").dimensionality
PRESSURE_DIM = ureg("MPa").dimensionality
TEMP_DIM = ureg("degC").dimensionality

QTY_PATTERN = re.compile(
    r"\b([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*(mm|cm|m|kg|g|kN|lbf|N|MPa|kPa|Pa|psi|ksi|degC|°C)\b"
)


def format_num(mag: float | int, digits: int = 3) -> str:
    """Format a numerical magnitude keeping the report's precision rule."""
    if isinstance(mag, int) or (isinstance(mag, float) and mag == int(mag) and abs(mag) < 1e15):
        return str(int(mag))
    x = float(mag)
    if abs(x) < 10**digits:
        return f"{x:.{digits}g}"
    if abs(x) < 1e15:
        return f"{x:.0f}"
    return f"{x:.{digits}g}"


def _convert_qty(q: Any) -> tuple[str, str] | None:
    """Return (imperial_str, metric_str) for length, mass, force, stress, or temperature."""
    dim = q.dimensionality
    if dim == LENGTH_DIM:
        in_mag = float(q.to("inch").magnitude)
        if abs(in_mag) > 120:
            imp_val = format_num(float(q.to("ft").magnitude))
            imp_unit = "ft"
        else:
            imp_val = format_num(in_mag)
            imp_unit = "in"
        if str(q.units) in ("mm", "millimeter", "cm", "centimeter", "m", "meter"):
            met_str = format_quantity(q)
        else:
            met_str = f"{format_num(float(q.to('mm').magnitude))} mm"
        return f"{imp_val} {imp_unit}", met_str
    if dim == MASS_DIM:
        imp_val = format_num(float(q.to("lb").magnitude))
        if str(q.units) in ("kg", "kilogram", "g", "gram"):
            met_str = format_quantity(q)
        else:
            met_str = f"{format_num(float(q.to('kg').magnitude))} kg"
        return f"{imp_val} lb", met_str
    if dim == FORCE_DIM:
        imp_val = format_num(float(q.to("lbf").magnitude))
        if str(q.units) in ("N", "newton", "kN"):
            met_str = format_quantity(q)
        else:
            met_str = f"{format_num(float(q.to('N').magnitude))} N"
        return f"{imp_val} lbf", met_str
    if dim == PRESSURE_DIM:
        psi_mag = float(q.to("psi").magnitude)
        if abs(psi_mag) >= 1000:
            imp_val = format_num(float(q.to("ksi").magnitude))
            imp_unit = "ksi"
        else:
            imp_val = format_num(psi_mag)
            imp_unit = "psi"
        if str(q.units) in ("Pa", "pascal", "kPa", "MPa", "GPa"):
            met_str = format_quantity(q)
        else:
            met_str = f"{format_num(float(q.to('MPa').magnitude))} MPa"
        return f"{imp_val} {imp_unit}", met_str
    if dim == TEMP_DIM:
        imp_val = format_num(float(q.to("degF").magnitude))
        if str(q.units) in ("degC", "degree_Celsius"):
            met_str = format_quantity(q)
        else:
            met_str = f"{format_num(float(q.to('degC').magnitude))} degC"
        return f"{imp_val} °F", met_str
    return None


def display(q: Any, units: str = "metric") -> str:
    """Format quantity ``q`` in the product's display units.

    When ``units == 'imperial'``, shows imperial first and metric in brackets
    (e.g. ``'31.5 in (800 mm)'``). When ``units == 'metric'`` (default),
    output is unchanged metric (e.g. ``'800 mm'``).
    """
    if q is None:
        return ""
    if units != "imperial":
        if is_quantity(q):
            return format_quantity(q)
        return str(q)

    if is_quantity(q):
        conv = _convert_qty(q)
        return f"{conv[0]} ({conv[1]})" if conv else format_quantity(q)

    text = str(q)
    try:
        parsed = parse_quantity(text)
        conv = _convert_qty(parsed)
        if conv:
            return f"{conv[0]} ({conv[1]})"
        return format_quantity(parsed)
    except UnitError:
        pass

    def _repl(m: re.Match[str]) -> str:
        start, end = m.span()
        prefix = text[:start].rstrip()
        suffix = text[end:].lstrip()
        if prefix.endswith("(") and suffix.startswith(")"):
            return m.group(0)
        s = m.group(0)
        try:
            parsed = parse_quantity(s)
            conv = _convert_qty(parsed)
            if conv is not None:
                return f"{conv[0]} ({conv[1]})"
        except Exception:
            pass
        return s

    return QTY_PATTERN.sub(_repl, text)
