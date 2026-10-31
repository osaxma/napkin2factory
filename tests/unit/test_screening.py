"""M2 (v0.2): concept screening — labelled numbers, the concept-v0 rules, the verdict (N5).

The first test is the DEC-011 regression, the release's reason to exist: the v0.1 kiln,
995 mm wide with its controller box, screens red on an 800 mm alcove once the open door is
counted beside the hinge — in minute five rather than hour forty.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from napkin2factory.concepts.massing import compose
from napkin2factory.concepts.screening import (
    screen,
    write_screening_json,
    write_screening_to_card,
)
from napkin2factory.core import concepts as cm
from napkin2factory.core.model import ConceptCard, RuleRow, Screening
from napkin2factory.core.units import parse_quantity
from napkin2factory.rulepacks.concept_checks import (
    concept_packs,
    parse_circuit,
    rule_params,
    run_concept_rules,
)

KILN: dict[str, Any] = {
    "id": "C-001",
    "title": "The v0.1 kiln as built",
    "layout": {"load": "front", "door": "hinged-left", "controls": "side-right"},
    "envelope": {
        "chamber": ["200 mm", "200 mm", "200 mm"],
        # the kiln's layers and fit clearances (examples/kiln/model/parameters.yaml)
        "insulation": [
            {"name": "brick", "thickness": "64 mm", "conductivity": "0.25 W/(m*K)"},
            {
                "name": "fiber",
                "thickness": "125 mm",
                "conductivity": "0.15 W/(m*K)",
                "clearance": "3 mm",
            },
            {"name": "shell", "thickness": "1.2 mm", "clearance": "2 mm"},
        ],
        "power": "2.5 kW",
        "max_temperature": "1200 degC",
    },
    "site": {"alcove_width": "800 mm", "circuit": "240V-13A", "region": "SA"},
    "massing": [
        # guard-sized body; with the controller box beside it the kiln is 995 mm wide
        {
            "kit": "enclosure",
            "as": "body",
            "material": "mild steel",
            "args": {
                "length": "695 mm",
                "width": "650 mm",
                "height": "642 mm",
                "thickness": "2.5 mm",
            },
            "at": {"z": "700 mm"},
        },
        {
            "kit": "block",
            "as": "controls",
            "material": "abs",
            "process_class": "cots-controls",
            "args": {"length": "260 mm", "width": "120 mm", "height": "160 mm"},
            "at": {"x": "517.5 mm", "z": "1100 mm"},
        },
        {
            "kit": "block",
            "as": "door",
            "material": "mild steel",
            "process_class": "sheet-metal",
            "args": {"length": "250 mm", "width": "3 mm", "height": "600 mm"},
            "at": {"y": "-330 mm", "z": "720 mm"},
        },
        {
            "kit": "frame",
            "as": "stand",
            "material": "mild steel",
            "args": {
                "length": "600 mm",
                "width": "600 mm",
                "height": "700 mm",
                "member": {"size": "25 mm", "wall": "1.5 mm"},
            },
        },
    ],
}

SMALL: dict[str, Any] = {
    "id": "C-002",
    "title": "Compact",
    "layout": {"load": "front", "door": "hinged-right", "controls": "front-below"},
    "envelope": {"chamber": ["150 mm", "150 mm", "150 mm"], "insulation": "100 mm"},
    "site": {"alcove_width": "800 mm", "region": "EU"},
    "massing": [
        {
            "kit": "enclosure",
            "as": "body",
            "material": "mild steel",
            "args": {
                "length": "400 mm",
                "width": "400 mm",
                "height": "400 mm",
                "thickness": "1.5 mm",
            },
        },
        {
            "kit": "block",
            "as": "door",
            "material": "mild steel",
            "args": {"length": "300 mm", "width": "3 mm", "height": "300 mm"},
            "at": {"y": "-201.5 mm", "z": "50 mm"},
        },
    ],
}


def _card(base: dict[str, Any], **changes: Any) -> ConceptCard:
    data = copy.deepcopy(base)
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(data.get(key), dict):
            data[key] = {**data[key], **value}
        else:
            data[key] = value
    return ConceptCard.model_validate(data)


def _without(base: dict[str, Any], section: str, key: str, **changes: Any) -> ConceptCard:
    data = copy.deepcopy(base)
    del data[section][key]
    for k, v in changes.items():
        data[k] = {**data[k], **v}
    return ConceptCard.model_validate(data)


def _screen(card: ConceptCard) -> Screening:
    return screen(card, compose(card, write=False))


def _rule(s: Screening, rid: str) -> RuleRow:
    return next(r for r in s.rules if r.id == rid)


def _q(s: Screening, section: str, name: str, unit: str) -> float:
    values = s.computed if section == "computed" else s.estimates
    return float(parse_quantity(values[name].value).to(unit).magnitude)


@pytest.fixture(scope="module")
def kiln() -> Screening:
    return _screen(_card(KILN))


# --- DEC-011: the regression --------------------------------------------------------


def test_kiln_like_card_screens_red_on_the_alcove_with_door_swing(kiln: Screening) -> None:
    assert kiln.verdict == "red"
    width = _rule(kiln, "fits-site-width")
    assert width.status == "fail" and width.relies_on == ["computed"]
    # the message names the door-swing term, not just the body width
    assert "995 mm for the body plus 250 mm for the open door" in width.message
    assert "hinged-left" in width.message and "alcove is 800 mm" in width.message
    assert _q(kiln, "computed", "width", "mm") == pytest.approx(995)
    assert _q(kiln, "computed", "footprint_with_door_swing", "mm") == pytest.approx(1245)

    # the estimate strip: order-of-magnitude bands, not exact values
    lo, hi = _q(kiln, "e", "cost_low", "USD"), _q(kiln, "e", "cost_high", "USD")
    assert lo <= 2500 and hi >= 2000, "the cost band brackets DEC-012's ≈ 2200 USD"
    assert 220 < lo < hi < 22000
    # 2.5 kW against ~0.8 kW of loss and ~27 MJ stored: hours, not minutes or days (DEC-004;
    # the kiln's own calc gives 4.8 h at 2.5 kW, its 7 h plan carries a 1.28 power margin)
    assert 3 <= _q(kiln, "e", "heat_up_time", "hour") <= 10
    assert 500 <= _q(kiln, "e", "heat_loss", "W") <= 1500
    assert 15 <= _q(kiln, "e", "stored_heat", "MJ") <= 40
    # labels present on every number
    assert all(v.label == "computed" for v in kiln.computed.values())
    assert all(v.label == "estimate" for v in kiln.estimates.values())
    # the card's own inputs come back as given, never as an estimate (review gate A, C1)
    assert all(v.label == "given" for v in kiln.given.values())
    assert set(kiln.given) == {"power", "circuit_class"}
    assert kiln.given["power"].value == "2.5 kW"
    assert kiln.given["power"].source == "on the card"
    assert kiln.given["power"].ref == "envelope.power"

    wide = _screen(_card(KILN, site={"alcove_width": "1300 mm"}))
    assert _rule(wide, "fits-site-width").status == "pass"
    assert "1245 mm with the door open" in _rule(wide, "fits-site-width").message


def test_seven_hour_plan_needs_about_two_kilowatts() -> None:
    data = copy.deepcopy(KILN)
    del data["envelope"]["power"]
    data["envelope"]["heat_up_time"] = "7 h"
    s = _screen(ConceptCard.model_validate(data))
    # DEC-004: 0.9 kW of loss plus 27 MJ over 7 h needs about 1.95 kW
    assert 1.5 <= _q(s, "e", "required_power", "kW") <= 2.6
    assert "heat_up_time" not in s.estimates
    assert _rule(s, "circuit-available").status == "pass"  # the estimated power is checked


# --- rule by rule: one red card and one green -----------------------------------------


def test_door_swing_term_sources() -> None:
    no_door = copy.deepcopy(KILN)
    no_door["massing"] = [m for m in no_door["massing"] if m["as"] != "door"]
    s = _screen(_card(no_door, site={"alcove_width": "1000 mm"}))
    row = _rule(s, "fits-site-width")
    assert row.status == "pass" and "+ 0 mm" in row.message
    assert "not counted" in s.computed["footprint_with_door_swing"].source
    declared = _card(no_door, envelope={**KILN["envelope"], "door_width": "300 mm"})
    s = _screen(declared)
    assert "envelope.door_width 300 mm" in _rule(s, "fits-site-width").message
    sliding = _screen(_card(KILN, layout={"door": "sliding"}, site={"alcove_width": "1000 mm"}))
    assert _rule(sliding, "fits-site-width").status == "pass"


def test_fits_site_depth_and_height(kiln: Screening) -> None:
    assert _rule(kiln, "fits-site-depth").status == "skip"
    tight = _screen(_card(KILN, site={"alcove_depth": "500 mm", "alcove_height": "1000 mm"}))
    assert _rule(tight, "fits-site-depth").status == "fail"
    assert "656 mm deep but the alcove is 500 mm deep" in _rule(tight, "fits-site-depth").message
    assert _rule(tight, "fits-site-height").status == "fail"
    roomy = _screen(_card(KILN, site={"alcove_depth": "700 mm", "alcove_height": "1400 mm"}))
    assert _rule(roomy, "fits-site-depth").status == "pass"
    assert _rule(roomy, "fits-site-height").status == "pass"


def test_circuit_available(kiln: Screening) -> None:
    assert _rule(kiln, "circuit-available").status == "pass"
    assert kiln.given["circuit_class"].value == "the 240V-13A circuit"
    assert "circuit_class" not in kiln.estimates
    assert _rule(kiln, "circuit-available").relies_on == ["estimate", "given"]
    small = _screen(_card(KILN, site={"circuit": "240V-10A"}))
    row = _rule(small, "circuit-available")
    assert row.status == "fail" and "more than the 240V-10A circuit on site" in row.message
    by_region = _without(KILN, "site", "circuit")
    s = _screen(by_region)
    assert _rule(s, "circuit-available").status == "pass"
    assert s.estimates["circuit_class"].value == "16 A dedicated circuit"  # from a table
    assert "circuit_class" not in s.given
    huge = by_region.model_copy(update={"envelope": {**by_region.envelope}})
    huge.envelope["power"] = parse_quantity("10 kW")
    assert _rule(_screen(huge), "circuit-available").status == "fail"


def test_unknown_region_warns_not_fails() -> None:
    s = _screen(_without(KILN, "site", "circuit", site={"region": "XX"}))
    row = _rule(s, "circuit-available")
    assert row.status == "warn"
    assert row.message == "no circuit table for region XX — confirm the supply"
    assert "circuit_class" not in s.estimates
    assert any("region XX" in n for n in s.notes)
    assert "circuit-available" not in {r.id for r in s.failing}, "a warning never reddens"


def test_mass_vs_lift_class(kiln: Screening) -> None:
    row = _rule(kiln, "mass-vs-lift-class")
    assert row.status == "warn" and row.severity == "warn"
    assert "equipment handling" in row.message and "not a two-person lift" in row.message
    assert kiln.estimates["lift_class"].value == "equipment"
    light = _screen(_card(SMALL))
    assert _rule(light, "mass-vs-lift-class").status == "pass"
    strict = _screen(_card(SMALL, site={"lift_class": "one-person"}))
    assert _rule(strict, "mass-vs-lift-class").status == "pass"
    heavy = _screen(_card(KILN, site={"lift_class": "one-person"}))
    assert "not a one-person lift" in _rule(heavy, "mass-vs-lift-class").message


def test_blank_vs_stock_sheet(kiln: Screening) -> None:
    row = _rule(kiln, "blank-vs-stock-sheet")
    assert row.status == "fail"
    assert "body: the flat blank is about 1979 × 1934 mm" in row.message
    ok = _screen(_card(SMALL))
    assert _rule(ok, "blank-vs-stock-sheet").status == "pass"
    assert "body 1200 × 1200 mm" in _rule(ok, "blank-vs-stock-sheet").message
    strip = {
        "kit": "plate",
        "as": "strip",
        "material": "aluminium",
        "args": {"width": "3500 mm", "depth": "100 mm", "thickness": "2 mm"},
        "at": {"z": "500 mm"},
    }
    long = _screen(_card(SMALL, massing=[*SMALL["massing"], strip]))
    assert (
        "strip: the flat blank is about 3500 × 100 mm"
        in _rule(long, "blank-vs-stock-sheet").message
    )
    assert "aluminium" in _rule(long, "blank-vs-stock-sheet").message
    leg = {
        "kit": "bracket_l",
        "as": "leg",
        "material": "stainless steel",
        "args": {"length": "100 mm", "height": "80 mm", "width": "50 mm", "thickness": "2 mm"},
    }
    s = _screen(_card(SMALL, massing=[leg]))
    assert "leg 180 × 50 mm" in _rule(s, "blank-vs-stock-sheet").message
    blocks = _screen(_card(SMALL, massing=[SMALL["massing"][1]]))
    assert _rule(blocks, "blank-vs-stock-sheet").status == "skip"


def test_sheet_blank_resolves_fit_to() -> None:
    """A door sized by ``fit_to`` screens with its real blank, not 0 mm (M4 fix of M3)."""
    door: dict[str, Any] = {
        "kit": "panel",
        "as": "door",
        "material": "mild steel",
        "args": {"fit_to": {"width": "400 mm", "height": "300 mm"}, "thickness": "1.5 mm"},
    }
    lid = copy.deepcopy(door) | {"kit": "plate", "as": "lid"}
    plain = _screen(_card(SMALL, massing=[door, lid]))
    message = _rule(plain, "blank-vs-stock-sheet").message
    assert "door 396 × 296 mm" in message and "lid 396 × 296 mm" in message  # 2 mm default
    styled = _screen(_card(SMALL, massing=[door], style={"reveal": "5 mm"}))
    assert "door 390 × 290 mm" in _rule(styled, "blank-vs-stock-sheet").message
    own = copy.deepcopy(door)
    own["args"]["reveal"] = "3 mm"
    mine = _screen(_card(SMALL, massing=[own], style={"reveal": "5 mm"}))
    assert "door 394 × 294 mm" in _rule(mine, "blank-vs-stock-sheet").message


def test_walls_fit_envelope(kiln: Screening) -> None:
    assert _rule(kiln, "walls-fit-envelope").status == "pass"
    assert "2 × 195 mm of insulation" in _rule(kiln, "walls-fit-envelope").message
    big = _screen(_card(KILN, envelope={**KILN["envelope"], "chamber": ["400 mm"] * 3}))
    row = _rule(big, "walls-fit-envelope")
    assert row.status == "fail" and big.verdict == "red"
    assert "the width needs 790 mm (chamber 400 mm + 2 × 195 mm of insulation)" in row.message
    assert "but body is only 695 mm" in row.message


def test_controls_not_adjacent_hot_face(kiln: Screening) -> None:
    assert _rule(kiln, "controls-not-adjacent-hot-face").status == "pass"
    top = _screen(_card(SMALL, layout={"controls": "top"}))
    row = _rule(top, "controls-not-adjacent-hot-face")
    assert row.status == "warn" and "controls above the door" in row.message
    assert top.verdict == "green", "a warning never reddens"
    front = _screen(_card(SMALL, layout={"controls": "front-left"}))
    assert "controls beside the door" in _rule(front, "controls-not-adjacent-hot-face").message
    lid = _screen(_card(SMALL, layout={"door": "top-lid", "controls": "side-right"}))
    assert _rule(lid, "controls-not-adjacent-hot-face").status == "pass"


# --- missing inputs, labels, writers --------------------------------------------------


def test_missing_envelope_omits_estimates_with_a_note() -> None:
    s = _screen(_card(SMALL).model_copy(update={"envelope": {}}))
    assert not {"heat_loss", "stored_heat", "heat_up_time", "current"} & set(s.estimates)
    assert any("envelope.chamber" in n for n in s.notes)
    assert any("no power on the card" in n for n in s.notes)
    assert _rule(s, "walls-fit-envelope").status == "skip"
    assert _rule(s, "circuit-available").status == "skip"
    assert s.verdict == "green" and "width" in s.computed


def test_no_material_means_no_mass_and_a_note() -> None:
    bare = copy.deepcopy(SMALL)
    for call in bare["massing"]:
        call.pop("material")
    s = _screen(_card(bare))
    assert "mass" not in s.computed and "total_mass" not in s.estimates
    assert any("give these shapes a material: body, door" in n for n in s.notes)
    assert any("cost leaves out body (no material, so no mass)" in n for n in s.notes)
    assert _rule(s, "mass-vs-lift-class").status == "skip"


def test_insulation_inputs_that_cannot_be_used_are_noted() -> None:
    odd = _screen(_card(SMALL, envelope={**SMALL["envelope"], "insulation": ["50 mm", "50 mm"]}))
    assert "heat_loss" not in odd.estimates and any("named layers" in n for n in odd.notes)
    layer = {"name": "mystery", "thickness": "100 mm"}
    s = _screen(_card(SMALL, envelope={**SMALL["envelope"], "insulation": [layer]}))
    assert "heat_loss" not in s.estimates
    assert any("mystery: give a conductivity" in n for n in s.notes)
    assert _rule(s, "walls-fit-envelope").status == "pass", "thicknesses alone still screen"
    weak = _screen(_card(SMALL, envelope={**SMALL["envelope"], "power": "100 W"}))
    assert any("never reach temperature" in n for n in weak.notes)


def test_labels_at_the_data_level(kiln: Screening, tmp_path: Path) -> None:
    card = _card(KILN)
    path = write_screening_json(tmp_path, card, kiln)
    data = json.loads(path.read_text())
    assert data["verdict"] == "red" and data["id"] == "C-001"
    assert {v["label"] for v in data["computed"].values()} == {"computed"}
    assert {v["label"] for v in data["estimates"].values()} == {"estimate"}
    assert {v["label"] for v in data["given"].values()} == {"given"}
    groups = ("given", "computed", "estimates")
    assert all(v["source"] for g in groups for v in data[g].values())
    assert all(set(r["relies_on"]) <= {"computed", "estimate", "given"} for r in data["rules"])
    # the engineer's reference travels in the data (ref), the owner's sentence in source
    refs = {v["ref"].split(" ")[0] for v in data["estimates"].values()}
    assert "thermal_enclosure.steady_loss" in refs and "mass_cost.lift_class" in refs
    assert data["estimates"]["heat_up_time"]["source"] == (
        "from the walls' stored heat and the element power"
    )
    assert data["estimates"]["lift_class"]["source"].endswith("; to be checked")
    for g in groups:
        for v in data[g].values():
            for word in ("massing", "calc", "[verify]", "thermal_enclosure", "mass_cost", "."):
                assert word not in v["source"], (word, v)


def test_screening_round_trips_through_the_card(kiln: Screening, tmp_path: Path) -> None:
    cm.write_card(tmp_path, _card(KILN))
    path = cm.card_path(tmp_path, "C-001")
    text = path.read_text()
    path.write_text(
        text.replace("title: The v0.1 kiln as built", "title: The v0.1 kiln as built  # mine")
    )
    write_screening_to_card(tmp_path, "C-001", kiln)
    text = path.read_text()
    assert "# mine" in text, "comments survive"
    assert "    width: {value: 995 mm, label: computed" in text, "one flow line per value"
    back = cm.load_card(tmp_path, "C-001")
    assert back.verdict == "red" and back.screening == kiln


def test_concept_pack_is_shaped_like_the_others() -> None:
    (pack,) = concept_packs()
    assert pack.id == "concept-v0" and pack.applies_to == {"scope": "concept"}
    ids = [r["id"] for r in pack.rules]
    assert ids[:3] == ["fits-site-width", "fits-site-depth", "fits-site-height"]
    assert {r["severity"] for r in pack.rules} == {"fail", "warn"}
    assert rule_params("fits-site-width") == {"door_swing_factor": 1.0}
    assert rule_params("nope") == {}
    assert parse_circuit("240V-13A") is not None and parse_circuit("dedicated") is None


def test_unknown_check_is_a_skip_row() -> None:
    from napkin2factory.rulepacks.runner import RulePack

    pack = RulePack("x", "x", {"scope": "concept"}, [{"id": "r", "check": "nope"}], Path("x.yaml"))
    (row,) = run_concept_rules(_card(SMALL), {}, {}, None, None, [pack])
    assert row.status == "skip" and "unknown check 'nope'" in row.message


def test_part_rule_runner_never_applies_the_concept_pack() -> None:
    from napkin2factory.rulepacks.runner import load_packs, pack_applies

    class FakePart:
        process = "sheet-metal"

    (pack,) = [p for p in load_packs() if p.id == "concept-v0"]
    assert not pack_applies(pack, FakePart())


def test_summary_line_keeps_inputs_given_and_collapses_one_source_cost(kiln: Screening) -> None:
    """Review gate A, C1 and C9."""
    from napkin2factory.concepts.build import summary_line
    from napkin2factory.core.model.concepts import LabelledValue

    line = summary_line(_card(KILN), kiln)
    assert (
        "2.5 kW (on the card) on the 240V-13A circuit — fits with a fifth to spare (estimate)"
        in line
    )
    one = LabelledValue(value="43 USD", label="estimate", source="one band")
    flat = kiln.model_copy(
        update={"estimates": {**kiln.estimates, "cost_low": one, "cost_high": one}}
    )
    line = summary_line(_card(KILN), flat)
    assert "43 USD (estimate, one source)" in line and "43–43" not in line


# --- review gate B: owner words ------------------------------------------------------------


def test_masses_under_ten_kilograms_keep_one_decimal() -> None:
    """Gate B, B3: never "about 0 kg: a one-person lift"."""
    from napkin2factory.rulepacks.concept_checks import kg_text

    assert kg_text(0.445) == "0.4 kg" and kg_text(9.94) == "9.9 kg"
    assert kg_text(23.4) == "23 kg" and kg_text(142.0) == "142 kg"
    plate = {
        "id": "C-003",
        "title": "Plate",
        "massing": [
            {
                "kit": "block",
                "as": "bracket",
                "material": "mild steel",
                "args": {"length": "120 mm", "width": "60 mm", "height": "6 mm"},
            }
        ],
    }
    s = _screen(ConceptCard.model_validate(plate))
    assert _rule(s, "mass-vs-lift-class").message == "about 0.3 kg: a one-person lift"


def test_a_card_without_a_door_has_no_door_row() -> None:
    """Gate B, C11: no door on the card, no "width with the door open" row."""
    no_door = copy.deepcopy(SMALL)
    no_door["layout"] = {"load": "top"}
    no_door["massing"] = no_door["massing"][:1]
    s = _screen(ConceptCard.model_validate(no_door))
    assert "footprint_with_door_swing" not in s.computed and "width" in s.computed
    row = _rule(s, "fits-site-width")
    assert row.status == "pass" and row.message == "400 mm wide fits the 800 mm alcove"
    assert "door" not in row.message
    sliding = _screen(_card(SMALL, layout={"door": "sliding"}))
    foot = sliding.computed["footprint_with_door_swing"]
    assert foot.source == "the body only: a sliding door swings nothing beside it"


def test_cost_source_names_what_is_priced_and_what_is_not(kiln: Screening) -> None:
    """Gate B, B2: the cost line in words; the per-process list stays in ref."""
    cost = kiln.estimates["cost_high"]
    assert cost.source.startswith("rough cost of the ")
    assert cost.source.endswith("from cost bands per process; to be checked") or (
        "are not counted; to be checked" in cost.source or "is not counted" in cost.source
    )
    assert "cots-controls" not in cost.source and "cots-controls" in (cost.ref or "")
    assert kiln.computed["width"].source == "measured across the rough shapes"
    assert kiln.computed["footprint_with_door_swing"].source == (
        "the body plus the door leaf swung open beside the hinge"
    )
