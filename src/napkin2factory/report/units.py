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

_NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
#: ``50 x 50 x 1.5 mm``: a dimension group with one unit at its end (B4, S-226).
_GROUP = rf"\b(?P<group>{_NUM}(?:\s*[x×]\s*{_NUM})+)\s*(?P<gunit>mm|cm|m)\b"
_SINGLE = (
    rf"\b(?P<single>{_NUM})\s*"
    r"(?P<unit>mm|cm|m|kg|g|kN|lbf|N|MPa|kPa|Pa|psi|ksi|degC|°C)\b"
)
QTY_PATTERN = re.compile(f"{_GROUP}|{_SINGLE}")
#: A shop reads an inch to the thousandth at best, so a small length stops at three decimals.
MAX_INCH_DECIMALS = 3


def format_num(mag: float | int, digits: int = 3, max_decimals: int | None = None) -> str:
    """Format a numerical magnitude keeping the report's precision rule.

    ``max_decimals`` caps the digits after the point (``0.0591`` becomes ``0.059``).
    """
    if isinstance(mag, int) or (isinstance(mag, float) and mag == int(mag) and abs(mag) < 1e15):
        return str(int(mag))
    x = float(mag)
    if abs(x) < 10**digits:
        text = f"{x:.{digits}g}"
        if max_decimals is not None and "e" not in text and "." in text:
            if len(text.split(".")[1]) > max_decimals:
                text = f"{x:.{max_decimals}f}".rstrip("0").rstrip(".") or "0"
        return text
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
            imp_val = format_num(in_mag, max_decimals=MAX_INCH_DECIMALS)
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
        if m.group("group"):
            return _convert_group(m.group("group"), m.group("gunit")) or m.group(0)
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


def _convert_group(numbers: str, unit: str) -> str | None:
    """``50 x 50 x 1.5`` + ``mm`` as ``1.97 x 1.97 x 0.059 in (50 x 50 x 1.5 mm)`` (B4, S-226).

    Every number of a dimension group moves to the owner's unit together, so an inch reader
    never meets "50 x 50" beside an inch sign. A group stays in inches however long it is:
    one unit for every number is what a shop reads (a single long length may still read in feet).
    """
    parts = [p.strip() for p in re.split(r"[x×]", numbers)]
    try:
        inches = [float(parse_quantity(f"{p} {unit}").to("inch").magnitude) for p in parts]
    except Exception:
        return None
    shown = [format_num(i, max_decimals=MAX_INCH_DECIMALS) for i in inches]
    return f"{' x '.join(shown)} in ({' x '.join(parts)} {unit})"
