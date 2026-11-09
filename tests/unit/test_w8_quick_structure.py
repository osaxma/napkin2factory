"""Wave 8: a quick change shows the structure figures first (B-0327, S-345)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from napkin2factory.core.loader import load_product
from napkin2factory.ecr import live, live_text
from napkin2factory.mcp.combined import ToolRunner
from tests.conftest import EXAMPLES, copy_product


def test_quick_change_shows_structure_figures_first_live(tmp_path: Path) -> None:
    """A quick change on table puts structure requirements first with figures."""
    root = copy_product(EXAMPLES / "table", tmp_path / "table", prebuilt=True)
    product = load_product(root)
    out = live.quick(product, sets=["param://table-length=1800mm"])

    impact = out["impact"]
    assert impact["has_structure"] is True
    lines = impact["requirement_lines"]
    assert len(lines) >= 7

    # Sag requirement is first with before and after figures
    first = lines[0]
    assert first.startswith("Sag under the centre load:")
    assert "1.70518 mm" in first or "1.71 mm" in first
    assert "→" in first
    assert "2.50058 mm" in first or "2.5 mm" in first
    assert "against 2.5 mm" in first
    assert "(fails)" in first

    # Other structure requirements follow
    struct_titles = [
        "Sag under the centre load",
        "Long-term sag",
        "Strength of the spanning members",
        "Leg buckling",
        "The table does not tip over",
        "Racking sway",
        "Welded corners",
    ]
    for i, title in enumerate(struct_titles):
        assert lines[i].startswith(f"{title}:")
        assert "→" in lines[i]
        assert "against" in lines[i]
        assert "(passes)" in lines[i] or "(fails)" in lines[i]

    # Non-structure requirements come after structure ones
    non_struct_lines = lines[len(struct_titles) :]
    assert any("Top length" in line for line in non_struct_lines)

    # Markdown text format
    text = out["text"]
    assert "## Requirements" in text
    assert f"- {first}" in text


def test_quick_change_mcp_summary_keeps_structure_lines(tmp_path: Path) -> None:
    """n2f_ecr's summary keeps structure requirement lines first, whole, and capped at 10."""
    root = copy_product(EXAMPLES / "table", tmp_path / "table", prebuilt=True)
    runner = ToolRunner(root)

    res = asyncio.run(
        runner.call("n2f_ecr", {"action": "quick", "set": ["param://table-length=1800mm"]})
    )
    assert not res.is_error
    body = json.loads(res.text)
    assert body["ok"] is True

    reqs = body["requirements"]
    assert isinstance(reqs, list)
    assert len(reqs) <= 10

    first = reqs[0]
    assert first.startswith("Sag under the centre load:")
    assert "against 2.5 mm" in first
    assert "(fails)" in first
    # No clipping or ellipsis at the end of the line
    assert not first.endswith("…")


def test_product_without_structure_requirement(tmp_path: Path) -> None:
    """A product without structure checks warns that sag/tipping are not checked."""
    root = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", prebuilt=True, render=False)
    product = load_product(root)
    out = live.quick(product, sets=["param://bracket-width=70mm"])

    impact = out["impact"]
    assert impact["has_structure"] is False
    lines = impact["requirement_lines"]
    warn_line = "No structure requirement: the sag and tipping are not checked."
    assert lines[0] == warn_line
    assert f"- {warn_line}" in out["text"]

    nxt = live_text.next_step(impact, out["ecr"], approve_first=False)
    assert nxt == "ask the owner for the load and add a structure requirement"

    root2 = copy_product(EXAMPLES / "bracket", tmp_path / "bracket2", prebuilt=True, render=False)
    runner = ToolRunner(root2)
    res = asyncio.run(
        runner.call("n2f_ecr", {"action": "quick", "set": ["param://bracket-width=70mm"]})
    )
    body = json.loads(res.text)
    assert body["ok"] is True
    assert body["requirements"][0] == warn_line
    assert body["next"] == {"say": "ask the owner for the load and add a structure requirement"}
