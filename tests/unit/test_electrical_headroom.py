"""v0.6 M5 follow-up: the supply-headroom choice on a European 16 A supply, the dedicated pick made.

B-0151: the calc kit's circuit table now holds cited EU classes above 16 A, so a load above
half of a European 16 A supply raises E11's choice (both options), not a lone warning.
B-0149: ``dedicated: true`` on the supply is the ``dedicated`` pick made in the model: the
row passes on the model itself, so after ``n2f decide … --pick dedicated`` and the field set,
``n2f status`` no longer says the choice is "not yet in the design" (S-171).
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from napkin2factory.calckit import power
from napkin2factory.cli.app import app
from napkin2factory.core.checks.choices import UNAPPLIED
from napkin2factory.core.graph.runner import run_build
from napkin2factory.core.loader import load_product
from napkin2factory.core.units import Quantity as Q
from napkin2factory.domains.electrical.model import Supply
from tests.conftest import copy_product
from tests.unit.test_electrical_checks import HEADROOM, HEATER, MINIMAL, _edit, _rows

SUPPLY = "model/electrical/supply.yaml"


def _eu16(tmp_path: Path, name: str = "hb", *, git: bool = False) -> Path:
    """The minimal heated box on a European 16 A supply with a 2500 W heater (10.9 A)."""
    root = copy_product(MINIMAL, tmp_path / name, git=git)
    _edit(root, HEATER, "power: 500 W", "power: 2500 W")
    _edit(root, "model/parameters.yaml", "{value: 10, unit: A", "{value: 16, unit: A")
    _edit(
        root,
        SUPPLY,
        '"the 10 A breaker of the socket circuit", rating: 10 A',
        ('"the 16 A breaker of the socket circuit", rating: 16 A'),
    )
    return root


def _dedicated(root: Path) -> None:
    _edit(root, SUPPLY, "region: EU\n", "region: EU\ndedicated: true\n")


def test_the_table_holds_cited_eu_classes_above_16_a() -> None:
    rows = {r["label"]: r for r in power.circuit_rows("EU")}
    assert {"20 A dedicated circuit", "32 A dedicated circuit (IEC 60309 32 A outlet)"} <= set(rows)
    for label in ("20 A dedicated circuit", "32 A dedicated circuit (IEC 60309 32 A outlet)"):
        assert rows[label]["verify"] is True and "IEC 60898-1" in rows[label]["source"]
    # a current a 16 A class cannot carry with headroom now finds the 20 A class
    assert power.circuit_class("EU", Q(15, "A")).label == "20 A dedicated circuit"


def test_a_eu_16_a_supply_raises_the_choice_with_both_options(tmp_path: Path) -> None:
    row = _rows(_eu16(tmp_path))[HEADROOM]
    assert row.status == "choice"
    assert row.detail["blocks"] == "none"
    assert row.message.startswith("10.9 A of the 16 A circuit")
    opts = {o["id"]: o for o in row.detail["options"]}
    assert list(opts) == ["dedicated", "larger"]
    assert opts["dedicated"]["summary"] == (
        "a dedicated 16 A circuit; nothing else may be plugged into it"
    )
    assert opts["dedicated"]["what_it_takes"] == (
        "the electrician fits or confirms a 16 A circuit that serves this product alone, the "
        "supply says so (`dedicated: true` in the wiring's supply file), and the manual says "
        "nothing else may be plugged into it"
    )
    assert opts["larger"]["summary"] == (
        "a 20 A dedicated circuit: room for a bigger load later; the electrician fits thicker cable"
    )
    assert opts["larger"]["what_it_takes"].startswith("the supply's rating becomes 20 A")


def test_a_dedicated_supply_passes_the_row(tmp_path: Path) -> None:
    root = _eu16(tmp_path)
    _dedicated(root)
    row = _rows(root)[HEADROOM]
    assert row.status == "pass"
    assert row.message == (
        "10.9 A of the 16 A circuit, more than half of it; the circuit serves this product "
        "alone, so nothing else may be plugged into it (the electrician confirms)."
    )
    assert row.detail["dedicated"] is True


def test_dedicated_is_optional_and_off_by_default() -> None:
    assert Supply(voltage="230 V").dedicated is False
    assert Supply(voltage="230 V", dedicated=True).dedicated is True


def test_no_larger_class_says_how_to_make_the_circuit_dedicated(tmp_path: Path) -> None:
    root = copy_product(MINIMAL, tmp_path / "au")
    _edit(root, HEATER, "power: 500 W", "power: 2500 W")
    _edit(root, SUPPLY, "region: EU", "region: AU")
    _edit(root, "model/parameters.yaml", "{value: 10, unit: A", "{value: 20, unit: A")
    row = _rows(root)[HEADROOM]
    assert row.status == "warn"
    assert "`dedicated: true`" in row.message
    _edit(root, SUPPLY, "region: AU\n", "region: AU\ndedicated: true\n")
    assert _rows(root)[HEADROOM].status == "pass"


def _status(root: Path) -> str:
    r = CliRunner().invoke(app, ["status", "--dir", str(root)])
    assert r.exit_code == 0, r.output
    return r.output


def test_decided_dedicated_then_made_is_in_the_design(tmp_path: Path) -> None:
    root = _eu16(tmp_path, git=True)
    run_build(load_product(root), render=False, quiet=True)
    r = CliRunner().invoke(
        app,
        ["decide", HEADROOM, "--pick", "dedicated", "--by", "Ada", "--dir", str(root), "--json"],
    )
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)["status"] == "pass"
    run_build(load_product(root), render=False, quiet=True)
    assert "not yet in the design" in _status(root)  # decided, the model not yet changed
    _dedicated(root)
    run_build(load_product(root), render=False, quiet=True)
    said = _status(root)
    assert "not yet in the design" not in said and UNAPPLIED not in said
    assert _rows(root)[HEADROOM].status == "pass"
    choices = root / "build" / "checks" / "choices.json"
    listed = json.loads(choices.read_text(encoding="utf-8")) if choices.exists() else []
    assert HEADROOM not in json.dumps(listed)
