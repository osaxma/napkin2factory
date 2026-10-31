"""B-0016: `n2f init` warms the CAD kernel in a detached background process."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from typer.testing import CliRunner

from napkin2factory.cli import kernel as kernel_mod
from napkin2factory.cli.app import app


class _FakePopen:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def __init__(self, argv: list[str], **kwargs: Any) -> None:
        _FakePopen.calls.append((argv, kwargs))


@pytest.fixture
def fake_popen(monkeypatch: pytest.MonkeyPatch) -> type[_FakePopen]:
    _FakePopen.calls = []
    monkeypatch.setattr(subprocess, "Popen", _FakePopen)
    return _FakePopen


def test_warmup_spawns_a_detached_import(
    fake_popen: type[_FakePopen], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("N2F_NO_WARMUP", raising=False)
    proc = kernel_mod.warm_kernel_in_background()
    assert isinstance(proc, _FakePopen)
    [(argv, kwargs)] = fake_popen.calls
    assert argv == [sys.executable, "-c", "import build123d"]
    assert kwargs["start_new_session"] is True
    for stream in ("stdin", "stdout", "stderr"):
        assert kwargs[stream] is subprocess.DEVNULL


def test_warmup_is_off_under_the_env_var(
    fake_popen: type[_FakePopen], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("N2F_NO_WARMUP", "1")
    assert kernel_mod.warm_kernel_in_background() is None
    assert fake_popen.calls == []


def test_init_announces_the_warmup(
    tmp_path: Path, fake_popen: type[_FakePopen], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("N2F_NO_WARMUP", raising=False)
    monkeypatch.delitem(sys.modules, "build123d", raising=False)
    result = CliRunner().invoke(app, ["init", str(tmp_path / "warm"), "--no-tracking"])
    assert result.exit_code == 0, result.output
    assert len(fake_popen.calls) == 1
    assert (
        'next: sketch two directions — `n2f concept new "<title>"` — or go straight to '
        "`n2f build`; then open the folder with your AI client. The CAD kernel is warming up "
        "in the background (one to two minutes the first time on a machine)"
    ) in result.output


def test_init_skips_the_warmup_when_the_kernel_is_loaded(
    tmp_path: Path, fake_popen: type[_FakePopen], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("N2F_NO_WARMUP", raising=False)
    monkeypatch.setitem(sys.modules, "build123d", ModuleType("build123d"))
    result = CliRunner().invoke(app, ["init", str(tmp_path / "cold"), "--no-tracking", "--json"])
    assert result.exit_code == 0, result.output
    assert fake_popen.calls == []
    assert json.loads(result.output)["kernel_warmup"] is False


def test_init_json_reports_the_warmup(
    tmp_path: Path, fake_popen: type[_FakePopen], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("N2F_NO_WARMUP", raising=False)
    monkeypatch.delitem(sys.modules, "build123d", raising=False)
    result = CliRunner().invoke(app, ["init", str(tmp_path / "warm"), "--no-tracking", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["kernel_warmup"] is True


def test_init_without_warmup_keeps_the_plain_hint(
    tmp_path: Path, fake_popen: type[_FakePopen], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("N2F_NO_WARMUP", "1")
    monkeypatch.delitem(sys.modules, "build123d", raising=False)
    result = CliRunner().invoke(app, ["init", str(tmp_path / "plain"), "--no-tracking"])
    assert result.exit_code == 0, result.output
    assert fake_popen.calls == []
    assert "warming up" not in result.output
    assert "or go straight to `n2f build` (the first run loads the CAD kernel" in result.output
