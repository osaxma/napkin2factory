"""Side liner: a K23 slab with horizontal element grooves on the chamber face.

Frame: the slab is a block ``brick-thickness`` (X) × ``liner-outer-depth`` (Y) ×
``chamber-height`` (Z) with its base centre at the origin; the chamber face is +X (the
assembly mirrors the right-hand one). Grooves run along Y and are open towards +X.
"""


def build(P, I, kit):  # noqa: N803 — P and I are the recording accessors
    """Block minus evenly spaced grooves; features record the grooves for the drawing."""
    from build123d import Box, Location

    from napkin2factory.geometry.features import Cutout, Dim

    t = P.mm("brick-thickness")
    depth = P.mm("liner-outer-depth")
    height = P.mm("chamber-height")
    gw = P.mm("element-groove-width")
    gd = P.mm("element-groove-depth")
    n = int(P["element-grooves-per-wall"].magnitude)
    result = kit.block(length=t, width=depth, height=height)
    shape = result.shape
    pitch = height / (n + 1)
    for i in range(n):
        z = pitch * (i + 1)
        groove = Box(gd * 2, depth, gw).moved(Location((t / 2, 0.0, z)))
        shape = shape - groove
        result.features.cutouts.append(
            Cutout(face="right", center=(0.0, z), width=depth, height=gw, label=f"groove-{i + 1}")
        )
    shape.label = result.shape.label
    result.shape = shape
    result.features.process = "cut-block"
    result.dims.append(Dim("groove pitch", pitch, (t / 2, 0, pitch), (t / 2, 0, 2 * pitch), view="front"))
    result.dims.append(Dim("groove depth", gd, (t / 2 - gd, depth / 2, pitch), (t / 2, depth / 2, pitch), view="top"))
    result.props["groove_count"] = n
    result.props["groove_length_total"] = n * depth
    return result
