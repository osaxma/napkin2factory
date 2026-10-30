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
    so_w, so_d, so_h = P.mm("shell-outer-width"), P.mm("shell-outer-depth"), P.mm("shell-outer-height")
    lo_w, lo_d, lo_h = P.mm("liner-outer-width"), P.mm("liner-outer-depth"), P.mm("liner-outer-height")
    si_w, si_d = P.mm("shell-inner-width"), P.mm("shell-inner-depth")
    clr = P.mm("fiber-clearance")
    fb_w, fb_d = P.mm("fiber-box-width"), P.mm("fiber-box-depth")
    gap, gt = P.mm("guard-gap"), P.mm("guard-thickness")
    go_w, go_d, go_h = P.mm("guard-outer-width"), P.mm("guard-outer-depth"), P.mm("guard-outer-height")
    standoff = P.mm("controller-standoff")
    cb_w, cb_d, cb_h = P.mm("controller-box-width"), P.mm("controller-box-depth"), P.mm("controller-box-height")
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

    # --- insulation inside the shell cavity: y ∈ [y_f, y_f + si_d], x ∈ ±si_w/2, z from the shell floor ---
    z_fib0 = shell_z0 + sh_t
    z_brick0 = z_fib0 + fib
    z_cham0 = z_brick0 + brick
    y_in0 = y_f
    # fiber slabs (panel: X width, Y height, Z thickness; no rotation)
    res.add(place("part://fiber-slab", parts["fiber-slab"], translate=(0.0, y_in0 + fb_d / 2, z_fib0), label="fiber-floor"))
    res.add(place("part://fiber-slab", parts["fiber-slab"], translate=(0.0, y_in0 + fb_d / 2, z_fib0 + fib + lo_h), label="fiber-roof"))
    # fiber sides (panel width = liner height, height = cavity depth; +90° about Y puts the
    # thickness along +X and the panel's width along Z)
    z_mid = z_fib0 + fib + lo_h / 2
    res.add(place("part://fiber-side", parts["fiber-side"], translate=(-fb_w / 2, y_in0 + fb_d / 2, z_mid), rotate=(0.0, 90.0, 0.0), label="fiber-left"))
    res.add(place("part://fiber-side", parts["fiber-side"], translate=(fb_w / 2 - fib, y_in0 + fb_d / 2, z_mid), rotate=(0.0, 90.0, 0.0), label="fiber-right"))
    # fiber back (panel in the XZ plane; −90° about X puts the thickness along +Y)
    res.add(place("part://fiber-back", parts["fiber-back"], translate=(0.0, y_in0 + fb_d - fib, z_mid), rotate=(-90.0, 0.0, 0.0), label="fiber-back"))
    # brick box inside the fiber box: y ∈ [y_in0 + fib, y_in0 + fib + lo_d]
    y_b0 = y_in0 + fib
    res.add(place("part://liner-slab", parts["liner-slab"], translate=(0.0, y_b0 + lo_d / 2, z_brick0), label="floor"))
    res.add(place("part://liner-slab", parts["liner-slab"], translate=(0.0, y_b0 + lo_d / 2, z_cham0 + ch), label="roof"))
    res.add(place("part://liner-side", parts["liner-side"], translate=(-(cw / 2 + brick / 2), y_b0 + lo_d / 2, z_cham0), label="left"))
    res.add(place("part://liner-side", parts["liner-side"], translate=((cw / 2 + brick / 2), y_b0 + lo_d / 2, z_cham0), rotate=(0.0, 0.0, 180.0), label="right"))
    res.add(place("part://liner-back", parts["liner-back"], translate=(0.0, y_b0 + lo_d - brick / 2, z_cham0), label="back"))

    # --- door: skin just in front of the guard lip, plug reaching the brick line ---
    res.add(place("asm://door", parts["door"], translate=(0.0, -door_gap, z_cham0 + ch / 2), label="door"))

    # --- controller box beside the guard with an air gap (tray opening up) ---
    cx = go_w / 2 + standoff + cb_w / 2
    cy = go_d / 2
    cz = guard_z0 + go_h - cb_h
    res.add(place("part://controller-box", parts["controller-box"], translate=(cx, cy, cz), label="controller"))
    t = P.mm("controller-sheet")
    res.add(place("part://pid-controller", parts["pid-controller"], translate=(cx - 40.0, cy, cz + t + 1.0), label="pid"))
    res.add(place("part://ssr", parts["ssr"], translate=(cx + 45.0, cy, cz + t + 1.0), label="ssr"))
    # the thermocouple is BOM-only (inserted through a drilled hole; see its notes)
    del lo_w, cb_d, clr, si_w, si_d
    return res
