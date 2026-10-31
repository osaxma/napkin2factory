"""``n2f build`` plumbing: ``--offline`` and the CAD-kernel loading note."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import ModuleType

import pytest
from typer.testing import CliRunner

from napkin2factory.cli import kernel as kernel_mod
from napkin2factory.cli.app import app
from napkin2factory.cli.common import err_console


def test_offline_flag_sets_env_before_the_build(bracket: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("N2F_OFFLINE", raising=False)
    result = CliRunner().invoke(app, ["build", "--offline", "--explain", "-C", str(bracket)])
    assert result.exit_code == 0, result.output
    assert os.environ.get("N2F_OFFLINE") == "1"


def test_kernel_note_is_silent_when_the_kernel_is_already_loaded(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setitem(sys.modules, "build123d", ModuleType("build123d"))
    with err_console.capture() as cap:
        kernel_mod.load_cad_kernel()
    assert cap.get() == ""


def test_kernel_note_precedes_the_import(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delitem(sys.modules, "build123d", raising=False)
    with err_console.capture() as cap:
        kernel_mod.load_cad_kernel()
    assert "CAD kernel" in cap.get() and "couple of minutes" in cap.get()
    assert "build123d" in sys.modules


def test_build_module_still_exports_the_kernel_loader():
    from napkin2factory.cli import build as build_cmd

    assert build_cmd.load_cad_kernel is kernel_mod.load_cad_kernel
    assert build_cmd.KERNEL_NOTE == kernel_mod.KERNEL_NOTE
