"""Door fiber plug: ceramic fiber board stack, tapered so it clears the opening on the swing.

Frame: front face (bonded to the door tray) at z = 0, the plug grows along +Z into the kiln
(the door assembly turns +Z to +Y). Width along X, height along Y, both centred.
"""


def build(P, I, kit):  # noqa: N803
    """Frustum: ``door-plug-width`` × ``door-plug-height`` at the front, sides drawn in by taper."""
    import math

    from build123d import Rectangle, extrude

    from napkin2factory.geometry.features import Dim

    w = P.mm("door-plug-width")
    h = P.mm("door-plug-height")
    d = P.mm("door-fiber-thickness")
    taper = float(P["door-plug-taper"].to("degree").magnitude)
    result = kit.block(length=w, width=h, height=d)
    # build123d: a positive taper draws the sides in along the extrusion
    shape = extrude(Rectangle(w, h), amount=d, taper=taper)
    shape.label = result.shape.label
    result.shape = shape
    result.features.process = "cut-sheet"
    rear_w = w - 2 * d * math.tan(math.radians(taper))
    result.dims.append(
        Dim("rear width", rear_w, (-rear_w / 2, -h / 2, d), (rear_w / 2, -h / 2, d), view="top")
    )
    result.props["taper_deg"] = taper
    result.props["rear_width"] = rear_w
    return result
