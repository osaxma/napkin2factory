"""Resistive heating elements and the supply circuit they need.

Element sizing from a rated power (mirrors ``examples/kiln/model/calcs/element.py``,
DEC-004/DEC-005)::

    I = P / V          R = V² / P          L = R · A / ρ          q = P / (π · d · L)

Resistivity, surface-load limits and circuit ratings are the caller's or come from
the tables named below; every one is [verify]:

* Kanthal A1 resistivity 1.45 Ω·mm²/m at 20 °C (Kanthal A-1 datasheet); the hot
  resistance is ~4 % higher (Ct ≈ 1.04 at 1200 °C), ignored (conservative for wire
  length). Pass it as ``resistivity``; it is not stored here.
* :data:`KANTHAL_GROOVE_SURFACE_LOAD_LIMIT` — the Kanthal handbook's guidance for wire
  coils in grooves at a 1200 °C furnace temperature.
* Circuit classes per region — ``calckit/data/circuits.yaml`` (every row ``verify:
  true``; the owner or their electrician confirms them). An unknown region returns an
  ``unknown_region`` verdict; callers warn, never fail.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from napkin2factory.calckit._cases import Case
from napkin2factory.calckit._tables import load_table
from napkin2factory.core.units import Quantity

#: A pint quantity from the shared registry (pint is untyped for mypy).
Qty = Any

#: Maximum wire surface load for Kanthal A1 coils in brick grooves at a 1200 °C furnace
#: temperature (Kanthal "Resistance heating alloys and systems for industrial furnaces"
#: handbook, surface-load guidance for embedded/grooved elements) [verify].
KANTHAL_GROOVE_SURFACE_LOAD_LIMIT = Quantity(2.0, "W/cm**2")

#: Minimum circuit rating over the element current. The kiln's REQ-006 ceiling (3000 W
#: on a 16 A, 230 V circuit) is a ratio of ~1.23; compare NEC 210.19(A)/210.20(A), which
#: sizes continuous loads at 125 % (pass ``headroom=1.25`` for US circuits) [verify].
CIRCUIT_HEADROOM_MIN = 1.2


def element_current(power: Qty, voltage: Qty) -> Qty:
    """Element current at rated power, ``I = P / V`` (A)."""
    return (power / voltage).to("A")


def cold_resistance(power: Qty, voltage: Qty) -> Qty:
    """Cold resistance for the rated power, ``R = V² / P`` (ohm)."""
    return (voltage**2 / power).to("ohm")


def wire_cross_section(diameter: Qty) -> Qty:
    """Round-wire cross-section, ``A = π/4 · d²`` (mm²)."""
    d = diameter.to("mm")
    return Quantity(math.pi / 4 * d.magnitude**2, "mm**2")


def wire_length(resistance: Qty, resistivity: Qty, diameter: Qty) -> Qty:
    """Wire length that gives ``resistance``, ``L = R · A / ρ`` (m).

    Args:
        resistance: the element resistance (cold).
        resistivity: wire resistivity, e.g. 1.45 Ω·mm²/m for Kanthal A1 at 20 °C
            (Kanthal A-1 datasheet) [verify].
        diameter: wire diameter.
    """
    return (resistance * wire_cross_section(diameter) / resistivity).to("m")


def surface_load(power: Qty, diameter: Qty, length: Qty) -> Qty:
    """Wire surface load, ``q = P / (π · d · L)`` (W/cm²).

    Compare with :data:`KANTHAL_GROOVE_SURFACE_LOAD_LIMIT` for coils in grooves [verify].
    """
    area = math.pi * diameter * length
    return (power / area).to("W/cm**2")


@dataclass(frozen=True)
class CircuitVerdict:
    """Which supply circuit class covers an element current in a region.

    Attributes:
        status: ``ok`` (a class covers the current with the headroom), ``no_class`` (the
            region is known but no class is large enough) or ``unknown_region`` (no
            table rows; callers warn, never fail).
        region: the region code asked for.
        current: the element current asked about (A).
        message: one plain sentence for the owner.
        label: the chosen class (``ok`` only).
        kind: ``plug`` or ``dedicated`` (``ok`` only).
        voltage: the class voltage (``ok`` only).
        rating: the class rating (A) (``ok`` only).
        headroom: rating over current (``ok`` only).
        source: the table row's source (``ok`` only).
        verify: the table row still needs a person's confirmation.
    """

    status: str
    region: str
    current: Qty
    message: str
    label: str | None = None
    kind: str | None = None
    voltage: Qty | None = None
    rating: Qty | None = None
    headroom: float | None = None
    source: str | None = None
    verify: bool = True


def circuit_rows(region: str) -> list[dict[str, Any]]:
    """Rows of ``circuits.yaml`` for a region code (case-insensitive); may be empty."""
    code = region.strip().upper()
    return [r for r in load_table("circuits") if str(r["region"]).upper() == code]


def circuit_class(
    region: str,
    current: Qty,
    *,
    voltage: Qty | None = None,
    headroom: float = CIRCUIT_HEADROOM_MIN,
) -> CircuitVerdict:
    """The smallest circuit class in ``region`` that carries ``current`` with headroom.

    Reads ``calckit/data/circuits.yaml`` (rows ``{region, label, voltage, rating_a, kind,
    source, verify}``, all ``verify: true``). A class covers the current when
    ``rating ≥ headroom · current`` (default :data:`CIRCUIT_HEADROOM_MIN`, 20 %). Among
    the covering classes the lowest rating wins, a plug before a dedicated circuit at the
    same rating.

    Args:
        region: region code (``SA``, ``EU``, ``UK``, ``US``, ``AU``).
        current: the element current.
        voltage: only consider classes at this voltage (the current was computed for it).
        headroom: minimum rating over current.

    Returns:
        A :class:`CircuitVerdict`; ``unknown_region`` when the table has no rows for the
        region (never an exception).
    """
    amps = float(current.to("A").magnitude)
    rows = circuit_rows(region)
    if not rows:
        return CircuitVerdict(
            status="unknown_region",
            region=region,
            current=current.to("A"),
            message=(
                f"no circuit classes on file for region {region!r}; confirm the supply "
                "with a licensed electrician"
            ),
        )
    if voltage is not None:
        volts = float(voltage.to("V").magnitude)
        rows = [r for r in rows if math.isclose(float(r["voltage"]), volts, rel_tol=1e-6)]
    covering = [r for r in rows if float(r["rating_a"]) >= headroom * amps]
    if not covering:
        return CircuitVerdict(
            status="no_class",
            region=region,
            current=current.to("A"),
            message=(
                f"{amps:.1f} A needs a circuit of at least {headroom * amps:.1f} A; no class "
                f"on file for {region} is that large"
            ),
        )
    best = min(covering, key=lambda r: (float(r["rating_a"]), r["kind"] != "plug"))
    rating = float(best["rating_a"])
    return CircuitVerdict(
        status="ok",
        region=region,
        current=current.to("A"),
        message=(
            f"{amps:.1f} A fits {best['label']} ({best['kind']}, {rating:g} A, "
            f"{float(best['voltage']):g} V) with {rating / amps:.2f}× headroom"
        ),
        label=str(best["label"]),
        kind=str(best["kind"]),
        voltage=Quantity(float(best["voltage"]), "V"),
        rating=Quantity(rating, "A"),
        headroom=rating / amps,
        source=str(best["source"]),
        verify=bool(best["verify"]),
    )


def circuit_for_power(
    region: str, power: Qty, *, headroom: float = CIRCUIT_HEADROOM_MIN
) -> CircuitVerdict:
    """The smallest circuit class in ``region`` for an element of ``power``.

    Each voltage on file for the region is tried (``I = P / V``) and the lowest covering
    rating wins; the verdict's ``current`` is the current at the chosen voltage. An
    unknown region returns ``unknown_region``, a known region with nothing large enough
    returns ``no_class`` for the highest voltage on file.
    """
    rows = circuit_rows(region)
    if not rows:
        return circuit_class(region, Quantity(0.0, "A"), headroom=headroom)
    verdicts = []
    for volts in sorted({float(r["voltage"]) for r in rows}):
        v = Quantity(volts, "V")
        verdicts.append(
            circuit_class(region, element_current(power, v), voltage=v, headroom=headroom)
        )
    ok = [v for v in verdicts if v.status == "ok"]
    if not ok:
        return verdicts[-1]

    def rank(v: CircuitVerdict) -> tuple[float, bool]:
        rating = 0.0 if v.rating is None else float(v.rating.to("A").magnitude)
        return rating, v.kind != "plug"

    return min(ok, key=rank)


# --- reference cases (F17) -------------------------------------------------------------

#: Kanthal's direct-calculation example for a wire element (the wire maker's handbook).
_KANTHAL = (
    "Kanthal, 'Design of wire elements', in Design calculations and standard tolerances "
    "(Kanthal heating-material handbook, p. 51), direct calculation method, example: "
    "20 kW at 220 V, Kanthal AF, resistivity 1.39 ohm mm2/m, Ct = 1.06 at 1200 degC"
)
_HAND = "hand computation: "

#: Every public function's reference cases; ``external`` ones come from a published source.
CASES: list[Case] = [
    Case(
        "element_current",
        Quantity(90.9, "A"),
        _KANTHAL + ": I = P/U = 20 000/220 = 90.9 A",
        args=(Quantity(20, "kW"), Quantity(220, "V")),
        abs=0.05,
        external=True,
    ),
    Case(
        "surface_load",
        Quantity(3.95, "W/cm**2"),
        _KANTHAL + ": with the nearest standard wire, 5.0 mm, the actual surface load is "
        "3.95 W/cm2",
        args=(Quantity(20, "kW"), Quantity(5.0, "mm"), Quantity(32.2496, "m")),
        abs=0.005,
        external=True,
        note="the wire length is the example's own data carried through: cold resistance "
        "U^2/(P Ct) = 220^2/(20 000 x 1.06) = 2.28302 ohm, L = R A / rho = 2.28302 x "
        "19.63495 / 1.39 = 32.2496 m",
    ),
    Case(
        "element_current",
        Quantity(2500 / 230, "A"),
        _HAND + "2500 W on 230 V: I = 10.8696 A",
        args=(Quantity(2500, "W"), Quantity(230, "V")),
        rel=1e-12,
    ),
    Case(
        "cold_resistance",
        Quantity(21.16, "ohm"),
        _HAND + "2500 W on 230 V: R = 230^2 / 2500 = 21.16 ohm",
        args=(Quantity(2500, "W"), Quantity(230, "V")),
        rel=1e-12,
    ),
    Case(
        "wire_cross_section",
        Quantity(math.pi / 4 * 1.6**2, "mm**2"),
        _HAND + "1.6 mm wire: A = pi/4 x 1.6^2 = 2.010619 mm2",
        args=(Quantity(1.6, "mm"),),
        rel=1e-12,
    ),
    Case(
        "wire_length",
        Quantity(32.2496, "m"),
        _HAND + "the handbook example's cold resistance 2.28302 ohm in 5.0 mm wire at 1.39 "
        "ohm mm2/m: L = 2.28302 x 19.63495 / 1.39 = 32.2496 m",
        args=(Quantity(2.28302, "ohm"), Quantity(1.39, "ohm*mm**2/m"), Quantity(5.0, "mm")),
        rel=1e-5,
    ),
    Case(
        "surface_load",
        Quantity(1.6950895, "W/cm**2"),
        _HAND + "2500 W in 29.3412 m of 1.6 mm wire: q = 2500 / (pi x 0.16 cm x 2934.12 cm) "
        "= 1.69509 W/cm2",
        args=(Quantity(2500, "W"), Quantity(1.6, "mm"), Quantity(29.341175415, "m")),
        rel=1e-6,
    ),
    Case(
        "circuit_rows",
        "SA",
        "calckit/data/circuits.yaml: the region code matches whatever its case",
        args=("sa",),
        pick="0.region",
    ),
    Case(
        "circuit_class",
        Quantity(16, "A"),
        "calckit/data/circuits.yaml, region SA: 10.87 A over the 13 A socket is 13/10.87 = "
        "1.196 < 1.2 headroom, so the 16 A dedicated circuit (16/10.87 = 1.472)",
        args=("SA", Quantity(10.87, "A")),
        pick="rating",
        rel=1e-12,
    ),
    Case(
        "circuit_for_power",
        Quantity(30, "A"),
        "calckit/data/circuits.yaml, region US: 2500 W is 20.8 A at 120 V (no 120 V class "
        "reaches 1.2 x 20.8 = 25 A) and 10.4 A at 240 V, so the 30 A 240 V circuit",
        args=("US", Quantity(2500, "W")),
        pick="rating",
        rel=1e-12,
    ),
]


__all__ = [
    "CASES",
    "CIRCUIT_HEADROOM_MIN",
    "KANTHAL_GROOVE_SURFACE_LOAD_LIMIT",
    "CircuitVerdict",
    "circuit_class",
    "circuit_for_power",
    "circuit_rows",
    "cold_resistance",
    "element_current",
    "surface_load",
    "wire_cross_section",
    "wire_length",
]
