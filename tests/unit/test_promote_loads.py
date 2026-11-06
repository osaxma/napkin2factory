"""B-0230: promotion keeps the card's loads, limits and budget, in the owner's units.

The product is a copy of the table example with its three cards put back to "exploring" (the
copy is promoted, never built: promotion only reads the model and the cards).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from napkin2factory.concepts.promote import promote
from napkin2factory.concepts.promote.decision import plain_reason
from tests.conftest import EXAMPLES, copy_product


def _table(tmp: Path, imperial: bool = False, **site: str) -> Path:
    root = copy_product(EXAMPLES / "table", tmp / "table", git=False)
    for cid in ("C-001", "C-002", "C-003"):
        f = root / "concepts" / f"{cid}.yaml"
        text = re.sub(r"^status: .*$", "status: exploring", f.read_text(), flags=re.M)
        text = re.sub(r"^decision: .*\n", "", text, flags=re.M)
        if cid == "C-002":
            for key, value in site.items():
                text = re.sub(rf"^  {key}: .*$", f"  {key}: {value}", text, flags=re.M)
        f.write_text(text)
    if imperial:
        n2f = root / "n2f.yaml"
        n2f.write_text(n2f.read_text().replace("units: metric", "units: imperial"))
    return root


def _file(root: Path, rel: str) -> Any:
    return yaml.safe_load((root / rel).read_text(encoding="utf-8"))


def test_loads_limit_and_budget_are_seeded(tmp_path: Path) -> None:
    root = _table(tmp_path)
    result = promote(root, "C-002", snapshot=False)
    by_name = {p.name: p for p in result.params}
    # a load the model had no name for is a new parameter; one it already had is found
    assert by_name["edge-offset"].status == "new" and by_name["edge-offset"].value == "75 mm"
    assert (
        by_name["point-load"].status == "new" and by_name["point-load"].source == "site.point_load"
    )
    assert by_name["edge-load"].status == "declared"
    seeded = _file(root, "model/parameters.yaml")["parameters"]
    assert seeded["point-load"]["owner"] == "napkin" and seeded["point-load"]["value"] == 1471.5
    titles = {r.title: r for r in result.requirements}
    sag = titles["Sag stays within the limit"]
    assert sag.data["statement"].endswith("the sag is at most 2.5 mm.")
    assert sag.data["allocation"] == ["asm://table"]
    cost = titles["Within the budget"]
    assert cost.data["verify"] == {
        "kind": "bom_rollup",
        "target": "bom://rollups#total_cost",
        "op": "<=",
        "value": "1600 USD",
    }


def test_a_load_of_the_wrong_kind_is_listed_not_dropped(tmp_path: Path) -> None:
    root = _table(tmp_path, point_load="2.5 mm")
    result = promote(root, "C-002", snapshot=False)
    assert any(n.startswith("site.point_load") and "not seeded" in n for n in result.notes)


def test_statements_use_the_display_units_and_the_bound_stays_exact(tmp_path: Path) -> None:
    root = _table(tmp_path, imperial=True, mass_limit="150 lb")
    result = promote(root, "C-002", snapshot=False)
    weight = next(r for r in result.requirements if r.about == "weight")
    assert weight.data["statement"] == "The assembled product weighs less than 150 lb."
    assert "68.0389" not in weight.data["statement"]
    assert weight.data["verify"]["value"].startswith("68.0389")  # exact, in the model's unit
    sag = next(r for r in result.requirements if r.about == "sag")
    assert "0.098 in" in sag.data["statement"]


def test_a_default_style_writes_no_form_requirement(tmp_path: Path) -> None:
    root = _table(tmp_path)
    result = promote(root, "C-002", snapshot=False)
    assert [r for r in result.requirements if r.about == "form"] == []


def test_the_decision_names_other_ideas_without_their_calculations(tmp_path: Path) -> None:
    root = _table(tmp_path)
    promote(root, "C-002", snapshot=False)
    dec = _file(root, "model/decisions.yaml")["decisions"][-1]
    text = dec["context"]
    assert "C-001" in text and "sags 14.3 mm" in text
    for calc in ("FL^3", "Roark", "[verify]", "needed", "materials.yaml"):
        assert calc not in text


def test_plain_reason_cuts_the_formula() -> None:
    msg = (
        "the top sags 14.3 mm (computed), beyond the 2.5 mm limit "
        "(limit ÷ sag is 0.2, 1 needed) — F*L^3"
    )
    assert plain_reason(msg) == "the top sags 14.3 mm (computed), beyond the 2.5 mm limit"


def test_plain_reason_keeps_plain_explanation_after_a_dash() -> None:
    msg = (
        "it needs 1245 mm of width — 995 mm for the body plus 250 mm for the door "
        "— but the room is 800 mm"
    )
    assert plain_reason(msg) == msg


def test_overwriting_a_parameter_keeps_the_next_line_apart() -> None:
    """An overwrite in the middle of the file must not join its line to the next one."""
    from napkin2factory.concepts.promote.parameters import _edit_param_value

    text = "parameters:\n  a-b: {value: 1, unit: mm}\n  c: {value: 2, unit: mm}\n"
    assert _edit_param_value(text, "a-b", "9") == (
        "parameters:\n  a-b: {value: 9, unit: mm}\n  c: {value: 2, unit: mm}\n"
    )
