"""Load-cell capacity margin: the cell's rating over the rated load (SPEC section 6, CR-1)."""

from __future__ import annotations


def load_cell_margin(P):  # noqa: N803
    """The load cell's rated capacity divided by the rated load.

    1 means the cell is exactly at its limit; below 1 the cell is too small for the load.
    The requirement verifies this ratio is at least 1, so a change of the rated load
    re-runs the check against the same cell (B-0279).
    """
    return (P["load-cell-capacity"] / P["rated-load"]).to("")
