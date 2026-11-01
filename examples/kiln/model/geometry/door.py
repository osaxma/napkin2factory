"""Door sub-assembly: a plug door (tray, fiber plug, brick slab) with its own guard in front.

Door frame: the plug's front face is at y = 0 and the plug grows into the kiln (+Y); the
tray's face lies just in front of it (y < 0) and the door guard one air gap further out.
Centred on x = 0, z = 0. Everything here is placed from the door's own sizes: the kiln hangs
the door on its hinge post by the lower hinge's joint (a port, P4), so no kiln position is read
here (DEC-019).

Rotation convention (build123d ``Location`` Euler angles, degrees): −90° about X maps a
part's +Z to +Y and its +Y to −Z, so a tray open on +Z opens towards the kiln and a part
built along +Z grows into it.
"""


def build(P, I, parts):  # noqa: N803
    """Place tray, door guard, fiber plug, brick slab, two hinges (left) and the latch (right)."""
    from napkin2factory.geometry.assembly import AssemblyResult, place, place_by

    skin_t = P.mm("door-skin-thickness")
    dft = P.mm("door-fiber-thickness")
    pin_x = P.mm("hinge-pin-x")
    pin_depth = P.mm("hinge-pin-depth")
    spacing = P.mm("hinge-spacing")
    hinge_len = P.mm("hinge-length")
    dg_w = P.mm("door-guard-width")
    wall_end = P.mm("door-guard-depth") - P.mm("door-guard-offset")  # door guard's wall ends
    latch_len, latch_w, latch_h = P.mm("latch-length"), P.mm("latch-width"), P.mm("latch-height")
    latch_back = wall_end - P.mm("latch-setback")  # the latch body's rear end
    res = AssemblyResult()
    rot = (-90.0, 0.0, 0.0)
    # enclosure kit: tray base at z ∈ [0, t]; −90° about X puts the base at y ∈ [0, t]
    res.add(
        place(
            "part://door-tray",
            parts["door-tray"],
            translate=(0.0, -skin_t, 0.0),
            rotate=rot,
            label="tray",
        )
    )
    # the door guard on its four standoffs, placed by its interface with the tray (P1)
    res.add(
        place_by(
            I, res, "door-guard-standoff", "part://door-guard", parts["door-guard"], label="guard"
        )
    )
    # plug: extruded along +Z from z = 0 → y ∈ [0, dft]; brick slab behind it
    res.add(place("part://door-fiber", parts["door-fiber"], rotate=rot, label="fiber"))
    res.add(
        place(
            "part://door-brick",
            parts["door-brick"],
            translate=(0.0, dft, 0.0),
            rotate=rot,
            label="brick",
        )
    )
    # hinge barrels (a block along +Z from its base centre) on the pin axis, just outside the
    # door guard's left wall; hinge-1 is the lower one, the joint the kiln hangs the door by
    for i, zc in enumerate((-spacing / 2, spacing / 2)):
        res.add(
            place(
                "part://hinge",
                parts["hinge"],
                translate=(pin_x, pin_depth, zc - hinge_len / 2),
                label=f"hinge-{i + 1}",
            )
        )
    # latch body (a block along X from its base centre) turned to run along Y, against the
    # door guard's right wall, its rear end latch-setback in front of the wall ends
    res.add(
        place(
            "part://latch",
            parts["latch"],
            translate=(dg_w / 2 + latch_w / 2, latch_back - latch_len / 2, -latch_h / 2),
            rotate=(0.0, 0.0, 90.0),
            label="latch",
        )
    )
    return res
