"""Tests for Domain.bom_lines hook, rollups, and bom.csv consumable rows (S-188)."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from napkin2factory.bom.files import COLUMNS, write_csv
from napkin2factory.bom.rollups import compute_rollups
from napkin2factory.core.domain import BomLine, Domain
from napkin2factory.core.loader import load_product
from napkin2factory.core.registry import installed
from napkin2factory.domains.electrical.outputs.consumables import electrical_bom_lines
from napkin2factory.geometry.accessors import ReadLog
from tests.conftest import EXAMPLES, FIXTURES, copy_product

MINIMAL = FIXTURES / "electrical" / "minimal"


def test_bom_lines_hook_called_and_records_reads(tmp_path: Path) -> None:
    """compute_rollups calls registered domain's bom_lines with a read-recording reader."""
    recorded_keys: list[str] = []

    def fake_bom_lines(product: Any, reader: Any) -> list[BomLine]:
        reader("custom://read/key")
        recorded_keys.append("custom://read/key")
        return [
            BomLine(
                id="wire-test",
                name="Test wire, 1 mm², PVC",
                quantity=2.5,
                unit="m",
                unit_cost=1.5,
                domain="fake",
                source="test source",
            )
        ]

    fake_domain = Domain(name="fake", bom_lines=fake_bom_lines)
    root = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", git=False)
    product = load_product(root)

    log = ReadLog()
    with installed(fake_domain):
        rollups = compute_rollups(product, log=log)

    assert "custom://read/key" in recorded_keys
    assert "custom://read/key" in rollups["reads"]
    assert "consumables" in rollups
    assert len(rollups["consumables"]) == 1
    c = rollups["consumables"][0]
    assert c["id"] == "wire-test"
    assert c["name"] == "Test wire, 1 mm², PVC"
    assert c["quantity"] == 2.5
    assert c["unit"] == "m"
    assert c["unit_cost"] == 1.5
    assert c["ext_cost"] == 3.75
    assert c["domain"] == "fake"
    assert c["source"] == "test source"


def test_unpriced_consumable_sets_cost_complete_false(tmp_path: Path) -> None:
    """An unpriced consumable (unit_cost None or quantity None) sets cost_complete False."""

    def fake_unpriced(product: Any, reader: Any) -> list[BomLine]:
        return [
            BomLine(
                id="unpriced-cable",
                name="Unpriced cable",
                quantity=10.0,
                unit="m",
                unit_cost=None,
                domain="fake",
            )
        ]

    fake_domain = Domain(name="fake", bom_lines=fake_unpriced)
    root = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", git=False)
    product = load_product(root)

    with installed(fake_domain):
        rollups = compute_rollups(product)

    assert rollups["cost_complete"] is False

    # Also test quantity None
    def fake_no_qty(product: Any, reader: Any) -> list[BomLine]:
        return [
            BomLine(
                id="no-qty-cable",
                name="No quantity cable",
                quantity=None,
                unit="m",
                unit_cost=2.0,
                domain="fake",
            )
        ]

    fake_domain_no_qty = Domain(name="fake", bom_lines=fake_no_qty)
    with installed(fake_domain_no_qty):
        rollups_no_qty = compute_rollups(product)

    assert rollups_no_qty["cost_complete"] is False


def test_priced_consumable_adds_to_total_cost(tmp_path: Path) -> None:
    """A priced consumable adds quantity * unit_cost to total_cost."""
    root = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", git=False)
    product = load_product(root)

    # Base rollups without consumables
    base_rollups = compute_rollups(product)
    base_cost = base_rollups["total_cost"]

    def fake_priced(product: Any, reader: Any) -> list[BomLine]:
        return [
            BomLine(
                id="priced-cable",
                name="Priced cable",
                quantity=4.0,
                unit="m",
                unit_cost=3.50,
                domain="fake",
            )
        ]

    fake_domain = Domain(name="fake", bom_lines=fake_priced)
    with installed(fake_domain):
        rollups = compute_rollups(product)

    assert rollups["total_cost"] == round(base_cost + 4.0 * 3.50, 2)
    # If all parts in bracket are priced, cost_complete stays the same as base
    assert rollups["cost_complete"] == base_rollups["cost_complete"]


def test_bom_csv_rows_and_qty_unit(tmp_path: Path) -> None:
    """bom.csv gains one row per consumable with kind 'consumable', qty, and qty_unit column."""
    rollups: dict[str, Any] = {
        "top_assemblies": ["asm://top"],
        "structure": {
            "asm://top": [
                {
                    "level": 0,
                    "uri": "part://base",
                    "id": "base",
                    "name": "Base Part",
                    "kind": "custom",
                    "qty": 1,
                    "total_qty": 1,
                    "unit_cost": 10.0,
                    "ext_cost": 10.0,
                    "children": [],
                }
            ]
        },
        "consumables": [
            {
                "id": "cu-1p5-pvc",
                "name": "1.5 mm² PVC, 1.5 mm², PVC, 70 °C (H07V-K class)",
                "quantity": 1.7,
                "unit": "m",
                "unit_cost": None,
                "ext_cost": None,
                "domain": "electrical",
                "source": "",
            }
        ],
        "total_cost": 10.0,
        "cost_complete": False,
    }
    csv_path = tmp_path / "bom.csv"
    write_csv(csv_path, rollups)

    text = csv_path.read_text(encoding="utf-8")
    table, _, _ = text.partition("\n\n")
    reader = list(csv.DictReader(table.splitlines()))

    assert list(reader[0].keys()) == COLUMNS
    assert COLUMNS[-1] == "qty_unit"

    # Part row
    part_row = reader[0]
    assert part_row["id"] == "base"
    assert part_row["kind"] == "custom"
    assert part_row["qty_unit"] == ""

    # Consumable row
    consumable_row = reader[1]
    assert consumable_row["id"] == "cu-1p5-pvc"
    assert consumable_row["kind"] == "consumable"
    assert consumable_row["qty"] == "1.7"
    assert consumable_row["total_qty"] == "1.7"
    assert consumable_row["qty_unit"] == "m"
    assert consumable_row["unit_cost_usd"] == ""


def test_electrical_bom_lines_on_minimal_fixture() -> None:
    """electrical_bom_lines returns one BomLine per conductor on minimal electrical fixture."""
    product = load_product(MINIMAL)
    reads: list[str] = []

    def reader(key: str) -> Any:
        reads.append(key)
        return None

    lines = electrical_bom_lines(product, reader)
    assert len(lines) == 1
    bl = lines[0]
    assert bl.id == "cu-1p5-pvc"
    assert bl.domain == "electrical"
    assert bl.unit == "m"
    assert bl.quantity == 1.7  # 0.4 + 0.4 + 0.2 + 0.2 + 0.5
    assert bl.unit_cost is None
    assert "1.5 mm² PVC" in bl.name
    assert "1.5 mm²" in bl.name
    assert "PVC, 70 °C (H07V-K class)" in bl.name


def test_electrical_bom_lines_missing_wire_length(tmp_path: Path) -> None:
    """Missing wire length makes quantity None."""
    root = copy_product(MINIMAL, tmp_path / "min_missing", git=False)
    # Remove length from one connection
    circuit_yaml = root / "model" / "electrical" / "circuits" / "heater.yaml"
    text = circuit_yaml.read_text(encoding="utf-8")
    circuit_yaml.write_text(text.replace("length: 0.5 m, ", ""), encoding="utf-8")

    product = load_product(root)
    lines = electrical_bom_lines(product, lambda k: None)
    assert len(lines) == 1
    assert lines[0].quantity is None


def test_compute_rollups_on_electrical_minimal(tmp_path: Path) -> None:
    """compute_rollups picks up electrical consumables from the registered electrical domain."""
    product = load_product(MINIMAL)
    rollups = compute_rollups(product)

    assert "consumables" in rollups
    assert len(rollups["consumables"]) == 1
    c = rollups["consumables"][0]
    assert c["id"] == "cu-1p5-pvc"
    assert c["quantity"] == 1.7
    assert c["unit"] == "m"
    assert c["unit_cost"] is None
    assert c["domain"] == "electrical"
    # Unpriced cable makes cost_complete False
    assert rollups["cost_complete"] is False

    csv_path = tmp_path / "bom.csv"
    write_csv(csv_path, rollups)
    table, _, _ = csv_path.read_text(encoding="utf-8").partition("\n\n")
    rows = list(csv.DictReader(table.splitlines()))

    cable_row = next(r for r in rows if r["id"] == "cu-1p5-pvc")
    assert cable_row["kind"] == "consumable"
    assert cable_row["qty"] == "1.7"
    assert cable_row["qty_unit"] == "m"
