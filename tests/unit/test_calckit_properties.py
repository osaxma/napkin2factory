"""Property tests of the calc kit, one block per pack (F17): what must hold for any input,
not just the reference cases — monotonic in insulation, bounded by the hot face, and the
exact identities between functions (inverses, P = V·I, q·π·d·L = P, V·ρ = m).
"""

from __future__ import annotations

import math

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from napkin2factory.calckit import mass_cost, power
from napkin2factory.calckit import thermal_enclosure as te
from napkin2factory.calckit.thermal_enclosure import Layer
from napkin2factory.core.units import Quantity as Q

FAST = settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])

side = st.floats(0.05, 2.0)  # chamber side, m
thick = st.floats(0.005, 0.3)  # layer thickness, m
cond = st.floats(0.03, 2.0)  # W/(m K)
hot = st.floats(100.0, 1300.0)  # degC
h_conv = st.floats(2.0, 30.0)  # W/(m2 K)
emis = st.floats(0.0, 1.0)


def _mag(q, unit):
    return float(q.to(unit).magnitude)


# --- thermal_enclosure ----------------------------------------------------------------------


@FAST
@given(st.floats(0.2, 2.0), thick, thick, st.floats(0.03, 0.2), hot, st.floats(5.0, 30.0), emis)
def test_more_insulation_never_loses_more(s, t1, extra, k, t_hot, h, e):
    """Thicker insulation loses less, past the critical thickness.

    A thicker wall also grows the outer surface; for a conductive wall on a small box with a
    weak film the larger surface wins (the critical-radius effect, ~2k/h for a sphere), which
    hypothesis found with k = 1 W/(m K), h = 2 W/(m2 K). So the property is stated for
    insulation (k ≤ 0.2 W/(m K), h ≥ 5 W/(m2 K): 2k/h ≤ 0.08 m) on boxes of half-side ≥ 0.1 m.
    """
    inner = (Q(s, "m"),) * 3
    args = (Q(t_hot, "degC"), Q(25, "degC"), Q(h, "W/(m**2*K)"), Q(e, ""))
    thin = te.steady_loss(inner, [Layer(Q(t1, "m"), Q(k, "W/(m*K)"), "w")], *args)
    thicker = te.steady_loss(inner, [Layer(Q(t1 + extra, "m"), Q(k, "W/(m*K)"), "w")], *args)
    assert _mag(thicker.loss, "W") <= _mag(thin.loss, "W") * (1 + 1e-9)


@FAST
@given(side, thick, cond, hot, h_conv, emis)
def test_skin_is_bounded_by_room_and_hot_face_and_balances(s, t, k, t_hot, h, e):
    inner = (Q(s, "m"),) * 3
    r = te.steady_loss(
        inner,
        [Layer(Q(t, "m"), Q(k, "W/(m*K)"), "w")],
        Q(t_hot, "degC"),
        Q(25, "degC"),
        Q(h, "W/(m**2*K)"),
        Q(e, ""),
    )
    ts = _mag(r.outer_skin_temperature, "degC")
    assert 25 - 1e-6 <= ts <= t_hot + 1e-6
    # conduction through the wall equals what the skin gives off (the solved balance)
    a_s = _mag(te.box_areas(inner, [Layer(Q(t, "m"), None, "w")])[-1], "m**2")
    tk, ta = ts + 273.15, 298.15
    out = a_s * (h * (tk - ta) + te.SIGMA * e * (tk**4 - ta**4))
    assert _mag(r.loss, "W") == pytest.approx(out, rel=1e-6, abs=1e-6)


@FAST
@given(side, thick, thick, cond, cond, hot)
def test_interfaces_fall_from_the_hot_face(s, t1, t2, k1, k2, t_hot):
    inner = (Q(s, "m"),) * 3
    layers = [Layer(Q(t1, "m"), Q(k1, "W/(m*K)"), "a"), Layer(Q(t2, "m"), Q(k2, "W/(m*K)"), "b")]
    r = te.steady_loss(
        inner, layers, Q(t_hot, "degC"), Q(25, "degC"), Q(8, "W/(m**2*K)"), Q(0.9, "")
    )
    temps = [t_hot] + [_mag(x, "degC") for x in r.interface_temperatures]
    assert all(a >= b - 1e-6 for a, b in zip(temps, temps[1:], strict=False))
    # the wall resistance is the sum of the layer resistances
    total = sum(_mag(x, "K/W") for x in te.layer_resistances(inner, layers))
    assert _mag(te.wall_resistance(inner, layers), "K/W") == pytest.approx(total, rel=1e-12)


@FAST
@given(st.floats(1e3, 1e9), st.floats(1.0, 1e4), st.floats(0.1, 48.0))
def test_heat_up_power_and_time_are_inverses(stored, loss, hours):
    p = te.heat_up_power(Q(stored, "J"), Q(loss, "W"), Q(hours, "hour"))
    t = te.heat_up_time(Q(stored, "J"), Q(loss, "W"), p)
    assert _mag(t, "hour") == pytest.approx(hours, rel=1e-9)


@FAST
@given(st.floats(250.0, 1500.0), st.floats(250.0, 1500.0), emis, emis)
def test_guard_sits_between_room_and_hot_face(t_hot, t_amb, e1, e2):
    lo, hi = sorted((t_hot, t_amb))
    t_g = te.guard_temperature(
        Q(hi, "K"),
        Q(1, "m**2"),
        Q(1.2, "m**2"),
        Q(max(e1, 1e-3), ""),
        Q(max(e2, 1e-3), ""),
        h_outer=Q(5, "W/(m**2*K)"),
        t_ambient=Q(lo, "K"),
    )
    assert lo - 1e-6 <= _mag(t_g, "K") <= hi + 1e-6


# --- power ----------------------------------------------------------------------------------

watts = st.floats(10.0, 2e4)
volts = st.floats(12.0, 480.0)
dia = st.floats(0.1, 8.0)  # mm
rho = st.floats(0.5, 2.0)  # ohm mm2/m


@FAST
@given(watts, volts)
def test_current_and_resistance_identities(p, v):
    i = power.element_current(Q(p, "W"), Q(v, "V"))
    r = power.cold_resistance(Q(p, "W"), Q(v, "V"))
    assert _mag(i * Q(v, "V"), "W") == pytest.approx(p, rel=1e-12)  # P = V·I
    assert _mag(i**2 * r, "W") == pytest.approx(p, rel=1e-12)  # P = I²·R


@FAST
@given(watts, volts, dia, rho)
def test_wire_length_and_surface_load_identities(p, v, d, resistivity):
    r = power.cold_resistance(Q(p, "W"), Q(v, "V"))
    length = power.wire_length(r, Q(resistivity, "ohm*mm**2/m"), Q(d, "mm"))
    # the wire of that length has the resistance back: R = ρ·L/A
    area = power.wire_cross_section(Q(d, "mm"))
    assert _mag(Q(resistivity, "ohm*mm**2/m") * length / area, "ohm") == pytest.approx(
        _mag(r, "ohm"), rel=1e-12
    )
    q = power.surface_load(Q(p, "W"), Q(d, "mm"), length)
    assert _mag(q * math.pi * Q(d, "mm") * length, "W") == pytest.approx(p, rel=1e-12)


@FAST
@given(st.sampled_from(["SA", "EU", "UK", "US", "AU"]), st.floats(0.1, 40.0))
def test_a_chosen_circuit_always_has_the_headroom(region, amps):
    v = power.circuit_class(region, Q(amps, "A"))
    assert v.status in ("ok", "no_class")
    if v.status == "ok":
        assert _mag(v.rating, "A") >= power.CIRCUIT_HEADROOM_MIN * amps - 1e-9


# --- mass_cost ------------------------------------------------------------------------------


@FAST
@given(st.floats(1e-6, 10.0), st.sampled_from(["mild steel", "stainless", "aluminium", "K23"]))
def test_mass_is_volume_times_density(volume, material):
    rho, _ = mass_cost.density(material)
    m = mass_cost.mass(Q(volume, "m**3"), material)
    assert _mag(m, "kg") == pytest.approx(volume * _mag(rho, "kg/m**3"), rel=1e-12)


@FAST
@given(st.floats(0.1, 500.0), st.floats(0.0, 100.0))
def test_lift_class_never_gets_lighter_with_more_mass(kg, more):
    order = ["one-person", "two-person", "equipment"]
    a = mass_cost.lift_class(Q(kg, "kg")).label
    b = mass_cost.lift_class(Q(kg + more, "kg")).label
    assert order.index(b) >= order.index(a)


@FAST
@given(st.floats(10.0, 3500.0), st.floats(10.0, 3500.0))
def test_stock_fit_does_not_depend_on_orientation(a, b):
    one = mass_cost.stock_sheet_fits((Q(a, "mm"), Q(b, "mm")))
    other = mass_cost.stock_sheet_fits((Q(b, "mm"), Q(a, "mm")))
    assert (one.fits, one.sheet) == (other.fits, other.sheet)


@FAST
@given(st.floats(0.1, 200.0), st.integers(1, 20))
def test_cost_band_is_linear_in_count(kg, n):
    one = mass_cost.cost_estimate("cut-block", mass=Q(kg, "kg"))
    many = mass_cost.cost_estimate("cut-block", mass=Q(kg, "kg"), count=n)
    assert _mag(many.low, "USD") == pytest.approx(n * _mag(one.low, "USD"), rel=1e-12)
    assert _mag(many.low, "USD") <= _mag(many.high, "USD")
