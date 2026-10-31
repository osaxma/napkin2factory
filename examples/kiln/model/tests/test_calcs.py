"""Hand-checked values for the kiln calcs (run with: uv run pytest examples/kiln/model/tests)."""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "calcs"))

SIGMA = 5.670374419e-8


@pytest.fixture(scope="module")
def P():  # noqa: N802
    from napkin2factory.core.loader import load_product
    from napkin2factory.geometry.accessors import make_accessors

    product = load_product(Path(__file__).resolve().parents[2])
    return make_accessors(product)[0]


def test_box_areas_and_resistances_by_hand(P):  # noqa: N803
    import thermal

    # chamber 0.2 m cube; brick outer 0.328; fiber outer 0.328 + 2·(0.003 + 0.125) = 0.584;
    # shell outer 0.584 + 2·(0.002 + 0.0012) = 0.5904; guard 0.5904 + 2·0.025 = 0.6404 (all cubes: A = 6·s²)
    expect = [6 * s**2 for s in (0.2, 0.328, 0.584, 0.5904, 0.6404)]
    assert thermal._areas(P) == pytest.approx(expect, rel=1e-9)
    # R_b = 0.064 / (0.25·√(0.24·0.645504)) = 0.6504 K/W; R_f = 0.125 / (0.15·√(0.645504·2.046336)) = 0.7251 K/W
    r_b, r_f = thermal._body_resistances(P)
    assert r_b == pytest.approx(0.064 / (0.25 * math.sqrt(0.24 * 0.645504)), rel=1e-9)
    assert r_b == pytest.approx(0.6504, rel=1e-3)
    assert r_f == pytest.approx(0.7251, rel=1e-3)


def test_body_balance_by_hand(P):  # noqa: N803
    import thermal

    q = thermal.heat_loss(P).to("W").magnitude
    ts = thermal.shell_temperature(P).to("kelvin").magnitude
    tg = thermal.guard_temperature(P).to("kelvin").magnitude
    ti = thermal.interface_temperature(P).to("kelvin").magnitude
    # expected (solved by hand iteration): shell ≈ 79 °C, guard ≈ 44 °C, interface ≈ 670 °C
    assert ts - 273.15 == pytest.approx(78.75, abs=0.1)
    assert tg - 273.15 == pytest.approx(44.04, abs=0.1)
    assert ti - 273.15 == pytest.approx(669.8, abs=0.5)
    # the solved temperatures satisfy both balances (re-derived here, not through the module)
    a_s, a_g = 6 * 0.5904**2, 6 * 0.6404**2
    q_body = (1473.15 - ts) / (0.6504065 + 0.7250715)
    q_rad = SIGMA * a_s * (ts**4 - tg**4) / (1 / 0.9 + (a_s / a_g) * (1 / 0.9 - 1))
    assert q_body == pytest.approx(a_s * 5 * (ts - 323.15) + q_rad, rel=1e-4)
    assert q_rad == pytest.approx(a_g * (5 * (tg - 298.15) + SIGMA * 0.9 * (tg**4 - 298.15**4)), rel=1e-4)
    assert 1473.15 - q_body * 0.6504065 == pytest.approx(ti, rel=1e-5)
    # body ≈ 815 W plus door ≈ 83 W
    assert q_body == pytest.approx(815.2, rel=1e-2)
    assert q == pytest.approx(897.9, rel=1e-2)


def test_door_by_hand(P):  # noqa: N803
    import thermal

    # plug 0.324 × 0.324 m; R_db = 0.064/(0.25·√(0.04·0.104976)) = 3.951 K/W; R_df = 0.153/(0.15·0.104976) = 9.717 K/W
    a_plug = 0.324 * 0.324
    r = 0.064 / (0.25 * math.sqrt(0.04 * a_plug)) + 0.153 / (0.15 * a_plug)
    assert r == pytest.approx(13.667, rel=1e-3)
    td = thermal.door_skin_temperature(P).to("kelvin").magnitude
    tdg = thermal.door_guard_temperature(P).to("kelvin").magnitude
    a_face = 1.5 * a_plug
    assert (1473.15 - td) / r == pytest.approx(a_face * (5 * (td - 298.15) + SIGMA * 0.9 * (td**4 - 298.15**4)), rel=1e-4)
    assert td - 273.15 == pytest.approx(69.7, abs=0.2)
    # door guard: equal areas → ε_eff = 1/(1/0.9 + 1/0.9 − 1)
    e_eff = 1 / (1 / 0.9 + 1 / 0.9 - 1)
    assert SIGMA * e_eff * (td**4 - tdg**4) == pytest.approx(5 * (tdg - 298.15) + SIGMA * 0.9 * (tdg**4 - 298.15**4), rel=1e-4)
    assert tdg - 273.15 == pytest.approx(41.9, abs=0.2)
    # the touch requirement looks at the hotter guard (the body guard here)
    assert thermal.max_touch_temperature(P).magnitude == pytest.approx(thermal.guard_temperature(P).magnitude)


def test_stored_heat_and_power_by_hand(P):  # noqa: N803
    import thermal

    ti = thermal.interface_temperature(P).magnitude  # degC
    ts = thermal.shell_temperature(P).magnitude
    plug = 0.324 * 0.324
    v_brick = 0.328 * 0.264 * 0.328 - 0.2**3 + plug * 0.064  # 0.02040 + 0.00672 = 0.02712 m³
    v_fiber = 0.584 * 0.583 * 0.584 - 0.334 * 0.334 * (0.583 - 0.125) + plug * 0.153  # 0.14775 + 0.01606 = 0.1638 m³
    assert v_brick == pytest.approx(0.02712, rel=1e-3)
    assert v_fiber == pytest.approx(0.1638, rel=1e-3)
    e = 480 * 1000 * v_brick * ((1200 + ti) / 2 - 25) + 260 * 1050 * v_fiber * ((ti + ts) / 2 - 25)
    assert thermal.stored_heat(P).to("J").magnitude == pytest.approx(e, rel=1e-6)
    assert e == pytest.approx(27.46e6, rel=1e-2)
    # 0.898 kW + 27.46 MJ / 25200 s = 1.99 kW; 2.5 kW gives a margin of 1.26
    assert thermal.required_power(P).to("W").magnitude == pytest.approx(897.9 + 27.46e6 / 25200, rel=1e-2)


def test_element_by_hand(P):  # noqa: N803
    import element

    assert element.current(P).magnitude == pytest.approx(2500 / 230, rel=1e-6)  # 10.87 A on 16 A
    assert element.resistance(P).magnitude == pytest.approx(230**2 / 2500, rel=1e-6)
    # L = R·A/ρ = 21.16 Ω × 2.0106 mm² / 1.45 Ω·mm²/m = 29.34 m
    length = 21.16 * (math.pi / 4 * 1.6**2) / 1.45
    assert element.wire_length(P).magnitude == pytest.approx(length, rel=1e-6)
    assert length == pytest.approx(29.34, rel=1e-3)
    # turns = L / (π·(12 − 1.6) mm) = 29341 / 32.67 = 898
    turns = length * 1000 / (math.pi * (12 - 1.6))
    assert element.coil_turns(P).magnitude == pytest.approx(turns, rel=1e-6)
    assert turns == pytest.approx(898, abs=1)
    # grooves: 5 × (2 × 200 + 200) = 3000 mm; pitch 3000 / 898 = 3.34 mm = 2.09 d
    assert element.available_groove_length(P).magnitude == pytest.approx(3000)
    assert element.coil_pitch(P).magnitude == pytest.approx(3000 / turns, rel=1e-6)
    assert element.pitch_factor(P).magnitude == pytest.approx(3000 / turns / 1.6, rel=1e-6)
    assert element.pitch_factor(P).magnitude == pytest.approx(2.09, abs=0.01)
    # surface load 2500 W / (π × 0.16 cm × 2934 cm) = 1.70 W/cm²
    assert element.surface_load(P).to("W/cm**2").magnitude == pytest.approx(2500 / (math.pi * 0.16 * length * 100), rel=1e-6)
    assert element.surface_load(P).to("W/cm**2").magnitude == pytest.approx(1.70, abs=0.01)
    assert element.power_margin(P).magnitude == pytest.approx(1.26, abs=0.02)


def test_swing_by_hand(P):  # noqa: N803
    import swing

    # pin x = −(door-guard-width/2 + 1 + 6) = −(702.4/2 + 7) = −358.2, y 62; opening edge (167, 26);
    # rear corner (162 − 217·tan 6°, 215) = (139.19, 215)
    a_rear = 162 - 217 * math.tan(math.radians(6))
    r0_sq = (167 + 358.2) ** 2 + (26 - 62) ** 2
    expect = math.sqrt(r0_sq - (215 - 62) ** 2) - 358.2 - a_rear
    assert swing.plug_clearance(P).to("mm").magnitude == pytest.approx(expect, rel=1e-6)
    assert expect == pytest.approx(6.32, abs=0.01)
