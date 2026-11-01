"""Door sub-assembly: a plug door (tray, fiber plug, brick slab) with its own guard in front.

Door frame: the plug's front face is at y = 0 and the plug grows into the kiln (+Y); the
tray's face lies just in front of it (y < 0) and the door guard one air gap further out.
Centred on x = 0, z = 0 (the kiln assembly lifts the door to the chamber centre).

Rotation convention (build123d ``Location`` Euler angles, degrees): −90° about X maps a
part's +Z to +Y and its +Y to −Z, so a tray open on +Z opens towards the kiln and a part
built along +Z grows into it.
"""


def build(P, I, parts):  # noqa: N803
    """Place tray, door guard, fiber plug, brick slab, two hinges (left) and the latch (right)."""
    from napkin2factory.geometry.assembly import AssemblyResult, place

    skin_t = P.mm("door-skin-thickness")
    dg_off = P.mm("door-guard-offset")
    dft = P.mm("door-fiber-thickness")
    pin_x = P.mm("hinge-pin-x")
    pin_y = P.mm("hinge-pin-y")
    door_gap = P.mm("door-gap")
    spacing = P.mm("hinge-spacing")
    dg_w = P.mm("door-guard-width")
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
    res.add(
        place(
            "part://door-guard",
            parts["door-guard"],
            translate=(0.0, -dg_off, 0.0),
            rotate=rot,
            label="guard",
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
    # hinge barrels (block 12 × 12 × 60, base centre at the origin) on the pin axis; the pin
    # axis is given from the guard lip plane, the door frame sits door-gap in front of it
    for i, zc in enumerate((-spacing / 2, spacing / 2)):
        res.add(
            place(
                "part://hinge",
                parts["hinge"],
                translate=(pin_x, pin_y + door_gap, zc - 30.0),
                label=f"hinge-{i + 1}",
            )
        )
    # latch (block 60 × 15 × 25) turned to run along Y, against the door guard's right wall
    res.add(
        place(
            "part://latch",
            parts["latch"],
            translate=(dg_w / 2 + 7.5, 22.0, -12.5),
            rotate=(0.0, 0.0, 90.0),
            label="latch",
        )
    )
    return res
