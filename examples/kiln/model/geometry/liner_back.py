"""Back liner: a K23 slab with horizontal element grooves on the chamber face (−Y)."""


def build(P, I, kit):  # noqa: N803
    """Block ``chamber-width`` × ``brick-thickness`` × ``chamber-height`` with grooves on −Y."""
    from build123d import Box, Location

    from napkin2factory.geometry.features import Cutout

    w = P.mm("chamber-width")
    t = P.mm("brick-thickness")
    height = P.mm("chamber-height")
    gw = P.mm("element-groove-width")
    gd = P.mm("element-groove-depth")
    n = int(P["element-grooves-per-wall"].magnitude)
    result = kit.block(length=w, width=t, height=height)
    shape = result.shape
    pitch = height / (n + 1)
    for i in range(n):
        z = pitch * (i + 1)
        groove = Box(w, gd * 2, gw).moved(Location((0.0, -t / 2, z)))
        shape = shape - groove
        result.features.cutouts.append(
            Cutout(face="front", center=(0.0, z), width=w, height=gw, label=f"groove-{i + 1}")
        )
    shape.label = result.shape.label
    result.shape = shape
    result.features.process = "cut-block"
    result.props["groove_count"] = n
    result.props["groove_length_total"] = n * w
    return result
