"""Unit test for engine internal error handling under run_in_process (B-0309)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from napkin2factory.cli import engine as eng


def test_run_in_process_internal_error_json_safe_verb(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A safe verb escaping with an unhandled exception prints engine_internal JSON and exits 70."""

    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated engine crash")

    monkeypatch.setattr("napkin2factory.cli.app.run_app", boom)

    out = io.StringIO()
    err = io.StringIO()
    req = {
        "argv": ["build", "--json"],
        "cwd": str(tmp_path),
    }
    code = eng.run_in_process(req, out, err, tmp_path)

    assert code == eng.EXIT_INTERNAL
    assert "Traceback" in err.getvalue()
    assert "RuntimeError: simulated engine crash" in err.getvalue()

    lines = out.getvalue().strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["error"] == "engine_internal"
    assert data["message"] == "RuntimeError: simulated engine crash"
    assert data["next"] == "N2F_NO_ENGINE=1 n2f build --json"
    assert data["log"] == str(eng.log_path(tmp_path))


def test_run_in_process_internal_error_json_state_changing_verb(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A state-changing verb escaping with an unhandled exception names look_at command in next."""

    def boom(*args: object, **kwargs: object) -> None:
        raise ValueError("corrupted state")

    monkeypatch.setattr("napkin2factory.cli.app.run_app", boom)

    out = io.StringIO()
    err = io.StringIO()
    req = {
        "argv": ["undo", "--json"],
        "cwd": str(tmp_path),
    }
    code = eng.run_in_process(req, out, err, tmp_path)

    assert code == eng.EXIT_INTERNAL
    assert "ValueError: corrupted state" in err.getvalue()

    lines = out.getvalue().strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["error"] == "engine_internal"
    assert data["message"] == "ValueError: corrupted state"
    assert data["next"] == "n2f checkpoints"
    assert data["log"] == str(eng.log_path(tmp_path))


def test_run_in_process_internal_error_json_state_changing_verb_with_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A state-changing verb preserves --dir in look_at command in next."""

    def boom(*args: object, **kwargs: object) -> None:
        raise ValueError("corrupted state")

    monkeypatch.setattr("napkin2factory.cli.app.run_app", boom)

    out = io.StringIO()
    err = io.StringIO()
    req = {
        "argv": ["undo", "--dir", "other_prod", "--json"],
        "cwd": str(tmp_path),
    }
    code = eng.run_in_process(req, out, err, tmp_path)

    assert code == eng.EXIT_INTERNAL
    lines = out.getvalue().strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["error"] == "engine_internal"
    assert data["next"] == "n2f checkpoints --dir other_prod"


def test_run_in_process_internal_error_without_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Without --json, stderr gets the traceback, stdout is unchanged, and exit code is 1."""

    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr("napkin2factory.cli.app.run_app", boom)

    out = io.StringIO()
    err = io.StringIO()
    req = {
        "argv": ["build"],
        "cwd": str(tmp_path),
    }
    code = eng.run_in_process(req, out, err, tmp_path)

    assert code == 1
    assert out.getvalue() == ""
    assert "RuntimeError: boom" in err.getvalue()
    assert "Traceback" in err.getvalue()
