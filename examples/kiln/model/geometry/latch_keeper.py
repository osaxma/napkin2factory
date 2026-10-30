"""Latch keeper: the hinge post's mirror on the guard's right wall, 60 mm long.

Frame: origin on the guard's outer face at the keeper's front edge, z centred. Leg x ∈ [0, t],
y ∈ [0, leg]; web x ∈ [0, reach], y ∈ [0, t].
"""


def build(P, I, kit):  # noqa: N803
    """Leg box fused with web box; the interface build drills the two bolt holes in the leg."""
    from build123d import Box, Location

    t = P.mm("hinge-post-thickness")
    leg = P.mm("hinge-post-leg")
    reach = P.mm("hinge-post-reach")
    length = 60.0  # as long as the latch body (part latch: 60 mm)
    result = kit.block(length=reach, width=leg, height=length)
    leg_box = Box(t, leg, length).moved(Location((t / 2, leg / 2, 0.0)))
    web_box = Box(reach, t, length).moved(Location((reach / 2, t / 2, 0.0)))
    shape = leg_box.fuse(web_box)
    shape.label = result.shape.label
    result.shape = shape
    result.features.process = "machining"
    result.props["reach"] = reach
    return result
