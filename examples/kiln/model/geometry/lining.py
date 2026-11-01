"""Lining (a grouping, ``build: phantom``): the fiber box and the brick box inside the shell.

Lining frame: X across, Y from the front (the shell's lip plane, y = 0) to the back, Z up from
the shell's inner floor (z = 0), centred on x = 0. The kiln places the lining at the front of
the shell's floor. No part here has an interface, so every position is typed in; the build
marks them as placed by coordinates (P1, DEC-020).

Rotation convention (build123d ``Location`` Euler angles, degrees): +90° about Y turns a
panel's thickness to +X; +90° about X turns it to −Y and keeps its +Y pointing up.
"""


def build(P, I, parts):  # noqa: N803
    """Fiber floor, roof, sides and back, then the brick box behind the door's plug."""
    from napkin2factory.geometry.assembly import AssemblyResult, place

    fib = P.mm("fiber-thickness")
    brick = P.mm("brick-thickness")
    cw, ch = P.mm("chamber-width"), P.mm("chamber-height")
    li_d = P.mm("liner-outer-depth")
    lc = P.mm("lining-clearance")
    seal = P.mm("door-seal-gap")
    fi_h = P.mm("fiber-inner-height")
    fb_w, fb_d = P.mm("fiber-box-width"), P.mm("fiber-box-depth")
    res = AssemblyResult()

    # --- the fiber box sits on the shell floor (fiber-clearance above it only) ---
    z_brick0 = fib + lc
    z_cham0 = z_brick0 + brick
    # fiber slabs (panel: X width, Y height, Z thickness; no rotation)
    res.add(
        place(
            "part://fiber-slab",
            parts["fiber-slab"],
            translate=(0.0, fb_d / 2, 0.0),
            label="fiber-floor",
        )
    )
    res.add(
        place(
            "part://fiber-slab",
            parts["fiber-slab"],
            translate=(0.0, fb_d / 2, fib + fi_h),
            label="fiber-roof",
        )
    )
    # fiber sides (panel width = fiber-inner-height, height = box depth; +90° about Y puts the
    # thickness along +X and the panel's width along Z)
    z_mid = fib + fi_h / 2  # = chamber centre
    res.add(
        place(
            "part://fiber-side",
            parts["fiber-side"],
            translate=(-fb_w / 2, fb_d / 2, z_mid),
            rotate=(0.0, 90.0, 0.0),
            label="fiber-left",
        )
    )
    res.add(
        place(
            "part://fiber-side",
            parts["fiber-side"],
            translate=(fb_w / 2 - fib, fb_d / 2, z_mid),
            rotate=(0.0, 90.0, 0.0),
            label="fiber-right",
        )
    )
    # fiber back (panel in the XZ plane). +90° about X puts the thickness along −Y and keeps the
    # panel's +Y (its hole coordinates, chamber-centred) pointing up, so the tail holes stay low.
    res.add(
        place(
            "part://fiber-back",
            parts["fiber-back"],
            translate=(0.0, fb_d, z_mid),
            rotate=(90.0, 0.0, 0.0),
            label="fiber-back",
        )
    )
    # --- brick box behind the door's plug and the gasket: y ∈ [y_b0, y_b0 + li_d] ---
    y_b0 = fib + brick + seal
    yc = y_b0 + li_d / 2
    res.add(
        place(
            "part://liner-slab", parts["liner-slab"], translate=(0.0, yc, z_brick0), label="floor"
        )
    )
    res.add(
        place(
            "part://liner-slab",
            parts["liner-slab"],
            translate=(0.0, yc, z_cham0 + ch),
            label="roof",
        )
    )
    res.add(
        place(
            "part://liner-side",
            parts["liner-side"],
            translate=(-(cw / 2 + brick / 2), yc, z_cham0),
            label="left",
        )
    )
    # right slab mirrored by 180° about Y (keeps its front face at −Y, grooves face −X)
    res.add(
        place(
            "part://liner-side",
            parts["liner-side"],
            translate=((cw / 2 + brick / 2), yc, z_cham0 + ch),
            rotate=(0.0, 180.0, 0.0),
            label="right",
        )
    )
    res.add(
        place(
            "part://liner-back",
            parts["liner-back"],
            translate=(0.0, y_b0 + li_d - brick / 2, z_cham0),
            label="back",
        )
    )
    # the element, its tail bushes and the mortar are BOM-only (geometry: none)
    return res
