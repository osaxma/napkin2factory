"""Tip-over at the tilt IEC 61010-1 section 7.3 asks of equipment (SPEC 4.3, [verify clause]).

The stand is lifted on one edge until the centre of gravity is over it: the restoring moment
is m g x (x from the centre of gravity to the tipping edge), the overturning moment the edge
load m g tan(tilt) acting at the centre-of-gravity height, so FS = x / (z_cg tan tilt)
(``structural.tip_over_safety_factor``).
"""

from __future__ import annotations

import math

from napkin2factory.calckit import structural
from napkin2factory.core.units import Quantity

#: Mass in kg of every item, the made parts as built (volume x density) and the bought-in
#: ones by allowance [verify each against the chosen catalogue part], SPEC section 4.6.
_M = {
    "feet": 0.100,
    "tray": 1.574,
    "lid": 0.713,
    "base beam": 0.826,
    "lower platen": 1.178,
    "columns": 1.822,
    "crosshead": 0.826,
    "upper platen": 0.502,
    "load cell": 0.350,
    "actuator": 4.000,
    "shroud": 1.608,
    "door": 0.840,
    "psu": 0.600,
    "controller": 0.400,
    "e-stop": 0.150,
    "limit switches": 0.100,
    "inlet": 0.080,
    "interlock": 0.150,
    "hinges": 0.100,
    "fasteners and wiring": 0.600,
}


def _items(P):  # noqa: N803
    """(mass kg, y mm towards the front, z mm above the bench) of every item, door closed."""
    mm = lambda q: float(q.to("mm").magnitude)  # noqa: E731
    foot, sheet, tray_h = mm(P["foot-height"]), mm(P["sheet-thickness"]), mm(P["console-height"])
    beam_h, base = mm(P["beam-height"]), mm(P["base-z"])
    col_len = mm(P["column-length"])
    # the tray: its floor at the foot top, its four walls at half their height, weighted by area
    area_floor = mm(P["console-width"]) * mm(P["console-depth"])
    area_walls = 2 * (mm(P["console-width"]) + mm(P["console-depth"])) * tray_h
    z_tray = (area_floor * (foot + sheet / 2) + area_walls * (foot + tray_h / 2)) / (
        area_floor + area_walls
    )
    z_guard = base + beam_h + mm(P["guard-height"]) / 2
    z_cross = mm(P["crosshead-z"]) + beam_h / 2
    z_actuator = mm(P["crosshead-z"]) - mm(P["actuator-length"]) / 2  # centre at mid-length
    z_upper = z_actuator - mm(P["actuator-length"]) / 2 - mm(P["adapter-height"])
    z_cell = z_upper - mm(P["load-cell-height"]) / 2
    z_plate = z_cell - mm(P["load-cell-height"]) / 2 - mm(P["upper-platen-thickness"]) / 2
    front = mm(P["guard-depth"]) / 2
    return [
        (_M["feet"], 0.0, foot / 2),
        (_M["tray"], 0.0, z_tray),
        (_M["lid"], 0.0, foot + tray_h + sheet / 2),
        (_M["base beam"], 0.0, base + beam_h / 2),
        (_M["lower platen"], 0.0, base + beam_h + mm(P["lower-platen-thickness"]) / 2),
        (_M["columns"], 0.0, base + beam_h + col_len / 2),
        (_M["crosshead"], 0.0, z_cross),
        (_M["upper platen"], 0.0, z_plate),
        (_M["load cell"], 0.0, z_cell),
        (_M["actuator"], 0.0, z_actuator),
        (
            _M["shroud"],
            -41.8,
            z_guard,
        ),  # the back and the two sides: centre of gravity behind the middle
        (_M["door"], front, z_guard),
        (_M["psu"], 0.0, 57.0),  # on the tray floor, 90 mm tall [verify]
        (_M["controller"], 0.0, 37.0),  # 50 mm tall [verify]
        (_M["e-stop"], 130.0, 150.0),  # on the lid, at the front
        (_M["limit switches"], 0.0, z_actuator),
        (_M["inlet"], -175.0, 65.0),  # on the back face
        (_M["interlock"], front, z_guard),
        (_M["hinges"], front, z_guard),
        (_M["fasteners and wiring"], 0.0, base + beam_h + col_len / 2),
    ]


def tip_over_factor(P):  # noqa: N803
    """Tip-over factor at the tilt, door closed, about the nearer tipping edge.

    The front or back foot line; the sides, 180 mm out, are further and not the worst.
    """
    items = _items(P)
    mass = sum(m for m, _, _ in items)
    z_cg = sum(m * z for m, _, z in items) / mass
    y_cg = sum(m * y for m, y, _ in items) / mass
    edge = min(
        float(P["tip-half-width"].to("mm").magnitude) - y_cg,
        float(P["tip-half-width"].to("mm").magnitude) + y_cg,
    )
    tilt = float(P["tilt"].to("rad").magnitude)
    edge_load = Quantity(mass * 9.80665 * math.tan(tilt), "N")
    res = structural.tip_over_safety_factor(
        Quantity(mass, "kg"), Quantity(edge, "mm"), edge_load, Quantity(z_cg, "mm")
    )
    return Quantity(float(res.safety_factor), "")
