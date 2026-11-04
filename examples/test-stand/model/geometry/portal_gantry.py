"""The portal frame: base beam, two columns, crosshead, the platens, actuator and load cell.

Frame: the same as the console's (see geometry/base_console.py). The base beam stands on the
console lid at z = ``base-z`` (the one typed-in anchor); the load axis is x = 0, y = 0. The
columns, the crosshead, the lower platen and the actuator are placed by their joints (P1).
The load cell and the upper platen hang on the actuator's rod and have no joint of their own.
"""


def build(P, I, parts):  # noqa: N803
    """Place the frame, the platens, the actuator under the crosshead and the load cell."""
    from napkin2factory.geometry.assembly import AssemblyResult, place, place_by

    base, beam_h = P.mm("base-z"), P.mm("beam-height")
    top = P.mm("crosshead-z")
    res = AssemblyResult()
    res.add(place("part://base-beam", parts["base-beam"], translate=(0, 0, base)))
    for side in ("left", "right"):
        res.add(
            place_by(
                I,
                res,
                f"column-base-{side}",
                "part://column",
                parts["column"],
                label=f"column-{side}",
            )
        )
    res.add(
        place_by(
            I,
            res,
            "column-top-left",
            "part://top-crosshead",
            parts["top-crosshead"],
            onto="column-left",
        )
    )
    res.add(place_by(I, res, "lower-platen-mount", "part://lower-platen", parts["lower-platen"]))
    # hanging under the crosshead, bottom to top: actuator, rod-end adapter (not modelled),
    # load cell, upper platen
    res.add(place_by(I, res, "actuator-crosshead-mount", "part://actuator", parts["actuator"]))
    z_cell = top - P.mm("actuator-length") - P.mm("adapter-height") - P.mm("load-cell-height")
    res.add(place("part://load-cell", parts["load-cell"], translate=(0, 0, z_cell)))
    z_plate = z_cell - P.mm("upper-platen-thickness")
    res.add(place("part://upper-platen", parts["upper-platen"], translate=(0, 0, z_plate)))
    # the two limit switches on the inside of the frame, behind the load axis
    for name, z in (("lower", base + beam_h + 120), ("upper", top - 120)):
        res.add(
            place(
                "part://limit-switch",
                parts["limit-switch"],
                translate=(-110, -25, z),
                label=f"limit-{name}",
            )
        )
    return res
