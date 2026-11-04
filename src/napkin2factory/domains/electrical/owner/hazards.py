"""What the wiring tells the derived ceremony (W6, S-205): is the supply mains?

The ceremony (``napkin2factory.core.ceremony``) asks each domain with content whether it
finds hazardous energy.  The wiring does when the supply is above extra-low voltage; the
limits are the pack's ``entry-voltage`` parameters (IEC 61140:2016 / IEC 60449 voltage
band I: 50 V AC, 120 V ripple-free DC), so one cited number serves the cable-entry rule and
this one.
"""

from __future__ import annotations

from typing import Any

from napkin2factory.core.units import magnitude_in
from napkin2factory.core.uris import Uri
from napkin2factory.domains.electrical.checks.pack import rule
from napkin2factory.domains.electrical.model import has_content, supply


def _volts(product: Any, value: Any) -> float | None:
    """The supply voltage in volts, following a ``param://`` reference; ``None`` if unknown."""
    try:
        if isinstance(value, Uri):
            value = product.parameter_value(value.id)
        return magnitude_in(value, "V")
    except Exception:  # an unreadable voltage is reported by the wiring checks, not here
        return None


def hazards(product: Any) -> list[str]:
    """Hazardous energy in the wiring, in owner words (empty when none)."""
    sup = supply(product)
    if sup is None:
        return []
    volts = _volts(product, sup.voltage)
    if volts is None:
        return []
    limit = rule("entry-voltage").param("elv-dc" if sup.dc else "elv-ac")
    if volts > magnitude_in(limit, "V"):
        kind = "DC" if sup.dc else "AC"
        return [
            f"it runs on mains: the supply is {volts:g} V {kind} (given), above extra-low voltage"
        ]
    return []


__all__ = ["hazards", "has_content"]
