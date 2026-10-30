"""Steady-state heat loss, surface temperatures and stored heat of the kiln.

Body walls — mean-area conduction. The walls are about as thick as the chamber is wide, so
a flat-slab model (one area for every layer) is badly wrong. Each layer gets the geometric
mean of its inner and outer box areas, the usual treatment for thick-walled furnace boxes
(Incropera & DeWitt, *Fundamentals of Heat and Mass Transfer*, ch. 3, conduction shape
factors; furnace-design practice) [verify]:

    A = 2(w·d + w·h + d·h) of a box
    A_in  = chamber (cw, cd, ch);  A_b = brick outer (+2·tb);  A_f = fiber outer (+2·(lc + tf))
    A_s = shell outer (+2·(fiber-clearance + shell-thickness));  A_g = guard (+2·guard-gap)
    R_b = tb / (k_b·√(A_in·A_b)),   R_f = tf / (k_f·√(A_b·A_f))

Shell and guard — two-node boundary. The ventilated guard is a radiation shield: the shell
loses heat by convection to the gap air (assumed at ``gap-air-temperature``, the ventilation
carries it away) and by radiation to the guard; the guard loses what it receives by
convection and radiation to the room (Incropera & DeWitt ch. 13, enclosure of two grey
surfaces, A_s inside A_g):

    (T_hot − T_s)/(R_b + R_f) = A_s·h_c·(T_s − T_gap) + Q_rad
    Q_rad = σ·A_s·(T_s⁴ − T_g⁴) / (1/ε_s + (A_s/A_g)·(1/ε_g − 1))
    Q_rad = A_g·[h_c·(T_g − T_amb) + σ·ε_g·(T_g⁴ − T_amb⁴)]

Door — the plug: brick slab over the mean of the chamber opening and the plug face, fiber
plug over the plug face; the tray's steel face spreads the heat over ``door-face-spread``
times the plug face (estimate [verify]) and loses it to the room by convection and
radiation; the door guard is the same radiation shield with equal areas on both sides.

Conductivities, densities and specific heats come from ``parameters.yaml`` (Morgan K-23 and
Kaowool 1260 board datasheets [verify]); h_c = 5 W/m²K natural convection [verify]; the
gap air temperature is an assumption to be measured [verify]. Not modelled: edge and corner
bridges at the shell lip, standoff conduction (sixteen M6 standoffs), the door gasket leak.
"""

from __future__ import annotations

import math

from napkin2factory.core.units import Quantity

SIGMA = 5.670374419e-8  # Stefan–Boltzmann constant, W/(m²·K⁴)


def _k(P, name):  # noqa: N803
    """Temperature parameter in kelvin (float)."""
    return float(P[name].to("kelvin").magnitude)


def _m(P, name):  # noqa: N803
    """Length parameter in metres (float)."""
    return float(P[name].to("m").magnitude)


def _box_area(w, d, h):
    """Surface area of a box, m²."""
    return 2.0 * (w * d + w * h + d * h)


def _areas(P):  # noqa: N803
    """Inner, brick-outer, fiber-outer, shell-outer and guard box areas, m²."""
    cw, cd, ch = _m(P, "chamber-width"), _m(P, "chamber-depth"), _m(P, "chamber-height")
    tb, tf = _m(P, "brick-thickness"), _m(P, "fiber-thickness")
    lc, fc = _m(P, "lining-clearance"), _m(P, "fiber-clearance")
    st, gap = _m(P, "shell-thickness"), _m(P, "guard-gap")
    dims = [cw, cd, ch]
    out = [_box_area(*dims)]
    for grow in (2 * tb, 2 * (lc + tf), 2 * (fc + st), 2 * gap):
        dims = [x + grow for x in dims]
        out.append(_box_area(*dims))
    return tuple(out)


def _body_resistances(P):  # noqa: N803
    """Brick and fiber resistances of the body (mean-area method), K/W."""
    a_in, a_b, a_f, _, _ = _areas(P)
    k_b = float(P["brick-conductivity"].to("W/(m*K)").magnitude)
    k_f = float(P["fiber-conductivity"].to("W/(m*K)").magnitude)
    r_b = _m(P, "brick-thickness") / (k_b * math.sqrt(a_in * a_b))
    r_f = _m(P, "fiber-thickness") / (k_f * math.sqrt(a_b * a_f))
    return r_b, r_f


def _bisect(f, lo, hi):
    """Root of a monotone function on [lo, hi] by bisection (to 1e-9 K)."""
    f_lo = f(lo)
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        f_mid = f(mid)
        if (f_mid > 0) == (f_lo > 0):
            lo, f_lo = mid, f_mid
        else:
            hi = mid
        if hi - lo < 1e-9:
            break
    return 0.5 * (lo + hi)


def _shield(P, t_hot_face, a_in, a_out, e_in, e_out):  # noqa: N803
    """Temperature of a guard receiving radiation from a surface at ``t_hot_face``, K."""
    t_amb = _k(P, "ambient-temperature")
    h_c = float(P["convection-coefficient"].to("W/(m**2*K)").magnitude)
    denom = 1.0 / e_in + (a_in / a_out) * (1.0 / e_out - 1.0)

    def balance(t_g):
        gain = SIGMA * a_in * (t_hot_face**4 - t_g**4) / denom
        loss = a_out * (h_c * (t_g - t_amb) + SIGMA * e_out * (t_g**4 - t_amb**4))
        return gain - loss

    return _bisect(balance, t_amb, t_hot_face)


def _body(P):  # noqa: N803
    """Solve the body: (Q, T_shell, T_guard, T_interface) in W and K."""
    t_hot, t_amb, t_gap = _k(P, "max-temperature"), _k(P, "ambient-temperature"), _k(P, "gap-air-temperature")
    h_c = float(P["convection-coefficient"].to("W/(m**2*K)").magnitude)
    e_s = float(P["shell-emissivity"].magnitude)
    e_g = float(P["guard-emissivity"].magnitude)
    _, _, _, a_s, a_g = _areas(P)
    r_b, r_f = _body_resistances(P)

    def residual(t_s):
        t_g = _shield(P, t_s, a_s, a_g, e_s, e_g)
        q_rad = SIGMA * a_s * (t_s**4 - t_g**4) / (1.0 / e_s + (a_s / a_g) * (1.0 / e_g - 1.0))
        return (t_hot - t_s) / (r_b + r_f) - a_s * h_c * (t_s - t_gap) - q_rad

    t_s = _bisect(residual, max(t_amb, t_gap), t_hot)
    t_g = _shield(P, t_s, a_s, a_g, e_s, e_g)
    q = (t_hot - t_s) / (r_b + r_f)
    return q, t_s, t_g, t_hot - q * r_b


def _door(P):  # noqa: N803
    """Solve the door: (Q, T_tray face, T_door guard) in W and K."""
    t_hot, t_amb = _k(P, "max-temperature"), _k(P, "ambient-temperature")
    h_c = float(P["convection-coefficient"].to("W/(m**2*K)").magnitude)
    e_s = float(P["shell-emissivity"].magnitude)
    e_g = float(P["guard-emissivity"].magnitude)
    k_b = float(P["brick-conductivity"].to("W/(m*K)").magnitude)
    k_f = float(P["fiber-conductivity"].to("W/(m*K)").magnitude)
    a_d_in = _m(P, "chamber-width") * _m(P, "chamber-height")
    a_plug = _m(P, "door-plug-width") * _m(P, "door-plug-height")
    r_db = _m(P, "brick-thickness") / (k_b * math.sqrt(a_d_in * a_plug))
    r_df = _m(P, "door-fiber-thickness") / (k_f * a_plug)
    a_face = float(P["door-face-spread"].magnitude) * a_plug

    def balance(t_d):
        q_in = (t_hot - t_d) / (r_db + r_df)
        return q_in - a_face * (h_c * (t_d - t_amb) + SIGMA * e_s * (t_d**4 - t_amb**4))

    t_d = _bisect(balance, t_amb, t_hot)
    t_dg = _shield(P, t_d, a_face, a_face, e_s, e_g)
    return (t_hot - t_d) / (r_db + r_df), t_d, t_dg


def _degc(t_k):
    """Kelvin float → degC Quantity."""
    return Quantity(t_k, "kelvin").to("degC")


def heat_loss(P):  # noqa: N803
    """Steady-state heat loss at max temperature, body plus door, W."""
    return Quantity(_body(P)[0] + _door(P)[0], "W")


def shell_temperature(P):  # noqa: N803
    """Inner (hot) shell temperature at steady state, degC (behind the guard; not touchable)."""
    return _degc(_body(P)[1])


def guard_temperature(P):  # noqa: N803
    """Body guard temperature at steady state, degC (accessible surface)."""
    return _degc(_body(P)[2])


def interface_temperature(P):  # noqa: N803
    """Brick/fiber interface temperature of the body walls, degC (fiber board class check)."""
    return _degc(_body(P)[3])


def door_skin_temperature(P):  # noqa: N803
    """Door tray face temperature at steady state, degC (behind the door guard)."""
    return _degc(_door(P)[1])


def door_guard_temperature(P):  # noqa: N803
    """Door guard temperature at steady state, degC (accessible surface)."""
    return _degc(_door(P)[2])


def max_touch_temperature(P):  # noqa: N803
    """Hottest accessible surface: the larger of the body guard and door guard, degC (REQ-003)."""
    return _degc(max(_body(P)[2], _door(P)[2]))


def stored_heat(P):  # noqa: N803
    """Heat stored in brick and fiber from cold to steady state, J.

    Each material is raised to the mean of its two face temperatures: brick between the hot
    face and the brick/fiber interface, fiber between the interface and the shell. Brick:
    the body's brick box less the chamber, plus the door slab; fiber: the fiber box less its
    hollow, plus the door plug. Densities and specific heats from ``parameters.yaml``.
    """
    t_hot, t_amb = _k(P, "max-temperature"), _k(P, "ambient-temperature")
    _, t_s, _, t_i = _body(P)
    cw, cd, ch = _m(P, "chamber-width"), _m(P, "chamber-depth"), _m(P, "chamber-height")
    li_w, li_d, li_h = _m(P, "liner-outer-width"), _m(P, "liner-outer-depth"), _m(P, "liner-outer-height")
    fb_w, fb_d, fb_h = _m(P, "fiber-box-width"), _m(P, "fiber-box-depth"), _m(P, "fiber-box-height")
    fi_w, fi_h = _m(P, "fiber-inner-width"), _m(P, "fiber-inner-height")
    tb, tf = _m(P, "brick-thickness"), _m(P, "fiber-thickness")
    plug = _m(P, "door-plug-width") * _m(P, "door-plug-height")
    v_brick = li_w * li_d * li_h - cw * cd * ch + plug * tb
    v_fiber = fb_w * fb_d * fb_h - fi_w * fi_h * (fb_d - tf) + plug * _m(P, "door-fiber-thickness")
    rc_b = float((P["brick-density"] * P["brick-specific-heat"]).to("J/(m**3*K)").magnitude)
    rc_f = float((P["fiber-density"] * P["fiber-specific-heat"]).to("J/(m**3*K)").magnitude)
    e_b = rc_b * v_brick * ((t_hot + t_i) / 2 - t_amb)
    e_f = rc_f * v_fiber * ((t_i + t_s) / 2 - t_amb)
    return Quantity(e_b + e_f, "J")


def required_power(P):  # noqa: N803
    """Element power needed: steady loss plus stored heat over the heat-up time, W."""
    return (heat_loss(P) + stored_heat(P) / P["heat-up-time"]).to("W")
