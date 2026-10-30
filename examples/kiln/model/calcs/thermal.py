"""Steady-state heat loss and skin temperature of the kiln (1-D series conduction).

Model: each wall is a flat composite slab brick → fiber → (thin steel, neglected) with the
chamber face at ``max-temperature`` and the outer skin losing heat to ambient by a lumped
film coefficient ``skin-film-coefficient`` (natural convection + radiation, nominal).

    q'' = (T_hot − T_amb) / (t_brick/k_brick + t_fiber/k_fiber + 1/h)          [W/m²]
    T_skin = T_amb + q''/h
    Q = q'' × A_outer

Sources: series thermal resistance (Incropera & DeWitt, *Fundamentals of Heat and Mass
Transfer*, ch. 3); K23 conductivity from the Morgan Thermal Ceramics K-23 datasheet
(0.20–0.30 W/m·K over 400–1000 °C, taken as 0.25 at the mean wall temperature) [verify];
fiber board 0.12 W/m·K at ~300 °C mean [verify]; h = 10 W/m²·K is a common nominal value
for a vertical surface a few tens of degrees above room air [verify]. Edges and corners are
neglected (conservative for skin temperature, slightly optimistic for heat loss).
"""

from __future__ import annotations

from napkin2factory.core.units import Quantity


def _resistance(P):  # noqa: N803
    """Area-specific thermal resistance of one wall, m²·K/W (conduction + film)."""
    r_brick = (P["brick-thickness"] / P["brick-conductivity"]).to("m**2*K/W")
    r_fiber = (P["fiber-thickness"] / P["fiber-conductivity"]).to("m**2*K/W")
    r_film = (1 / P["skin-film-coefficient"]).to("m**2*K/W")
    return r_brick + r_fiber + r_film


def _delta_t(P):  # noqa: N803
    """Hot face minus ambient, as a temperature difference (kelvin)."""
    hot = P["max-temperature"].to("kelvin")
    amb = P["ambient-temperature"].to("kelvin")
    return (hot - amb).to("kelvin")


def heat_flux(P):  # noqa: N803
    """Steady heat flux through a wall, W/m²."""
    return (_delta_t(P) / _resistance(P)).to("W/m**2")


def outer_area(P):  # noqa: N803
    """Outer surface area of the insulated box (six faces), m²."""
    w = P["shell-outer-width"]
    d = P["shell-outer-depth"]
    h = P["shell-outer-height"]
    return (2 * (w * d + w * h + d * h)).to("m**2")


def heat_loss(P):  # noqa: N803
    """Steady-state heat loss at max temperature, W."""
    return (heat_flux(P) * outer_area(P)).to("W")


def skin_temperature(P):  # noqa: N803
    """Outer skin temperature at steady state, degC."""
    rise = (heat_flux(P) / P["skin-film-coefficient"]).to("kelvin")
    amb = P["ambient-temperature"].to("kelvin")
    return Quantity((amb + rise).to("kelvin").magnitude, "kelvin").to("degC")


SIGMA = Quantity(5.670374419e-8, "W/(m**2*K**4)")  # Stefan–Boltzmann constant


def guard_temperature(P):  # noqa: N803
    """Touch-guard temperature at steady state, degC (the accessible surface, REQ-003).

    The guard is a ventilated radiation shield: convection from the hot inner shell leaves
    through the vent slots, so the guard is heated only by radiation across the gap and
    cooled by natural convection and radiation to the room:

        σ ε_eff (T_s⁴ − T_g⁴) = h (T_g − T_amb) + σ ε_g (T_g⁴ − T_amb⁴),
        ε_eff = 1 / (1/ε_s + 1/ε_g − 1)      (two large parallel grey plates)

    Source: Incropera & DeWitt, radiation shields (ch. 13); solved by fixed-point
    iteration on T_g. The inner shell temperature T_s comes from :func:`skin_temperature`.
    """
    t_s = skin_temperature(P).to("kelvin").magnitude
    t_amb = P["ambient-temperature"].to("kelvin").magnitude
    h = P["skin-film-coefficient"].to("W/(m**2*K)").magnitude
    e_s = float(P["shell-emissivity"].magnitude)
    e_g = float(P["guard-emissivity"].magnitude)
    sigma = SIGMA.magnitude
    e_eff = 1.0 / (1.0 / e_s + 1.0 / e_g - 1.0)
    t_g = t_amb + 30.0
    for _ in range(200):
        gain = sigma * e_eff * (t_s**4 - t_g**4)
        loss = h * (t_g - t_amb) + sigma * e_g * (t_g**4 - t_amb**4)
        # Newton step on f(T) = gain − loss
        dgain = -4 * sigma * e_eff * t_g**3
        dloss = h + 4 * sigma * e_g * t_g**3
        step = (gain - loss) / (dgain - dloss)
        t_g -= step
        if abs(step) < 1e-6:
            break
    return Quantity(t_g, "kelvin").to("degC")


def stored_heat(P):  # noqa: N803
    """Heat to bring the brick lining from ambient to its mean temperature, J (rough)."""
    # K23 density ~480 kg/m³, cp ~1.0 kJ/kg·K [verify]; mean brick temperature ≈ 0.6 × hot face.
    rho = Quantity(480, "kg/m**3")
    cp = Quantity(1000, "J/(kg*K)")
    w = P["liner-outer-width"]
    d = P["liner-outer-depth"] + P["brick-thickness"]
    h = P["liner-outer-height"]
    cw, cd, ch = P["chamber-width"], P["chamber-depth"], P["chamber-height"]
    volume = (w * d * h - cw * cd * ch).to("m**3")
    mean_rise = 0.6 * _delta_t(P)
    return (rho * volume * cp * mean_rise).to("J")


def required_power(P):  # noqa: N803
    """Element power needed: steady loss plus stored heat over the heat-up time, W."""
    return (heat_loss(P) + stored_heat(P) / P["heat-up-time"]).to("W")
