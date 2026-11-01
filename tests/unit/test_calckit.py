"""Hand-checked tests for the calc kit (napkin2factory.calckit), N4.

Each test's comment shows the hand computation; the kiln test pins the kiln's verified
numbers (recorded before the kiln's calcs were routed through the kit).
"""

from __future__ import annotations

import math

import pint
import pytest

from napkin2factory.calckit import TableError, load_table, mass_cost, power, table_names
from napkin2factory.calckit import _tables as tables
from napkin2factory.calckit import thermal_enclosure as te
from napkin2factory.calckit.thermal_enclosure import Layer
from napkin2factory.core.units import Quantity as Q
from tests.conftest import EXAMPLES, copy_product

SIGMA = 5.670374419e-8
CUBE = (Q(1, "m"), Q(1, "m"), Q(1, "m"))


def _mag(q, unit):
    return float(q.to(unit).magnitude)


# --- thermal_enclosure ---------------------------------------------------------------


def test_box_areas_by_hand():
    # 1 m cube: A = 6 m²; + 0.1 m layer → 1.2 m cube: 6·1.44 = 8.64 m²;
    # + 0.05 m clearance + 0.1 m layer → grows 0.3 m: 1.5 m cube … from 1.2: 6·1.5² = 13.5 m²
    layers = [Layer(Q(100, "mm"), Q(1, "W/(m*K)"), "a"), Layer(Q(0.1, "m"), None, "b", Q(50, "mm"))]
    areas = [_mag(a, "m**2") for a in te.box_areas(CUBE, layers)]
    assert areas == pytest.approx([6.0, 8.64, 13.5], rel=1e-12)


def test_layer_and_wall_resistance_by_hand():
    # one 0.1 m layer, k = 1 W/m·K, on a 1 m cube: A_mean = √(6 · 8.64) = √51.84 = 7.2 m²
    # → R = 0.1 / (1 · 7.2) = 0.013889 K/W
    slab = Layer(Q(0.1, "m"), Q(1, "W/(m*K)"), "slab")
    assert _mag(te.wall_resistance(CUBE, [slab]), "K/W") == pytest.approx(0.1 / 7.2, rel=1e-12)
    # behind a 0.05 m clearance the layer grows the box by 0.3 m: A_out = 6·1.3² = 10.14,
    # A_in stays 6 (the clearance is geometry only) → A_mean = √60.84 = 7.8 → R = 0.012821
    gap_slab = Layer(Q(0.1, "m"), Q(1, "W/(m*K)"), "slab", clearance=Q(0.05, "m"))
    rs = te.layer_resistances(CUBE, [gap_slab, Layer(Q(1, "mm"), None, "skin")])
    assert _mag(rs[0], "K/W") == pytest.approx(0.1 / 7.8, rel=1e-12)
    assert _mag(rs[1], "K/W") == 0.0  # neglected skin
    with pytest.raises(ValueError, match="no conducting layer"):
        te.wall_resistance(CUBE, [Layer(Q(1, "mm"), None, "skin")])
    with pytest.raises(ValueError, match="width, depth, height"):
        te.box_areas((Q(1, "m"),), [slab])


def test_steady_loss_by_hand():
    # ε = 0 → pure convection, a series circuit: R_wall = 1/72, R_conv = 1/(h·A_s) = 1/(10·8.64)
    # = 1/86.4; q = ΔT / (1/72 + 1/86.4) = 1000 · 72·86.4/158.4 = 39 272.7 W;
    # skin = T_amb + q/86.4 = 25 + 454.545 °C
    slab = Layer(Q(0.1, "m"), Q(1, "W/(m*K)"), "slab")
    r = te.steady_loss(CUBE, [slab], Q(1025, "degC"), Q(25, "degC"), Q(10, "W/(m**2*K)"), Q(0, ""))
    assert _mag(r.loss, "W") == pytest.approx(1000 * 72 * 86.4 / 158.4, rel=1e-8)
    assert _mag(r.outer_skin_temperature, "degC") == pytest.approx(25 + 72000 / 158.4, rel=1e-8)
    assert len(r.interface_temperatures) == 1
    assert _mag(r.wall_resistance, "K/W") == pytest.approx(1 / 72, rel=1e-12)
    # with radiation the skin is cooler and the loss higher; the balance still closes
    r2 = te.steady_loss(
        CUBE, [slab], Q(1025, "degC"), Q(25, "degC"), Q(10, "W/(m**2*K)"), Q(0.9, "")
    )
    ts, ta = _mag(r2.outer_skin_temperature, "K"), 298.15
    assert _mag(r2.loss, "W") == pytest.approx(
        8.64 * (10 * (ts - ta) + SIGMA * 0.9 * (ts**4 - ta**4)), rel=1e-7
    )
    assert _mag(r2.loss, "W") > _mag(r.loss, "W")


def test_guard_temperature_by_hand():
    # classic radiation shield: equal areas, ε = 1, no convection (h = 0):
    # T_h⁴ − T_g⁴ = T_g⁴ − T_a⁴ → T_g = ((400⁴ + 300⁴)/2)^¼ = 360.288 K
    t_g = te.guard_temperature(
        Q(400, "K"),
        Q(1, "m**2"),
        Q(1, "m**2"),
        Q(1.0, ""),
        Q(1.0, ""),
        h_outer=Q(0, "W/(m**2*K)"),
        t_ambient=Q(300, "K"),
    )
    assert _mag(t_g, "K") == pytest.approx(((400**4 + 300**4) / 2) ** 0.25, rel=1e-9)
    assert _mag(t_g, "K") == pytest.approx(360.288, abs=1e-3)
    # gap-air extension: radiation switched off (ε → 0), hot face at ambient; the guard sits
    # between gap air (350 K) and room (300 K) with equal films → T_g = (350 + 300)/2 = 325 K
    t_g2 = te.guard_temperature(
        Q(300, "K"),
        Q(1, "m**2"),
        Q(1, "m**2"),
        Q(1e-12, ""),
        Q(1e-12, ""),
        h_outer=Q(5, "W/(m**2*K)"),
        t_ambient=Q(300, "K"),
        h_gap_air=Q(5, "W/(m**2*K)"),
        t_gap_air=Q(350, "K"),
    )
    assert _mag(t_g2, "K") == pytest.approx(325.0, abs=1e-6)


def test_guarded_loss_by_hand():
    # ε → 0: no radiation, so the guard stays at ambient and the skin balances conduction
    # against convection to the gap air: (T_h − T_s)·72 = 86.4·(T_s − T_gap)
    # → T_s − T_gap = 72·975/158.4 = 443.18 K, q = 975 · 72·86.4/158.4 = 38 290.9 W
    slab = Layer(Q(0.1, "m"), Q(1, "W/(m*K)"), "slab")
    skin = Layer(Q(1, "mm"), None, "skin")
    r = te.guarded_loss(
        CUBE,
        [slab, Layer(Q(0, "m"), None, "skin")],
        Q(25, "mm"),
        Q(1025, "degC"),
        Q(25, "degC"),
        Q(50, "degC"),
        Q(10, "W/(m**2*K)"),
        Q(1e-12, ""),
        Q(1e-12, ""),
    )
    assert _mag(r.loss, "W") == pytest.approx(975 * 72 * 86.4 / 158.4, rel=1e-8)
    assert _mag(r.outer_skin_temperature, "degC") == pytest.approx(50 + 72 * 975 / 158.4, rel=1e-8)
    assert _mag(r.guard_temperature, "degC") == pytest.approx(25.0, abs=1e-6)
    assert [_mag(t, "degC") for t in r.interface_temperatures] == pytest.approx(
        [_mag(r.outer_skin_temperature, "degC")] * 2
    )
    # a two-layer wall: the first interface is T_h − q·R_1
    r2 = te.guarded_loss(
        CUBE,
        [slab, slab, skin],
        Q(25, "mm"),
        Q(1025, "degC"),
        Q(25, "degC"),
        Q(50, "degC"),
        Q(5, "W/(m**2*K)"),
        Q(0.9, ""),
        Q(0.9, ""),
    )
    r1 = _mag(te.layer_resistances(CUBE, [slab])[0], "K/W")
    assert _mag(r2.interface_temperatures[0], "K") == pytest.approx(
        1298.15 - _mag(r2.loss, "W") * r1, rel=1e-12
    )


def test_stored_heat_by_hand():
    # 1 m cube inside a 0.5 m layer → 2 m cube: V = 8 − 1 = 7 m³; ρ·c = 1000·1000 = 1 MJ/m³K;
    # faces at T_amb + 1000 K and T_amb → mean rise 500 K → E = 7 · 1e6 · 500 = 3.5 GJ
    layer = Layer(Q(0.5, "m"), Q(1, "W/(m*K)"), "block")
    e = te.stored_heat(
        CUBE,
        [layer],
        [Q(1000, "kg/m**3")],
        [Q(1000, "J/(kg*K)")],
        Q(1025, "degC"),
        Q(25, "degC"),
        [Q(25, "degC")],
    )
    assert _mag(e, "J") == pytest.approx(3.5e9, rel=1e-12)
    # an air gap (None) stores nothing; a clearance is empty: a 0.5 m clearance then a
    # 0.5 m layer → shell between 2 m and 3 m cubes: 27 − 8 = 19 m³ at a uniform +1000 K → 19 GJ
    e2 = te.stored_heat(
        CUBE,
        [Layer(Q(0.5, "m"), None, "gap"), Layer(Q(0.5, "m"), None, "solid")],
        [None, Q(1000, "kg/m**3")],
        [None, Q(1000, "J/(kg*K)")],
        Q(1025, "degC"),
        Q(25, "degC"),
        [Q(1025, "degC"), Q(1025, "degC")],
    )
    assert _mag(e2, "J") == pytest.approx(19e9, rel=1e-12)
    with pytest.raises(ValueError, match="one entry per layer"):
        te.stored_heat(CUBE, [layer], [], [], Q(1, "degC"), Q(0, "degC"), [])


def test_heat_up_power_and_time_by_hand():
    # 1 kW loss + 36 MJ over 5 h (18 000 s) = 1000 + 2000 = 3000 W; inverse: 36 MJ / 2 kW = 5 h
    assert _mag(te.heat_up_power(Q(36, "MJ"), Q(1, "kW"), Q(5, "hour")), "W") == pytest.approx(3000)
    assert _mag(te.heat_up_time(Q(36, "MJ"), Q(1, "kW"), Q(3, "kW")), "hour") == pytest.approx(5)
    with pytest.raises(ValueError, match="never reaches"):
        te.heat_up_time(Q(36, "MJ"), Q(1, "kW"), Q(900, "W"))


def test_bisect_root_by_hand():
    # x² − 2 on [0, 2] → √2
    assert te.bisect_root(lambda x: x * x - 2, 0.0, 2.0, tol=1e-12) == pytest.approx(math.sqrt(2))


def test_length_where_temperature_expected_raises():
    slab = Layer(Q(0.1, "m"), Q(1, "W/(m*K)"), "slab")
    with pytest.raises(pint.DimensionalityError):
        te.steady_loss(CUBE, [slab], Q(100, "mm"), Q(25, "degC"), Q(10, "W/(m**2*K)"), Q(0.9, ""))


def test_bare_numbers_are_unit_errors():
    """Review gate A, C10: an emissivity (or any input) given as a bare float is refused."""
    from napkin2factory.core.units import UnitError

    slab = Layer(Q(0.1, "m"), Q(1, "W/(m*K)"), "slab")
    args = [CUBE, [slab], Q(1025, "degC"), Q(25, "degC"), Q(10, "W/(m**2*K)"), Q(0.9, "")]
    for i, bare in ((5, 0.9), (4, 5.0), (3, 25.0)):
        bad = list(args)
        bad[i] = bare
        with pytest.raises(UnitError, match="expects a quantity"):
            te.steady_loss(*bad)


# --- power -----------------------------------------------------------------------------


def test_element_sizing_by_hand():
    # kiln element (DEC-004): 2500 W on 230 V → I = 10.87 A, R = 230²/2500 = 21.16 Ω;
    # 1.6 mm Kanthal A1: A = π/4·1.6² = 2.0106 mm²; L = 21.16 · 2.0106 / 1.45 = 29.34 m;
    # surface load 2500 / (π · 0.16 cm · 2934.1 cm) = 1.695 W/cm² (< 2.0 limit)
    i = power.element_current(Q(2500, "W"), Q(230, "V"))
    assert _mag(i, "A") == pytest.approx(10.8696, rel=1e-5)
    r = power.cold_resistance(Q(2500, "W"), Q(230, "V"))
    assert _mag(r, "ohm") == pytest.approx(21.16, rel=1e-12)
    assert _mag(power.wire_cross_section(Q(1.6, "mm")), "mm**2") == pytest.approx(
        math.pi / 4 * 1.6**2
    )
    length = power.wire_length(r, Q(1.45, "ohm*mm**2/m"), Q(1.6, "mm"))
    assert _mag(length, "m") == pytest.approx(21.16 * math.pi / 4 * 1.6**2 / 1.45, rel=1e-12)
    assert _mag(length, "m") == pytest.approx(29.34, abs=0.01)
    load = power.surface_load(Q(2500, "W"), Q(1.6, "mm"), length)
    assert _mag(load, "W/cm**2") == pytest.approx(1.695, abs=1e-3)
    assert load < power.KANTHAL_GROOVE_SURFACE_LOAD_LIMIT


def test_circuit_class_by_hand():
    # SA, 10.87 A: the 13 A socket gives 13/10.87 = 1.196 < 1.2; the 16 A dedicated circuit
    # gives 16/10.87 = 1.472 ≥ 1.2 → dedicated 16 A
    v = power.circuit_class("SA", Q(10.87, "A"))
    assert v.status == "ok" and v.kind == "dedicated" and _mag(v.rating, "A") == 16
    assert v.headroom == pytest.approx(16 / 10.87)
    assert v.verify is True and v.source
    # 5 A fits the 13 A socket (plug wins over a larger dedicated circuit)
    assert power.circuit_class("sa", Q(5, "A")).kind == "plug"
    # unknown region: a verdict, not an exception
    z = power.circuit_class("ZZ", Q(10.9, "A"))
    assert z.status == "unknown_region" and z.label is None
    # too much current for anything on file
    assert power.circuit_class("SA", Q(40, "A")).status == "no_class"
    # voltage filter: US at 240 V only → the 30 A NEMA 6-30
    us = power.circuit_class("US", Q(10, "A"), voltage=Q(240, "V"))
    assert us.status == "ok" and _mag(us.rating, "A") == 30


def test_circuit_for_power_by_hand():
    # US, 2500 W: at 120 V I = 20.83 A needs ≥ 25 A (none at 120 V); at 240 V I = 10.42 A
    # → the 30 A dedicated circuit
    v = power.circuit_for_power("US", Q(2500, "W"))
    assert v.status == "ok" and _mag(v.voltage, "V") == 240 and _mag(v.rating, "A") == 30
    assert _mag(v.current, "A") == pytest.approx(2500 / 240)
    # EU: 2500 W / 230 V = 10.87 A → 16 A socket (plug before dedicated at the same rating)
    assert power.circuit_for_power("EU", Q(2500, "W")).kind == "plug"
    assert power.circuit_for_power("ZZ", Q(2500, "W")).status == "unknown_region"
    assert power.circuit_for_power("UK", Q(9000, "W")).status == "no_class"


# --- mass_cost -------------------------------------------------------------------------


def test_mass_by_hand():
    # 1 m³ of mild steel at 7850 kg/m³ = 7850 kg; 10 L of K23 at 480 kg/m³ = 4.8 kg
    assert _mag(mass_cost.mass(Q(1, "m**3"), "mild steel"), "kg") == pytest.approx(7850)
    assert _mag(mass_cost.mass(Q(10, "L"), "K23 insulating firebrick"), "kg") == pytest.approx(4.8)
    rho, src = mass_cost.density("unobtainium")
    assert _mag(rho, "kg/m**3") == 7850 and "assumed mild steel" in src


def test_cost_estimate_by_hand(monkeypatch):
    # cut-block (K-23, from per-part estimates): 18.8–40.1 USD/kg × 40 kg = 752–1604 USD
    c = mass_cost.cost_estimate("cut-block", mass=Q(40, "kg"))
    assert c.known and c.low < c.high
    assert _mag(c.low, "USD") == pytest.approx(752) and _mag(c.high, "USD") == pytest.approx(1604)
    assert "per-part estimates" in c.source and c.verify
    # per item: cots-controls 35–120 USD × 3 = 105–360 USD
    k = mass_cost.cost_estimate("cots-controls", count=3)
    assert (_mag(k.low, "USD"), _mag(k.high, "USD")) == pytest.approx((105, 360))
    u = mass_cost.cost_estimate("vacuum-forming", mass=Q(1, "kg"))
    assert not u.known and u.low is None
    with pytest.raises(ValueError, match="mass="):
        mass_cost.cost_estimate("cut-block")
    # per m² rows (none shipped yet): 10–20 USD/m² × 2 m² × 2 = 40–80 USD
    row = {
        "process_class": "paint",
        "unit": "per_m2",
        "low_usd": 10,
        "high_usd": 20,
        "source": "test",
        "verify": True,
    }
    monkeypatch.setattr(mass_cost, "load_table", lambda name: [row])
    p = mass_cost.cost_estimate("paint", area=Q(2, "m**2"), count=2)
    assert (_mag(p.low, "USD"), _mag(p.high, "USD")) == pytest.approx((40, 80))
    with pytest.raises(ValueError, match="area="):
        mass_cost.cost_estimate("paint")
    monkeypatch.setattr(mass_cost, "load_table", lambda name: [{**row, "unit": "per_hour"}])
    with pytest.raises(ValueError, match="unknown unit"):
        mass_cost.cost_estimate("paint", area=Q(1, "m**2"))


def test_lift_class_by_hand():
    # HSE guideline: ≤ 25 kg one person, ≤ 33 kg two people, heavier → equipment
    assert mass_cost.lift_class(Q(110, "kg")).label == "equipment"
    assert mass_cost.lift_class(Q(110, "kg")).max_mass is None
    assert mass_cost.lift_class(Q(25, "kg")).label == "one-person"
    assert mass_cost.lift_class(Q(30000, "g")).label == "two-person"


def test_lift_class_heavier_than_every_bounded_row(monkeypatch):
    rows = [{"label": "one-person", "max_kg": 25, "source": "s", "verify": True}]
    monkeypatch.setattr(mass_cost, "load_table", lambda name: rows)
    v = mass_cost.lift_class(Q(40, "kg"))
    assert v.label == "one-person" and _mag(v.max_mass, "kg") == 25


def test_stock_sheet_fits_by_hand():
    # 1770 × 1100 mm: 1100 > 1000 so not 1000 × 2000; 1100 ≤ 1220 and 1770 ≤ 2440 → 4 × 8 ft
    v = mass_cost.stock_sheet_fits((Q(1770, "mm"), Q(1100, "mm")))
    assert v.fits and v.sheet.startswith("1220 x 2440")
    assert "1000 x 2000 mm" not in v.fitting and "1250 x 2500 mm" in v.fitting
    # 1770 × 900 mm fits 1000 × 2000 (900 ≤ 1000, 1770 ≤ 2000), either way round
    assert mass_cost.stock_sheet_fits((Q(900, "mm"), Q(1.77, "m"))).sheet == "1000 x 2000 mm"
    # a 10 mm margin each side pushes 1990 × 990 to 2010 × 1010 → past 1000 × 2000
    m = mass_cost.stock_sheet_fits((Q(1990, "mm"), Q(990, "mm")), margin=Q(10, "mm"))
    assert m.sheet != "1000 x 2000 mm"
    assert not mass_cost.stock_sheet_fits((Q(3100, "mm"), Q(1600, "mm"))).fits
    unknown = mass_cost.stock_sheet_fits((Q(1, "m"), Q(1, "m")), "titanium")
    assert not unknown.known and not unknown.fits


# --- tables ----------------------------------------------------------------------------


def test_every_table_row_has_source_and_verify():
    names = table_names()
    assert set(names) >= {"circuits", "cost_bands", "lift_classes", "materials", "stock_sheets"}
    for name in names:
        rows = load_table(name)
        assert rows, name
        for row in rows:
            assert row["source"].strip(), (name, row)
            assert row["verify"] is True, (name, row)
    for row in load_table("cost_bands"):
        assert row["low_usd"] <= row["high_usd"], row


def test_load_table_errors(tmp_path, monkeypatch):
    with pytest.raises(TableError, match="no calc-kit table"):
        load_table("nope")
    monkeypatch.setattr(tables, "DATA_DIR", tmp_path)
    tables._load.cache_clear()
    try:
        (tmp_path / "bad.yaml").write_text("rows:\n  - {label: x, verify: true}\n")
        with pytest.raises(TableError, match="'source'"):
            load_table("bad")
        (tmp_path / "empty.yaml").write_text("rows: []\n")
        with pytest.raises(TableError, match="non-empty"):
            load_table("empty")
        (tmp_path / "flag.yaml").write_text("rows:\n  - {source: s, verify: maybe}\n")
        with pytest.raises(TableError, match="true or false"):
            load_table("flag")
        (tmp_path / "blank.yaml").write_text("rows:\n  - {source: '  ', verify: true}\n")
        with pytest.raises(TableError, match="empty 'source'"):
            load_table("blank")
        (tmp_path / "scalar.yaml").write_text("rows:\n  - 3\n")
        with pytest.raises(TableError, match="not a mapping"):
            load_table("scalar")
    finally:
        tables._load.cache_clear()


def test_load_table_returns_a_copy():
    rows = load_table("circuits")
    rows[0]["region"] = "XX"
    assert load_table("circuits")[0]["region"] != "XX"


# --- the kiln reproduces through the kit (NAPKIN_STAGE §7 drift guard) ------------------

#: run_calc values on examples/kiln recorded before thermal.py and element.py were routed
#: through the calc kit (2026-10-31).
KILN_BASELINE = {
    "thermal.heat_loss": (897.8213970645693, "W"),
    "thermal.shell_temperature": (78.82249988280137, "degC"),
    "thermal.guard_temperature": (44.06301738229678, "degC"),
    "thermal.interface_temperature": (669.8416436138237, "degC"),
    "thermal.door_skin_temperature": (69.68888798747344, "degC"),
    "thermal.door_guard_temperature": (41.89269820977222, "degC"),
    "thermal.max_touch_temperature": (44.06301738229678, "degC"),
    "thermal.stored_heat": (27466899.55404149, "J"),
    "thermal.required_power": (1987.7777285741522, "W"),
    "element.current": (10.869565217391305, "A"),
    "element.resistance": (21.16, "ohm"),
    "element.wire_area": (2.0106192982974678, "mm**2"),
    "element.wire_length": (29.341175415154773, "m"),
    "element.surface_load": (1.6950895460898474, "W/cm**2"),
    "element.power_margin": (1.2576858891528424, ""),
    "element.circuit_headroom": (1.472, ""),
    "element.coil_turns": (898.0371352785147, ""),
    "element.coil_pitch": (3.3406190926275987, "mm"),
    "element.pitch_factor": (2.087886932892249, ""),
}


@pytest.fixture(scope="module")
def kiln(tmp_path_factory):
    from napkin2factory.core.loader import load_product

    return load_product(
        copy_product(EXAMPLES / "kiln", tmp_path_factory.mktemp("k") / "kiln", git=False)
    )


def test_kiln_numbers_reproduce_through_calckit(kiln):
    from napkin2factory.core.checks.calcs import load_calc_module, run_calc

    for uri, (value, unit) in KILN_BASELINE.items():
        got = run_calc(kiln, f"calc://{uri}").value
        mag = float(got.to(unit).magnitude) if unit else float(got.to("").magnitude)
        assert mag == pytest.approx(value, rel=5e-7), uri  # six significant figures
    # and the kiln's calc modules really go through the kit
    assert load_calc_module(kiln, "thermal").kit is te
    assert load_calc_module(kiln, "element").kit is power


def test_kiln_body_directly_through_calckit(kiln):
    # the same body solve from the kiln's parameters, called on the kit directly
    from napkin2factory.geometry.accessors import make_accessors

    P = make_accessors(kiln)[0]
    inner = (P["chamber-width"], P["chamber-depth"], P["chamber-height"])
    layers = [
        Layer(P["brick-thickness"], P["brick-conductivity"], "brick"),
        Layer(P["fiber-thickness"], P["fiber-conductivity"], "fiber", P["lining-clearance"]),
        Layer(P["shell-thickness"], None, "shell", P["fiber-clearance"]),
    ]
    r = te.guarded_loss(
        inner,
        layers,
        P["guard-gap"],
        P["max-temperature"],
        P["ambient-temperature"],
        P["gap-air-temperature"],
        P["convection-coefficient"],
        P["shell-emissivity"],
        P["guard-emissivity"],
    )
    assert _mag(r.guard_temperature, "degC") == pytest.approx(44.0630173823, rel=5e-7)
    assert _mag(r.outer_skin_temperature, "degC") == pytest.approx(78.8224998828, rel=5e-7)
    assert _mag(r.interface_temperatures[0], "degC") == pytest.approx(669.841643614, rel=5e-7)
    # body loss = total 897.82 W less the door (the door is the kiln's own model)
    assert 800 < _mag(r.loss, "W") < 897.83


def test_one_row_per_material_for_screening_and_massing():
    """Review gate A, C4: screening's layer defaults and the massing densities agree."""
    from napkin2factory.core.packs import load_module

    # the layer defaults are the kiln's own screens' since v0.5 (F8, F10)
    heated = EXAMPLES / "kiln" / "model" / "screens" / "heated_enclosure.py"
    pack = load_module(heated, "screens")
    FIBER_BOARD, LAYER_MATERIALS = pack.FIBER_BOARD, pack.LAYER_MATERIALS  # noqa: N806
    from napkin2factory.geometry.materials import density_kg_m3

    rows = {r["name"]: r for r in load_table("materials")}
    fiber, brick = rows["ceramic fiber board (Kaowool 1260)"], rows["K-23 insulating firebrick"]
    assert (FIBER_BOARD.conductivity, FIBER_BOARD.density) == (0.15, 260.0)
    assert (fiber["conductivity"], fiber["density"]) == (0.15, 260)
    assert LAYER_MATERIALS[0].density == brick["density"] == 480
    assert density_kg_m3("ceramic fiber board")[0] == fiber["density"]
    assert density_kg_m3("fiber board")[0] == fiber["density"]
    assert density_kg_m3("K23 brick")[0] == brick["density"]
    assert density_kg_m3("mild steel")[0] == rows["mild steel"]["density"] == 7850
    # the kiln's own parameters carry the same values
    params = (EXAMPLES / "kiln" / "model" / "parameters.yaml").read_text()
    assert (
        "fiber-conductivity:  {value: 0.15" in params
        and "fiber-density:       {value: 260" in params
    )
