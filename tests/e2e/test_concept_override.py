"""M4 (v0.2): a red card promoted with --override, and its alcove requirement fails (N8).

Split from test_concept_promote.py so it runs on its own test worker (S-080); same fixture.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.conftest import EXAMPLES, copy_product
from tests.e2e.test_concept_promote import _check, _req, _run
from tests.unit.test_promote import overlay_cards


@pytest.fixture
def product(tmp_path: Path) -> Path:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", git=True)
    overlay_cards(root)
    return root


def test_red_card_overridden_and_its_alcove_requirement_fails(product: Path) -> None:
    root = product
    _run("concept", "build", "C-004", "--no-render", cwd=root)
    refused = _run("concept", "promote", "C-004", "--override", cwd=root, code=3)
    assert "--override needs --reason" in refused.stderr
    res = json.loads(
        _run(
            "concept",
            "promote",
            "C-004",
            "--override",
            "--reason",
            "the owner will widen the alcove",
            "--by",
            "owner",
            "--json",
            cwd=root,
        ).stdout
    )
    assert res["dec"] == "DEC-002" and res["override"] is True
    # the alcove row and the open door's own row (B-0023)
    assert [r["uri"] for r in res["requirements"]] == ["req://REQ-004", "req://REQ-005"]
    assert res["requirements"][0]["verify"] == {
        "kind": "geometry_prop",
        "target": "asm://bracket#props.bbox.x",
        "op": "<=",
        "value": "100 mm",
    }
    # no form requirement applies, and none needs a note (review gate B, B4)
    assert not any("form requirement" in n for n in res["notes"])
    _run("validate", cwd=root)
    _run("build", "--no-render", cwd=root)
    data = _check(root, code=2)
    row = _req(data, "REQ-004")
    assert row["status"] == "fail" and row["message"] == "bbox.x = 120 mm <= 100 mm"
    assert _req(data, "REQ-005")["status"] == "pass"  # the door itself did not change
