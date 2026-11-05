"""Tests for mechanical domain interface kinds (milestone M2b, S-203).

Verifies the registration, spec validation, per-party hole cutting, checks,
and build integration for threaded-insert, wood-screw-pattern, t-slot-joint,
and hinge-pin interface kinds.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from napkin2factory.core.checks.interface import check_interface
from napkin2factory.core.graph.runner import run_build
from napkin2factory.core.loader import load_product, validate
from napkin2factory.core.model.interfaces import BoltPatternSpec
from napkin2factory.core.registry import registry
from napkin2factory.core.units import mm
from napkin2factory.core.uris import Uri
from napkin2factory.core.vcs import Vcs
from napkin2factory.domains.mechanical.interfaces import (
    HingePinSpec,
    ThreadedInsertSpec,
    TSlotSpec,
    WoodScrewSpec,
    check_hinge_pin,
    check_t_slot,
    check_threaded_insert,
    check_wood_screw,
)

pytestmark = pytest.mark.xdist_group("test_mechanical_interface_kinds")


def test_mechanical_interface_kinds_registered() -> None:
    """The four interface kinds are registered through the mechanical domain."""
    kinds = registry().interface_kinds()
    for name in ("threaded-insert", "wood-screw-pattern", "t-slot-joint", "hinge-pin"):
        assert name in kinds, f"interface kind {name!r} not registered"

    assert issubclass(kinds["threaded-insert"].spec, BoltPatternSpec)
    assert issubclass(kinds["wood-screw-pattern"].spec, BoltPatternSpec)
    assert issubclass(kinds["t-slot-joint"].spec, BoltPatternSpec)
    assert issubclass(kinds["hinge-pin"].spec, BoltPatternSpec)


def test_threaded_insert_spec_holes_and_hardware() -> None:
    """ThreadedInsertSpec gives clearance hole to passing party and bore to insert_part."""
    spec = ThreadedInsertSpec(
        thread="M8",
        insert_length="12 mm",
        insert_part="part://board",
        diameter="9 mm",
        bore_diameter="10 mm",
    )
    assert mm(spec.hole_for("part://tab")) == pytest.approx(9.0)
    assert mm(spec.hole_for("part://board")) == pytest.approx(10.0)
    assert mm(spec.hole_for("board")) == pytest.approx(10.0)


def test_threaded_insert_spec_derived_clearance_and_bore() -> None:
    """ThreadedInsertSpec derives clearance and bore from metric thread when omitted."""
    spec = ThreadedInsertSpec(
        thread="M6",
        insert_length="10 mm",
        insert_part="part://plastic-boss",
    )
    assert mm(spec.diameter) == pytest.approx(6.6)
    assert mm(spec.hole_for("part://cover")) == pytest.approx(6.6)
    assert mm(spec.hole_for("part://plastic-boss")) == pytest.approx(8.0)


def test_wood_screw_spec_holes() -> None:
    """WoodScrewSpec gives clearance hole to passing party and pilot hole to wood_part."""
    spec = WoodScrewSpec(
        screw_size="#8",
        pilot_diameter="2.8 mm",
        wood_part="part://shelf",
        diameter="4.5 mm",
    )
    assert mm(spec.hole_for("part://bracket")) == pytest.approx(4.5)
    assert mm(spec.hole_for("part://shelf")) == pytest.approx(2.8)
    assert mm(spec.hole_for("shelf")) == pytest.approx(2.8)


def test_t_slot_spec_holes_and_hardware() -> None:
    """TSlotSpec gives clearance hole to bracket and no hole to slot_part; lists t-nut."""
    spec = TSlotSpec(
        slot_part="part://extrusion",
        diameter="5.5 mm",
        fastener="part://m5-screw",
        tnut="part://m5-tnut",
    )
    assert mm(spec.hole_for("part://bracket")) == pytest.approx(5.5)
    assert spec.hole_for("part://extrusion") is None
    assert spec.hole_for("extrusion") is None

    items = spec.hardware_items()
    assert len(items) == 2
    parts = {str(item.part): item.per_hole for item in items}
    assert parts == {"part://m5-screw": 1, "part://m5-tnut": 1}


def test_hinge_pin_spec_holes() -> None:
    """HingePinSpec gives pin diameter to both parties."""
    spec = HingePinSpec(pin_diameter="6 mm", axis_note="vertical rotation")
    assert mm(spec.diameter) == pytest.approx(6.0)
    assert spec.count == 1
    assert mm(spec.hole_for("part://leaf-a")) == pytest.approx(6.0)
    assert mm(spec.hole_for("part://leaf-b")) == pytest.approx(6.0)


def _create_test_product(root: Path) -> Path:
    """Build a test product with steel tab, wood board, and extrusion."""
    (root / "model" / "parts").mkdir(parents=True, exist_ok=True)
    (root / "model" / "assemblies").mkdir(parents=True, exist_ok=True)
    (root / "model" / "interfaces").mkdir(parents=True, exist_ok=True)
    (root / "model" / "geometry").mkdir(parents=True, exist_ok=True)

    (root / "n2f.yaml").write_text(
        "schema: 1\n"
        "system: '>=0.7,<0.8'\n"
        "product:\n"
        "  id: ifaces-test\n"
        "  name: Mechanical Interfaces Test\n"
        "units: metric\n"
    )
    (root / "operator.yaml").write_text("persona: owner\n")
    (root / "model" / "parameters.yaml").write_text("parameters: {}\n")
    (root / "model" / "requirements.yaml").write_text("requirements: []\n")
    (root / "model" / "decisions.yaml").write_text("decisions: []\n")

    (root / "model" / "parts" / "tab.yaml").write_text(
        "id: tab\n"
        "rev: A\n"
        "name: Steel Tab\n"
        "kind: custom\n"
        "process: sheet-metal\n"
        "material: {name: mild steel}\n"
        "tolerance_class: ISO2768-m\n"
        "geometry: {kit: block, args: {length: 50 mm, width: 30 mm, height: 3 mm}}\n"
        "interfaces: [iface://tab-board, iface://tab-extrusion]\n"
        "cost: {unit: 1 USD, basis: estimate}\n"
        "lead_time: 1 d\n"
    )

    (root / "model" / "parts" / "board.yaml").write_text(
        "id: board\n"
        "rev: A\n"
        "name: Wood Board\n"
        "kind: custom\n"
        "process: cut-block\n"
        "material: {name: plywood}\n"
        "tolerance_class: ISO2768-m\n"
        "geometry: {kit: block, args: {length: 100 mm, width: 60 mm, height: 18 mm}}\n"
        "interfaces: [iface://tab-board]\n"
        "cost: {unit: 5 USD, basis: estimate}\n"
        "lead_time: 1 d\n"
    )

    (root / "model" / "parts" / "extrusion.yaml").write_text(
        "id: extrusion\n"
        "rev: A\n"
        "name: T-slot Extrusion\n"
        "kind: custom\n"
        "process: cut-block\n"
        "material: {name: aluminium}\n"
        "tolerance_class: ISO2768-m\n"
        "geometry: {kit: block, args: {length: 40 mm, width: 40 mm, height: 100 mm}}\n"
        "interfaces: [iface://tab-extrusion]\n"
        "cost: {unit: 10 USD, basis: estimate}\n"
        "lead_time: 1 d\n"
    )

    (root / "model" / "interfaces" / "tab-board.yaml").write_text(
        "id: tab-board\n"
        "kind: threaded-insert\n"
        "parties: [part://tab, part://board]\n"
        "description: Steel tab joined to wood board by threaded insert.\n"
        "frames:\n"
        "  part://tab: {origin: [0, 0, 0], normal: [0, 0, 1], x_axis: [1, 0, 0]}\n"
        "  part://board: {origin: [0, 0, 18], normal: [0, 0, 1], x_axis: [1, 0, 0]}\n"
        "spec:\n"
        "  pattern: rect\n"
        "  count: 1\n"
        "  thread: M8\n"
        "  insert_length: 12 mm\n"
        "  insert_part: part://board\n"
        "  diameter: 9 mm\n"
        "  bore_diameter: 10 mm\n"
    )

    (root / "model" / "interfaces" / "tab-extrusion.yaml").write_text(
        "id: tab-extrusion\n"
        "kind: t-slot-joint\n"
        "parties: [part://tab, part://extrusion]\n"
        "description: Steel tab joined to t-slot extrusion.\n"
        "frames:\n"
        "  part://tab: {origin: [0, 0, 0], normal: [0, 0, 1], x_axis: [1, 0, 0]}\n"
        "  part://extrusion: {origin: [0, 0, 100], normal: [0, 0, 1], x_axis: [1, 0, 0]}\n"
        "spec:\n"
        "  pattern: rect\n"
        "  count: 1\n"
        "  slot_part: part://extrusion\n"
        "  diameter: 5.5 mm\n"
    )

    (root / "model" / "assemblies" / "kit.yaml").write_text(
        "id: kit\n"
        "rev: A\n"
        "name: Joint Kit\n"
        "geometry: {module: geometry/kit.py}\n"
        "children:\n"
        "  - {part: part://board, qty: 1}\n"
        "  - {part: part://tab, qty: 1}\n"
        "  - {part: part://extrusion, qty: 1}\n"
    )

    (root / "model" / "geometry" / "kit.py").write_text(
        "def build(P, I, parts):\n"
        "    from napkin2factory.geometry.assembly import AssemblyResult, place, place_by\n"
        "    res = AssemblyResult()\n"
        "    res.add(place('part://board', parts['board']))\n"
        "    res.add(place_by(I, res, 'tab-board', 'part://tab', parts['tab']))\n"
        "    res.add(place_by(I, res, 'tab-extrusion', 'part://extrusion', parts['extrusion']))\n"
        "    return res\n"
    )

    Vcs(root).init()
    return root


def test_threaded_insert_and_t_slot_build_and_check(tmp_path: Path) -> None:
    """Test tmp product builds: wood part gets bore, steel gets clearance, extrusion uncut."""
    root = _create_test_product(tmp_path / "product")

    # 1. Validate
    prod, problems = validate(root)
    assert prod is not None
    assert not problems.errors, [str(p) for p in problems.errors]

    # 2. Build
    product = load_product(root)
    run_build(product, render=False, quiet=True)

    # 3. Read features.json
    build_dir = root / "build"
    board_feats = json.loads((build_dir / "parts" / "board" / "features.json").read_text())
    tab_feats = json.loads((build_dir / "parts" / "tab" / "features.json").read_text())
    ext_feats = json.loads((build_dir / "parts" / "extrusion" / "features.json").read_text())

    # Wood board hole is the bore diameter (10 mm)
    board_pats = [p for p in board_feats["patterns"] if p["interface"] == "iface://tab-board"]
    assert len(board_pats) == 1
    assert board_pats[0]["diameter"] == pytest.approx(10.0)

    # Steel tab hole for tab-board is the clearance diameter (9 mm)
    tab_tb_pats = [p for p in tab_feats["patterns"] if p["interface"] == "iface://tab-board"]
    assert len(tab_tb_pats) == 1
    assert tab_tb_pats[0]["diameter"] == pytest.approx(9.0)

    # Steel tab hole for tab-extrusion is 5.5 mm
    tab_te_pats = [p for p in tab_feats["patterns"] if p["interface"] == "iface://tab-extrusion"]
    assert len(tab_te_pats) == 1
    assert tab_te_pats[0]["diameter"] == pytest.approx(5.5)

    # T-slot extrusion gets NO hole (leaves extrusion uncut)
    ext_te_pats = [p for p in ext_feats["patterns"] if p["interface"] == "iface://tab-extrusion"]
    assert len(ext_te_pats) == 0
    assert not any(h.get("interface") == "iface://tab-extrusion" for h in ext_feats["holes"])

    # 4. Interface checks pass
    rep_tb = check_interface(product, product.interfaces["tab-board"], build_dir)
    assert rep_tb.status == "pass", rep_tb.message
    assert rep_tb.parties["part://board"]["diameter"] == pytest.approx(10.0)
    assert rep_tb.parties["part://tab"]["diameter"] == pytest.approx(9.0)
    assert "threaded insert into Wood Board (plywood)" in rep_tb.message

    rep_te = check_interface(product, product.interfaces["tab-extrusion"], build_dir)
    assert rep_te.status == "pass", rep_te.message
    assert rep_te.parties["part://extrusion"]["status"] == "pass"
    assert rep_te.parties["part://extrusion"]["why"] == "no holes cut (by spec)"
    assert "t-slot joint on T-slot Extrusion" in rep_te.message


def test_wrong_material_fails_threaded_insert_check(tmp_path: Path) -> None:
    """Threaded insert check fails when receiving part is metal, naming material and fix."""
    root = _create_test_product(tmp_path / "product")
    board_yaml = root / "model" / "parts" / "board.yaml"
    board_yaml.write_text(board_yaml.read_text().replace("name: plywood", "name: mild steel"))

    product = load_product(root)
    run_build(product, render=False, quiet=True)

    rep = check_interface(product, product.interfaces["tab-board"], root / "build")
    assert rep.status == "fail"
    assert "mild steel" in rep.message.lower()
    assert "threaded inserts require a wood or plastic receiving part" in rep.message
    assert "change Wood Board's material or use a bolt pattern" in rep.message


def test_threaded_insert_missing_party() -> None:
    """check_threaded_insert fails when insert_part is not in parties."""

    class FakeIface:
        parties = [Uri.parse("part://a"), Uri.parse("part://b")]
        spec = ThreadedInsertSpec(
            thread="M8",
            insert_length="12 mm",
            insert_part="part://c",
        )

    res = check_threaded_insert(
        type("P", (), {"parts": {}, "assemblies": {}})(), FakeIface(), Path("/tmp")
    )
    assert res["status"] == "fail"
    assert "not among the joint parties" in res["message"]


def test_wrong_material_fails_wood_screw_check() -> None:
    """Wood screw check fails when receiving part is metal, naming material and fix."""

    class FakePart:
        name = "Steel Bracket"
        material = type("Material", (), {"name": "mild steel", "spec": None})()

    class FakeIface:
        parties = [Uri.parse("part://cover"), Uri.parse("part://bracket")]
        spec = WoodScrewSpec(
            screw_size="#8",
            pilot_diameter="2.8 mm",
            wood_part="part://bracket",
        )

    class FakeProduct:
        parts = {"bracket": FakePart(), "cover": FakePart()}
        assemblies: dict[str, Any] = {}

    res = check_wood_screw(FakeProduct(), FakeIface(), Path("/tmp"))
    assert res["status"] == "fail"
    assert "mild steel" in res["message"]
    assert "wood screws require a wood or plastic receiving part" in res["message"]
    assert "change Steel Bracket's material or use a bolt pattern" in res["message"]


def test_tslot_warns_on_non_extrusion() -> None:
    """T-slot joint warns when slot part is not extrusion-cut and profile is not t-slot."""

    class FakePart:
        name = "Bracket"
        process = "sheet-metal"
        geometry = None

    class FakeIface:
        parties = [Uri.parse("part://plate"), Uri.parse("part://bracket")]
        spec = TSlotSpec(
            slot_part="part://bracket",
            diameter="5.5 mm",
        )

    class FakeProduct:
        parts = {"bracket": FakePart(), "plate": FakePart()}
        assemblies: dict[str, Any] = {}

    res = check_t_slot(FakeProduct(), FakeIface(), Path("/tmp"))
    assert res["status"] == "warn"
    assert "process is 'sheet-metal' and profile is not t-slot" in res["message"]
    assert "t-slot joints expect an extrusion-cut t-slot member" in res["message"]


def test_hinge_pin_check() -> None:
    """Hinge pin check requires exactly two parties."""

    class FakeProduct:
        parts: dict[str, Any] = {}
        assemblies: dict[str, Any] = {}

    class FakeIface2:
        parties = [Uri.parse("part://leaf-a"), Uri.parse("part://leaf-b")]
        spec = HingePinSpec(pin_diameter="6 mm")

    res2 = check_hinge_pin(FakeProduct(), FakeIface2(), Path("/tmp"))
    assert res2["status"] == "pass"
    assert "hinge pin joins" in res2["message"]

    class FakeIface3:
        parties = [
            Uri.parse("part://a"),
            Uri.parse("part://b"),
            Uri.parse("part://c"),
        ]
        spec = HingePinSpec(pin_diameter="6 mm")

    res3 = check_hinge_pin(FakeProduct(), FakeIface3(), Path("/tmp"))
    assert res3["status"] == "fail"
    assert "a hinge pin joins exactly two parties, but 3 were given" in res3["message"]
