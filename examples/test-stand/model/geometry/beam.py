"""A beam of the portal frame: a rectangular hollow section cut to length (SPEC section 5.1).

Frame: origin at the bottom centre of the beam, its length along x, its section ``beam-width``
wide (y) and ``beam-height`` tall (z), the wall ``beam-wall`` all round, open at both ends.
Serves the crosshead and the base beam: one section, so one set of section properties in the
calcs. The interfaces drill the bolt holes.
"""


def build(P, I, kit):  # noqa: N803
    """The solid beam from the block generator, less the bore along its whole length."""
    from build123d import Box, Location

    length, width = P.mm("beam-length"), P.mm("beam-width")
    height, wall = P.mm("beam-height"), P.mm("beam-wall")
    result = kit.block(length=length, width=width, height=height)
    bore = Box(length + 2.0, width - 2 * wall, height - 2 * wall).moved(
        Location((0, 0, height / 2))
    )
    shape = result.shape.cut(bore)
    shape.label = result.shape.label
    result.shape = shape
    result.features.process = "extrusion-cut"
    result.props["section_area"] = width * height - (width - 2 * wall) * (height - 2 * wall)
    return result
