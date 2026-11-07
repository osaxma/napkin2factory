"""Under ``--json`` every failure is one JSON object on stdout: error, message, next (S-313).

The agent is the first caller: it reads stdout, so a failure it can parse says what happened and
what to run next, with the exit code kept (1 a product error, 2 a usage error or a failed check).
Text mode is unchanged: ``✗`` and click's own messages on stderr, nothing on stdout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from napkin2factory.cli.app import run_app
from tests.conftest import EXAMPLES, copy_product


def run(
    args: list[str], capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> tuple[int, str, str]:
    """``run_app`` in this process the way ``n2f`` runs it; (exit code, stdout, stderr)."""
    monkeypatch.setattr(sys, "argv", ["n2f", *args])
    monkeypatch.setenv("COLUMNS", "200")
    capsys.readouterr()
    with pytest.raises(SystemExit) as stop:
        run_app(list(args), prog_name="n2f")
    seen = capsys.readouterr()
    return int(stop.value.code or 0), seen.out, seen.err


def test_not_a_product_is_an_object_with_the_init_next_step(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    code, out, err = run(["status", "--json"], capsys, monkeypatch)
    assert code == 1
    obj = json.loads(out)
    assert set(obj) == {"error", "message", "next"} and obj["error"] == "not_a_product"
    assert "n2f init" in obj["next"] and "isn't a napkin2factory product" in obj["message"]
    assert "✗" in err  # the stderr line stays
    code, out, err = run(["status", "--dir", str(tmp_path), "--json"], capsys, monkeypatch)
    assert code == 1 and json.loads(out)["next"].startswith(f"n2f init {tmp_path}")


def test_text_mode_is_unchanged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    code, out, err = run(["status"], capsys, monkeypatch)
    assert code == 1 and out == "" and "✗ this folder isn't a napkin2factory product" in err


def test_a_bad_option_is_a_usage_error_object(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    code, out, err = run(["build", "--no-such-option", "--json"], capsys, monkeypatch)
    assert code == 2
    obj = json.loads(out)
    assert obj["error"] == "usage_error" and "--no-such-option" in obj["message"]
    assert obj["next"] == "run `n2f build --help`"
    code, out, _ = run(["ecr", "start", "--bogus", "--json"], capsys, monkeypatch)
    assert code == 2 and json.loads(out)["next"] == "run `n2f ecr start --help`"


def test_an_unknown_verb_is_a_usage_error_object(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    code, out, _ = run(["frobnicate", "--json"], capsys, monkeypatch)
    assert code == 2
    obj = json.loads(out)
    assert obj["error"] == "usage_error" and "frobnicate" in obj["message"]
    assert obj["next"] == "run `n2f --help`"


def test_the_usage_error_text_is_clicks_own_without_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    code, out, err = run(["build", "--no-such-option"], capsys, monkeypatch)
    assert code == 2 and out == "" and "No such option" in err and "Usage:" in err


def test_a_named_error_carries_its_own_code_and_next(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "b", git=False)
    code, out, _ = run(
        ["check", "--scope", "asm://nope", "--json", "--dir", str(root)], capsys, monkeypatch
    )
    assert code == 1
    obj = json.loads(out)
    assert obj["error"] == "error" and "no assembly" in obj["message"] and obj["next"]


def test_a_failing_check_keeps_its_own_json_and_exit_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "b", git=False, prebuilt=True)
    req = root / "model" / "requirements.yaml"
    req.write_text(
        req.read_text()
        + """  - id: REQ-004
    title: Thin sheet
    statement: The sheet is at most 1 mm thick.
    category: manufacturing
    verify: {kind: param_bound, target: param://bracket-thickness, op: "<=", value: 1 mm}
    allocation: [param://bracket-thickness]
"""
    )
    code, out, _ = run(["check", "--json", "--dir", str(root)], capsys, monkeypatch)
    assert code == 2
    data = json.loads(out)  # one object: the check result, not an error wrapped around it
    assert "error" not in data and data["summary"]["fail"] >= 1
