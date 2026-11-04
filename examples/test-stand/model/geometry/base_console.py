"""The console: tray, lid, feet, and what lives inside and on it (SPEC section 3.2).

Frame (shared by all four assemblies, so the sub-assemblies are placed at the origin): x
across the stand, y from the back (-) to the front (+), z up from the bench. The console is
centred on x and y, its feet on the bench (z = 0).
"""


def build(P, I, parts):  # noqa: N803
    """Place tray, lid, four feet and the bought-in parts inside and on the console."""
    from napkin2factory.geometry.assembly import AssemblyResult, place

    foot, height = P.mm("foot-height"), P.mm("console-height")
    width, depth = P.mm("console-width"), P.mm("console-depth")
    floor = foot + P.mm("sheet-thickness")  # top of the tray floor
    res = AssemblyResult()
    res.add(place("part://console-tray", parts["console-tray"], translate=(0, 0, foot)))
    res.add(place("part://console-lid", parts["console-lid"], translate=(0, 0, foot + height)))
    dx = width / 2 - P.mm("foot-inset")
    dy = depth / 2 - P.mm("foot-inset")
    for i, (sx, sy) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1))):
        res.add(
            place(
                "part://rubber-foot",
                parts["rubber-foot"],
                translate=(sx * dx, sy * dy, 0),
                label=f"foot-{i + 1}",
            )
        )
    # inside the tray: the inlet against the back wall, the power supply and the controller
    # on the floor
    res.add(place("part://inlet", parts["inlet"], translate=(0, -depth / 2 + 17, 45)))
    res.add(place("part://psu", parts["psu"], translate=(90, 0, floor)))
    res.add(place("part://controller", parts["controller"], translate=(-90, 0, floor)))
    # on the lid at the front right: the E-stop
    res.add(
        place(
            "part://e-stop",
            parts["e-stop"],
            translate=(140, 130, foot + height + P.mm("sheet-thickness")),
        )
    )
    return res
