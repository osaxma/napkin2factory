"""DoD item 2 timing: init → build → check on the bracket template in under two minutes.

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
