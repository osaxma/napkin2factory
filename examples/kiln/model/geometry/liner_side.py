"""Side liner: a K23 slab with blind horizontal element grooves on the chamber face.

Frame: the slab is a block ``brick-thickness`` (X) × ``liner-outer-depth`` (Y) ×
``chamber-height`` (Z) with its base centre at the origin; the chamber face is +X and the
front face (−Y) faces the door. Grooves run along Y over the chamber depth only (blind at
the back, where the back liner butts against the slab) and are open towards +X. The
assembly turns the right-hand slab 180° about Y, which keeps the front at −Y.
"""


def build(P, I, kit):  # noqa: N803 — P and I are the recording accessors
    """Block minus evenly spaced blind grooves; features record the grooves for the drawing."""
    from build123d import Box, Location

    from napkin2factory.geometry.features import Cutout, Dim

    t = P.mm("brick-thickness")
    depth = P.mm("liner-outer-depth")
    height = P.mm("chamber-height")
    cd = P.mm("chamber-depth")
    gw = P.mm("element-groove-width")
    gd = P.mm("element-groove-depth")
    n = int(P["element-grooves-per-wall"].magnitude)
    result = kit.block(length=t, width=depth, height=height)
    shape = result.shape
    pitch = height / (n + 1)
    yc = -depth / 2 + cd / 2  # groove centre: open at the front face, blind at the back
    for i in range(n):
        z = pitch * (i + 1)
        groove = Box(gd * 2, cd, gw).moved(Location((t / 2, yc, z)))
        shape = shape - groove
        result.features.cutouts.append(
            Cutout(face="right", center=(yc, z), width=cd, height=gw, label=f"groove-{i + 1}")
        )
    shape.label = result.shape.label
    result.shape = shape
    result.features.process = "cut-block"
    result.dims.append(Dim("groove pitch", pitch, (t / 2, -depth / 2, pitch), (t / 2, -depth / 2, 2 * pitch), view="front"))
    result.dims.append(Dim("groove depth", gd, (t / 2 - gd, -depth / 2, pitch), (t / 2, -depth / 2, pitch), view="top"))
    result.dims.append(Dim("groove length", cd, (t / 2, -depth / 2, pitch), (t / 2, -depth / 2 + cd, pitch), view="top"))
    result.props["groove_count"] = n
    result.props["groove_length_total"] = n * cd
    return result
