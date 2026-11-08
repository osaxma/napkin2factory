"""Tests for failed quick change handling and bare floats in checks (B-0322, S-336).

- Bare floats returned by calcs are converted to dimensionless quantities so requirement checks
  do not crash with AttributeError.
- When ecr quick fails after opening a request, it aborts the request itself and reports that the
  change was not made and nothing is left open, with a specific next step.
- When the self-abort itself fails, next names `n2f ecr abort <id>` (MCP: abort, ecr_id).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from napkin2factory.core.checks.calcs import run_calc
from napkin2factory.core.checks.engine import EvalContext
from napkin2factory.core.checks.evaluators import evaluate_requirement
from napkin2factory.core.loader import load_product
from napkin2factory.core.units import is_quantity
from napkin2factory.core.vcs import Vcs
from napkin2factory.ecr import live
from napkin2factory.mcp.combined import ToolRunner
from napkin2factory.mcp.tools import Step
from tests.conftest import n2f


def _make_minimal_product(
    root: Path, fail_on_change: bool = False, calc_float: float | None = None
) -> Path:
    """Create a minimal valid product repo with git tracking."""
    root.mkdir(parents=True, exist_ok=True)
    vcs = Vcs(root)
    vcs.init()
    (root / "n2f.yaml").write_text(
        "schema: 2\n"
        "system: '>=0.8,<0.9'\n"
        "product:\n"
        "  id: test-bench\n"
        "  name: Test Bench\n"
        "units: metric\n",
        encoding="utf-8",
    )
    (root / "model").mkdir()
    (root / "model" / "parameters.yaml").write_text(
        "parameters:\n  worktop-length: {value: 1000, unit: mm, description: Length}\n",
        encoding="utf-8",
    )
    (root / "model" / "calcs").mkdir()

    calc_val = calc_float if calc_float is not None else 2.5
    calc_body = f"def stress_ratio(P):\n    return float({calc_val})\n"
    (root / "model" / "calcs" / "bench.py").write_text(calc_body, encoding="utf-8")

    (root / "model" / "assemblies").mkdir()
    (root / "model" / "assemblies" / "workbench.yaml").write_text(
        "id: workbench\nname: Workbench\ngeometry: {module: geometry/bench.py}\n",
        encoding="utf-8",
    )
    (root / "model" / "geometry").mkdir()

    if fail_on_change:
        geo_body = (
            "def build(P, I, parts):\n"
            "    if P['worktop-length'].to('mm').magnitude > 1500:\n"
            "        raise ValueError('CNC bed exceeded (1500 mm)')\n"
            "    return None\n"
        )
    else:
        geo_body = "def build(P, I, parts):\n    return None\n"

    (root / "model" / "geometry" / "bench.py").write_text(geo_body, encoding="utf-8")

    req_target = "'asm://workbench#props.bbox.x'"
    (root / "model" / "requirements.yaml").write_text(
        "requirements:\n"
        "  - id: REQ-001\n"
        "    title: Stress ratio\n"
        "    statement: Safety factor exceeds 2.0.\n"
        "    category: performance\n"
        "    priority: must\n"
        "    verify: {kind: calc, target: 'calc://bench.stress_ratio', op: '>=', value: 2.0}\n"
        "  - id: REQ-002\n"
        "    title: Bounding box width\n"
        "    statement: Width at most 1600 mm.\n"
        "    category: geometry\n"
        "    priority: must\n"
        f"    verify: {{kind: geometry_prop, target: {req_target}, op: '<=', value: 1600 mm}}\n",
        encoding="utf-8",
    )
    (root / "changes").mkdir()
    vcs.snapshot("Initial product state")
    return root


class _FakeSteps:
    """Step runner using canned responses."""

    def __init__(self, answers: dict[tuple[str, ...], Any]) -> None:
        self.answers = answers

    async def run(self, argv: list[str]) -> Step:
        key = tuple(w for w in argv if not w.startswith("-"))
        for n in (2, 1):
            if key[:n] in self.answers:
                ans = self.answers[key[:n]]
                code, data = ans if isinstance(ans, tuple) else (0, ans)
                return Step(argv, code, json.dumps(data), "", "warm", 0.1)
        return Step(argv, 0, "{}", "", "warm", 0.1)


def test_bare_float_from_calc_is_read_as_dimensionless_quantity(tmp_path: Path) -> None:
    """Item 2: bare float from calc is read as quantity; requirement check evaluates ok."""
    root = _make_minimal_product(tmp_path / "prod", calc_float=2.5)
    product = load_product(root)

    # 1. run_calc returns dimensionless Quantity
    rec = run_calc(product, "calc://bench.stress_ratio")
    assert is_quantity(rec.value)
    assert str(rec.value.units) == "dimensionless"
    assert rec.value.magnitude == pytest.approx(2.5)
    assert hasattr(rec.value, "dimensionality")

    # 2. evaluate_requirement evaluates successfully without AttributeError
    ctx = EvalContext(product, root / "build")
    res = evaluate_requirement(ctx, product.requirements["REQ-001"])
    assert res.status == "pass"
    assert "2.5 >= 2" in res.message


def test_bare_float_failing_threshold_evaluates_without_crash(tmp_path: Path) -> None:
    """Item 2: bare float below threshold evaluates to fail properly."""
    root = _make_minimal_product(tmp_path / "prod", calc_float=1.5)
    product = load_product(root)

    ctx = EvalContext(product, root / "build")
    res = evaluate_requirement(ctx, product.requirements["REQ-001"])
    assert res.status == "fail"
    assert "1.5 >= 2" in res.message


def test_quick_failure_aborts_itself_cli_json(tmp_path: Path) -> None:
    """Item 3 (CLI --json): failed quick aborts itself, reports nothing open, specific next."""
    root = _make_minimal_product(tmp_path / "prod", fail_on_change=True)

    proc = n2f(
        "ecr",
        "quick",
        "--set",
        "param://worktop-length=2000 mm",
        "--json",
        cwd=root,
    )
    assert proc.returncode == 3
    data = json.loads(proc.stdout)
    assert data["error"] == "ecr_error"
    assert "the change was not made and nothing is left open" in data["message"]
    # Specific next step, not generic
    assert "n2f build" not in data["next"]
    assert "n2f --help" not in data["next"]
    assert "fix" in data["next"]

    # Verify no change request is left open and parameter is unchanged
    prod_after = load_product(root)
    assert live.open_request(prod_after) is None
    assert prod_after.parameters["worktop-length"].value == 1000


def test_quick_failure_aborts_itself_mcp(tmp_path: Path) -> None:
    """Item 3 (MCP): failed quick change aborts itself and MCP tool returns specific next."""
    root = _make_minimal_product(tmp_path / "prod", fail_on_change=True)
    runner = ToolRunner(root)

    res = asyncio.run(
        runner.call("n2f_ecr", {"action": "quick", "set": ["param://worktop-length=2000 mm"]})
    )
    assert res.is_error
    data = json.loads(res.text)
    assert not data["ok"]
    assert "the change was not made and nothing is left open" in data["error"]["message"]
    assert "n2f build" not in data["next"]["say"]
    assert live.open_request(load_product(root)) is None


def test_quick_failure_self_abort_fails_cli_json(tmp_path: Path) -> None:
    """Item 4 (CLI --json): if self-abort fails, next names `n2f ecr abort <id>` with real id."""
    root = _make_minimal_product(tmp_path / "prod", fail_on_change=True)

    err = RuntimeError("simulated abort failure")
    with patch("napkin2factory.ecr.live.abort", side_effect=err):
        proc = n2f(
            "ecr",
            "quick",
            "--set",
            "param://worktop-length=2000 mm",
            "--json",
            cwd=root,
        )
        assert proc.returncode == 3
        data = json.loads(proc.stdout)
        assert data["error"] == "ecr_error"
        assert "ECR-001 could not be aborted automatically" in data["message"]
        assert data["next"] == "`n2f ecr abort ECR-001`"


def test_quick_failure_self_abort_fails_mcp(tmp_path: Path) -> None:
    """Item 4 (MCP): if self-abort fails, next names n2f_ecr action=abort id=<id> with real id."""
    fake_quick = (
        3,
        {
            "error": "ecr_error",
            "message": "checks failed; ECR-001 could not be aborted automatically",
            "next": "`n2f ecr abort ECR-001`",
        },
    )
    fake_status = {"gates": [], "next_step": ""}
    steps = _FakeSteps({("ecr", "quick"): fake_quick, ("status",): fake_status})
    runner = ToolRunner(tmp_path, steps=steps)

    res = asyncio.run(
        runner.call("n2f_ecr", {"action": "quick", "set": ["param://worktop-length=2000 mm"]})
    )
    assert res.is_error
    data = json.loads(res.text)
    assert not data["ok"]
    assert data["next"] == {
        "tool": "n2f_ecr",
        "arguments": {"action": "abort", "ecr_id": "ECR-001"},
    }
