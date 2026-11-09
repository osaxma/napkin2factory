"""Tests for the support check: every part is held up (B-0328, S-346)."""

from __future__ import annotations

import json
from pathlib import Path

from build123d import Box, export_step

from napkin2factory.core.checks.evaluators import EvalContext
from napkin2factory.core.checks.modules import RowModules
from napkin2factory.core.domain import StageContext
from napkin2factory.core.loader import load_product
from napkin2factory.domains.mechanical.support import (
    _boxes_connected,
    check_support,
    support_stage,
)
from tests.conftest import EXAMPLES, copy_product


def test_table_support_passes(tmp_path: Path) -> None:
    """The prebuilt table passes the support check."""
    root = copy_product(EXAMPLES / "table", tmp_path / "table", prebuilt=True)
    prod = load_product(root)

    rep = check_support(prod, "table", root / "build")
    assert rep.ok is True
    assert len(rep.unsupported) == 0
    assert len(rep.ground) == 1
    assert "part://apron-frame#1" in rep.ground

    sctx = StageContext(
        product=prod,
        build_dir=root / "build",
        ectx=EvalContext(prod, root / "build"),
        keep=lambda aid: True,
        within=None,
        modules=RowModules(prod),
    )
    res = support_stage(sctx)
    assert len(res) == 1
    assert res[0].id == "support://table"
    assert res[0].kind == "support"
    assert res[0].title == "every part is held up"
    assert res[0].status == "pass"


def test_table_shortened_legs_fails(tmp_path: Path) -> None:
    """Shortened legs where rails sit on legs' top edges only fails and names top and rails."""
    root = copy_product(EXAMPLES / "table", tmp_path / "short_table", git=False)

    (root / "model/parts/table-leg.yaml").write_text(
        "id: table-leg\nname: Table leg\nkind: custom\ngeometry: none\n"
    )
    (root / "model/parts/top-rails.yaml").write_text(
        "id: top-rails\nname: Top rails\nkind: custom\ngeometry: none\n"
    )

    (root / "build/parts/table-leg").mkdir(parents=True)
    (root / "build/parts/top-rails").mkdir(parents=True)
    (root / "build/parts/top-board").mkdir(parents=True, exist_ok=True)
    (root / "build/assemblies/table").mkdir(parents=True, exist_ok=True)

    # Leg ends at 735 mm; rail sits between leg lines at 735 to 824 mm; top sits on rail
    export_step(Box(50, 50, 735), str(root / "build/parts/table-leg/model.step"))
    export_step(Box(600, 50, 89), str(root / "build/parts/top-rails/model.step"))
    export_step(Box(700, 100, 30), str(root / "build/parts/top-board/model.step"))

    instances = [
        {
            "node": "part://table-leg#1",
            "uri": "part://table-leg",
            "translation": [0.0, 0.0, 367.5],
            "rotation": [0.0, 0.0, 0.0, 1.0],
        },
        {
            "node": "part://top-rails#1",
            "uri": "part://top-rails",
            "translation": [325.0, 0.0, 779.5],
            "rotation": [0.0, 0.0, 0.0, 1.0],
        },
        {
            "node": "part://top-board#1",
            "uri": "part://top-board",
            "translation": [325.0, 0.0, 839.0],
            "rotation": [0.0, 0.0, 0.0, 1.0],
        },
    ]
    (root / "build/assemblies/table/instances.json").write_text(json.dumps(instances))

    prod = load_product(root)
    rep = check_support(prod, "table", root / "build")
    assert rep.ok is False
    assert "part://top-rails#1" in rep.unsupported
    assert "part://top-board#1" in rep.unsupported
    assert "Top rails" in rep.unsupported_titles
    assert "Oak tabletop" in rep.unsupported_titles

    sctx = StageContext(
        product=prod,
        build_dir=root / "build",
        ectx=EvalContext(prod, root / "build"),
        keep=lambda aid: True,
        within=None,
        modules=RowModules(prod),
    )
    res = support_stage(sctx)
    assert len(res) == 1
    assert res[0].status == "fail"
    msg = res[0].message
    assert "Top rails is not held up: it touches nothing that leads to the floor" in msg
    assert "Oak tabletop is not held up: it touches nothing that leads to the floor" in msg


def test_connection_rule_boxes() -> None:
    """Connection rule: face touch connects, edge touch does not, 10 mm interface connects."""
    box_a = ((0.0, 0.0, 0.0), (10.0, 10.0, 10.0))

    # Face touch connects (gap 0 mm <= 0.5 mm, overlap area 100 mm² >= 1 mm²)
    box_face = ((0.0, 0.0, 10.0), (10.0, 10.0, 20.0))
    assert _boxes_connected(box_a, box_face, has_interface=False) is True

    # Edge touch does not connect (overlap area along edge is 0 mm² < 1 mm²)
    box_edge = ((10.0, 0.0, 10.0), (20.0, 10.0, 20.0))
    assert _boxes_connected(box_a, box_edge, has_interface=False) is False

    # 10 mm gap connects only with a declared interface
    box_gap = ((0.0, 0.0, 20.0), (10.0, 10.0, 30.0))
    assert _boxes_connected(box_a, box_gap, has_interface=False) is False
    assert _boxes_connected(box_a, box_gap, has_interface=True) is True

    # More than 30 mm gap does not connect even with declared interface
    box_far = ((0.0, 0.0, 45.0), (10.0, 10.0, 55.0))
    assert _boxes_connected(box_a, box_far, has_interface=True) is False
