"""The benchmark oracle on small synthetic outputs shaped like n2f's own (S-209).

No command runs here: ``Evidence`` is handed ready-made JSON, so these tests pin the matchers,
the tolerances, the ambiguity errors and the exit codes. The same code against real products is
``tests/e2e/test_benchmarks.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from tests.benchmarks import oracle
from tests.benchmarks.oracle_evidence import Card, Evidence
from tests.benchmarks.oracle_match import (
    MatchError,
    categorize,
    judge,
    number_and_unit,
    parse_bound_message,
    pick_card,
    same_bound,
)
from tests.benchmarks.oracle_schema import CardSel, Expect, Oracle, load_oracle


def _val(text: str) -> dict[str, str]:
    return {"value": text, "label": "computed", "source": "", "ref": ""}


def _rule(rid: str, status: str, title: str = "", message: str = "") -> dict[str, str]:
    return {"id": rid, "title": title, "status": status, "message": message}


def _card(
    cid: str, status: str, materials: list[str], rules: list[dict[str, str]], **vals: Any
) -> Card:
    screening = {
        "given": {},
        "computed": {k: _val(v) for k, v in vals.get("computed", {}).items()},
        "estimates": {k: _val(v) for k, v in vals.get("estimates", {}).items()},
        "rules": rules,
        "verdict": "red" if any(r["status"] == "fail" for r in rules) else "green",
    }
    return Card(cid, status, cid, screening, materials, ["frame"] if cid == "x" else ["block"], 3)


def _cards() -> list[Card]:
    good = _card(
        "a",
        "promoted",
        ["white-oak", "mild steel"],
        [_rule("structural-deflection", "pass"), _rule("cost-vs-budget", "pass", "Within budget")],
        computed={"deflection": "1.58 mm", "tip_over_factor": "3.92", "mass": "45.3 kg"},
        estimates={"cost_low": "606 USD", "cost_high": "980 USD"},
    )
    weak = _card(
        "b",
        "rejected",
        ["southern-yellow-pine", "mild steel"],
        [_rule("structural-deflection", "fail", "Sag stays within the limit", "heavy mass sag")],
        computed={"deflection": "14.3 mm", "mass": "24.7 kg"},
    )
    heavy = _card(
        "c",
        "rejected",
        ["white-oak", "mild steel"],
        [
            _rule("weight-limit", "fail", "Weight stays under the limit", "148 kg is over 70 kg"),
            _rule(
                "cost-vs-budget", "fail", "Cost stays within budget", "2450 USD is over 1600 USD"
            ),
            _rule("structural-yield", "pass"),
        ],
        computed={"deflection": "0.837 mm", "mass": "148 kg"},
        estimates={"cost_low": "2450 USD", "cost_high": "3010 USD"},
    )
    return [good, weak, heavy]


def _req(rid: str, msg: str, safety: bool = False, category: str = "performance") -> dict[str, Any]:
    return {
        "id": f"req://{rid}",
        "kind": "requirement",
        "message": msg,
        "safety": safety,
        "status": "pass",
        "title": f"title of {rid}",
    }


def _check() -> dict[str, Any]:
    reqs = [
        _req("R1", "calc://s.sag = 1.58 mm <= 2.5 mm"),
        _req("R2", "calc://s.creep = 0.754 mm <= 2.5 mm"),
        _req("R3", "calc://s.tip = 3.92 >= 2"),
        _req("R4", "calc://s.buckle = 38.3 >= 2"),
        _req("R5", "EXAMPLE SIGN-OFF, NOT A REVIEW — calc://s.tip2 = 3.9 >= 2", safety=True),
        _req("R6", "mass = 45.3 kg < 70 kg"),
        _req("R7", "total_cost = 980 USD < 1600 USD (some parts have no declared cost)"),
    ]
    elec = {
        "id": "elec-rule://supply-load@supply",
        "kind": "electrical",
        "status": "pass",
        "message": "The Motor circuit draws 1.5 A of the supply's 15 A (given).",
        "detail": {"load_a": 1.5, "rule": "electrical-v0/supply-load"},
    }
    mods = [{"id": "frame", "title": "x"}, {"id": None, "title": "The whole product"}]
    return {
        "status": "ok",
        "ceremony": "lite",
        "results": [*reqs, elec],
        "matrix": {"modules": mods},
    }


def _ev(**over: Any) -> Evidence:
    base: dict[str, Any] = {
        "cards": _cards(),
        "check": _check(),
        "rollups": {
            "total_mass": 45.3,
            "total_mass_unit": "kg",
            "total_cost": 790.0,
            "total_cost_unit": "USD",
            "distinct_parts": 5,
        },
        "manifest": {"region": "US"},
        "supply": None,
        "status": {
            "gates": [
                {
                    "name": "verify",
                    "ok": False,
                    "blockers": ["REQ-5: needs a human sign-off (x)", "something else"],
                }
            ]
        },
    }
    return Evidence(**{**base, **over})


def _fig(find: dict[str, Any], **kw: Any) -> Any:
    from tests.benchmarks.oracle_schema import Figure

    return Figure.model_validate({"name": "n", "what": "w", "find": find, **kw})


def _fact(**kw: Any) -> Any:
    from tests.benchmarks.oracle_schema import Fact

    return Fact.model_validate({"name": "n", "what": "w", **kw})


# --- reading numbers ---------------------------------------------------------------------


def test_numbers_and_bounds_are_read_from_n2f_text():
    assert number_and_unit("14.3 mm") == (14.3, "mm")
    assert number_and_unit("3.92") == (3.92, "")
    with pytest.raises(MatchError):
        number_and_unit("the 230V-16A circuit")
    assert parse_bound_message("bbox.x = 995.4 mm <= 1000 mm") == (
        (995.4, "mm"),
        "<=",
        (1000.0, "mm"),
    )
    assert parse_bound_message("8 l >= 8 l")[1] == ">="
    last = parse_bound_message("EXAMPLE SIGN-OFF — calc://t.m = 44.063 degC < 60 degC")
    assert last == ((44.063, "degC"), "<", (60.0, "degC"))
    assert parse_bound_message("total_cost = 2196.6 USD < 2500 USD (some parts)")[2] == (
        2500.0,
        "USD",
    )
    with pytest.raises(MatchError):
        parse_bound_message("nothing to see")


_PASSES = " — passes by computation; safety requirements also need a human sign-off"

#: The messages ``n2f check --json`` gives a requirement (core/checks/evaluators.py,
#: ``evaluate_requirement``): plain, failing, signed (example), unsigned safety, unsigned with
#: a stale or unrecorded sign-off. The last two end in words after the bound (S-223).
_SHAPES = [
    ("total_mass = 45.2439 kg <= 70 kg", (45.2439, "kg"), "<=", (70.0, "kg")),
    ("total_mass = 80 kg <= 70 kg", (80.0, "kg"), "<=", (70.0, "kg")),
    ("bbox.x = 1600 mm == 1600 mm", (1600.0, "mm"), "==", (1600.0, "mm")),
    ("calc://s.tip = 3.92427 >= 2", (3.92427, ""), ">=", (2.0, "")),
    ("calc://s.tip = 1.5 >= 2", (1.5, ""), ">=", (2.0, "")),
    (
        "EXAMPLE SIGN-OFF, NOT A REVIEW — calc://s.tip = 3.92427 >= 2",
        (3.92427, ""),
        ">=",
        (2.0, ""),
    ),
    ("calc://s.tip = 3.92427 >= 2" + _PASSES, (3.92427, ""), ">=", (2.0, "")),
    ("calc://s.rise = 44.1 degC < 60 degC" + _PASSES, (44.1, "degC"), "<", (60.0, "degC")),
    (
        "calc://s.sag = 1.58 mm <= 2.5 mm" + _PASSES + " (no sign-off)",
        (1.58, "mm"),
        "<=",
        (2.5, "mm"),
    ),
    (
        "calc://s.tip = 3.92 >= 2" + _PASSES + " (evidence changed since signing: calc://s.tip)",
        (3.92, ""),
        ">=",
        (2.0, ""),
    ),
    ("calc://s.tip = 3.92 >= 2 passes by computation", (3.92, ""), ">=", (2.0, "")),
    ("calc://s.share = 12 % <= 15 %", (12.0, "%"), "<=", (15.0, "%")),
]


@pytest.mark.parametrize(("message", "value", "op", "bound"), _SHAPES)
def test_a_requirement_message_gives_its_value_and_bound_whatever_follows_the_bound(
    message, value, op, bound
):
    assert parse_bound_message(message) == (value, op, bound)


def test_an_unsigned_safety_requirement_is_found_by_its_bound():
    check = _check()
    check["results"][4] = _req("R5", "calc://s.tip2 = 3.9 >= 2" + _PASSES, safety=True)
    check["results"][4]["status"] = "needs-human"
    tip = _fig({"requirement": {"bound": "2", "safety": True}}, expect=3.9)
    row = oracle.judge_figure(tip, _ev(check=check), {})
    assert row.passed and row.found == "3.9"


def test_bounds_compare_by_dimension_not_spelling():
    assert same_bound((2.5, "mm"), (0.0025, "m"))
    assert not same_bound((2.5, "mm"), (2.5, "kg"))
    assert not same_bound((2.0, ""), (2.0, "mm"))


def test_a_failing_rule_is_placed_by_its_words_not_its_id():
    assert categorize(_rule("structural-yield", "fail", "all about mass")) == "structural"
    assert categorize(_rule("weight-limit", "fail", "Weight stays under the limit")) == "mass"
    assert categorize(_rule("cost-vs-budget", "fail")) == "cost"
    assert categorize(_rule("fits-site-width", "fail", "Fits the alcove")) == "envelope"
    assert categorize(_rule("zzz", "fail", "no word")) is None
    assert categorize(_rule("zzz", "fail", "no word"), {"mass": ["zzz"]}) == "mass"


# --- cards -------------------------------------------------------------------------------


def test_a_card_is_found_by_outcome_and_property_never_id():
    cards = _cards()
    assert pick_card(cards, CardSel(status="promoted")).id == "a"
    assert pick_card(cards, CardSel(status="rejected", by=["structural"])).id == "b"
    assert pick_card(cards, CardSel(status="rejected", by=["mass", "cost"])).id == "c"
    assert pick_card(cards, CardSel(status="rejected", material="yellow pine")).id == "b"
    with pytest.raises(MatchError, match="2 cards"):
        pick_card(cards, CardSel(status="rejected"))
    with pytest.raises(MatchError, match="no card is"):
        pick_card(cards, CardSel(status="promoted", by=["cost"]))


def test_concepts_pass_when_each_rejection_has_its_reason():
    c = Oracle.model_validate(
        {
            "concepts": {
                "count": 3,
                "promoted": {"material": "white-oak"},
                "rejected": [{"by": ["structural"], "not_by": ["mass"]}, {"by": ["mass", "cost"]}],
            }
        }
    )
    rows = oracle.evaluate(c, _ev())
    assert all(r.passed for r in rows), [r for r in rows if not r.passed]


def test_concepts_fail_when_the_reason_differs_or_two_are_promoted():
    wrong = Oracle.model_validate({"concepts": {"rejected": [{"by": ["cost"]}, {"by": ["mass"]}]}})
    rows = oracle.evaluate(wrong, _ev())
    assert any(not r.passed and "every other card" in r.what for r in rows)
    cards = _cards()
    cards[1].status = "promoted"
    rows = oracle.evaluate(Oracle.model_validate({"concepts": {}}), _ev(cards=cards))
    assert any(not r.passed and "exactly one" in r.what for r in rows)


def test_a_promoted_card_with_a_failing_check_fails():
    cards = _cards()
    cards[0].screening["rules"].append(_rule("structural-yield", "fail", "Stress"))  # type: ignore[index]
    rows = oracle.evaluate(Oracle.model_validate({"concepts": {}}), _ev(cards=cards))
    assert any(not r.passed and "passes every screening check" in r.what for r in rows)


def test_no_concept_cards_is_a_fail_not_a_crash():
    rows = oracle.evaluate(Oracle.model_validate({"concepts": {}}), _ev(cards=[]))
    assert any(not r.passed for r in rows)


# --- figures -----------------------------------------------------------------------------


def test_screen_value_within_tolerance_and_with_unit_conversion():
    fig = _fig({"screen_value": "deflection"}, card="promoted", unit="mm", expect=1.58, tol=0.05)
    assert oracle.judge_figure(fig, _ev(), {}).passed
    fig = _fig({"screen_value": "deflection"}, card="promoted", unit="m", expect=0.00158)
    assert oracle.judge_figure(fig, _ev(), {}).passed
    off = _fig({"screen_value": "deflection"}, card="promoted", unit="mm", expect=1.9, tol=0.05)
    row = oracle.judge_figure(off, _ev(), {})
    assert not row.passed and "1.58" in row.found


def test_screen_value_missing_or_wrong_dimension_is_a_clear_fail():
    fig = _fig({"screen_value": "nothing_here"}, card="promoted", expect=1.0)
    row = oracle.judge_figure(fig, _ev(), {})
    assert not row.passed and "has no value named nothing_here" in row.found
    fig = _fig({"screen_value": "deflection"}, card="promoted", unit="kg", expect=1.0)
    assert "cannot read" in oracle.judge_figure(fig, _ev(), {}).found


def test_screen_value_names_may_fall_back():
    fig = _fig(
        {"screen_value": ["total_mass", "mass"]},
        card={"status": "rejected", "by": ["mass"]},
        unit="kg",
        expect=148,
        tol=0.02,
    )
    assert oracle.judge_figure(fig, _ev(), {}).passed


def test_requirement_found_by_its_bound_and_chosen_by_value_when_several_share_it():
    sag = _fig({"requirement": {"bound": "2.5 mm", "op": "<="}}, unit="mm", expect=1.58)
    assert oracle.judge_figure(sag, _ev(), {}).passed
    creep = _fig({"requirement": {"bound": "2.5 mm"}}, unit="mm", expect=0.754)
    row = oracle.judge_figure(creep, _ev(), {})
    assert row.passed and "of 1.58, 0.754" in row.found
    buckle = _fig({"requirement": {"bound": "2"}}, expect=38.3)
    assert oracle.judge_figure(buckle, _ev(), {}).passed
    tip = _fig({"requirement": {"bound": "2", "safety": True}}, expect=3.9)
    assert oracle.judge_figure(tip, _ev(), {}).passed
    miss = _fig({"requirement": {"bound": "2.5 mm"}}, unit="mm", expect=9.0)
    row = oracle.judge_figure(miss, _ev(), {})
    assert not row.passed and "none of" in row.found
    none = _fig({"requirement": {"bound": "99 mm"}}, expect=1.0)
    assert "no requirement is bounded at 99 mm" in oracle.judge_figure(none, _ev(), {}).found


def test_two_different_candidates_in_tolerance_are_ambiguous():
    check = _check()
    check["results"].append(_req("R8", "calc://s.other = 1.6 mm <= 2.5 mm"))
    check["results"].append(_req("R9", "calc://s.more = 1.58 mm <= 2.5 mm"))
    wide = _fig({"requirement": {"bound": "2.5 mm"}}, unit="mm", expect=1.2, tol=0.5)
    # 1.58 and 0.754 are both within 50 % of 1.2 but differ from each other by more than 50 %
    row = oracle.judge_figure(wide, _ev(check=check), {})
    assert not row.passed and "differing" in row.found


def _titled(rid: str, title: str, msg: str, safety: bool = False) -> dict[str, Any]:
    return {**_req(rid, msg, safety=safety), "title": title}


def test_words_tell_two_requirements_with_the_same_bound_apart():
    """S-230: a footprint width and a guard height both bounded at 400 mm."""
    check = _check()
    check["results"] = [
        _titled("W", "Footprint width", "bbox.x = 380 mm <= 400 mm"),
        _titled("H", "The guard fits its height", "bbox.z = 400 mm <= 400 mm"),
    ]
    plain = _fig({"requirement": {"bound": "400 mm"}}, unit="mm", at_most=400)
    row = oracle.judge_figure(plain, _ev(check=check), {})
    assert not row.passed and "differing" in row.found
    horizontal = _fig(
        {"requirement": {"bound": "400 mm", "words": r"bbox\.[xy]\b"}}, unit="mm", expect=380
    )
    assert oracle.judge_figure(horizontal, _ev(check=check), {}).passed
    not_height = _fig(
        {"requirement": {"bound": "400 mm", "not_words": "height|bbox.z"}}, unit="mm", expect=380
    )
    assert oracle.judge_figure(not_height, _ev(check=check), {}).passed
    none = _fig({"requirement": {"bound": "400 mm", "words": "depth"}}, unit="mm", at_most=400)
    assert "with the words 'depth'" in oracle.judge_figure(none, _ev(check=check), {}).found


def test_the_governing_factor_is_the_same_whether_one_requirement_or_two_carry_it():
    """S-230: beam 9.1 and bolt 7.4 apart, or one fatigue requirement showing 7.4."""
    apart = _check()
    apart["results"] = [
        _titled("A", "Beam fatigue factor", "calc://f.beam = 9.106 >= 1.5", safety=True),
        _titled("B", "Bolt fatigue factor", "calc://f.bolt = 7.42 >= 1.5", safety=True),
        _titled("C", "Tip-over factor", "calc://t.tip = 2.124 >= 1.5", safety=True),
    ]
    one = _check()
    one["results"] = [
        _titled("A", "Fatigue factor", "calc://f.both = 7.42 >= 1.5", safety=True),
        _titled("C", "Tip-over factor", "calc://t.tip = 2.124 >= 1.5", safety=True),
    ]
    find = {"bound": "1.5", "safety": True, "words": "fatigue", "aggregate": "min"}
    fig = _fig({"requirement": find}, expect=7.42, tol=0.05)
    for check in (apart, one):
        assert oracle.judge_figure(fig, _ev(check=check), {}).passed
    wrong = _fig({"requirement": {**find, "aggregate": "max"}}, expect=7.42, tol=0.05)
    assert not oracle.judge_figure(wrong, _ev(check=apart), {}).passed
    assert oracle.judge_figure(wrong, _ev(check=one), {}).passed


def test_a_list_of_values_and_a_range_accept_either_modelling():
    """S-230: the mass with or without a part for the wiring; a count with an allowance part."""
    mass = _fig({"rollup": "total_mass"}, unit="kg", expect=[45.3, 44.7], tol=0.02)
    assert oracle.judge_figure(mass, _ev(), {}).passed
    for got in (5, 6):
        count = _fig({"rollup": "distinct_parts"}, range=[5, 6])
        ev = _ev(rollups={"distinct_parts": got})
        assert oracle.judge_figure(count, ev, {}).passed
    assert not oracle.judge_figure(count, _ev(rollups={"distinct_parts": 7}), {}).passed


def test_several_candidates_for_a_single_surface_are_ambiguous():
    found = judge.__globals__["Found"]([1.0, 2.0], "somewhere")
    with pytest.raises(MatchError, match="2 candidates"):
        judge(found, Expect(expect=1.0), 0.05)


def test_rollup_and_result_figures():
    mass = _fig({"rollup": "total_mass"}, unit="kg", expect=45.3, tol=0.02)
    assert oracle.judge_figure(mass, _ev(), {}).passed
    parts = _fig({"rollup": "distinct_parts"}, expect=5, tol=0)
    assert oracle.judge_figure(parts, _ev(), {}).passed
    bad = _fig({"rollup": "nope"}, expect=1)
    assert "has no number nope" in oracle.judge_figure(bad, _ev(), {}).found
    cur = _fig(
        {"result": {"kind": "electrical", "rule": "supply-load", "path": "detail.load_a"}},
        unit="A",
        expect=1.5,
    )
    assert oracle.judge_figure(cur, _ev(), {}).passed
    rx = _fig(
        {"result": {"kind": "electrical", "regex": r"draws (?P<value>[\d.]+) (?P<unit>A)\b"}},
        unit="A",
        expect=1.5,
    )
    assert oracle.judge_figure(rx, _ev(), {}).passed
    none = _fig({"result": {"kind": "bom", "path": "x"}}, expect=1)
    assert "printed no bom result" in oracle.judge_figure(none, _ev(), {}).found


def test_screen_row_number_is_captured_from_the_message():
    cards = _cards()
    cards[0].screening["rules"][0]["message"] = "the top sags 1.58 mm (computed), within"  # type: ignore[index]
    find = {
        "screen_row": {
            "rule": "structural-deflection",
            "regex": r"sags (?P<value>[\d.]+) (?P<unit>mm)",
        }
    }
    fig = _fig(find, card="promoted", unit="mm", expect=1.58)
    assert oracle.judge_figure(fig, _ev(cards=cards), {}).passed


def test_range_and_bounds_judge_without_a_centre():
    fig = _fig({"rollup": "total_cost"}, range=[606, 980])
    assert oracle.judge_figure(fig, _ev(), {}).passed
    high = _fig({"rollup": "total_cost"}, at_most=500)
    assert not oracle.judge_figure(high, _ev(), {}).passed


# --- facts -------------------------------------------------------------------------------


def test_word_facts():
    assert oracle.judge_fact(_fact(fact="ceremony", equals="lite"), _ev()).passed
    assert not oracle.judge_fact(_fact(fact="ceremony", equals="standard"), _ev()).passed
    assert oracle.judge_fact(_fact(fact="region", equals="US"), _ev()).passed
    assert oracle.judge_fact(_fact(fact="supply", equals="none"), _ev()).passed
    old = _ev(check={"results": [], "matrix": {}})
    assert "no ceremony" in oracle.judge_fact(_fact(fact="ceremony", equals="lite"), old).found


def test_supply_values_resolve_a_parameter_reference():
    ev = _ev(
        supply={"voltage": "param://mains", "frequency": "60 Hz"},
        parameters={"mains": {"value": 120, "unit": "V"}},
    )
    assert oracle.judge_fact(_fact(fact="supply_voltage", unit="V", expect=120, tol=0), ev).passed
    assert oracle.judge_fact(_fact(fact="supply_frequency", unit="Hz", expect=60), ev).passed
    assert oracle.judge_fact(_fact(fact="supply", equals="present"), ev).passed


def test_count_facts_assemblies_and_gate_blockers():
    safety = _fact(fact="count_requirements", safety=True, expect=1)
    assert oracle.judge_fact(safety, _ev()).passed
    nofail = _fact(fact="count_requirements", status="fail", expect=0)
    assert oracle.judge_fact(nofail, _ev()).passed
    assert oracle.judge_fact(_fact(fact="assemblies", expect=1), _ev()).passed
    sign = _fact(fact="gate_blockers", gate="verify", matching="needs a human sign-off", expect=1)
    assert oracle.judge_fact(sign, _ev()).passed
    other = _fact(fact="gate_blockers", gate="verify", matching="sign-off", invert=True, expect=1)
    assert oracle.judge_fact(other, _ev()).passed
    nogate = _fact(fact="gate_blockers", gate="nope", expect=0)
    assert "no gate named nope" in oracle.judge_fact(nogate, _ev()).found


# --- the format and the command ----------------------------------------------------------


def test_the_format_refuses_what_it_does_not_know():
    with pytest.raises(ValidationError):
        Oracle.model_validate({"figurez": []})
    with pytest.raises(ValidationError, match="needs a card"):
        _fig({"screen_value": "x"}, expect=1)
    with pytest.raises(ValidationError, match="any other figure has none"):
        _fig({"rollup": "x"}, card="promoted", expect=1)
    with pytest.raises(ValidationError, match="say what to expect"):
        _fig({"rollup": "x"})
    with pytest.raises(ValidationError, match="exactly one surface"):
        _fig({"rollup": "x", "screen_value": "y"}, card="promoted", expect=1)
    with pytest.raises(ValidationError, match="needs equals"):
        _fact(fact="ceremony")


def _write(tmp_path: Path, doc: dict[str, Any]) -> tuple[Path, Path]:
    prod = tmp_path / "product"
    prod.mkdir()
    (prod / "n2f.yaml").write_text("schema: 1\n", encoding="utf-8")
    spec = tmp_path / "SPEC.oracle.yaml"
    spec.write_text(yaml.safe_dump(doc), encoding="utf-8")
    return prod, spec


def test_exit_codes_and_json(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(oracle, "Evidence", lambda product, build=True: _ev())
    good = {
        "title": "t",
        "facts": [{"name": "c", "what": "the ceremony", "fact": "ceremony", "equals": "lite"}],
        "pending": [{"what": "movement", "reason": "no form yet"}],
    }
    prod, spec = _write(tmp_path, good)
    assert oracle.main([str(prod), str(spec)]) == 0
    assert "1 passed, 0 failed, 1 pending" in capsys.readouterr().out
    assert oracle.main([str(prod), str(spec), "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert (
        doc["failed"] == 0 and doc["rows"][0]["passed"] and doc["pending"][0]["what"] == "movement"
    )
    good["facts"][0]["equals"] = "standard"
    spec.write_text(yaml.safe_dump(good), encoding="utf-8")
    assert oracle.main([str(prod), str(spec)]) == 1
    assert "FAIL" in capsys.readouterr().out


def test_unreadable_oracle_or_product_exit_2(tmp_path, capsys):
    prod, spec = _write(tmp_path, {"figurez": 1})
    assert oracle.main([str(prod), str(spec)]) == 2
    assert oracle.main([str(prod), str(tmp_path / "missing.yaml")]) == 2
    spec.write_text("title: t\n", encoding="utf-8")
    assert oracle.main([str(tmp_path), str(spec)]) == 2
    assert "not a product folder" in capsys.readouterr().err


def test_evidence_runs_a_command_once_and_only_when_asked():
    calls: list[tuple[str, ...]] = []

    def runner(product: Path, *args: str) -> str:
        calls.append(args)
        return json.dumps({"ceremony": "lite", "results": [], "matrix": {}})

    ev = Evidence(Path("/nowhere"), runner=runner, build=True)
    assert calls == []
    ev.check()
    ev.check()
    assert calls == [("build",), ("check", "--json")]
    assert [c for c in calls if c[0] == "concept"] == []


def test_the_real_table_oracle_is_a_valid_oracle():
    path = Path(__file__).resolve().parents[2] / "examples" / "table" / "SPEC.oracle.yaml"
    o = load_oracle(path)
    assert o.concepts is not None and len(o.concepts.rejected) == 2 and o.pending
