"""The guard shroud: a U of 5 mm polycarbonate, a back and two sides (SPEC sections 3.3 and 5.1).

Frame: origin on the bench-side bottom edge, centred on x and on the 160 mm depth (y from
-80 mm at the back to +80 mm at the front, where the door hangs), the guard ``guard-height``
tall (z). The sheet is routed flat and line-bent; the model shows the bent shape.
"""


def build(P, I, kit):  # noqa: N803
    """Back wall and two side walls fused into one solid."""
    from build123d import Box, Location

    width, depth = P.mm("guard-width"), P.mm("guard-depth")
    height, thick = P.mm("guard-height"), P.mm("guard-thickness")
    result = kit.block(length=width, width=depth, height=height)
    back = Box(width, thick, height).moved(Location((0, -depth / 2 + thick / 2, height / 2)))
    shape = back
    for sign in (-1.0, 1.0):
        side = Box(thick, depth - thick, height).moved(
            Location((sign * (width / 2 - thick / 2), thick / 2, height / 2))
        )
        shape = shape.fuse(side)
    shape.label = result.shape.label
    result.shape = shape
    result.features.process = "cnc-routing"
    return result
