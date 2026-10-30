"""Door sub-assembly: skin at the front, fiber plug behind it, brick plug behind that.

Door frame: the skin's back face is at y = 0 and the skin lies in front (y < 0); the plug
grows into the kiln (+Y). Centred on x = 0, z = 0 (the kiln assembly lifts the door to the
chamber centre).
"""


def build(P, I, parts):  # noqa: N803
    """Place skin, fiber plug, brick plug, two hinges on the left edge, latch on the right."""
    from napkin2factory.geometry.assembly import AssemblyResult, place

    skin_t = P.mm("door-skin-thickness")
    dft = P.mm("door-fiber-thickness")
    brick = P.mm("brick-thickness")
    door_w = P.mm("door-width")
    door_h = P.mm("door-height")
    ch = P.mm("chamber-height")
    res = AssemblyResult()
    # panel kit: centred, thickness along +Z. +90° about X → thickness along −Y: skin at y ∈ [−t, 0]
    res.add(place("part://door-skin", parts["door-skin"], rotate=(90.0, 0.0, 0.0), label="skin"))
    # −90° about X → thickness along +Y: fiber plug at y ∈ [0, dft]
    res.add(place("part://door-fiber", parts["door-fiber"], rotate=(-90.0, 0.0, 0.0), label="fiber"))
    # block kit: base centre at the origin, height along +Z: brick plug at y ∈ [dft, dft + brick]
    res.add(place("part://door-brick", parts["door-brick"], translate=(0.0, dft + brick / 2, -ch / 2), label="brick"))
    # hinges (blocks 50 × 12 × 60) on the skin's front face at the left edge; latch at the right
    hinge_x = -door_w / 2 + 25.0 + 7.5
    for i, z in enumerate((-door_h / 2 + 80.0, door_h / 2 - 140.0)):
        res.add(place("part://hinge", parts["hinge"], translate=(hinge_x, -skin_t - 6.0 - 1.0, z), label=f"hinge-{i + 1}"))
    res.add(place("part://latch", parts["latch"], translate=(door_w / 2 - 70.0, -skin_t - 7.5 - 1.0, -12.5), label="latch"))
    return res
