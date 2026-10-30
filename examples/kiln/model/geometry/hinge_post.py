"""Hinge post: a bolted angle on the guard's left wall carrying the door's hinge pin.

Frame: origin on the guard's outer face (the leg's inner face) at the post's front edge,
z centred on the post. The leg lies against the wall (x ∈ [−t, 0], y ∈ [0, leg]); the web
reaches out to the door guard's wall plane (x ∈ [−reach, 0], y ∈ [0, t]).
"""


def build(P, I, kit):  # noqa: N803
    """Leg box fused with web box; the interface build drills the four bolt holes in the leg."""
    from build123d import Box, Location

    t = P.mm("hinge-post-thickness")
    leg = P.mm("hinge-post-leg")
    reach = P.mm("hinge-post-reach")
    length = P.mm("hinge-post-length")
    result = kit.block(length=reach, width=leg, height=length)
    leg_box = Box(t, leg, length).moved(Location((-t / 2, leg / 2, 0.0)))
    web_box = Box(reach, t, length).moved(Location((-reach / 2, t / 2, 0.0)))
    shape = leg_box.fuse(web_box)
    shape.label = result.shape.label
    result.shape = shape
    result.features.process = "machining"
    result.props["reach"] = reach
    return result
