"""Hand-checked values for the kiln calcs (run with: uv run pytest examples/kiln/model/tests)."""

from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def P():  # noqa: N802
    from napkin2factory.core.loader import load_product
    from napkin2factory.geometry.accessors import make_accessors

    product = load_product(Path(__file__).resolve().parents[2])
    return make_accessors(product)[0]


def test_heat_flux_by_hand(P):  # noqa: N803
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "calcs"))
    import thermal

    # R = 0.064/0.25 + 0.125/0.12 + 1/10 = 0.256 + 1.0417 + 0.1 = 1.3977 m²K/W; ΔT = 1175 K
    r = 0.064 / 0.25 + 0.125 / 0.12 + 0.1
    assert thermal.heat_flux(P).magnitude == pytest.approx(1175 / r, rel=1e-3)
    # inner shell rise = q''/h ≈ 84 K → ~109 degC (hot: that is why there is a guard)
    assert thermal.skin_temperature(P).magnitude == pytest.approx(25 + 1175 / r / 10, rel=1e-3)
    # guard: radiation balance solved by hand to ~53 degC (see the docstring); below the 60 degC limit
    tg = thermal.guard_temperature(P).magnitude
    assert 45 < tg < 60, tg
    sigma, e_eff = 5.670374419e-8, 1 / (1 / 0.9 + 1 / 0.9 - 1)
    ts, ta, tk = 25 + 1175 / r / 10 + 273.15, 298.15, tg + 273.15
    assert sigma * e_eff * (ts**4 - tk**4) == pytest.approx(10 * (tk - ta) + sigma * 0.9 * (tk**4 - ta**4), rel=1e-4)


def test_element_by_hand(P):  # noqa: N803
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "calcs"))
    import element

    assert element.current(P).magnitude == pytest.approx(3000 / 230, rel=1e-6)
    assert element.resistance(P).magnitude == pytest.approx(230**2 / 3000, rel=1e-6)
    # L = R·A/ρ = 17.633 Ω × 2.0106 mm² / 1.45 Ω·mm²/m = 24.45 m
    assert element.wire_length(P).magnitude == pytest.approx(17.6333 * 2.0106 / 1.45, rel=1e-3)
