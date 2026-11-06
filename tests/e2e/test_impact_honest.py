"""Gate E B1, B4 and C7 (S-138): the build graph stays honest.

B1: rules record some objects whole (``iface://x``, ``dec://DEC-xxx``, ``calc://m.f``), and an
edit names a field of one (``iface://x#spec.depth``).  Impact must still name every rule the
build would rerun.  Each test predicts with :func:`compute_impact` before the edit, makes the
edit in the file, and compares with :func:`explain_build`, the build's own dry run (a superset
of what a build reruns: it assumes every upstream rerun changes its output).  The kiln is built
once per test session, without renders (about 60 s on the reference host), and each test edits
its own copy of it.

B4: the core's open-set tables (``core/data/*.yaml``) are inputs of the rules that read them,
so editing the driver words reruns every output that prints them.

C7: a ``--set`` that is not a valid edit is a plain error, never a traceback.

An end-to-end test (moved from tests/unit, S-196): building the whole kiln made it the
land gate's heaviest file, 164 worker-seconds of a 157 s `make check-fast`.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from napkin2factory.cli.app import app
from napkin2factory.core import registry as registry_mod
from napkin2factory.core.errors import N2FError
from napkin2factory.core.graph.impact import compute_impact, parse_set
from napkin2factory.core.graph.rules import build_rules
from napkin2factory.core.graph.runner import explain_build, run_build
from napkin2factory.core.loader import load_product
from tests.conftest import EXAMPLES, copy_product


@pytest.fixture
def kiln(tmp_path: Path) -> Path:
    """A copy of the kiln built without renders, its own for each test.

    A copy of the session's prebuilt kiln (S-196): the tests run on any worker and edit it
    freely, instead of sharing one built copy on one worker and rebuilding it to undo an edit.
    """
    return copy_product(
        EXAMPLES / "kiln", tmp_path / "kiln", git=False, prebuilt=True, render=False
    )


def _would_run(root: Path) -> set[str]:
    return {rid for rid, run, _ in explain_build(load_product(root), render=False) if run}


def _predict_then_edit(root: Path, uri_value: str, file: Path, old: str, new: str) -> Any:
    """Impact of ``uri_value`` on the built product, then the same edit made in ``file``."""
    report = compute_impact(load_product(root), [parse_set(uri_value)])
    text = file.read_text(encoding="utf-8")
    assert text.count(old) == 1, old
    file.write_text(text.replace(old, new), encoding="utf-8")
    return report


def test_an_interface_field_edit_names_every_rule_the_rebuild_runs(kiln: Path) -> None:
    """The parts read ``iface://door-guard-standoff`` whole; the edit names ``#spec.depth``."""
    report = _predict_then_edit(
        kiln,
        "iface://door-guard-standoff#spec.depth=12 mm",
        kiln / "model/interfaces/door-guard-standoff.yaml",
        "depth: 10 mm",
        "depth: 12 mm",
    )
    will = _would_run(kiln)
    assert {"part:door-tray", "part:door-guard", "checks"} <= will  # the edit is real
    assert will <= set(report.rules), sorted(will - set(report.rules))
    assert {"door-tray", "door-guard"} <= set(report.parts)


def test_a_decided_choice_field_edit_names_the_checks(kiln: Path) -> None:
    """The checks read a decided choice's ``dec://DEC-xxx`` whole; the edit names a field."""
    from napkin2factory.core.checks.choices import append_decision, decision_entry

    product = load_product(kiln)
    rows = json.loads((kiln / "build/checks/checks.json").read_text())["results"]
    row = next(r for r in rows if r["status"] == "choice")
    entry = decision_entry(product, row, row["detail"]["options"][0]["id"], "a tester", "note one")
    file = product.paths.decisions
    append_decision(file, entry)
    run_build(load_product(kiln), render=False, quiet=True)
    reads = json.loads((kiln / "build/.n2f/manifest.json").read_text())["entries"]["checks"]
    assert f"dec://{entry['id']}" in reads["reads"]
    report = _predict_then_edit(
        kiln, f"dec://{entry['id']}#rationale=note two", file, "note one", "note two"
    )
    will = _would_run(kiln)
    assert "checks" in will
    assert will <= set(report.rules), sorted(will - set(report.rules))


@pytest.mark.parametrize(
    ("text", "said"),
    [
        ("manifest://scope=x", "needs a selector"),
        ("calc://power", "--set expects <uri>=<value>"),
        ("nonsense=3", "nonsense"),
        ("part://No Such#name=x", "part://No Such"),
    ],
)
def test_a_bad_set_is_a_plain_error(text: str, said: str) -> None:
    """C7: the error names the edit and what is wrong with it (an N2FError, so the CLI says it)."""
    with pytest.raises(N2FError) as err:
        parse_set(text)
    assert said in str(err.value) and "Traceback" not in str(err.value)


def test_a_bad_set_on_the_command_line_prints_no_traceback(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", git=False)
    result = CliRunner().invoke(
        app, ["impact", "-C", str(root), "--set", "manifest://scope=x"], env={"COLUMNS": "200"}
    )
    assert result.exit_code == 1, result.output
    assert "needs a selector" in result.output
    assert "Traceback" not in result.output and not isinstance(result.exception, ValueError)


# ---- B4: the core's tables are inputs ---------------------------------------------------------


def _edited_tables(tmp_path: Path, name: str, old: str, new: str) -> Path:
    """A copy of ``core/data`` with one table edited."""
    data = tmp_path / "data"
    shutil.copytree(registry_mod.DATA, data)
    table = data / f"{name}.yaml"
    text = table.read_text(encoding="utf-8")
    assert text.count(old) == 1, old
    table.write_text(text.replace(old, new), encoding="utf-8")
    return data


DRIVER_WORDS = "serviced or replaced as one unit"


def test_editing_the_driver_words_reruns_every_output_that_prints_them(
    kiln: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entries = json.loads((kiln / "build/.n2f/manifest.json").read_text())["entries"]
    printing = {
        rid
        for rid, entry in entries.items()
        for rel in entry["outputs"]
        if DRIVER_WORDS.encode() in (kiln / "build" / rel).read_bytes()
    }
    assert {"bom", "asmsheet:door", "doc:assembly", "report", "site"} <= printing
    data = _edited_tables(tmp_path, "drivers", DRIVER_WORDS, "lifted off and swapped whole")
    monkeypatch.setattr(registry_mod, "DATA", data)
    will = _would_run(kiln)
    assert printing <= will, sorted(printing - will)
    assert not {r for r in will if r.startswith(("part:", "asm:", "drawing:"))}


@pytest.mark.parametrize(
    ("table", "old", "new", "moves"),
    [
        ("drivers", DRIVER_WORDS, "lifted off and swapped whole", {"validate", "bom"}),
        (
            "style_roles",
            '{id: opening, words: "a door, lid or hatch", styled: true',
            '{id: opening, words: "a door, lid or hatch", styled: false',
            {"validate", "checks", "report", "roles"},
        ),
        ("processes", "Sheet metal", "Sheet-metal work", {"validate", "checks"}),
    ],
)
def test_a_table_edit_moves_the_keys_of_the_rules_that_read_it(
    table: str, old: str, new: str, moves: set[str], tmp_path: Path
) -> None:
    """Exactly the rules reading the table move: ``roles`` stands for every part with a role."""
    product = load_product(EXAMPLES / "kiln")
    before = {r.id: dict(r.inputs) for r in build_rules(product, render=False)}
    data = _edited_tables(tmp_path, table, old, new)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(registry_mod, "DATA", data)
        registry_mod._style_roles_table.cache_clear()
        try:
            after = {r.id: dict(r.inputs) for r in build_rules(product, render=False)}
        finally:
            registry_mod._style_roles_table.cache_clear()
    roles = {f"part:{p.id}" for p in product.parts_with_geometry() if p.role}
    assert roles  # the kiln names roles, so the style-role case is not empty
    expected = (moves - {"roles"}) | (roles if "roles" in moves else set())
    assert {rid for rid in before if before[rid] != after[rid]} == expected


# ---- S-180, live since schema 2: a design change request's work in its impact report --------


def test_live_impact_reports_files_entities_scope_and_rebuild_artifacts(tmp_path: Path) -> None:
    """Gate H B1: a design ECR lists its files, entities, scope change and rebuild (S-261)."""
    from napkin2factory.core.vcs import Vcs
    from tests.conftest import FIXTURES, n2f

    whole = FIXTURES / "scope" / "external-box"
    root = copy_product(whole, tmp_path / "box", git=True)
    # take the wiring out to `later` and save that: the request starts from there
    shutil.rmtree(root / "model" / "electrical")
    for name in ("mains-entry.yaml", "control-entry.yaml"):
        p = root / "model" / "interfaces" / name
        p.write_text(
            p.read_text(encoding="utf-8")
            .replace("passes: [circuit://power]", "passes: []")
            .replace("passes: [circuit://control]", "passes: []"),
            encoding="utf-8",
        )
    manifest = root / "n2f.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            "electrical: {state: in, decision: DEC-001}",
            "electrical: {state: later, decision: DEC-001}",
        ),
        encoding="utf-8",
    )
    Vcs(root).snapshot("The wiring left for later")
    run_build(load_product(root), render=False, quiet=True)
    started = n2f(
        "ecr",
        "start",
        "--title",
        "Add the wiring",
        "--kind",
        "design",
        "--reason",
        "Wire the heater and probe to the control box.",
        "--task",
        "Wire the heater and probe",
        cwd=root,
    )
    assert started.returncode == 0, started.stdout + started.stderr
    # the designer's work, in place: the wiring is back
    shutil.copytree(whole / "model" / "electrical", root / "model" / "electrical")
    for name in ("mains-entry.yaml", "control-entry.yaml"):
        shutil.copy(whole / "model" / "interfaces" / name, root / "model" / "interfaces" / name)
    shutil.copy(whole / "n2f.yaml", root / "n2f.yaml")
    result = n2f("ecr", "impact", "--json", cwd=root)
    assert result.returncode == 0, result.stdout + result.stderr
    impact = json.loads(result.stdout)
    assert "model/electrical/supply.yaml" in impact["files"]["added"]
    assert "n2f.yaml" in impact["files"]["changed"]
    assert {"supply://supply", "circuit://power", "circuit://control"} <= set(
        impact["objects"]["added"]
    )
    assert "iface://mains-entry" in impact["objects"]["changed"]
    assert [s["words"] for s in impact["scope"]] == ["Wiring: left for later → done here"]
    assert {"elec:power", "elec:control", "checks"} <= set(impact["rebuilt"])
    md = (root / "build/changes/ECR-001-impact.md").read_text(encoding="utf-8")
    assert "- Wiring: left for later → done here" in md
    assert "## Designer tasks" in md and "Wire the heater and probe" in md


def test_impact_cost_delta_edit_to_unpriced_part(tmp_path: Path) -> None:
    """An edit to an unpriced part flags the incomplete cost delta (S-187)."""
    from napkin2factory.core.graph.impact import summarize

    root = copy_product(EXAMPLES / "kiln", tmp_path / "kiln-unpriced", git=False)
    tray_file = root / "model/parts/door-tray.yaml"
    text = tray_file.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if not line.startswith("cost:")]
    tray_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    prod = load_product(root)
    assert prod.parts["door-tray"].cost is None

    rep = compute_impact(prod, [parse_set("part://door-tray#material.spec=2 mm CR4")])
    assert rep.cost_delta == 0.0
    assert rep.cost_complete is False
    assert rep.to_dict()["cost_complete"] is False
    assert (
        "; 1 part(s) without a price: door-tray, so the cost change is incomplete" in rep.cost_note
    )
    md = summarize(rep, prod)
    assert "at least +0.00 USD per unit" in md
    assert rep.cost_note in md


def test_impact_cost_delta_priced_only_change(tmp_path: Path) -> None:
    """A change touching only priced parts leaves cost_note and cost_complete clean (S-187)."""
    from napkin2factory.core.graph.impact import summarize

    prod = load_product(copy_product(EXAMPLES / "kiln", tmp_path / "kiln", git=False))
    rep = compute_impact(prod, [parse_set("part://door-tray#cost.unit=80 USD")])
    assert rep.cost_delta == 20.0
    assert rep.cost_complete is True
    assert rep.to_dict()["cost_complete"] is True
    assert rep.cost_note == "from declared unit costs × quantities"
    md = summarize(rep, prod)
    assert "**Cost:** +20.00 USD per unit (from declared unit costs × quantities)." in md
    assert "at least" not in md
    assert "incomplete" not in md
