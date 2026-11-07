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

from tests.conftest import n2f, real_page_errors

TIMING = os.environ.get("N2F_TIMING") == "1"


@pytest.mark.timing
@pytest.mark.skipif(not TIMING, reason="timing assertions run only under N2F_TIMING=1 (D30)")
def test_bracket_first_run_under_two_minutes(tmp_path: Path) -> None:
    t0 = time.perf_counter()
    # each command in a process of its own, as the owner runs them: imports are in the budget
    demo, offline = tmp_path / "demo", {"N2F_OFFLINE": "1"}
    assert n2f("init", str(demo), "--template", "bracket", process=True).returncode == 0
    assert n2f("build", cwd=demo, env=offline, process=True).returncode == 0
    assert n2f("check", cwd=demo, env=offline, process=True).returncode == 0
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
    assert n2f("init", str(demo), "--template", "bracket", process=True).returncode == 0
    assert n2f("concept", "new", "Flat bracket", cwd=demo, process=True).returncode == 0
    r = n2f("concept", "new", "Gusseted bracket", "--from", "C-001", cwd=demo, process=True)
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
    assert real_page_errors(errors) == [], errors
    assert len(viewers) == 2


@pytest.mark.timing
@pytest.mark.skipif(not TIMING, reason="timing assertions run only under N2F_TIMING=1 (D30)")
def test_table_one_parameter_rebuild_budget(tmp_path: Path) -> None:
    """A one-parameter change on the tier-1 table rebuilds in a process of its own within 16 s.

    Measured at 10.4 to 10.9 s on a quiet host after M7's fast YAML loader (19.4 s at v0.8
    on a busier host; S-295 holds the split: 1.1 s start-up, 2.8 s CAD kernel import, about
    5.7 s of rules, 2.1 s of it renders). The 1 s target of road §2.1 is not met; this is a
    regression guard, not the target. The budget is generous because the host is shared.
    """
    from tests.conftest import EXAMPLES, copy_product

    demo = copy_product(EXAMPLES / "table", tmp_path / "table", prebuilt=True)
    params = demo / "model" / "parameters.yaml"
    text = params.read_text(encoding="utf-8")
    assert "table-height:      {value: 750" in text
    params.write_text(text.replace("{value: 750", "{value: 751", 1), encoding="utf-8")
    t0 = time.perf_counter()
    assert n2f("build", cwd=demo, env={"N2F_OFFLINE": "1"}, process=True).returncode == 0
    seconds = time.perf_counter() - t0
    assert seconds < 16, f"one-parameter rebuild took {seconds:.1f} s (budget 16 s, S-295)"
