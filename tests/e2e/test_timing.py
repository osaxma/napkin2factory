"""DoD item 2 timing: init → build → check on the bracket template in under two minutes
(v0.1), and two concepts plus the board in under a minute warm (v0.2 NAPKIN_STAGE DoD 2).

Runs only under ``N2F_TIMING=1`` (D30); never skipped silently otherwise — the skip reason
says so and ``make check-full`` sets the variable.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from tests.conftest import n2f

TIMING = os.environ.get("N2F_TIMING") == "1"


@pytest.mark.timing
@pytest.mark.skipif(not TIMING, reason="timing assertions run only under N2F_TIMING=1 (D30)")
def test_bracket_first_run_under_two_minutes(tmp_path: Path) -> None:
    t0 = time.perf_counter()
    assert n2f("init", str(tmp_path / "demo"), "--template", "bracket").returncode == 0
    assert n2f("build", cwd=tmp_path / "demo", env={"N2F_OFFLINE": "1"}).returncode == 0
    assert n2f("check", cwd=tmp_path / "demo", env={"N2F_OFFLINE": "1"}).returncode == 0
    seconds = time.perf_counter() - t0
    assert (tmp_path / "demo/build/report/index.html").is_file()
    assert seconds < 120, f"init → build → check took {seconds:.0f} s (budget 120 s, DoD item 2)"


@pytest.mark.timing
@pytest.mark.skipif(not TIMING, reason="timing assertions run only under N2F_TIMING=1 (D30)")
def test_two_concepts_and_board_under_a_minute_warm(tmp_path: Path) -> None:
    """NAPKIN_STAGE DoD 2: two concepts built and the board written in under 60 s, warm.

    How it is measured: ``n2f init`` and the two ``n2f concept new`` calls run as the owner
    would (separate processes, untimed). Then, in this process, the CAD kernel and the CLI are
    imported first — "warm" is the state after the first `n2f` command of a session, which
    `n2f init` itself starts warming (B-0016) — and the clock covers exactly
    ``n2f concept build --all`` (massing, screening, styled screenshots for both cards) plus
    ``n2f concept board``, run through the CLI in-process. The board is then opened from
    ``file://`` (untimed) and must load with no console errors.
    """
    from typer.testing import CliRunner

    from napkin2factory.cli.app import app
    from tests.validate_outputs import validate_outputs

    demo = tmp_path / "demo"
    assert n2f("init", str(demo), "--template", "bracket").returncode == 0
    assert n2f("concept", "new", "Flat bracket", cwd=demo).returncode == 0
    r = n2f("concept", "new", "Gusseted bracket", "--from", "C-001", cwd=demo)
    assert r.returncode == 0, r.stdout + r.stderr
    plates = {
        "C-001": "{kit: plate, as: body, material: mild steel, "
        "args: {width: 120 mm, depth: 40 mm, thickness: 4 mm}}",
        "C-002": "{kit: plate, as: body, material: mild steel, "
        "args: {width: 120 mm, depth: 60 mm, thickness: 6 mm}}",
    }
    for cid, call in plates.items():
        card = demo / "concepts" / f"{cid}.yaml"
        text = card.read_text()
        assert "massing: []" in text
        card.write_text(text.replace("massing: []", f"massing:\n  - {call}"))

    import build123d  # noqa: F401  # the warm kernel (B-0016): paid before the clock starts

    runner = CliRunner()
    t0 = time.perf_counter()
    built = runner.invoke(app, ["concept", "build", "--all", "-C", str(demo)])
    board = runner.invoke(app, ["concept", "board", "-C", str(demo)])
    seconds = time.perf_counter() - t0
    assert built.exit_code == 0, built.output
    assert board.exit_code == 0, board.output
    print(f"warm `n2f concept build --all` (2 cards) + `n2f concept board`: {seconds:.1f} s")
    page = demo / "build/concepts/board.html"
    assert validate_outputs(demo, "concepts") == []
    assert seconds < 60, f"two concepts and the board took {seconds:.0f} s (budget 60 s, DoD 2)"

    from playwright.sync_api import sync_playwright

    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
        tab = browser.new_page(viewport={"width": 1280, "height": 900})
        tab.on("pageerror", lambda e: errors.append(str(e)))
        tab.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        tab.goto(page.as_uri())
        viewers = tab.evaluate("window.n2fViewerReady.then(v => Object.keys(v))")
        browser.close()
    assert errors == [], errors
    assert len(viewers) == 2
