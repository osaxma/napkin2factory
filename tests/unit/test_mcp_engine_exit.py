"""The MCP server leaves no engine behind (S-291): none in a folder that is not a product yet,
and one this server started is stopped at exit even while it is still loading."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from napkin2factory.cli import engine
from napkin2factory.mcp.tools import StepRunner


def _no_engine_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    monkeypatch.delenv(engine.NO_ENGINE_ENV, raising=False)
    monkeypatch.setattr(engine, "capture", lambda *a, **k: calls.append("capture"))
    monkeypatch.setattr(engine, "spawn", lambda *a, **k: calls.append("spawn"))
    return calls


def test_no_engine_is_started_in_a_folder_that_is_not_a_product(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _no_engine_calls(monkeypatch)
    runner = StepRunner(tmp_path)
    asyncio.run(runner.start())
    step = asyncio.run(runner.run(["docs", "--json"]))
    assert step.exit == 0 and step.engine == "cold"
    assert calls == []


@pytest.mark.parametrize("state", ["running", "loading", "none"])
def test_exit_stops_an_engine_this_server_started_even_while_loading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    monkeypatch.delenv(engine.NO_ENGINE_ENV, raising=False)
    stopped: list[Any] = []
    monkeypatch.setattr(
        engine, "engine_status", lambda root: {"pid": 1} if state == "running" else None
    )
    monkeypatch.setattr(engine, "engine_starting", lambda root: state == "loading")
    monkeypatch.setattr(engine, "stop_engine", lambda root, wait=15.0: stopped.append(root))
    runner = StepRunner(tmp_path)  # not started: no engine answered at its start
    asyncio.run(runner.close())
    assert stopped == ([] if state == "none" else [tmp_path.resolve()])


def test_exit_leaves_an_engine_someone_else_started(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(engine.NO_ENGINE_ENV, raising=False)
    (tmp_path / "n2f.yaml").write_text("x: 1\n", encoding="utf-8")
    stopped: list[Any] = []
    monkeypatch.setattr(engine, "engine_status", lambda root: {"pid": 1})
    monkeypatch.setattr(engine, "spawn", lambda root: None)
    monkeypatch.setattr(engine, "stop_engine", lambda root, wait=15.0: stopped.append(root))
    runner = StepRunner(tmp_path)
    asyncio.run(runner.start())
    asyncio.run(runner.close())
    assert stopped == []
