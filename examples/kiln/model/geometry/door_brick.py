"""Door brick slab: K23, continuing the fiber plug's taper behind it.

Frame: front face (against the fiber plug) at z = 0, grows along +Z into the kiln. The front
size is the fiber plug's rear size, so the taper is one continuous surface.
"""


def build(P, I, kit):  # noqa: N803
    """Frustum of depth ``brick-thickness`` starting at the fiber plug's rear size."""
    import math

    from build123d import Rectangle, extrude

    from napkin2factory.geometry.features import Dim

    taper = float(P["door-plug-taper"].to("degree").magnitude)
    tan = math.tan(math.radians(taper))
    dft = P.mm("door-fiber-thickness")
    w = P.mm("door-plug-width") - 2 * dft * tan
    h = P.mm("door-plug-height") - 2 * dft * tan
    d = P.mm("brick-thickness")
    rear_w = w - 2 * d * tan
    rear_h = h - 2 * d * tan
    cw, ch = P.mm("chamber-width"), P.mm("chamber-height")
    assert rear_w > cw and rear_h > ch, "door brick slab must cover the chamber opening"
    result = kit.block(length=w, width=h, height=d)
    shape = extrude(Rectangle(w, h), amount=d, taper=taper)
    shape.label = result.shape.label
    result.shape = shape
    result.features.process = "cut-block"
    result.dims.append(
        Dim("rear width", rear_w, (-rear_w / 2, -h / 2, d), (rear_w / 2, -h / 2, d), view="top")
    )
    result.props["taper_deg"] = taper
    result.props["rear_width"] = rear_w
    return result
