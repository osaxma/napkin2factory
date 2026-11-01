"""Controls sub-assembly: the controller box with its lid and the four instruments inside.

Controls frame: the controller box's own frame (an enclosure tray open on +Z, base centred
at the origin). Everything is placed from the box: the lid by its joint with the box, the
instruments from the box's sizes and its cutouts. The kiln hangs the whole unit on the guard's
right wall by the box's joint with the guard (``controller-mount``, a port, P4; DEC-019).
"""

# Where the box's two front cutouts are (model/parts/controller-box.yaml: centres at x −70 and
# −10, 20 mm above the front face's centre) and the instruments' 48 × 48 DIN front.
PID_X, LIMIT_X, CUTOUT_UP = -70.0, -10.0, 20.0
DIN = 48.0
# The relay and the contactor stand 1 mm clear of the base's inner face, at the box's right.
SSR_AT, CONTACTOR_X, BASE_CLEAR = (45.0, -20.0), 100.0, 1.0


def build(P, I, parts):  # noqa: N803
    """Place the box at the origin, the lid by its seat, the instruments from the box."""
    from napkin2factory.geometry.assembly import AssemblyResult, place, place_by

    t = P.mm("controller-sheet")
    z_din = P.mm("controller-box-height") / 2 + CUTOUT_UP - DIN / 2  # instrument base, centred
    res = AssemblyResult()
    res.add(place("part://controller-box", parts["controller-box"], label="box"))
    res.add(
        place_by(
            I,
            res,
            "controller-lid-seat",
            "part://controller-lid",
            parts["controller-lid"],
            label="lid",
        )
    )
    res.add(
        place(
            "part://pid-controller",
            parts["pid-controller"],
            translate=(PID_X, 0.0, z_din),
            label="pid",
        )
    )
    res.add(
        place(
            "part://limit-controller",
            parts["limit-controller"],
            translate=(LIMIT_X, 0.0, z_din),
            label="limit",
        )
    )
    res.add(place("part://ssr", parts["ssr"], translate=(*SSR_AT, t + BASE_CLEAR), label="ssr"))
    res.add(
        place(
            "part://contactor",
            parts["contactor"],
            translate=(CONTACTOR_X, 0.0, t + BASE_CLEAR),
            label="contactor",
        )
    )
    return res
