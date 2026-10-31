"""M4 (v0.2): concepts → board → promote → the factory loop, by subprocess (N8, N10).

The fixture is the bracket plus the M2 and M4 cards (C-001/C-004 red, C-002/C-003 green).
Review gate A's question "do form requirements actually fail when violated?" is answered
here: the threshold in ``style.yaml`` is flipped and a hole is turned to face the front, and
the form requirement rows fail; the alcove requirement fails when the product is wider
than the alcove less the door swing.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import EXAMPLES, copy_product, n2f
from tests.unit.test_promote import overlay_cards

os.environ.setdefault("N2F_OFFLINE", "1")
GIT_WORDS = ("fatal:", "git ", "branch", "commit", "merge", "repository", "checkout")
NO_SHOTS = {"N2F_NO_PLAYWRIGHT": "1"}  # pictures are tested in test_board/test_screenshot


def _run(*args: str, cwd: Path, code: int = 0, env: dict[str, str] | None = None) -> Any:
    r = n2f(*args, cwd=cwd, env=env)
    assert r.returncode == code, f"{args}: {r.returncode}\n{r.stdout}\n{r.stderr}"
    low = (r.stdout + r.stderr).lower()
    for w in GIT_WORDS:
        assert w not in low, f"{args}: git vocabulary {w!r} leaked:\n{r.stdout}\n{r.stderr}"
    return r


@pytest.fixture
def product(tmp_path: Path) -> Path:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", git=True)
    overlay_cards(root)
    return root


def _check(root: Path, code: int = 0) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(_run("check", "--json", cwd=root, code=code).stdout)
    return data


def _req(data: dict[str, Any], rid: str) -> dict[str, Any]:
    row: dict[str, Any] = next(r for r in data["matrix"]["requirements"] if r["id"] == rid)
    return row


def _set_style(root: Path, old: str, new: str) -> None:
    path = root / "style.yaml"
    text = path.read_text()
    assert old in text, old
    path.write_text(text.replace(old, new))


def test_napkin_to_factory_with_form_requirements_that_bite(product: Path) -> None:
    root = product
    _run("concept", "build", "--all", cwd=root, env=NO_SHOTS)
    r = _run("concept", "board", cwd=root)
    assert "board: build/concepts/board.html — 4 directions side by side (2 with problems)" in (
        r.stdout
    )
    assert (root / "build" / "concepts" / "board.html").is_file()
    board = json.loads(_run("concept", "board", "--json", cwd=root).stdout)
    assert [c["verdict"] for c in board["cards"]] == ["red", "green", "green", "red"]

    refused = _run("concept", "promote", "C-001", cwd=root, code=3)
    assert "C-001 — this direction has problems:" in refused.stderr
    assert "--override --reason" in refused.stderr

    out = _run("concept", "promote", "C-003", cwd=root).stdout
    assert "C-003 is now the design direction (DEC-002)." in out
    assert "Seeded 5 parameters, 5 requirements (3 about form, 1 about the alcove" in out
    assert "C-001, C-002 and C-004 are kept as rejected alternatives" in out
    assert "Next: `n2f build && n2f check`." in out
    again = _run("concept", "promote", "C-002", cwd=root, code=3)
    assert "C-003 is already the chosen direction" in again.stderr

    _run("validate", cwd=root)
    _run("lint", cwd=root)
    _run("build", "--no-render", cwd=root)
    data = _check(root)
    rows = {r["id"]: r for r in data["matrix"]["requirements"]}
    assert rows["REQ-004"]["title"] == "Fits the alcove with the door open"
    assert rows["REQ-004"]["status"] == "pass" and rows["REQ-004"]["kind"] == "geometry_prop"
    assert rows["REQ-005"]["status"] == "pass"
    for rid in ("REQ-006", "REQ-007", "REQ-008"):
        assert rows[rid]["kind"] == "rule" and rows[rid]["status"] in ("pass", "skip"), rows[rid]
    st = json.loads(_run("status", "--json", cwd=root).stdout)
    assert st["gates"][0]["name"] == "napkin" and st["gates"][0]["ok"] is True
    assert st["stage"] != "napkin"

    # the bracket becomes a styled body: its 4 mm bend meets a 4 mm minimum …
    part = root / "model" / "parts" / "l-bracket.yaml"
    part.write_text(part.read_text() + "role: body\n")
    _set_style(root, "corner_radius: 8 mm", "corner_radius: 4 mm")
    _run("build", "--no-render", cwd=root)
    data = _check(root)
    assert _req(data, "REQ-006")["status"] == "pass"
    assert _req(data, "REQ-007")["status"] == "pass"
    # … and fails a 6 mm one (gate A: the threshold flipped, the requirement fails)
    _set_style(root, "corner_radius: 4 mm", "corner_radius: 6 mm")
    data = _check(root, code=2)
    row = _req(data, "REQ-006")
    assert row["status"] == "fail"
    assert "bend B1 is 4 mm, below the 6 mm corner radius chosen in style.yaml" in row["message"]
    _set_style(root, "corner_radius: 6 mm", "corner_radius: 4 mm")
    # turn the bracket so its wall leg (and its holes) faces the front
    geo = root / "model" / "geometry" / "bracket.py"
    geo.write_text(
        geo.read_text().replace(
            'place("part://l-bracket", parts["l-bracket"])',
            'place("part://l-bracket", parts["l-bracket"], rotate=(0.0, 0.0, 90.0))',
        )
    )
    _run("build", "--no-render", cwd=root)
    data = _check(root, code=2)
    row = _req(data, "REQ-007")
    assert row["status"] == "fail" and "is on the front" in row["message"]
    assert _req(data, "REQ-006")["status"] == "pass"


def test_red_card_overridden_and_its_alcove_requirement_fails(product: Path) -> None:
    root = product
    _run("concept", "build", "C-004", "--no-render", cwd=root)
    refused = _run("concept", "promote", "C-004", "--override", cwd=root, code=3)
    assert "--override needs --reason" in refused.stderr
    res = json.loads(
        _run(
            "concept",
            "promote",
            "C-004",
            "--override",
            "--reason",
            "the owner will widen the alcove",
            "--by",
            "owner",
            "--json",
            cwd=root,
        ).stdout
    )
    assert res["dec"] == "DEC-002" and res["override"] is True
    assert [r["uri"] for r in res["requirements"]] == ["req://REQ-004"]
    assert res["requirements"][0]["verify"] == {
        "kind": "geometry_prop",
        "target": "asm://bracket#props.bbox.x",
        "op": "<=",
        "value": "100 mm",
    }
    assert any("form requirement" in n for n in res["notes"])
    _run("validate", cwd=root)
    _run("build", "--no-render", cwd=root)
    data = _check(root, code=2)
    row = _req(data, "REQ-004")
    assert row["status"] == "fail" and row["message"] == "bbox.x = 120 mm <= 100 mm"
