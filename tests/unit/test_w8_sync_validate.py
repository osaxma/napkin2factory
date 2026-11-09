"""Wave 8: n2f_sync returns a failed validate's problems whole (B-0325)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from napkin2factory.mcp.combined import ToolRunner
from tests.conftest import EXAMPLES, copy_product
from tests.unit.test_mcp import Fake


def test_sync_returns_failed_validate_problems_whole(tmp_path: Path) -> None:
    """When validate fails, n2f_sync gives problems with file and field whole."""
    root = copy_product(EXAMPLES / "table", tmp_path / "table", prebuilt=True)

    # 1. Misspell one parameter key in model/parameters.yaml
    pfile = root / "model" / "parameters.yaml"
    pfile.write_text(pfile.read_text().replace("unit: mm", "unitt: mm", 1))

    # 2. Remove one required part field in model/parts/top-board.yaml
    part_file = root / "model" / "parts" / "top-board.yaml"
    lines = [line for line in part_file.read_text().splitlines() if not line.startswith("name:")]
    part_file.write_text("\n".join(lines) + "\n")

    runner = ToolRunner(root)
    res = asyncio.run(runner.call("n2f_sync", {}))
    assert res.is_error
    assert res.exit_code == 1

    body = json.loads(res.text)
    assert not body["ok"]
    assert "problems" in body
    assert len(body["problems"]) == 2

    p0 = body["problems"][0]
    assert p0["file"] == "model/parameters.yaml"
    assert p0["field"] == "parameters.table-length.unitt"
    assert p0["message"] == "Extra inputs are not permitted"
    assert "parameters.table-length.unitt" in p0["fix"]

    p1 = body["problems"][1]
    assert p1["file"] == "model/parts/top-board.yaml"
    assert p1["field"] == "name"
    assert p1["message"] == "Field required"
    assert "name" in p1["fix"]

    # next.say names the first problem's file
    say = body["next"]["say"]
    assert p0["file"] in say
    assert p0["field"] in say
    assert say.endswith("then call n2f_sync again.")


def test_sync_caps_problems_at_twenty(tmp_path: Path) -> None:
    """More than 20 problems are capped at 20 with a 'more' count."""
    raw_problems = [
        {
            "severity": "error",
            "rule": "schema",
            "file": str(tmp_path / "model" / f"part_{i}.yaml"),
            "subject": f"part_{i}",
            "message": f"field_{i}: Field required",
            "hint": f"add field_{i}",
        }
        for i in range(25)
    ]
    validate_data = {"ok": False, "problems": raw_problems}
    fake = Fake({("validate",): (1, validate_data)})
    runner = ToolRunner(tmp_path, steps=fake)
    res = asyncio.run(runner.call("n2f_sync", {}))
    body = json.loads(res.text)
    assert not body["ok"]
    assert len(body["problems"]) == 20
    assert body["more"] == 5
    assert body["problems"][0]["field"] == "field_0"
    assert body["problems"][0]["file"] == "model/part_0.yaml"
    assert "model/part_0.yaml" in body["next"]["say"]
