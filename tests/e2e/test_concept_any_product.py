"""The napkin stage on a fresh blank product: a wall shelf, no door, no alcove (gate F, B3).

``n2f init --template blank``, two cards (one fits its space, one does not), build, show,
the board and a promotion: nothing the owner reads names a door, an alcove or an oven
(S-137). The kiln keeps its own words through its pack (``tests/unit/
test_screening_any_product.py`` holds its cards to their shipped screening).
"""

from __future__ import annotations

import html
import re
import subprocess
from pathlib import Path

from tests.conftest import n2f

FOREIGN = re.compile(r"\b(door|doors|alcove|oven|kiln|chamber|hinge)\b", re.IGNORECASE)
SHELF = (
    "  - {kit: block, as: body, material: mild steel,"
    " args: {length: 600 mm, width: 250 mm, height: 20 mm}}"
)


def _run(*args: str, cwd: Path, code: int = 0) -> subprocess.CompletedProcess[str]:
    r = n2f(*args, cwd=cwd)
    assert r.returncode == code, f"{args}: {r.stdout}\n{r.stderr}"
    return r


def _card(root: Path, cid: str, width: str) -> None:
    path = root / "concepts" / f"{cid}.yaml"
    text = path.read_text(encoding="utf-8")
    text = text.replace("site: {}", f"site: {{width: {width}, depth: 300 mm}}")
    text = text.replace("massing: []", "massing:\n" + SHELF)
    path.write_text(text, encoding="utf-8")


def _page_text(path: Path) -> str:
    """The board's words, without its scripts and markup."""
    page = path.read_text(encoding="utf-8")
    page = re.sub(r"<script.*?</script>", " ", page, flags=re.S)
    return html.unescape(re.sub(r"<[^>]+>", " ", page))


def test_a_shelf_napkin_stage_names_no_door_and_no_alcove(tmp_path: Path) -> None:
    _run("init", str(tmp_path / "demo"), "--template", "blank", cwd=tmp_path)
    root = tmp_path / "demo"
    _run("concept", "new", "Wall shelf", cwd=root)
    _run("concept", "new", "Narrow wall shelf", cwd=root)
    skeleton = (root / "concepts" / "C-001.yaml").read_text(encoding="utf-8")
    assert not FOREIGN.search(skeleton), skeleton
    _card(root, "C-001", "800 mm")
    _card(root, "C-002", "500 mm")

    built = _run("concept", "build", "--all", cwd=root)
    assert "it is 600 mm wide but the space is 500 mm wide" in built.stdout
    shown = _run("concept", "show", "C-001", cwd=root).stdout
    assert "fits the space width [computed]: 600 mm wide fits the 800 mm space" in shown
    _run("concept", "board", cwd=root)
    board = _page_text(root / "build" / "concepts" / "board.html")
    assert "the space is 500 mm" in board

    promoted = _run("concept", "promote", "C-001", cwd=root).stdout
    assert "2 requirements (2 about the space)" in promoted
    assert "+ REQ-001 Fits the space width" in promoted
    reqs = (root / "model" / "requirements.yaml").read_text(encoding="utf-8")
    assert "The assembled product is at most 800 mm wide." in reqs

    said = {
        "build": built.stdout,
        "show": shown,
        "board": board,
        "promote": promoted,
        "requirements": reqs,
        "C-002": (root / "concepts" / "C-002.yaml").read_text(encoding="utf-8"),
    }
    for where, text in said.items():
        assert not FOREIGN.search(text), f"{where}: {FOREIGN.search(text)!r}\n{text}"
