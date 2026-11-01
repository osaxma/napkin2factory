"""Calcs prove themselves (F17, DoD 12): reference cases for every calc-kit function and every
kiln calc, one external case per pack, ``calc-case`` rows in ``n2f check``, the lint.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from napkin2factory.calckit import _cases, mass_cost, power, thermal_enclosure
from napkin2factory.calckit._cases import Case, compare, pick, run_case
from napkin2factory.core.checks import calcs as calc_checks
from napkin2factory.core.lint import lint
from napkin2factory.core.loader import load_product
from napkin2factory.core.units import Quantity as Q
from tests.conftest import EXAMPLES

PACKS = (thermal_enclosure, power, mass_cost)
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "calcs"


@pytest.mark.parametrize("pack", PACKS, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_every_kit_function_has_a_case_and_every_case_passes(pack) -> None:
    assert _cases.public_functions(pack), pack.__name__
    assert _cases.uncovered(pack) == []
    for case, outcome in _cases.run_pack(pack):
        assert outcome.ok, (case.fn, outcome)
        assert case.source.strip(), case.fn


@pytest.mark.parametrize("pack", PACKS, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_every_pack_has_an_external_case_with_its_source(pack) -> None:
    external = [c for c in _cases.pack_cases(pack) if c.external]
    assert external, pack.__name__
    for c in external:
        assert not c.source.lower().startswith("hand computation"), c.source
        assert len(c.source) > 40, c.source  # a precise citation, not a word


def test_case_counts() -> None:
    """The numbers the decision entry lists (S-125)."""
    counts = {m.__name__.rsplit(".", 1)[-1]: len(_cases.pack_cases(m)) for m in PACKS}
    external = {
        m.__name__.rsplit(".", 1)[-1]: sum(c.external for c in _cases.pack_cases(m)) for m in PACKS
    }
    assert counts == {"thermal_enclosure": 11, "power": 10, "mass_cost": 5}
    assert external == {"thermal_enclosure": 1, "power": 2, "mass_cost": 1}


def test_a_formula_change_is_caught() -> None:
    """Mutating a kit formula makes its external case miss (the point of F17)."""
    wrong = Case("f", Q(90.9, "A"), "s", args=(Q(20, "kW"), Q(220, "V")), abs=0.05)
    assert run_case(lambda p, v: (p / v).to("A"), wrong).ok
    out = run_case(lambda p, v: (p / v / 1.04).to("A"), wrong)
    assert not out.ok and out.expected == "90.9 A ± 0.05 A" and out.actual == "87.4126 A"


def test_compare_semantics() -> None:
    assert compare(Q(1.0005, "m"), Q(1, "m"), rel=1e-3).ok
    assert not compare(Q(1.002, "m"), Q(1, "m"), rel=1e-3).ok
    assert compare(Q(1000.4, "mm"), Q(1, "m"), abs_tol=0.001).ok  # abs in the expected unit
    assert compare(Q(50.05, "degC"), Q(50, "degC"), abs_tol=0.1).ok
    assert compare(Q(323.2, "K"), Q(50, "degC"), abs_tol=0.1).ok
    assert not compare(Q(1, "kg"), Q(1, "m")).ok  # a different kind of unit never passes
    assert compare(Q(1.26, ""), 1.26).ok  # a dimensionless result against a plain number
    assert compare(2.0, 2.0).ok and not compare(2.0, 2.1).ok
    assert compare("two-person", "two-person").ok and not compare("a", "b").ok
    assert not compare(float("nan"), 1.0).ok
    assert not compare("x", Q(1, "m")).ok
    assert compare(Q(1, "m"), Q(1, "m")).expected == "1 m ± 0.0001 %"  # default rel 1e-6


def test_pick_and_raising_case() -> None:
    assert pick({"a": [1, (2, 3)]}, "a.1.0") == 2
    out = run_case(lambda: 1 / 0, Case("f", 1.0, "s"))
    assert not out.ok and "ZeroDivisionError" in out.message


def test_run_pack_names_an_unknown_function(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(power, "CASES", [Case("no_such_fn", 1.0, "s")])
    ((_, outcome),) = _cases.run_pack(power)
    assert not outcome.ok and "no function no_such_fn" in outcome.message


# --- product calcs: the kiln and the fixture ------------------------------------------------


@pytest.fixture(scope="module")
def kiln():
    return load_product(EXAMPLES / "kiln")


def test_every_kiln_calc_has_a_case_and_every_row_passes(kiln) -> None:
    assert calc_checks.calcs_without_cases(kiln) == []
    rows = calc_checks.calc_case_rows(kiln)
    calcs = sum(len(f) for f in kiln.calcs.values())
    assert calcs == 21
    assert [r.status for r in rows] == ["pass"] * (calcs + 2), [
        (r.id, r.message) for r in rows if r.status != "pass"
    ]
    assert {r.kind for r in rows} == {"calc-case"}
    # the kiln's calcs use two calc-kit packs; their rows name the published sources
    kit = {r.id: r for r in rows if r.id.startswith("calc-case://calckit.")}
    assert sorted(kit) == ["calc-case://calckit.power", "calc-case://calckit.thermal_enclosure"]
    assert "Kanthal" in kit["calc-case://calckit.power"].message
    assert "Incropera" in kit["calc-case://calckit.thermal_enclosure"].message
    assert not [p for p in lint(kiln).items if p.rule == "L16-calc-case"]
    cases = calc_checks.product_cases(kiln)
    assert sum(len(v) for v in cases.values()) == 21


@pytest.fixture
def fixture_product(tmp_path: Path):
    root = tmp_path / "calcs"
    shutil.copytree(FIXTURE, root)
    return root


def _rows(root: Path) -> dict[str, object]:
    return {r.id: r for r in calc_checks.calc_case_rows(load_product(root))}


def test_wrong_case_fails_naming_calc_expected_and_actual(fixture_product: Path) -> None:
    rows = _rows(fixture_product)
    assert rows["calc-case://plate.area"].status == "pass"
    bad = rows["calc-case://plate.perimeter"]
    assert bad.status == "fail"
    assert bad.message.startswith("plate.perimeter: case 1 of 1 expected 650 mm ± 1 mm")
    assert "computed 600 mm" in bad.message
    assert "expected 650 mm" in bad.persona_message and "computed 600 mm" in bad.persona_message
    assert bad.detail["cases"][0]["actual"] == "600 mm"
    none = rows["calc-case://plate.volume"]
    assert none.status == "warn" and none.persona_message == calc_checks.NO_CASE


def test_calc_without_case_is_a_lint_warning(fixture_product: Path) -> None:
    (finding,) = [p for p in lint(load_product(fixture_product)).items if p.rule == "L16-calc-case"]
    assert finding.severity == "warn" and finding.subject == "calc://plate.volume"
    assert "plate.cases.yaml" in finding.hint and "source:" in finding.hint


def test_case_must_give_every_input(fixture_product: Path) -> None:
    path = fixture_product / "model/calcs/plate.cases.yaml"
    path.write_text(path.read_text().replace("  plate-height: 100 mm\n", ""))
    row = _rows(fixture_product)["calc-case://plate.area"]
    assert row.status == "fail" and "does not give 'plate-height'" in row.message


def test_malformed_cases_fail_with_the_reason(fixture_product: Path) -> None:
    path = fixture_product / "model/calcs/plate.cases.yaml"
    text = path.read_text()
    path.write_text(text.replace('      source: "hand computation: 200 mm × 100 mm"\n', ""))
    assert "has no source" in _rows(fixture_product)["calc-case://plate.area"].message
    path.write_text(text.replace("expect: 20000 mm**2", "expect: 20000 furlongz"))
    assert _rows(fixture_product)["calc-case://plate.area"].status == "fail"
    path.write_text(text + "  nosuch:\n    - {expect: 1 mm, source: s}\n")
    row = _rows(fixture_product)["calc-case://plate.nosuch"]
    assert row.status == "fail" and "not a calc" in row.message
    path.write_text("cases: [\n")
    assert _rows(fixture_product)["calc-case://plate.*"].status == "fail"


def test_cases_in_the_module(fixture_product: Path) -> None:
    """A module-level CASES of the same shape works when there is no .cases.yaml."""
    calcs = fixture_product / "model/calcs"
    (calcs / "plate.cases.yaml").unlink()
    src = (calcs / "plate.py").read_text()
    (calcs / "plate.py").write_text(
        src + "\n\nCASES = {'inputs': {'plate-width': '2 m', 'plate-height': '1 m',"
        " 'plate-thickness': '1 mm'}, 'cases': {'volume': [{'expect': '2 L',"
        " 'source': 'hand computation: 2 m × 1 m × 1 mm'}]}}\n"
    )
    rows = _rows(fixture_product)
    assert rows["calc-case://plate.volume"].status == "pass"
    assert rows["calc-case://plate.area"].status == "warn"


def test_no_calcs_no_rows() -> None:
    assert calc_checks.calc_case_rows(load_product(EXAMPLES / "bracket")) == []
