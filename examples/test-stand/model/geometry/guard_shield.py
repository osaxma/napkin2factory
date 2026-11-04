"""The guard: the fixed U-shroud, the door on the front, two hinges and the interlock.

Frame: the same as the console's. The guard stands on the base beam's level (z = ``base-z`` plus
the beam height) and closes the test zone on four sides: back and two sides in the shroud, the
front by the door (SPEC section 3.3).
"""


def build(P, I, parts):  # noqa: N803
    """Place shroud, door, hinges and the interlock switch."""
    from napkin2factory.geometry.assembly import AssemblyResult, place, place_by

    z0 = P.mm("base-z") + P.mm("beam-height")
    half_depth, thick = P.mm("guard-depth") / 2, P.mm("guard-thickness")
    res = AssemblyResult()
    res.add(place("part://guard-shroud", parts["guard-shroud"], translate=(0, 0, z0)))
    res.add(place_by(I, res, "guard-door-hinge", "part://guard-door", parts["guard-door"]))
    x_hinge = -P.mm("guard-width") / 2 + 5
    for name, z in (("lower", z0 + 50), ("upper", z0 + P.mm("guard-height") - 110)):
        res.add(
            place(
                "part://hinge",
                parts["hinge"],
                translate=(x_hinge, half_depth + thick + 5, z),
                label=f"hinge-{name}",
            )
        )
    res.add(
        place("part://interlock", parts["interlock"], translate=(160, half_depth - 10, z0 + 180))
    )
    return res
