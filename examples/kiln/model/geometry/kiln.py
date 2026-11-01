"""Top assembly: guard and shell on the stand, the lining inside, the door and the controls hung on.

World frame: X across, Y from front (−Y, door) to back (+Y), Z up. The guard's front lip
plane is y = 0; the guard's bottom sits on the stand at z = stand-height.

Only the stand is placed by typed-in coordinates (the anchor), and the lining, which has no
joint, is set at the front of the shell's floor. Everything else is placed by its joint
(``place_by``, P1): the guard, the shell, the hinge post and the latch keeper by their
interfaces, and the two units by their ports (P4): the door hangs on the post by its lower
hinge, the controls on the guard's right wall by the controller box (DEC-019).
"""


def build(P, I, parts):  # noqa: N803
    """Place every child; counts must match kiln.yaml (the checker verifies)."""
    from build123d import Location

    from napkin2factory.geometry.assembly import AssemblyResult, place, place_by

    res = AssemblyResult()

    # --- stand: footprint centred under the guard, floor at z = 0 (the one typed-in anchor) ---
    go_d = P.mm("guard-outer-depth")
    res.add(place("part://stand", parts["stand"], translate=(0.0, go_d / 2, 0.0), label="stand"))

    # --- guard on the stand's rails, shell inside it on the bottom standoffs (trays open to
    # the front); the other three standoff interfaces are checked, not used to place ---
    res.add(
        place_by(
            I, res, "shell-frame-mount", "part://guard-shell", parts["guard-shell"], label="guard"
        )
    )
    shell = res.add(
        place_by(
            I,
            res,
            "guard-standoff-bottom",
            "part://outer-shell",
            parts["outer-shell"],
            label="shell",
        )
    )

    # --- lining: its frame is the front of the shell's floor (shell tray coordinates: the
    # floor's inner face is the −Y wall's, the lip plane is z = shell-outer-depth) ---
    floor_front = shell.location * Location(
        (
            0.0,
            -P.mm("shell-outer-height") / 2 + P.mm("shell-thickness"),
            P.mm("shell-outer-depth"),
        )
    )
    lining_at = tuple(float(v) for v in floor_front.position)
    res.add(place("asm://lining", parts["lining"], translate=lining_at, label="lining"))

    # --- hinge post and latch keeper bolted to the guard's side walls ---
    res.add(
        place_by(
            I, res, "guard-hinge-post", "part://hinge-post", parts["hinge-post"], label="hinge-post"
        )
    )
    res.add(
        place_by(
            I,
            res,
            "guard-latch-keeper",
            "part://latch-keeper",
            parts["latch-keeper"],
            label="latch-keeper",
        )
    )

    # --- the door hangs on the hinge post by its lower hinge (the upper hinge and the latch
    # are checked where they meet, not used to place) ---
    res.add(
        place_by(I, res, "hinge-lower", "asm://door", parts["door"], inner="hinge-1", label="door")
    )

    # --- the controls hang beside the guard on 40 mm standoffs by the controller box ---
    res.add(
        place_by(I, res, "controller-mount", "asm://controls", parts["controls"], label="controls")
    )
    # thermocouples, the door switch, fasteners and consumables are BOM-only (geometry: none)
    return res
