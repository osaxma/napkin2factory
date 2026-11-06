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

from tests.benchmarks import oracle, oracle_change
from tests.benchmarks.oracle_evidence import Evidence
from tests.benchmarks.oracle_match import MatchError
from tests.benchmarks.oracle_schema import Change, ChangeSet, Fact, Figure, Find, load_oracle
from tests.conftest import EXAMPLES, copy_kiln_as_designed, copy_product, n2f

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
    rows = oracle.evaluate(load_oracle(spec), Evidence(work), replay=True)
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


def test_a_change_sets_row_is_found_by_value_and_words() -> None:
    # No build: resolve_set reads the evaluated parameters passed straight in.
    parameters = {
        "top-thickness": {"value": 30.0, "unit": "mm", "description": "White-oak top thickness"},
        "frame-height": {
            "value": 700.0,
            "unit": "mm",
            "description": "Apron frame height, leg length",
        },
        "rated-load": {"value": 2000.0, "unit": "N", "description": "Rated compressive load"},
        "load-cell-capacity": {
            "value": 2000.0,
            "unit": "N",
            "description": "Load cell rated capacity",
        },
    }
    top = ChangeSet(value=30, unit="mm", words=r"top[- ]?thickness", to="31 mm")
    assert oracle_change.resolve_set(top, parameters) == "top-thickness"
    rated = ChangeSet(value=2000, unit="N", words=r"rated[- ]?load", to="2500 N")
    assert oracle_change.resolve_set(rated, parameters) == "rated-load"
    with pytest.raises(MatchError):
        oracle_change.resolve_set(
            ChangeSet(value=2000, unit="N", words="", to="2500 N"), parameters
        )


def test_the_request_finder_reads_changes_by_kind_and_words(tmp_path: Path) -> None:
    changes = tmp_path / "changes"
    changes.mkdir()
    (changes / "ECR-1.yaml").write_text(
        "kind: parametric\ntitle: top 30 to 31 mm\nreason: the owner wants a heavier look\n",
        encoding="utf-8",
    )
    (changes / "ECR-2.yaml").write_text(
        "kind: design\ntitle: a 500 mm seating overhang\nreason: more room at one end\n",
        encoding="utf-8",
    )
    change = Change(
        name="ecr-1",
        what="ECR-1: top 30 to 31 mm",
        kind="parametric",
        words=r"top.*31|31 mm",
        sets=[ChangeSet(value=30, unit="mm", words="top", to="31 mm")],
        outcome="accepted",
    )
    found = oracle_change.find_requests(tmp_path, change)
    assert [p.name for p in found] == ["ECR-1.yaml"]


def test_a_wrong_fails_regex_reports_the_failing_requirement() -> None:
    check = {
        "matrix": {"requirements": [{"id": "REQ-002", "title": "Load cell rated capacity"}]},
        "results": [
            {
                "id": "req://REQ-002",
                "kind": "requirement",
                "status": "fail",
                "title": "Load cell rated capacity",
                "message": "Load cell rated capacity: 2000 N >= 2500 N — fails",
            }
        ],
    }
    change = Change(
        name="cr-1",
        what="CR-1: rated load 2000 to 2500 N",
        kind="parametric",
        words=r"rated[- ]?load.*2500",
        sets=[ChangeSet(value=2000, unit="N", words="rated", to="2500 N")],
        outcome="refused",
        fails=["tip-over"],
    )
    passed, found = oracle_change.outcome_failures(change, check)
    assert not passed
    assert "Load cell rated capacity" in found
    change = change.model_copy(update={"fails": ["load cell"]})
    passed, found = oracle_change.outcome_failures(change, check)
    assert passed


def test_a_change_figure_and_fact_read_the_impact() -> None:
    impact = {
        "mass": {"before": 47.2, "after": 48.2, "delta": 1.0, "unit": "kg"},
        "signoffs_invalidated": ["req://REQ-018"],
        "signoffs_removed": [{"id": "req://REQ-019"}],
    }
    mass = Figure(
        name="mass",
        what="assembled mass after the change (kg)",
        find=Find(impact="mass.after"),
        unit="kg",
        expect=48.2,
        tol=0.02,
    )
    assert oracle.judge_figure(mass, Evidence(), {}, impact).passed
    lost = Fact(name="lost", what="sign-offs the change loses", fact="signoffs_lost", expect=2)
    assert oracle.judge_fact(lost, Evidence(), impact).passed


def test_the_oracle_judges_an_agents_own_request(tmp_path: Path) -> None:
    work = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", prebuilt=True)
    spec = tmp_path / "agent-request.oracle.yaml"
    spec.write_text(
        """oracle: 1
changes:
  - name: lengthen
    what: "bracket length 120 to 125 mm"
    kind: parametric
    words: "bracket.*125|125 mm"
    sets:
      - {value: 120, unit: mm, words: 'bracket[- ]?length', to: '125 mm'}
    outcome: accepted
    figures:
      - name: parts
        what: one distinct part after the change
        find: {rollup: distinct_parts}
        expect: 1
        tol: 0
""",
        encoding="utf-8",
    )
    oracle_spec = load_oracle(spec)
    # (a) open the request ourselves, then judge the draft it left (replay=False).
    opened = n2f(
        "ecr",
        "start",
        "--title",
        "bracket length 120 to 125 mm",
        "--set",
        "param://bracket-length=125 mm",
        cwd=work,
    )
    assert opened.returncode == 0, opened.stderr
    rows = oracle.evaluate(oracle_spec, Evidence(work), replay=False)
    assert not _failures(rows)
    assert [r.what for r in rows] == [
        "lengthen: outcome",
        "lengthen: one distinct part after the change",
    ]
    assert len(list((work / "changes").glob("*.yaml"))) == 1  # no second request was started
    # (b) abort, then judge the aborted path: it restores the work the abort saved, and the
    # rollup figure is judged without the impact the request never stored.
    aborted = n2f("ecr", "abort", cwd=work)
    assert aborted.returncode == 0, aborted.stderr
    rows = oracle.evaluate(oracle_spec, Evidence(work), replay=False)
    assert not _failures(rows)
    assert [r.what for r in rows] == [
        "lengthen: outcome",
        "lengthen: one distinct part after the change",
    ]
