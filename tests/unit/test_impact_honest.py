"""Gate E B1, B4 and C7 (S-138): the build graph stays honest.

B1: rules record some objects whole (``iface://x``, ``dec://DEC-xxx``, ``calc://m.f``), and an
edit names a field of one (``iface://x#spec.depth``).  Impact must still name every rule the
build would rerun.  Each test predicts with :func:`compute_impact` before the edit, makes the
edit in the file, and compares with :func:`explain_build`, the build's own dry run (a superset
of what a build reruns: it assumes every upstream rerun changes its output).  The kiln is built
once, without renders (about 40 s on the reference host).

B4: the core's open-set tables (``core/data/*.yaml``) are inputs of the rules that read them,
so editing the driver words reruns every output that prints them.

C7: a ``--set`` that is not a valid edit is a plain error, never a traceback.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
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


@pytest.fixture(scope="module")
def kiln(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """A copy of the kiln built once without renders."""
    root = copy_product(EXAMPLES / "kiln", tmp_path_factory.mktemp("impact") / "kiln", git=False)
    run_build(load_product(root), render=False, quiet=True)
    yield root


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
    file = kiln / "model/interfaces/door-guard-standoff.yaml"
    text = file.read_text(encoding="utf-8")
    try:
        report = _predict_then_edit(
            kiln,
            "iface://door-guard-standoff#spec.depth=12 mm",
            file,
            "depth: 10 mm",
            "depth: 12 mm",
        )
        will = _would_run(kiln)
        assert {"part:door-tray", "part:door-guard", "checks"} <= will  # the edit is real
        assert will <= set(report.rules), sorted(will - set(report.rules))
        assert {"door-tray", "door-guard"} <= set(report.parts)
    finally:
        file.write_text(text, encoding="utf-8")


def test_a_decided_choice_field_edit_names_the_checks(kiln: Path) -> None:
    """The checks read a decided choice's ``dec://DEC-xxx`` whole; the edit names a field."""
    from napkin2factory.core.checks.choices import append_decision, decision_entry

    product = load_product(kiln)
    rows = json.loads((kiln / "build/checks/checks.json").read_text())["results"]
    row = next(r for r in rows if r["status"] == "choice")
    entry = decision_entry(product, row, row["detail"]["options"][0]["id"], "a tester", "note one")
    file = product.paths.decisions
    text = file.read_text(encoding="utf-8")
    try:
        append_decision(file, entry)
        run_build(load_product(kiln), render=False, quiet=True)
        assert (
            f"dec://{entry['id']}"
            in json.loads((kiln / "build/.n2f/manifest.json").read_text())["entries"]["checks"][
                "reads"
            ]
        )
        report = _predict_then_edit(
            kiln, f"dec://{entry['id']}#rationale=note two", file, "note one", "note two"
        )
        will = _would_run(kiln)
        assert "checks" in will
        assert will <= set(report.rules), sorted(will - set(report.rules))
    finally:
        file.write_text(text, encoding="utf-8")
        run_build(load_product(kiln), render=False, quiet=True)


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


# ---- S-180: a change request's patch in its impact report (gate H B1) ------------------------


def test_patch_impact_reports_files_entities_scope_and_rebuild_artifacts(tmp_path: Path) -> None:
    """Gate H B1: a design ECR with a patch lists its files, entities, scope change and rebuild."""
    import subprocess

    from napkin2factory.core.graph.impact import summarize
    from napkin2factory.ecr.lifecycle import new_ecr, run_impact
    from tests.conftest import FIXTURES

    root = copy_product(FIXTURES / "scope" / "external-box", tmp_path / "box", git=True)
    # take the wiring out to `later`, keeping the reverse diff as the change request's patch
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
    patch_dir = root / "changes"
    patch_dir.mkdir(exist_ok=True)
    diff = subprocess.run(
        ["git", "--no-pager", "diff", "--no-color", "-R"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    (patch_dir / "wiring.patch").write_text(diff, encoding="utf-8")
    run_build(load_product(root), render=False, quiet=True)
    new_ecr(
        load_product(root),
        title="Add the wiring",
        reason="Wire the heater and probe to the control box.",
        requested_by="human",
        kind="design",
        patch="changes/wiring.patch",
    )
    report_obj, md = run_impact(load_product(root), "ECR-001")
    impact = report_obj.to_dict()
    assert impact["patch"]["applies"] is True
    assert "model/electrical/supply.yaml" in impact["patch"]["files"]["added"]
    assert "n2f.yaml" in impact["patch"]["files"]["changed"]
    assert {"supply://supply", "circuit://power", "circuit://control"} <= set(
        impact["patch"]["objects"]["added"]
    )
    assert "iface://mains-entry" in impact["patch"]["objects"]["changed"]
    assert [s["words"] for s in impact["patch"]["scope"]] == ["Wiring: left for later → done here"]
    assert {"elec:power", "elec:control", "checks", "report"} <= set(impact["rules"])
    assert "Impact of 0 change(s)" not in md
    assert (
        "This change request carries the designer's work as a patch (`changes/wiring.patch`)" in md
    )
    assert "## What the patch changes" in md
    assert "- Wiring: left for later → done here" in md
    assert "- Wiring: 2 output(s): `control`, `power`" in md
    # an unapplicable patch reports why instead of crashing or silently claiming 0 changes
    bad = patch_dir / "bad.patch"
    bad.write_text("--- a/n2f.yaml\n+++ b/n2f.yaml\n@@ -1,1 +1,1 @@\n-not-there\n+x\n", "utf-8")
    prod = load_product(root)
    rep = compute_impact(prod, [], patch=bad)
    assert rep.patch is not None and not rep.patch.applies and rep.patch.problem
    bad_md = summarize(rep, prod)
    assert "does not apply to the model as it is now" in bad_md


def test_impact_cost_delta_edit_to_unpriced_part(kiln: Path, tmp_path: Path) -> None:
    """An edit to an unpriced part flags the incomplete cost delta (S-187)."""
    from napkin2factory.core.graph.impact import summarize

    root = copy_product(kiln, tmp_path / "kiln-unpriced", git=False)
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


def test_impact_cost_delta_patch_adding_unpriced_part(kiln: Path, tmp_path: Path) -> None:
    """A patch adding an unpriced part flags the incomplete cost delta (S-187)."""
    from napkin2factory.core.graph.impact import summarize

    root = copy_product(kiln, tmp_path / "kiln-patch", git=True)
    patch_dir = root / "changes"
    patch_dir.mkdir(exist_ok=True)
    patch_file = patch_dir / "unpriced.patch"
    patch_content = (
        "--- /dev/null\n"
        "+++ b/model/parts/bracket.yaml\n"
        "@@ -0,0 +1,9 @@\n"
        "+id: bracket\n"
        "+rev: A\n"
        "+name: Bracket\n"
        "+kind: custom\n"
        "+process: sheet-metal\n"
        '+material: {name: mild steel, spec: "1.0 mm CR4 (DC01)"}\n'
        "+finish: none\n"
        "+tolerance_class: ISO2768-m\n"
        "+geometry: none\n"
    )
    patch_file.write_text(patch_content, encoding="utf-8")

    prod = load_product(root)
    rep = compute_impact(prod, [], patch=patch_file)
    assert rep.patch is not None and rep.patch.applies is True
    assert rep.cost_delta == 0.0
    assert rep.cost_complete is False
    assert rep.to_dict()["cost_complete"] is False
    assert "; 1 part(s) without a price: bracket, so the cost change is incomplete" in rep.cost_note
    md = summarize(rep, prod)
    assert "at least +0.00 USD per unit" in md
    assert rep.cost_note in md


def test_impact_cost_delta_priced_only_change(kiln: Path) -> None:
    """A change touching only priced parts leaves cost_note and cost_complete clean (S-187)."""
    from napkin2factory.core.graph.impact import summarize

    prod = load_product(kiln)
    rep = compute_impact(prod, [parse_set("part://door-tray#cost.unit=80 USD")])
    assert rep.cost_delta == 20.0
    assert rep.cost_complete is True
    assert rep.to_dict()["cost_complete"] is True
    assert rep.cost_note == "from declared unit costs × quantities"
    md = summarize(rep, prod)
    assert "**Cost:** +20.00 USD per unit (from declared unit costs × quantities)." in md
    assert "at least" not in md
    assert "incomplete" not in md
