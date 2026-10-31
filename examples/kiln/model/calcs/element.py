"""Heating-element sizing from the rated power (no electrical design; wiring is the installer's).

    I = P / V          R = V² / P          L = R × A / ρ

Kanthal A1 resistivity 1.45 Ω·mm²/m at 20 °C (Kanthal A-1 datasheet); the hot resistance
is ~4 % higher (Ct ≈ 1.04 at 1200 °C), ignored here (conservative for wire length).

Current, resistance, wire section, wire length and surface load are computed by the system
calc kit (``napkin2factory.calckit.power``), the same functions screening uses.
"""

from __future__ import annotations

import math

from napkin2factory.calckit import power as kit


def current(P):  # noqa: N803
    """Element current at rated power, A."""
    return kit.element_current(P["element-power"], P["mains-voltage"])


def resistance(P):  # noqa: N803
    """Cold resistance for the rated power, ohm."""
    return kit.cold_resistance(voltage=P["mains-voltage"], power=P["element-power"])


def wire_area(P):  # noqa: N803
    """Wire cross-section, mm²."""
    return kit.wire_cross_section(P["element-wire-diameter"])


def wire_length(P):  # noqa: N803
    """Wire length for the required resistance, m."""
    return kit.wire_length(
        resistance=resistance(P),
        diameter=P["element-wire-diameter"],
        resistivity=P["element-resistivity"],
    )


def power_margin(P):  # noqa: N803
    """Rated power over the thermal requirement (dimensionless; must exceed 1)."""
    from thermal import required_power

    return (P["element-power"] / required_power(P)).to("dimensionless")


def circuit_headroom(P):  # noqa: N803
    """Dedicated circuit rating over the element current (dimensionless; must exceed 1)."""
    return (P["circuit-rating"] / current(P)).to("dimensionless")


def coil_turns(P):  # noqa: N803
    """Number of coil turns: wire length over the mean turn length π·(D − d) (dimensionless)."""
    d = P["element-wire-diameter"]
    mean_turn = math.pi * (P["element-coil-diameter"] - d)
    return (wire_length(P) / mean_turn).to("dimensionless")


def available_groove_length(P):  # noqa: N803
    """Groove length the coil is stretched into: n grooves on two sides and the back, mm."""
    n = float(P["element-grooves-per-wall"].magnitude)
    return (n * (2 * P["chamber-depth"] + P["chamber-width"])).to("mm")


def coil_pitch(P):  # noqa: N803
    """Distance between turns once the coil is stretched into the grooves, mm."""
    return (available_groove_length(P) / coil_turns(P)).to("mm")


def pitch_factor(P):  # noqa: N803
    """Coil pitch in wire diameters (dimensionless; ≥ 2 so turns do not touch or overheat)."""
    return (coil_pitch(P) / P["element-wire-diameter"]).to("dimensionless")


def surface_load(P):  # noqa: N803
    """Wire surface load P/(π·d·L), W/cm² (Kanthal handbook limit for grooves: ~2 W/cm² at 1200 °C)."""  # noqa: E501
    return kit.surface_load(
        diameter=P["element-wire-diameter"], length=wire_length(P), power=P["element-power"]
    )
