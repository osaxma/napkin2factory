"""Top assembly: guard and shell on the stand, insulation inside, door in front, controller beside.

World frame: X across, Y from front (−Y, door) to back (+Y), Z up. The guard's front lip
plane is y = 0; the guard's bottom sits on the stand at z = stand-height.

Rotation convention (build123d ``Location`` Euler angles, degrees): a rotation of +90°
about X maps a part's +Z to −Y and its +Y to +Z; −90° maps +Z to +Y. The enclosure kit
builds a tray open on +Z, so +90° about X turns the opening to the front (−Y) and the
tray's "width" (Y) into the kiln's height (Z).
"""


def build(P, I, parts):  # noqa: N803
    """Place every child; counts must match kiln.yaml (the checker verifies)."""
    from napkin2factory.geometry.assembly import AssemblyResult, place

    sh_t = P.mm("shell-thickness")
    fib = P.mm("fiber-thickness")
    brick = P.mm("brick-thickness")
    cw, ch = P.mm("chamber-width"), P.mm("chamber-height")
    stand_h = P.mm("stand-height")
    so_d, so_h = P.mm("shell-outer-depth"), P.mm("shell-outer-height")
    li_d = P.mm("liner-outer-depth")
    lc = P.mm("lining-clearance")
    seal = P.mm("door-seal-gap")
    fi_h = P.mm("fiber-inner-height")
    fb_w, fb_d = P.mm("fiber-box-width"), P.mm("fiber-box-depth")
    gap, gt = P.mm("guard-gap"), P.mm("guard-thickness")
    go_w, go_d, go_h = P.mm("guard-outer-width"), P.mm("guard-outer-depth"), P.mm("guard-outer-height")
    standoff = P.mm("controller-standoff")
    cb_w, cb_h = P.mm("controller-box-width"), P.mm("controller-box-height")
    door_gap = P.mm("door-gap")
    res = AssemblyResult()

    # --- stand: footprint centred under the guard, floor at z = 0 ---
    res.add(place("part://stand", parts["stand"], translate=(0.0, go_d / 2, 0.0), label="stand"))

    # --- guard and shell trays, opening to the front ---
    guard_z0 = stand_h
    res.add(place("part://guard-shell", parts["guard-shell"], translate=(0.0, go_d, guard_z0 + go_h / 2), rotate=(90.0, 0.0, 0.0), label="guard"))
    y_f = gt + gap  # the shell's front lip plane
    shell_z0 = guard_z0 + gt + gap
    res.add(place("part://outer-shell", parts["outer-shell"], translate=(0.0, y_f + so_d, shell_z0 + so_h / 2), rotate=(90.0, 0.0, 0.0), label="shell"))

    # --- insulation: the fiber box sits on the shell floor (fiber-clearance above it only) ---
    z_fib0 = shell_z0 + sh_t
    z_brick0 = z_fib0 + fib + lc
    z_cham0 = z_brick0 + brick
    y_in0 = y_f  # fiber box front face = shell lip plane
    # fiber slabs (panel: X width, Y height, Z thickness; no rotation)
    res.add(place("part://fiber-slab", parts["fiber-slab"], translate=(0.0, y_in0 + fb_d / 2, z_fib0), label="fiber-floor"))
    res.add(place("part://fiber-slab", parts["fiber-slab"], translate=(0.0, y_in0 + fb_d / 2, z_fib0 + fib + fi_h), label="fiber-roof"))
    # fiber sides (panel width = fiber-inner-height, height = box depth; +90° about Y puts the
    # thickness along +X and the panel's width along Z)
    z_mid = z_fib0 + fib + fi_h / 2  # = chamber centre
    res.add(place("part://fiber-side", parts["fiber-side"], translate=(-fb_w / 2, y_in0 + fb_d / 2, z_mid), rotate=(0.0, 90.0, 0.0), label="fiber-left"))
    res.add(place("part://fiber-side", parts["fiber-side"], translate=(fb_w / 2 - fib, y_in0 + fb_d / 2, z_mid), rotate=(0.0, 90.0, 0.0), label="fiber-right"))
    # fiber back (panel in the XZ plane). +90° about X puts the thickness along −Y and keeps the
    # panel's +Y (its hole coordinates, chamber-centred) pointing up, so the tail holes stay low.
    res.add(place("part://fiber-back", parts["fiber-back"], translate=(0.0, y_in0 + fb_d, z_mid), rotate=(90.0, 0.0, 0.0), label="fiber-back"))
    # brick box behind the door's plug and the gasket: y ∈ [y_b0, y_b0 + li_d]
    y_b0 = y_f + fib + brick + seal
    yc = y_b0 + li_d / 2
    res.add(place("part://liner-slab", parts["liner-slab"], translate=(0.0, yc, z_brick0), label="floor"))
    res.add(place("part://liner-slab", parts["liner-slab"], translate=(0.0, yc, z_cham0 + ch), label="roof"))
    res.add(place("part://liner-side", parts["liner-side"], translate=(-(cw / 2 + brick / 2), yc, z_cham0), label="left"))
    # right slab mirrored by 180° about Y (keeps its front face at −Y, grooves face −X)
    res.add(place("part://liner-side", parts["liner-side"], translate=((cw / 2 + brick / 2), yc, z_cham0 + ch), rotate=(0.0, 180.0, 0.0), label="right"))
    res.add(place("part://liner-back", parts["liner-back"], translate=(0.0, y_b0 + li_d - brick / 2, z_cham0), label="back"))

    # --- door: plug face door-gap in front of the guard lip plane, centred on the chamber ---
    res.add(place("asm://door", parts["door"], translate=(0.0, -door_gap, z_cham0 + ch / 2), label="door"))

    # --- hinge post and latch keeper bolted to the guard's side walls ---
    hp_y = P.mm("hinge-post-y")
    guard_zc = guard_z0 + go_h / 2
    res.add(place("part://hinge-post", parts["hinge-post"], translate=(-go_w / 2, hp_y, guard_zc), label="hinge-post"))
    # keeper centred on the guard's mid-height, where its bolt holes are (2 mm above the chamber centre)
    res.add(place("part://latch-keeper", parts["latch-keeper"], translate=(go_w / 2, hp_y, guard_zc), label="latch-keeper"))

    # --- controller box beside the guard on 40 mm standoffs (tray opening up), lid on top ---
    cx = go_w / 2 + standoff + cb_w / 2
    cy = go_d / 2
    cz = guard_z0 + go_h - cb_h
    t = P.mm("controller-sheet")
    res.add(place("part://controller-box", parts["controller-box"], translate=(cx, cy, cz), label="controller"))
    res.add(place("part://controller-lid", parts["controller-lid"], translate=(cx, cy, cz + cb_h), label="controller-lid"))
    res.add(place("part://pid-controller", parts["pid-controller"], translate=(cx - 70.0, cy, cz + 76.0), label="pid"))
    res.add(place("part://limit-controller", parts["limit-controller"], translate=(cx - 10.0, cy, cz + 76.0), label="limit"))
    res.add(place("part://ssr", parts["ssr"], translate=(cx + 45.0, cy - 20.0, cz + t + 1.0), label="ssr"))
    res.add(place("part://contactor", parts["contactor"], translate=(cx + 100.0, cy, cz + t + 1.0), label="contactor"))
    # element, thermocouples, door switch, fasteners and consumables are BOM-only (geometry: none)
    return res
