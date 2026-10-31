"""scripts/verify_list.py: the list of numbers still to be confirmed."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def vl() -> ModuleType:
    spec = importlib.util.spec_from_file_location("verify_list", REPO / "scripts/verify_list.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_list"] = mod
    spec.loader.exec_module(mod)
    return mod


def _tree(root: Path) -> None:
    data = root / "src/napkin2factory/calckit/data"
    data.mkdir(parents=True)
    (data / "widgets.yaml").write_text(
        "table: widgets\n"
        "rows:\n"
        "  - {name: sprocket, size: 3, verify: true, source: 'Widget handbook p. 4'}\n"
        "  - {name: cog, size: 5}\n"
        "  - {name: gear, size: 7, verify: false}\n"
    )
    model = root / "examples/gadget/model"
    model.mkdir(parents=True)
    (model / "decisions.yaml").write_text(
        "decisions:\n"
        "  - {id: DEC-001, title: Steel frame, verify: true}\n"
        "  - {id: DEC-002, title: Blue paint}\n"
    )
    (root / "DECISIONS.md").write_text(
        "# Decisions\n\n"
        "`[verify]` marks numbers to confirm (preamble, not listed).\n\n"
        "## Index\n\n"
        "| S-002 | Second | in force [verify]: index row, not listed |\n\n"
        "## S-001 — First (2026-01-01)\n\n"
        "Nothing to check here.\n\n"
        "## S-002 — Second (2026-01-02)\n\n"
        "The bolt torque is 12 N·m `[verify]` from the catalogue.\n"
        "Another plain line.\n"
    )


def test_tiny_tree_lists_exactly_the_marked_entries(vl: ModuleType, tmp_path: Path):
    _tree(tmp_path)
    assert vl.collect_table_rows(tmp_path) == [
        vl.TableRow("widgets.yaml", "sprocket", "Widget handbook p. 4")
    ]
    assert vl.collect_product_decisions(tmp_path) == [
        vl.ProductDecision("gadget", "DEC-001", "Steel frame")
    ]
    lines = vl.collect_tagged_lines(tmp_path)
    assert [(t.heading_id, t.text) for t in lines] == [
        ("S-002", "The bolt torque is 12 N·m `[verify]` from the catalogue.")
    ]
    out = vl.build_report(tmp_path)
    assert "| widgets.yaml | sprocket | Widget handbook p. 4 |" in out
    assert "| gadget | DEC-001 | Steel frame |" in out
    assert "### S-002" in out and "### S-001" not in out
    for absent in ("cog", "gear", "DEC-002", "Blue paint", "preamble", "index row"):
        assert absent not in out


def test_main_prints_for_root(vl: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    _tree(tmp_path)
    assert vl.main(["--root", str(tmp_path)]) == 0
    assert "sprocket" in capsys.readouterr().out


def test_trim_and_heading_label(vl: ModuleType):
    assert vl.trim("a  b\tc") == "a b c"
    cut = vl.trim("x" * 200)
    assert len(cut) == 120 and cut.endswith("…")
    assert vl.heading_label("S-064 — The calc kit (N4) (2026-10-31)") == "S-064"
    assert (
        vl.heading_label("Review gate 3 (engineering) — outcome") == "Review gate 3 (engineering)"
    )


def test_real_repo_smoke(vl: ModuleType):
    out = vl.build_report(REPO)
    assert "materials.yaml" in out
    assert "S-064" in out
