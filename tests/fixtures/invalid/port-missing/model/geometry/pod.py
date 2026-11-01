"""The pod in its own frame: the plate at the origin, a rail along each long edge."""


def build(P, I, parts):  # noqa: N803
    """Place the plate and the two rails (labelled, so the top can pick one)."""
    from napkin2factory.geometry.assembly import AssemblyResult, place

    res = AssemblyResult()
    res.add(place("part://plate", parts["plate"], label="plate"))
    for side, y in (("left", 30.0), ("right", -30.0)):
        res.add(place("part://rail", parts["rail"], translate=(0.0, y, 5.0), label=side))
    return res
