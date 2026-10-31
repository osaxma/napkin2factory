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

The body walls, the shell/guard balance and the door guard are computed by the system calc
kit (``napkin2factory.calckit.thermal_enclosure``: ``guarded_loss``, ``guard_temperature``,
``box_areas``, ``layer_resistances``), the same functions screening uses, so the two
fidelities cannot drift apart (NAPKIN_STAGE §7). The door plug and the stored heat stay here:
their geometry (an open-fronted liner, a tapered plug) is specific to this kiln.
"""

from __future__ import annotations

import math

from napkin2factory.calckit import thermal_enclosure as kit
from napkin2factory.core.units import Quantity

SIGMA = 5.670374419e-8  # Stefan–Boltzmann constant, W/(m²·K⁴)


def _k(P, name):  # noqa: N803
    """Temperature parameter in kelvin (float)."""
    return float(P[name].to("kelvin").magnitude)


def _m(P, name):  # noqa: N803
    """Length parameter in metres (float)."""
    return float(P[name].to("m").magnitude)


def _wall(P):  # noqa: N803
    """Chamber, wall layers (brick; fiber behind lining-clearance; shell behind fiber-clearance)."""
    inner = (P["chamber-width"], P["chamber-depth"], P["chamber-height"])
    tb, tf = P["brick-thickness"], P["fiber-thickness"]
    lc, fc = P["lining-clearance"], P["fiber-clearance"]
    st, gap = P["shell-thickness"], P["guard-gap"]
    layers = [
        kit.Layer(tb, P["brick-conductivity"], "brick"),
        kit.Layer(tf, P["fiber-conductivity"], "fiber", clearance=lc),
        kit.Layer(st, None, "shell", clearance=fc),
    ]
    return inner, layers, gap


def _areas(P):  # noqa: N803
    """Inner, brick-outer, fiber-outer, shell-outer and guard box areas, m²."""
    inner, layers, gap = _wall(P)
    areas = kit.box_areas(inner, [*layers, kit.Layer(gap, None, "guard gap")])
    return tuple(float(a.to("m**2").magnitude) for a in areas)


def _body_resistances(P):  # noqa: N803
    """Brick and fiber resistances of the body (mean-area method), K/W."""
    inner, layers, _ = _wall(P)
    r_b, r_f, _ = kit.layer_resistances(inner, layers)
    return float(r_b.to("K/W").magnitude), float(r_f.to("K/W").magnitude)


def _body(P):  # noqa: N803
    """Solve the body (calc kit ``guarded_loss``): the steady-state result, quantities."""
    t_hot, t_amb, t_gap = P["max-temperature"], P["ambient-temperature"], P["gap-air-temperature"]
    h_c = P["convection-coefficient"]
    e_s, e_g = P["shell-emissivity"], P["guard-emissivity"]
    inner, layers, gap = _wall(P)
    return kit.guarded_loss(inner, layers, gap, t_hot, t_amb, t_gap, h_c, e_s, e_g)


def _door(P):  # noqa: N803
    """Solve the door: (Q in W, T_tray face in K, T_door guard as degC quantity)."""
    t_hot, t_amb = _k(P, "max-temperature"), _k(P, "ambient-temperature")
    h_c = float(P["convection-coefficient"].to("W/(m**2*K)").magnitude)
    e_s = float(P["shell-emissivity"].magnitude)
    e_g = P["guard-emissivity"]
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

    t_d = kit.bisect_root(balance, t_amb, t_hot)
    face = Quantity(a_face, "m**2")
    t_dg = kit.guard_temperature(
        Quantity(t_d, "kelvin"),
        face,
        face,
        P["shell-emissivity"],
        e_g,
        h_outer=P["convection-coefficient"],
        t_ambient=P["ambient-temperature"],
    )
    return (t_hot - t_d) / (r_db + r_df), t_d, t_dg


def _degc(t_k):
    """Kelvin float → degC Quantity."""
    return Quantity(t_k, "kelvin").to("degC")


def heat_loss(P):  # noqa: N803
    """Steady-state heat loss at max temperature, body plus door, W."""
    return Quantity(_body(P).loss.to("W").magnitude + _door(P)[0], "W")


def shell_temperature(P):  # noqa: N803
    """Inner (hot) shell temperature at steady state, degC (behind the guard; not touchable)."""
    return _body(P).outer_skin_temperature


def guard_temperature(P):  # noqa: N803
    """Body guard temperature at steady state, degC (accessible surface)."""
    return _body(P).guard_temperature


def interface_temperature(P):  # noqa: N803
    """Brick/fiber interface temperature of the body walls, degC (fiber board class check)."""
    return _body(P).interface_temperatures[0]


def door_skin_temperature(P):  # noqa: N803
    """Door tray face temperature at steady state, degC (behind the door guard)."""
    return _degc(_door(P)[1])


def door_guard_temperature(P):  # noqa: N803
    """Door guard temperature at steady state, degC (accessible surface)."""
    return _door(P)[2]


def max_touch_temperature(P):  # noqa: N803
    """Hottest accessible surface: the larger of the body guard and door guard, degC (REQ-003)."""
    return max(_body(P).guard_temperature, _door(P)[2])


def stored_heat(P):  # noqa: N803
    """Heat stored in brick and fiber from cold to steady state, J.

    Each material is raised to the mean of its two face temperatures: brick between the hot
    face and the brick/fiber interface, fiber between the interface and the shell. Brick:
    the body's brick box less the chamber, plus the door slab; fiber: the fiber box less its
    hollow, plus the door plug. Densities and specific heats from ``parameters.yaml``.
    """
    t_hot, t_amb = _k(P, "max-temperature"), _k(P, "ambient-temperature")
    body = _body(P)
    t_s = float(body.outer_skin_temperature.to("kelvin").magnitude)
    t_i = float(body.interface_temperatures[0].to("kelvin").magnitude)
    cw, cd, ch = _m(P, "chamber-width"), _m(P, "chamber-depth"), _m(P, "chamber-height")
    li_w, li_d = _m(P, "liner-outer-width"), _m(P, "liner-outer-depth")
    li_h = _m(P, "liner-outer-height")
    fb_w, fb_d = _m(P, "fiber-box-width"), _m(P, "fiber-box-depth")
    fb_h = _m(P, "fiber-box-height")
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
    loss = heat_loss(P)
    return kit.heat_up_power(loss=loss, stored=stored_heat(P), heat_up_time=P["heat-up-time"])
