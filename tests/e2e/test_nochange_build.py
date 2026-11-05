"""A build with nothing changed is fast and touches nothing (M1c, R12, S-247).

The correctness test runs everywhere: a second build leaves every file of ``build/``
byte-identical, and one changed parameter rebuilds what reads it and nothing else. The timing
test runs only under ``N2F_TIMING=1`` (D30): a fresh ``n2f build`` process, as an owner's
agent runs it, on tier 1 (``examples/table``) with nothing changed.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.conftest import EXAMPLES, copy_product, n2f

TIMING = os.environ.get("N2F_TIMING") == "1"

#: Seconds a no-change build of examples/table may take as a fresh process (R12 targets 2 s).
#: Measured on the maintainer's host (S-247): 1.3 s, best of three, bytecode compiled; the
#: budget is that plus headroom. CI gets 2.5x because its runners are slower and noisier.
HOST_BUDGET_S = 2.0
BUDGET_S = HOST_BUDGET_S * (2.5 if os.environ.get("CI") == "true" else 1.0)


def _digests(build: Path) -> dict[str, str]:
    """SHA-256 of every file under ``build/``, by path relative to it."""
    return {
        str(p.relative_to(build)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(build.rglob("*"))
        if p.is_file()
    }


def test_nochange_build_is_byte_identical_and_a_change_rebuilds_what_reads_it(
    tmp_path: Path,
) -> None:
    table = copy_product(EXAMPLES / "table", tmp_path / "table", prebuilt=True)
    before = _digests(table / "build")
    assert before

    again = n2f("build", cwd=table)
    assert again.returncode == 0, again.stdout + again.stderr
    assert "built: 0 rebuilt" in again.stdout
    assert _digests(table / "build") == before  # manifest included: nothing was even rewritten

    params = table / "model" / "parameters.yaml"
    text = params.read_text()
    changed, n = re.subn(r"(tab-thickness:\s*\{value: )4,", r"\g<1>5,", text)
    assert n == 1
    params.write_text(changed)
    rebuilt = n2f("build", cwd=table)
    assert rebuilt.returncode == 0, rebuilt.stdout + rebuilt.stderr
    assert "built: 0 rebuilt" not in rebuilt.stdout
    after = _digests(table / "build")
    differs = {k for k in before.keys() | after.keys() if before.get(k) != after.get(k)}
    assert "parts/apron-frame/model.step" in differs  # the part that reads the parameter
    assert not {k for k in differs if k.startswith("parts/top-board/")}  # one that does not


@pytest.mark.timing
@pytest.mark.skipif(not TIMING, reason="timing assertions run only under N2F_TIMING=1 (D30)")
def test_nochange_build_of_tier_1_is_fast(tmp_path: Path) -> None:
    table = copy_product(EXAMPLES / "table", tmp_path / "table", prebuilt=True)
    env = {k: v for k, v in os.environ.items() if k != "PYTHONDONTWRITEBYTECODE"}
    env.update({"N2F_OFFLINE": "1", "COLUMNS": "200"})

    def run() -> float:
        t0 = time.perf_counter()
        r = subprocess.run(
            [sys.executable, "-m", "napkin2factory.cli", "build"],
            cwd=table,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        elapsed = time.perf_counter() - t0
        assert r.returncode == 0, r.stdout + r.stderr
        assert "built: 0 rebuilt" in r.stdout, r.stdout  # nothing changed, so nothing ran
        return elapsed

    # the first run may compile bytecode the venv was installed without (a host that sets
    # PYTHONDONTWRITEBYTECODE); it is untimed, and the best of the next two is the measure
    run()
    seconds = min(run(), run())
    assert seconds < BUDGET_S, f"a no-change build took {seconds:.1f} s (budget {BUDGET_S:.1f} s)"
