"""The MCP tools use a product's warm engine when one is up, else a cold process (S-305, S-327)."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import pytest

from napkin2factory.cli import engine as eng
from napkin2factory.mcp.combined import ToolRunner
from tests.conftest import EngineGuard


def _requests(root: Path) -> int:
    info = eng.engine_status(root)
    return -1 if info is None else int(info["requests"])


def _body(runner: ToolRunner, name: str, **args: Any) -> dict[str, Any]:
    body: dict[str, Any] = json.loads(asyncio.run(runner.call(name, args)).text)
    return body


def _same_but_timing(body: dict[str, Any]) -> dict[str, Any]:
    steps = [{k: v for k, v in s.items() if k not in ("seconds", "engine")} for s in body["steps"]]
    return {**body, "steps": steps}


def test_a_tool_call_goes_through_the_engine_and_matches_the_spawned_cli(
    short_product: Path, engines: EngineGuard, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = ToolRunner(short_product)
    engines.start(short_product)
    assert _requests(short_product) == 0

    warm = _body(runner, "n2f_ecr", action="list")
    assert _requests(short_product) == 1  # one step, run in the engine
    assert warm["ok"] and [s["engine"] for s in warm["steps"]] == ["warm"]

    monkeypatch.setenv("N2F_NO_ENGINE", "1")  # the same call, spawned as before
    cold = _body(runner, "n2f_ecr", action="list")
    assert _requests(short_product) == 1
    assert [s["engine"] for s in cold["steps"]] == ["cold"]
    assert _same_but_timing(cold) == _same_but_timing(warm)

    # a failing call reads the same through both
    monkeypatch.delenv("N2F_NO_ENGINE")
    bad_warm = _body(runner, "n2f_ecr", action="show", ecr_id="ECR-999")
    monkeypatch.setenv("N2F_NO_ENGINE", "1")
    bad_cold = _body(runner, "n2f_ecr", action="show", ecr_id="ECR-999")
    assert not bad_warm["ok"] and _same_but_timing(bad_warm) == _same_but_timing(bad_cold)
    assert _requests(short_product) == 2


def test_with_no_engine_the_step_runs_cold_and_starts_an_engine(
    short_product: Path, engines: EngineGuard
) -> None:
    assert eng.engine_status(short_product) is None
    first = _body(ToolRunner(short_product), "n2f_ecr", action="list")
    assert first["ok"] and first["steps"][0]["engine"] == "cold"
    engines.track(short_product)


def test_the_server_starts_an_engine_and_stops_only_its_own(
    short_product: Path, engines: EngineGuard
) -> None:
    engines.track(short_product)

    async def ours() -> None:
        runner = ToolRunner(short_product)
        await runner.start()
        deadline = time.monotonic() + 40
        while eng.engine_status(short_product) is None and time.monotonic() < deadline:
            await asyncio.sleep(0.1)
        assert eng.engine_status(short_product) is not None
        await runner.close()

    asyncio.run(ours())
    deadline = time.monotonic() + 20
    while eng.engine_status(short_product) is not None and time.monotonic() < deadline:
        time.sleep(0.1)
    assert eng.engine_status(short_product) is None  # an engine the server started stops with it


def test_an_engine_someone_else_started_is_left_running(
    short_product: Path, engines: EngineGuard
) -> None:
    engines.start(short_product)

    async def theirs() -> None:
        runner = ToolRunner(short_product)
        await runner.start()
        await runner.close()

    asyncio.run(theirs())
    time.sleep(1)
    assert eng.engine_status(short_product) is not None
