"""The kit: the box at the origin, the cover onto it by their pass-through joint."""


def build(P, I, parts):  # noqa: N803
    """Place the box, then the cover through ``box-cover``."""
    from napkin2factory.geometry.assembly import AssemblyResult, place, place_by

    res = AssemblyResult()
    res.add(place("part://box", parts["box"]))
    res.add(place_by(I, res, "box-cover", "part://cover", parts["cover"]))
    return res
