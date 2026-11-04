"""Mains input current and the inlet fuse (SPEC section 4.3)."""

from __future__ import annotations


def input_current(P):  # noqa: N803
    """Mains current with the power supply at its full output: I = P / (eta V PF)."""
    return (P["psu-power"] / (P["psu-efficiency"] * P["mains-voltage"] * P["psu-power-factor"])).to(
        "A"
    )


def fuse_surplus(P):  # noqa: N803
    """The fuse rating less its least allowed rating, 1.25 times the input current."""
    return (P["fuse-rating"] - P["fuse-margin"] * input_current(P)).to("A")
