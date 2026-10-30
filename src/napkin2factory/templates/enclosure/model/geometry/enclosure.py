"""Assembly layout: lid on the lip, two brackets against the back wall."""


def build(P, I, parts):  # noqa: N803 — P and I are the recording accessors
    """Place base, lid and both brackets.

    Frames: the base plate is centred on XY with its underside at z = 0; the lid lies on
    the lip at z = box-height; brackets stand behind the back wall (+Y) with their vertical
    leg flat against it and the horizontal leg pointing away from the box on the floor.
    """
    from napkin2factory.geometry.assembly import AssemblyResult, place

    h = P.mm("box-height")
    w = P.mm("box-width")
    spacing = P.mm("bracket-spacing")
    bw = P.mm("bracket-width")
    res = AssemblyResult()
    res.add(place("part://base", parts["base"]))
    res.add(place("part://lid", parts["lid"], translate=(0.0, 0.0, h)))
    # bracket frame: outer corner at origin, horizontal leg +X, vertical leg +Z; rotate so the
    # horizontal leg points +Y (away from the box) and the vertical leg's outer face is at y=w/2.
    for i, x in enumerate((-spacing / 2, spacing / 2)):
        res.add(
            place(
                "part://bracket",
                parts["bracket"],
                translate=(x + bw / 2, w / 2, 0.0),
                rotate=(0.0, 0.0, 90.0),
                label=f"bracket-{i + 1}",
            )
        )
    return res
