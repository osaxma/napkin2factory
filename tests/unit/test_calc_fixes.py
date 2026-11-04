"""Calc-pack fixes from the table benchmark (S-207): Johnson columns, room-temperature EMC,
composite creep, the creep factor's single home, and the cost band against a budget.

Each number is pinned to a cited source; the benchmark's independent hand calculation is
``examples/table/SPEC.md`` §4.1 (branch task/spec-table).
"""

from __future__ import annotations

import math

import pytest

from napkin2factory.calckit import _tables
from napkin2factory.calckit.joints import (
    composite_creep_deflection,
    equilibrium_moisture_content,
    factor_of_safety,
    timber_k_def,
    wood_creep_deflection,
    wood_movement,
)
from napkin2factory.calckit.structural import (
    column_buckling_load,
    euler_buckling_load,
    johnson_buckling_load,
)
from napkin2factory.concepts.screens.base import ScreenValues
from napkin2factory.concepts.screens.generic import cost_band
from napkin2factory.core.model import ConceptCard
from napkin2factory.core.units import Quantity as Q

# --- 1. short columns: Johnson, and the choice by slenderness -------------------------

#: The table benchmark's leg: 50 x 50 x 1.5 mm steel tube, K = 2.0, 720 mm.
LEG = {
    "E": Q(200, "GPa"),
    "I_min": Q(114193.25, "mm**4"),
    "area": Q(291, "mm**2"),
    "yield_strength": Q(250, "MPa"),
    "length": Q(720, "mm"),
    "k_factor": 2.0,
}


def test_johnson_table_leg_matches_the_hand_calculation() -> None:
    """Shigley §4-12: lambda 72.7, sigma_cr 208.17 MPa, P_cr 60 578 N, factor 38.3."""
    res = johnson_buckling_load(**LEG, load=Q(1582.55, "N"))
    assert res.method == "johnson"
    assert res.slenderness == pytest.approx(72.69, abs=0.01)
    assert res.critical_slenderness == pytest.approx(125.66, abs=0.01)
    assert res.critical_load.to("N").magnitude == pytest.approx(60578, rel=1e-3)
    assert res.safety_factor == pytest.approx(38.3, abs=0.05)


def test_column_buckling_load_picks_the_curve_and_says_which() -> None:
    """Short leg: Johnson. Slender column: Euler, equal to euler_buckling_load."""
    assert column_buckling_load(**LEG).method == "johnson"
    slender = {**LEG, "length": Q(5, "m"), "k_factor": 1.0, "I_min": Q(1e-7, "m**4"),
               "area": Q(1e-4, "m**2")}  # fmt: skip
    res = column_buckling_load(**slender, load=Q(1000, "N"))
    assert res.method == "euler"
    assert res.slenderness == pytest.approx(158.11, abs=0.01)
    same = euler_buckling_load(Q(200, "GPa"), Q(1e-7, "m**4"), Q(5, "m"), 1.0)
    assert res.critical_load.to("N").magnitude == pytest.approx(same.critical_load.magnitude)
    assert res.safety_factor == pytest.approx(res.critical_load.magnitude / 1000)


def test_johnson_meets_euler_at_the_transition() -> None:
    """Shigley §4-12: both curves give S_y / 2 times A at lambda_c (tangent join)."""
    r = math.sqrt(114193.25 / 291.0)
    lam_c = math.sqrt(2 * math.pi**2 * 200000 / 250)
    length = Q(lam_c * r, "mm")
    j = johnson_buckling_load(**{**LEG, "length": length, "k_factor": 1.0})
    e = euler_buckling_load(Q(200, "GPa"), Q(114193.25, "mm**4"), length, 1.0)
    assert j.critical_load.to("N").magnitude == pytest.approx(250 * 291 / 2, rel=1e-9)
    assert j.critical_load.magnitude == pytest.approx(e.critical_load.magnitude, rel=1e-9)


def test_johnson_refuses_a_slender_column_and_euler_still_refuses_a_short_one() -> None:
    """Each formula keeps to its own range; the Euler message points at the Johnson route."""
    with pytest.raises(ValueError, match="euler_buckling_load"):
        johnson_buckling_load(**{**LEG, "length": Q(5, "m"), "k_factor": 1.0})
    with pytest.raises(ValueError, match="column_buckling_load"):
        euler_buckling_load(
            LEG["E"], LEG["I_min"], LEG["length"], 2.0,
            area=LEG["area"], yield_strength=LEG["yield_strength"],
        )  # fmt: skip


# --- 2. moisture: Hailwood-Horrobin at room temperature -------------------------------


@pytest.mark.parametrize(
    ("rh", "table", "equation"), [(30, 6.2, 6.17), (50, 9.2, 9.24), (70, 13.1, 13.09)]
)
def test_emc_matches_the_wood_handbook_table(rh: float, table: float, equation: float) -> None:
    """FPL-GTR-190 Table 4-2 at 70 degF (rounded to 0.1) and Eq. 4-5 (the SPEC's values)."""
    got = equilibrium_moisture_content(rh, Q(70, "degF"))
    assert got == pytest.approx(table, abs=0.05)
    assert got == pytest.approx(equation, abs=0.01)


def test_emc_default_is_21_degC_and_temperature_matters() -> None:
    """The default is 21 degC; a warmer room holds a little less moisture at the same RH."""
    assert equilibrium_moisture_content(0.5) == equilibrium_moisture_content(50, Q(21, "degC"))
    assert equilibrium_moisture_content(50, Q(40, "degC")) < equilibrium_moisture_content(50)
    with pytest.raises(ValueError, match="relative humidity"):
        equilibrium_moisture_content(100)


def test_wood_movement_for_the_spec_case() -> None:
    """Oak, 280 mm from the fixed line, 30 to 70 % RH: SPEC §4.1 gives 7.05 mm (6.9 points)."""
    got = wood_movement(Q(280, "mm"), "white-oak", (30, 70)).to("mm").magnitude
    assert got == pytest.approx(7.05, rel=0.01)
    whole = wood_movement(Q(800, "mm"), "white-oak", (30, 70)).to("mm").magnitude
    assert whole == pytest.approx(20.15, rel=0.01)
    # a single swing is taken as centred on 50 % RH: 40 points of RH is 30 to 70 %
    assert wood_movement(Q(280, "mm"), "white-oak", 0.4) == wood_movement(
        Q(280, "mm"), "white-oak", (30, 70)
    )


# --- 3. creep of a composite member ----------------------------------------------------

EI_TOP = Q(12300 * 800 * 30**3 / 12, "N*mm**2")
EI_RAILS = Q(2 * 200000 * 114193.25, "N*mm**2")


def test_composite_creep_reproduces_the_spec_long_term_sag() -> None:
    """SPEC §4.1: elastic 0.6614 mm under the sustained load becomes 0.754 mm (EN 1995-1-1)."""
    elastic = Q(0.661399803753192, "mm")
    got = composite_creep_deflection(elastic, [(EI_TOP, True), (EI_RAILS, False)])
    assert got.to("mm").magnitude == pytest.approx(0.754, abs=0.001)
    # the old whole-sag multiplier overstates it: 0.661 * 1.6 = 1.06 mm
    assert wood_creep_deflection(elastic).to("mm").magnitude == pytest.approx(1.058, abs=0.001)


def test_composite_creep_limits() -> None:
    """All timber gives the (1 + k_def) multiplier; no timber gives no creep; short term none."""
    d = Q(1.0, "mm")
    assert composite_creep_deflection(d, [(EI_TOP, True)]).magnitude == pytest.approx(1.6)
    assert composite_creep_deflection(d, [(EI_RAILS, False)]).magnitude == pytest.approx(1.0)
    both = [(EI_TOP, True), (EI_RAILS, False)]
    assert composite_creep_deflection(d, both, "instantaneous").magnitude == pytest.approx(1.0)
    assert composite_creep_deflection(d, both, moisture="wet").magnitude > (
        composite_creep_deflection(d, both).magnitude
    )
    with pytest.raises(ValueError, match="at least one"):
        composite_creep_deflection(d, [])


# --- 4. one home for k_def --------------------------------------------------------------


def test_k_def_comes_from_the_timber_table_and_load_cases_carry_no_creep_row() -> None:
    """EN 1995-1-1 Table 3.2: 0.60 / 0.80 / 2.00; the load-case table has no creep multiplier."""
    assert [timber_k_def("sustained", m) for m in ("dry", "damp", "wet")] == [0.6, 0.8, 2.0]
    assert timber_k_def("short-term") == 0.0
    with pytest.raises(ValueError, match="unknown moisture"):
        timber_k_def("sustained", "underwater")
    rows = _tables.load_table("load_cases")
    assert not [r for r in rows if r["check"] == "deflection" and r["load_kind"] == "sustained"]
    assert not any("creep" in str(r["source"]).lower() for r in rows)
    with pytest.raises(KeyError):
        factor_of_safety("deflection", "sustained")


# --- 5. the cost band against a budget ---------------------------------------------------


def _budget_row(budget: str | None) -> tuple[ScreenValues, list]:  # type: ignore[type-arg]
    site = {} if budget is None else {"budget": budget}
    card = ConceptCard.model_validate({"id": "C-001", "title": "table", "site": site})
    object.__setattr__(card, "region", "US")
    values = ScreenValues()
    values.cost_items.append(("top", "woodworking", 28.8))  # US band 9 to 22 USD/kg
    return values, cost_band(card, None, values)


def test_budget_outcomes() -> None:
    """High end within budget passes; low end over it fails; in between warns (amber)."""
    values, rows = _budget_row("2000 USD")
    assert [(r.id, r.status) for r in rows] == [("cost-vs-budget", "pass")]
    assert "within the 2000 USD budget" in rows[0].message
    assert values.given.raw["budget"].to("USD").magnitude == 2000

    _, rows = _budget_row("100 USD")
    assert rows[0].status == "fail" and rows[0].severity == "fail"
    assert "low end" in rows[0].message

    _, rows = _budget_row("400 USD")
    assert rows[0].status == "warn" and rows[0].severity == "warn"
    assert "budget sits inside the cost band" in rows[0].message


def test_no_budget_no_row() -> None:
    """A card without site.budget gets the cost band and no budget row."""
    values, rows = _budget_row(None)
    assert rows == [] and "cost_high" in values.estimate.raw
