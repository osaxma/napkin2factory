"""Heating-element sizing from the rated power (no electrical design; wiring is the installer's).

    I = P / V          R = V² / P          L = R × A / ρ

Kanthal A1 resistivity 1.45 Ω·mm²/m at 20 °C (Kanthal A-1 datasheet); the hot resistance
is ~4 % higher (Ct ≈ 1.04 at 1200 °C), ignored here (conservative for wire length).
"""

from __future__ import annotations

import math

from napkin2factory.core.units import Quantity


def current(P):  # noqa: N803
    """Element current at rated power, A."""
    return (P["element-power"] / P["mains-voltage"]).to("A")


def resistance(P):  # noqa: N803
    """Cold resistance for the rated power, ohm."""
    return (P["mains-voltage"] ** 2 / P["element-power"]).to("ohm")


def wire_area(P):  # noqa: N803
    """Wire cross-section, mm²."""
    d = P["element-wire-diameter"].to("mm")
    return Quantity(math.pi / 4 * d.magnitude**2, "mm**2")


def wire_length(P):  # noqa: N803
    """Wire length for the required resistance, m."""
    return (resistance(P) * wire_area(P) / P["element-resistivity"]).to("m")


def power_margin(P):  # noqa: N803
    """Rated power over the thermal requirement (dimensionless; must exceed 1)."""
    from thermal import required_power

    return (P["element-power"] / required_power(P)).to("dimensionless")


def circuit_headroom(P):  # noqa: N803
    """Dedicated circuit rating over the element current (dimensionless; must exceed 1)."""
    return (P["circuit-rating"] / current(P)).to("dimensionless")
