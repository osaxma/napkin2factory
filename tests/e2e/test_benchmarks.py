"""The benchmark oracle against real products (S-209, W9).

Every ``examples/*/SPEC.oracle.yaml`` is judged against its example (an oracle without a
product fails). Two
fixture oracles under ``tests/benchmarks/fixtures`` pin the surfaces the matchers read, on
products that already ship: the bracket's check and BOM output, the kiln's concept cards.
Runs in ``make check``, not ``make check-fast``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tests.benchmarks import oracle
from tests.benchmarks.oracle_evidence import Evidence
from tests.benchmarks.oracle_schema import load_oracle
from tests.conftest import EXAMPLES, copy_kiln_as_designed, copy_product

FIXTURES = Path(__file__).resolve().parents[1] / "benchmarks" / "fixtures"
SPECS = sorted(EXAMPLES.glob("*/SPEC.oracle.yaml"))


def _failures(rows: list[oracle.Row]) -> list[str]:
    return [f"{r.what}: {r.found} (expected {r.expected})" for r in rows if not r.passed]


@pytest.mark.parametrize("spec", SPECS, ids=[p.parent.name for p in SPECS])
def test_every_shipped_oracle_judges_its_example(spec: Path, tmp_path: Path) -> None:
    product = spec.parent
    assert (product / "n2f.yaml").is_file(), f"examples/{product.name} has an oracle but no product"
    if product.name == "kiln":
        # the oracle holds the kiln as designed; its open request ECR-001 changes the chamber
        # (S-261), and how an oracle judges a change is M4.0's (B-0218)
        work = copy_kiln_as_designed(tmp_path / product.name, git=True)
    else:
        work = copy_product(product, tmp_path / product.name, prebuilt=True)
    rows = oracle.evaluate(load_oracle(spec), Evidence(work))
    assert not _failures(rows)


def test_the_bracket_is_judged_from_n2f_check_and_the_bom(tmp_path: Path) -> None:
    work = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", prebuilt=True)
    rows = oracle.evaluate(load_oracle(FIXTURES / "bracket.oracle.yaml"), Evidence(work))
    assert len(rows) == 9
    assert not _failures(rows)


def test_a_wrong_expectation_fails_with_the_value_found(tmp_path: Path) -> None:
    work = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", prebuilt=True)
    wrong = (
        (FIXTURES / "bracket.oracle.yaml")
        .read_text(encoding="utf-8")
        .replace("expect: 120", "expect: 130")
    )
    (tmp_path / "wrong.yaml").write_text(wrong, encoding="utf-8")
    rows = oracle.evaluate(load_oracle(tmp_path / "wrong.yaml"), Evidence(work))
    failed = [r for r in rows if not r.passed]
    assert [r.what for r in failed] == ["overall width, found by the 150 mm bound it meets (mm)"]
    assert failed[0].found.startswith("120 mm")


def test_the_kiln_cards_are_judged_without_building_the_product(tmp_path: Path) -> None:
    work = tmp_path / "kiln"
    shutil.copytree(
        EXAMPLES / "kiln", work, ignore=shutil.ignore_patterns("build", "__pycache__", ".git")
    )
    rows = oracle.evaluate(load_oracle(FIXTURES / "kiln-concepts.oracle.yaml"), Evidence(work))
    assert not _failures(rows)
    assert not (work / "build" / "bom").exists()  # no product build was needed


def test_the_command_exits_1_on_a_failure_and_prints_each_row(tmp_path: Path, capsys) -> None:
    work = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", prebuilt=True)
    spec = FIXTURES / "bracket.oracle.yaml"
    assert oracle.main([str(work), str(spec), "--no-build"]) == 0
    assert capsys.readouterr().out.count("PASS") == 9
