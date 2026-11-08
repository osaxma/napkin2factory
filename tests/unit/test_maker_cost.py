"""Tests for maker, materials cost bands, and init asks (B-0319, B-0320, W7)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from napkin2factory.bom.rollups import compute_rollups
from napkin2factory.calckit import mass_cost
from napkin2factory.calckit.mass_cost import cost_band, cost_estimate
from napkin2factory.cli.init import check_place, cost_init_feedback, init
from napkin2factory.concepts.screens.base import ScreenValues
from napkin2factory.concepts.screens.generic import cost_band as cb_screen
from napkin2factory.core.errors import N2FError
from napkin2factory.core.loader import load_product
from napkin2factory.core.model import ConceptCard, Manifest
from napkin2factory.core.units import Quantity
from napkin2factory.core.yamlio import dump_roundtrip, load_roundtrip
from napkin2factory.mcp.combined import build_combined
from tests.conftest import EXAMPLES, copy_product

# ---------------------------------------------------------------------------------------------
# Item 1: Manifest maker field, cost_bands.yaml basis & materials rows, cost_band / estimate


def test_manifest_maker_field() -> None:
    """Manifest.maker is optional (None), accepts owner and shop, rejects others."""
    m_default = Manifest.model_validate({"product": {"id": "p", "name": "P"}})
    assert m_default.maker is None

    m_owner = Manifest.model_validate({"product": {"id": "p", "name": "P"}, "maker": "owner"})
    assert m_owner.maker == "owner"

    m_shop = Manifest.model_validate({"product": {"id": "p", "name": "P"}, "maker": "shop"})
    assert m_shop.maker == "shop"

    with pytest.raises(ValidationError):
        Manifest.model_validate({"product": {"id": "p", "name": "P"}, "maker": "factory"})


def test_cost_bands_materials_rows() -> None:
    """cost_bands.yaml has basis column; materials rows for woodworking & welding in US & EU."""
    rows = mass_cost.load_table("cost_bands")
    for r in rows:
        assert r.get("basis") in ("made", "materials"), f"invalid basis in row: {r}"

    materials_keys = {(r["process_class"], r["region"], r["basis"]) for r in rows}
    expected = {
        ("woodworking", "US", "materials"),
        ("woodworking", "EU", "materials"),
        ("welding", "US", "materials"),
        ("welding", "EU", "materials"),
    }
    assert expected.issubset(materials_keys)

    date_re = re.compile(r"^\d{4}-\d{2}$")
    for r in rows:
        if r.get("basis") == "materials":
            assert r["verify"] is True
            assert date_re.match(r["as_of"])
            assert r["unit"] == "per_kg"
            src = r["source"]
            assert len(src) > 20
            assert "materials only" in src
            assert (
                "retail stock" in src
                or "softwood lumber" in src
                or "mild steel tube" in src
                or "dimensional" in src
            )


def test_cost_band_and_estimate_take_basis() -> None:
    """cost_band and cost_estimate take basis (default made, or materials)."""
    b_made = cost_band("woodworking", region="US", basis="made")
    assert b_made.basis == "made"
    assert b_made.low == 9.0 and b_made.high == 22.0

    b_mat = cost_band("woodworking", region="US", basis="materials")
    assert b_mat.basis == "materials"
    assert b_mat.low == 1.0 and b_mat.high == 4.0

    est_mat = cost_estimate("woodworking", mass=Quantity(5, "kg"), region="US", basis="materials")
    assert float(est_mat.low.to("USD").magnitude) == pytest.approx(5.0)
    assert float(est_mat.high.to("USD").magnitude) == pytest.approx(20.0)


# ---------------------------------------------------------------------------------------------
# Item 2: Cost screening rule wording with and without maker


def _run_cost_screen(
    items: list[tuple[str, str, float | None, tuple[float, float] | None]],
    maker: str | None = None,
    budget: str | None = "500 USD",
    region: str | None = "US",
) -> tuple[ScreenValues, list[Any]]:
    card = ConceptCard.model_validate(
        {"id": "C-001", "title": "t", "site": {"budget": budget} if budget else {}}
    )
    values = ScreenValues()
    values.shared["region"] = region
    if maker:
        values.shared["maker"] = maker
    values.cost_items += [(name, pclass, kg) for name, pclass, kg, _ext in items]
    rows = cb_screen(card, None, values)
    return values, rows


def test_cost_rule_wording_with_maker_owner() -> None:
    """With maker: owner, uses materials band and wording says materials only, owner builds it."""
    values, rows = _run_cost_screen(
        [("top", "woodworking", 10.0, None)], maker="owner", budget="100 USD"
    )
    src = values.estimate.out["cost_low"].source
    assert "materials only, the owner builds it" in src
    assert values.estimate.raw["cost_low"].to("USD").magnitude == pytest.approx(10.0)
    assert values.estimate.raw["cost_high"].to("USD").magnitude == pytest.approx(40.0)
    budget_row = next(r for r in rows if r.id == "cost-vs-budget")
    assert budget_row.status == "pass"


def test_cost_rule_wording_with_maker_shop() -> None:
    """With maker: shop, uses made band and wording says made by a shop."""
    values, rows = _run_cost_screen(
        [("top", "woodworking", 10.0, None)], maker="shop", budget="300 USD"
    )
    src = values.estimate.out["cost_low"].source
    assert "made by a shop" in src
    assert values.estimate.raw["cost_low"].to("USD").magnitude == pytest.approx(90.0)
    assert values.estimate.raw["cost_high"].to("USD").magnitude == pytest.approx(220.0)
    budget_row = next(r for r in rows if r.id == "cost-vs-budget")
    assert budget_row.status == "pass"


def test_cost_rule_without_maker_hints_materials_figure_when_it_would_pass() -> None:
    """Without maker, shop rate used; when shop fails but materials passes, hints maker: owner."""
    values, rows = _run_cost_screen(
        [("top", "woodworking", 10.0, None)], maker=None, budget="50 USD"
    )
    # Shop rates: 90 to 220 USD vs 50 USD budget -> fails
    assert values.estimate.raw["cost_low"].to("USD").magnitude == pytest.approx(90.0)
    budget_row = next(r for r in rows if r.id == "cost-vs-budget")
    assert budget_row.status == "fail"
    # Materials figure is 10 to 40 USD, which is <= 50 USD
    assert "if the owner builds it, the materials alone are 10 USD to 40 USD" in budget_row.message
    assert "set `maker: owner` in n2f.yaml" in budget_row.message


# ---------------------------------------------------------------------------------------------
# Item 3: Made part without cost auto-prices from built mass in rollups


def test_rollup_auto_prices_part_with_maker_owner_and_follows_size(tmp_path: Path) -> None:
    """In a product with maker: owner, a custom part with no cost gets estimate from built mass."""
    root = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", git=False)

    # 1. Product without maker: custom part with no cost has no price
    part_path = root / "model" / "parts" / "l-bracket.yaml"
    data = load_roundtrip(part_path)
    data["process"] = "woodworking"
    data.pop("cost", None)
    data["mass"] = "5.0 kg"
    dump_roundtrip(part_path, data)

    product_no_maker = load_product(root)
    rollups_no_maker = compute_rollups(product_no_maker)
    lines_no_maker = rollups_no_maker["structure"]["asm://bracket"]
    bracket_ln = next(ln for ln in lines_no_maker if ln["id"] == "l-bracket")
    assert bracket_ln["unit_cost"] is None
    assert bracket_ln["cost_basis"] == ""
    assert bracket_ln["cost_note"] == ""

    # 2. Product with maker: owner: gets estimate from materials woodworking band
    manifest_path = root / "n2f.yaml"
    m_data = load_roundtrip(manifest_path)
    m_data["maker"] = "owner"
    m_data["region"] = "US"
    dump_roundtrip(manifest_path, m_data)

    product_owner = load_product(root)
    rollups_owner = compute_rollups(product_owner)
    lines_owner = rollups_owner["structure"]["asm://bracket"]
    bracket_owner = next(ln for ln in lines_owner if ln["id"] == "l-bracket")

    # Woodworking materials band US: 1.0 to 4.0 USD/kg. For 5 kg: low 5, high 20, midpoint 12.5
    assert bracket_owner["cost_basis"] == "estimate"
    assert bracket_owner["unit_cost"] == pytest.approx(12.5)
    assert (
        bracket_owner["cost_note"]
        == "materials US woodworking band, as of 2026-11: USD 1–4/kg × 5 kg; mid-point"
    )

    # 3. Size changes (mass changes to 10 kg): price and note follow
    data["mass"] = "10.0 kg"
    dump_roundtrip(part_path, data)

    product_resized = load_product(root)
    rollups_resized = compute_rollups(product_resized)
    bracket_resized = next(
        ln for ln in rollups_resized["structure"]["asm://bracket"] if ln["id"] == "l-bracket"
    )
    # For 10 kg: low 10, high 40, midpoint 25.0
    assert bracket_resized["cost_basis"] == "estimate"
    assert bracket_resized["unit_cost"] == pytest.approx(25.0)
    assert (
        bracket_resized["cost_note"]
        == "materials US woodworking band, as of 2026-11: USD 1–4/kg × 10 kg; mid-point"
    )


# ---------------------------------------------------------------------------------------------
# Item 4: Init CLI & MCP tool taking region and maker, confirm, ask


def test_init_check_place() -> None:
    """check_place validates maker alongside region and units."""
    reg, units, maker = check_place("us", "metric", "owner")
    assert reg == "US"
    assert units == "metric"
    assert maker == "owner"

    with pytest.raises(N2FError) as exc:
        check_place(None, None, "invalid")
    assert "--maker: unknown maker 'invalid'; choose owner or shop" in str(exc.value)


def test_cost_init_feedback_combinations() -> None:
    """cost_init_feedback gives words with confirm when given, and ask when missing."""
    costs, confirm, ask = cost_init_feedback("US", "owner")
    assert costs == "costs in US dollars, from US prices; the owner builds it"
    assert confirm == "ask the owner whether this is right before reading costs"
    assert ask == []

    costs_shop, confirm_shop, _ = cost_init_feedback("EU", "shop")
    assert costs_shop == "costs in euros, from EU prices; made by a shop"
    assert confirm_shop == "ask the owner whether this is right before reading costs"

    costs_none, confirm_none, ask_none = cost_init_feedback(None, None)
    assert costs_none == "region not set"
    assert confirm_none is None
    assert len(ask_none) == 2
    assert any("region" in q.lower() or "built and bought" in q.lower() for q in ask_none)
    assert any("maker" in q.lower() or "custom parts" in q.lower() for q in ask_none)


def test_init_cli_json_with_and_without_region_and_maker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """n2f init --json emits confirm when given and ask when missing."""
    captured: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "napkin2factory.cli.init.emit_json",
        lambda obj: captured.append(obj),
    )

    # 1. Given both region and maker
    dest1 = tmp_path / "p1"
    init(
        directory=dest1,
        template="blank",
        name="P1",
        style="industrial",
        region="US",
        units="metric",
        maker="owner",
        no_tracking=True,
        json_out=True,
    )
    assert len(captured) == 1
    out1 = captured[0]
    assert out1["region"] == "US"
    assert out1["maker"] == "owner"
    assert out1["costs"] == "costs in US dollars, from US prices; the owner builds it"
    assert out1["confirm"] == "ask the owner whether this is right before reading costs"
    assert "ask" not in out1

    # 2. Missing both region and maker
    captured.clear()
    dest2 = tmp_path / "p2"
    init(
        directory=dest2,
        template="blank",
        name="P2",
        style="industrial",
        region=None,
        units="metric",
        maker=None,
        no_tracking=True,
        json_out=True,
    )
    assert len(captured) == 1
    out2 = captured[0]
    assert out2["region"] is None
    assert out2["maker"] is None
    assert out2["costs"] == "region not set"
    assert "confirm" not in out2
    assert len(out2["ask"]) == 2


@pytest.mark.anyio
async def test_mcp_init_product_with_and_without_region_and_maker(tmp_path: Path) -> None:
    """n2f_init_product handles region and maker, confirm, and ask."""
    tools = {t.name: t for t in build_combined()}
    desc = tools["n2f_init_product"].description.lower()
    assert "never infer region or maker from the machine or its time zone" in desc

    from tests.unit.test_mcp import _runner

    # 1. Calling with given region and maker
    runner1, _ = _runner(tmp_path / "p1", {("init",): {"product": "p1", "files": 26}})
    res1 = await runner1.call(
        "n2f_init_product",
        {"name": "P1", "units": "metric", "region": "US", "maker": "owner"},
    )
    data1 = json.loads(res1.text)
    assert not res1.is_error
    assert data1["costs"] == "costs in US dollars, from US prices; the owner builds it"
    assert data1["confirm"] == "ask the owner whether this is right before reading costs"
    assert "ask" not in data1

    # 2. Calling without region and maker
    runner2, _ = _runner(tmp_path / "p2", {("init",): {"product": "p2", "files": 26}})
    res2 = await runner2.call("n2f_init_product", {"name": "P2", "units": "metric"})
    data2 = json.loads(res2.text)
    assert not res2.is_error
    assert data2["costs"] == "region not set"
    assert "confirm" not in data2
    assert len(data2["ask"]) == 2
