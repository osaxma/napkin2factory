"""The envelope checks that are plain geometry: daylight and clear width (SPEC section 3.2)."""

from __future__ import annotations


def daylight(P):  # noqa: N803
    """Daylight from the lower platen top to the upper platen underside, rod retracted.

    The crosshead underside less the actuator, the rod-end adapter, the load cell and the upper
    platen, less the lower platen top.
    """
    return (
        P["crosshead-z"]
        - P["actuator-length"]
        - P["adapter-height"]
        - P["load-cell-height"]
        - P["upper-platen-thickness"]
        - P["lower-platen-top-z"]
    ).to("mm")


def clear_width(P):  # noqa: N803
    """Clear width between the two columns at the load axis: the span less one column side."""
    return (P["span"] - P["column-size"]).to("mm")
