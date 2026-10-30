"""Back liner: a K23 slab with horizontal element grooves on the chamber face (−Y), drilled
through along Y for the two element tails (at the lowest groove) and the two thermocouples
(at chamber mid-height)."""


def build(P, I, kit):  # noqa: N803
    """Block ``chamber-width`` × ``brick-thickness`` × ``chamber-height`` with grooves and holes."""
    from build123d import Box, Cylinder, Location

    from napkin2factory.geometry.features import Cutout, Hole

    w = P.mm("chamber-width")
    t = P.mm("brick-thickness")
    height = P.mm("chamber-height")
    gw = P.mm("element-groove-width")
    gd = P.mm("element-groove-depth")
    n = int(P["element-grooves-per-wall"].magnitude)
    tail_x = P.mm("tail-hole-x")
    tail_d = P.mm("tail-hole-brick")
    tc_x = P.mm("thermocouple-offset-x")
    tc_d = P.mm("thermocouple-hole")
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
    holes = [
        (-tail_x, pitch, tail_d, "tail-left"),
        (tail_x, pitch, tail_d, "tail-right"),
        (-tc_x, height / 2, tc_d, "thermocouple-control"),
        (tc_x, height / 2, tc_d, "thermocouple-limit"),
    ]
    for x, z, d, label in holes:
        shape = shape - Cylinder(d / 2, 2 * t, rotation=(90, 0, 0)).moved(Location((x, 0.0, z)))
        result.features.holes.append(Hole(center=(x, 0.0, z), diameter=d, axis=(0.0, 1.0, 0.0), label=label))
    shape.label = result.shape.label
    result.shape = shape
    result.features.process = "cut-block"
    result.props["groove_count"] = n
    result.props["groove_length_total"] = n * w
    return result
