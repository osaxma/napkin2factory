"""An agent's loop through the seven MCP tools on a real product (S-327, M8).

Driven only through ``ToolRunner.call``, as the protocol handler does. The suite sets
``N2F_NO_ENGINE=1``, so every step runs as a cold process; the warm path has its own test
(``tests/unit/test_engine_mcp.py``). End to end, so it runs in ``make check``, not in the land
gate.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from napkin2factory.mcp.combined import SUMMARY_LIMIT, ToolRunner
from tests.conftest import EXAMPLES, copy_product


def _call(runner: ToolRunner, _tool: str, **args: Any) -> dict[str, Any]:
    res = asyncio.run(runner.call(_tool, args))
    assert len(res.text) < SUMMARY_LIMIT, (_tool, len(res.text))
    body: dict[str, Any] = json.loads(res.text)
    assert body["ok"] == (not res.is_error), res.text[:400]
    return body


def test_sync_then_a_quick_change_and_its_undo(tmp_path: Path) -> None:
    product = copy_product(EXAMPLES / "table", tmp_path / "table", prebuilt=True)
    params = product / "model" / "parameters.yaml"
    original = params.read_text(encoding="utf-8")
    runner = ToolRunner(product)

    synced = _call(runner, "n2f_sync")
    assert [s["command"].split()[1] for s in synced["steps"]] == [
        "validate",
        "lint",
        "build",
        "check",
        "status",
    ]
    assert synced["gates"] and synced["next"]
    assert all(s["engine"] == "cold" for s in synced["steps"])

    quick = _call(
        runner,
        "n2f_ecr",
        action="quick",
        set=["param://table-height=770 mm"],
        reason="a taller table",
    )
    assert [s["command"].split()[1] for s in quick["steps"]] == ["status", "ecr", "status"]
    assert quick["delta"]["mass"]["delta"] > 0  # a taller table weighs more
    assert quick["next"] == {"tool": "n2f_sync", "arguments": {}}
    assert params.read_text(encoding="utf-8") != original

    # one undo takes back the whole change request: the saved record, then the edit
    # (`ecr quick` leaves the checkpoints "Started", "set ..."; undo first saves the record)
    undone = _call(runner, "n2f_ecr", action="undo")
    assert len(undone["undid"]) == 2 and undone["undid"][0].startswith("ECR-001")
    assert params.read_text(encoding="utf-8") == original
    assert undone["after"]["gates_open"] == quick["before"]["gates_open"]
    assert undone["next"] == {"tool": "n2f_sync", "arguments": {}}

    redone = _call(runner, "n2f_ecr", action="redo")
    assert len(redone["redid"]) == 2
    assert params.read_text(encoding="utf-8") != original

    refused = asyncio.run(runner.call("n2f_ecr", {"action": "quick", "set": ["param://nope=1"]}))
    assert refused.is_error
    assert json.loads(refused.text)["next"]


def test_init_product_makes_a_product_in_an_empty_folder(tmp_path: Path) -> None:
    folder = tmp_path / "thing"
    folder.mkdir()
    runner = ToolRunner(folder)
    made = _call(runner, "n2f_init_product", name="Thing", region="EU", units="metric")
    assert (folder / "n2f.yaml").is_file()
    assert (folder / "AGENTS.md").is_file() and (folder / "roles" / "pm.md").is_file()
    assert made["read_first"] == ["AGENTS.md", "roles/pm.md"] and made["files"]
    again = asyncio.run(
        runner.call("n2f_init_product", {"name": "T", "region": "EU", "units": "metric"})
    )
    assert again.is_error and json.loads(again.text)["next"]["tool"] == "n2f_sync"
