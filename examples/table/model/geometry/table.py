"""Assembly layout of the table: the top, with the apron frame fitted under it.

The top stands ``glide-height + frame-height`` above the floor (its underside); the frame
is placed by the ``top-fixing-long`` interface, so its fixing tabs meet the top's underside
and the frame's feet end ``glide-height`` above the floor, where the glides take over.
The inserts, screws and glides are bought parts without geometry: they are counted in the
bill of materials, not drawn.
"""

from __future__ import annotations


def build(P, I, parts):  # noqa: N803 — P and I are the recording accessors
    """Place the top, then the frame by the interface between them."""
    from napkin2factory.geometry.assembly import AssemblyResult, place, place_by

    res = AssemblyResult()
    underside = P.mm("glide-height") + P.mm("frame-height")
    res.add(place("part://top-board", parts["top-board"], translate=(0.0, 0.0, underside)))
    res.add(place_by(I, res, "top-fixing-long", "part://apron-frame", parts["apron-frame"]))
    return res
