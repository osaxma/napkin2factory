"""Plate calcs for the reference-case fixture: one right case, one wrong, one missing."""


def area(P):  # noqa: N803
    """Face area, mm²."""
    return (P["plate-width"] * P["plate-height"]).to("mm**2")


def perimeter(P):  # noqa: N803
    """Edge length, mm."""
    return (2 * (P["plate-width"] + P["plate-height"])).to("mm")


def volume(P):  # noqa: N803
    """Volume, mm³ (no reference case: the check warns)."""
    return (P["plate-width"] * P["plate-height"] * P["plate-thickness"]).to("mm**3")
