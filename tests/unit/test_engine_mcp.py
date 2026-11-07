"""The MCP server uses a product's warm engine when one is up; else it spawns the CLI (S-305)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from napkin2factory.cli import engine as eng
from napkin2factory.mcp.tools import ToolRunner
from tests.conftest import EngineGuard


def _requests(root: Path) -> int:
    info = eng.engine_status(root)
    return -1 if info is None else int(info["requests"])


def test_a_tool_call_goes_through_the_engine_and_matches_the_spawned_cli(
    short_product: Path, engines: EngineGuard, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = ToolRunner(short_product)
    engines.start(short_product)
    assert _requests(short_product) == 0

    warm = asyncio.run(runner.call("n2f_validate", {}))
    assert _requests(short_product) == 1  # it ran in the engine
    assert warm.exit_code == 0 and not warm.is_error

    monkeypatch.setenv("N2F_NO_ENGINE", "1")  # the same call, spawned as before
    cold = asyncio.run(runner.call("n2f_validate", {}))
    assert _requests(short_product) == 1
    assert cold == warm

    # a failing call reads the same through both
    monkeypatch.delenv("N2F_NO_ENGINE")
    bad_warm = asyncio.run(runner.call("n2f_check", {"scope": "asm://nope"}))
    monkeypatch.setenv("N2F_NO_ENGINE", "1")
    bad_cold = asyncio.run(runner.call("n2f_check", {"scope": "asm://nope"}))
    assert bad_warm.is_error and bad_warm == bad_cold
    assert _requests(short_product) == 2


def test_with_no_engine_the_call_spawns_the_cli_as_before(
    short_product: Path, engines: EngineGuard
) -> None:
    # the call finds no engine: it runs in a process, and starts an engine for the next one
    assert eng.engine_status(short_product) is None
    first = asyncio.run(ToolRunner(short_product).call("n2f_validate", {}))
    assert first.exit_code == 0 and '"ok": true' in first.text
    engines.track(short_product)
