"""Door swing: does the tapered plug clear the fiber opening as the door opens?

Plan view (X across, Y into the kiln, origin on the guard lip plane). The door turns about
the hinge pin at (x_p, y_p) on the left. The point that comes closest to the opening is the
plug's latch-side rear corner (x = a_rear, y = y_rear in the closed position); it sweeps a
circle about the pin. The opening's latch-side front edge (x = a_open, y = y_open, the fiber
box front face) is fixed. The corner clears the edge if its radius about the pin is smaller
than the edge's radius, i.e. if, at the depth y_rear, the edge's circle lies outside the
corner:

    R0² = (a_open − x_p)² + (y_open − y_p)²
    clearance = √(R0² − (y_rear − y_p)²) + x_p − a_rear

Plain rigid-body geometry (no source needed beyond the parameters); the plug faces are
straight, so only the corners matter, and the taper draws the rear corner in by
door-plug-depth·tan(taper).
"""

from __future__ import annotations

import math

from napkin2factory.core.units import Quantity


def plug_clearance(P):  # noqa: N803
    """Smallest gap between the plug's latch-side rear corner and the opening on the swing, mm."""
    x_p = P.mm("hinge-pin-x")
    y_p = P.mm("hinge-pin-y")
    a_open = P.mm("fiber-inner-width") / 2
    y_open = P.mm("guard-gap") + P.mm("guard-thickness")
    taper = math.radians(float(P["door-plug-taper"].to("degree").magnitude))
    a_rear = P.mm("door-plug-width") / 2 - P.mm("door-plug-depth") * math.tan(taper)
    y_rear = P.mm("door-plug-depth") - P.mm("door-gap")
    r0_sq = (a_open - x_p) ** 2 + (y_open - y_p) ** 2
    return Quantity(math.sqrt(r0_sq - (y_rear - y_p) ** 2) + x_p - a_rear, "mm")
