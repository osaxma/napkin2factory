"""v0.5 M4, DoD 5: scope is data (FOUNDATION F11).

``n2f.yaml`` ``scope:`` says per domain whether its work is ``in`` the product, done
elsewhere (``external``: a stub module with ports stands for it) or ``later`` (its
requirements and gate rows are left out of the Design and Verify gates, with a visible note;
a safety requirement never is).  ``n2f status``, the report overview and the release package
cover say it; ``release.json`` records it; ``n2f impact`` does not change with it.  The load
case family (``model/loads/``, ``load://``) is the reserved slot: defined and validated, read
by no solver.
"""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from napkin2factory.cli.app import app
from napkin2factory.core.build_units import BuildUnits
from napkin2factory.core.checks.stage import (
    compute_stage,
    later_requirements,
    requirement_in_domain,
    scope_entries,
)
from napkin2factory.core.graph.impact import compute_impact, parse_set
from napkin2factory.core.graph.runner import run_build
from napkin2factory.core.lint import lint
from napkin2factory.core.loader import load_product, validate
from napkin2factory.core.model import Manifest
from napkin2factory.core.registry import installed
from tests.conftest import EXAMPLES, FIXTURES, copy_product
from tests.fixtures.domains import toy

SCOPE = FIXTURES / "scope"


def _problems(root: Path) -> list[tuple[str, str, str]]:
    """``(file relative to root, rule, message)`` of every validation problem."""
    _, problems = validate(root)
    out = []
    for p in problems.items:
        try:
            rel = str(Path(p.file).relative_to(root))
        except ValueError:
            rel = p.file
        out.append((rel, p.rule, p.message))
    return out


def _cli(*args: str) -> str:
    result = CliRunner().invoke(app, list(args), env={"COLUMNS": "200"})
    return result.output


@pytest.fixture(scope="module")
def rig(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """The external-stub fixture built once (no renders)."""
    root = copy_product(SCOPE / "external", tmp_path_factory.mktemp("rig") / "rig")
    run_build(load_product(root), render=False, quiet=True)
    yield root


# ---- the schema ---------------------------------------------------------------------------


def test_manifest_scope_is_optional_and_strict() -> None:
    base = {"product": {"id": "x", "name": "X"}}
    assert Manifest.model_validate(base).scope == {}
    m = Manifest.model_validate(
        {**base, "scope": {"electrical": {"state": "later", "decision": "DEC-004"}}}
    )
    assert m.scope["electrical"].state == "later"
    with pytest.raises(ValidationError, match="state"):
        Manifest.model_validate({**base, "scope": {"electrical": {"state": "soon"}}})
    with pytest.raises(ValidationError, match="stub"):
        Manifest.model_validate(
            {**base, "scope": {"electrical": {"state": "later", "stub": "asm://controls"}}}
        )
    with pytest.raises(ValidationError):
        Manifest.model_validate({**base, "scope": {"electrical": {"state": "in", "decision": "x"}}})


# ---- external: a stub module with ports, or validation names the file --------------------------


def test_external_stub_validates() -> None:
    assert _problems(SCOPE / "external") == []


def test_external_without_a_stub_names_the_manifest() -> None:
    problems = _problems(SCOPE / "no-stub")
    assert [(f, r) for f, r, _ in problems] == [("n2f.yaml", "external")]
    assert "no module stands for it" in problems[0][2]


def _edit(root: Path, rel: str, old: str, new: str) -> None:
    path = root / rel
    text = path.read_text(encoding="utf-8")
    assert old in text, (rel, old)
    path.write_text(text.replace(old, new), encoding="utf-8")


def test_a_stub_with_children_or_without_ports_names_its_file(tmp_path: Path) -> None:
    root = copy_product(SCOPE / "external", tmp_path / "rig", git=False)
    stub = "model/assemblies/controls.yaml"
    _edit(root, stub, "ports: [iface://controls-mount]\n", "children:\n  - {part: part://frame}\n")
    found = {(f, r) for f, r, _ in _problems(root)}
    assert (stub, "external") in found  # children, and no ports
    messages = [m for f, _, m in _problems(root) if f == stub]
    assert any("has no children here" in m for m in messages)
    assert any("needs its ports" in m for m in messages)
    assert any("controls-mount joins this module" in m for m in messages)


def test_a_stub_must_be_the_one_scope_names(tmp_path: Path) -> None:
    root = copy_product(SCOPE / "external", tmp_path / "rig", git=False)
    _edit(root, "n2f.yaml", "stub: asm://controls", "stub: asm://panel")
    assert [(f, r) for f, r, _ in _problems(root)] == [("n2f.yaml", "external")]
    _edit(root, "n2f.yaml", "stub: asm://panel", "stub: asm://rig")
    problems = _problems(root)
    assert [(f, r) for f, r, _ in problems] == [("model/assemblies/rig.yaml", "external")]
    assert "build: unit" in problems[0][2]


def test_scope_decision_must_exist(tmp_path: Path) -> None:
    root = copy_product(SCOPE / "external", tmp_path / "rig", git=False)
    _edit(root, "n2f.yaml", "decision: DEC-002", "decision: DEC-009")
    problems = _problems(root)
    assert [(f, r) for f, r, _ in problems] == [("n2f.yaml", "scope")]
    assert "DEC-009" in problems[0][2]


def test_an_asm_party_is_still_refused_unless_it_is_a_stub(tmp_path: Path) -> None:
    root = copy_product(SCOPE / "external", tmp_path / "rig", git=False)
    _edit(root, "model/assemblies/controls.yaml", "build: external\n", "")
    rules = {r for _, r, _ in _problems(root)}
    assert "port" in rules  # the loader's own rule: an interface joins two parts (P4)


def test_build_units_supply_the_stub_not_build_it(rig: Path) -> None:
    units = BuildUnits(load_product(rig))
    assert units.is_external("controls")
    assert units.order() == ["rig"]  # the stub is no step
    assert units.supplied("rig") == [("controls", 1, ["iface://controls-mount"])]
    assert units.folded_ids("rig") == ["rig"]
    # its port closes where it is fitted, in the step of the unit that lists it
    assert units.unplaced_joints() == []
    joint = next(j for j in units.joints("rig") if j.iface == "controls-mount")
    assert joint.closes_in == "rig" and not joint.between_units
    plan = json.loads((rig / "build" / "bom" / "build-plan.json").read_text(encoding="utf-8"))
    assert plan["joints_in_no_step"] == []
    assert [j["interface"] for j in plan["units"]["rig"]["joints"]] == ["iface://controls-mount"]


# ---- later: left out of the gates with a note; safety never is ------------------------------


def test_requirements_belong_to_a_domain_by_tag_or_registration() -> None:
    product = load_product(SCOPE / "external")
    assert later_requirements(product) == {"wiring": ["REQ-002", "REQ-003"]}
    assert not requirement_in_domain(product.requirements["REQ-001"], "wiring")


def test_later_requirements_leave_the_verify_gate_with_a_note(rig: Path) -> None:
    rep = compute_stage(load_product(rig))
    verify = next(g for g in rep.gates if g.name == "verify")
    text = "\n".join(verify.blockers)
    assert "REQ-002" not in text  # left out: the wiring is later
    assert "REQ-003" in text  # a safety requirement never is
    note = next(r for r in verify.detail["rows"] if r["title"] == "Wiring")
    assert note["summary"] == (
        "later (DEC-002) — not checked at this stage; 1 requirement waits for it: REQ-002; "
        "REQ-003 is about safety and still needs a sign-off"
    )
    # without the scope the same requirement blocks: nothing was hidden, only moved
    product = load_product(rig)
    product.manifest.scope.pop("wiring")
    verify = next(g for g in compute_stage(product).gates if g.name == "verify")
    assert any(b.startswith("REQ-002") for b in verify.blockers)
    assert not any(r["title"] == "Wiring" for r in verify.detail.get("rows", []))


def test_status_shows_the_scope_rows(rig: Path) -> None:
    out = _cli("status", "--dir", str(rig))
    assert "Scope (what this product covers)" in out
    assert "Electrical: done elsewhere — the controls come wired from the supplier (DEC-001)" in out
    assert "Wiring: later — Wiring comes later (DEC-002)" in out
    assert "Wiring: later (DEC-002) — not checked at this stage" in out
    data = json.loads(_cli("status", "--dir", str(rig), "--json"))
    assert [(s["domain"], s["state"]) for s in data["scope"]] == [
        ("electrical", "external"),
        ("wiring", "later"),
    ]


def test_no_scope_reads_as_before(tmp_path: Path) -> None:
    root = copy_product(FIXTURES / "ports", tmp_path / "ports", git=False)
    rep = compute_stage(load_product(root))
    assert rep.scope == [] and "scope" not in rep.to_dict()
    assert "Scope" not in _cli("status", "--dir", str(root))
    assert scope_entries(load_product(root)) == []


def test_a_later_domains_gate_row_is_left_out(tmp_path: Path) -> None:
    """The toy domain's own row goes; its requirement too; its content is a lint warning."""
    with installed(toy.DOMAIN):
        root = copy_product(FIXTURES / "products" / "toy", tmp_path / "toy", git=False)
        decs = root / "model" / "decisions.yaml"
        decs.write_text(
            "decisions:\n  - {id: DEC-001, date: 2026-11-01, title: Toys come later, "
            "decision: The toys come later.}\n",
            encoding="utf-8",
        )
        run_build(load_product(root), render=False, quiet=True)
        before = next(g for g in compute_stage(load_product(root)).gates if g.name == "verify")
        assert any(r["title"] == "Toy things" for r in before.detail["rows"])
        with (root / "n2f.yaml").open("a", encoding="utf-8") as f:
            f.write("scope:\n  toy: {state: later, decision: DEC-001}\n")
        product = load_product(root)
        assert later_requirements(product) == {"toy": ["REQ-001"]}  # its verify kind and category
        verify = next(g for g in compute_stage(product).gates if g.name == "verify")
        titles = [r["title"] for r in verify.detail["rows"]]
        assert titles == ["Toy"]
        assert "1 requirement waits for it: REQ-001" in verify.detail["rows"][0]["summary"]
        warnings = [p for p in lint(product).warnings if p.rule == "L15-scope"]
        assert len(warnings) == 1 and "toy://widget" in warnings[0].message
        assert "set scope to in or remove it" in warnings[0].hint


def test_a_scope_without_a_decision_is_a_lint_warning(tmp_path: Path) -> None:
    root = copy_product(SCOPE / "external", tmp_path / "rig", git=False)
    _edit(root, "n2f.yaml", "wiring: {state: later, decision: DEC-002}", "wiring: {state: later}")
    found = [p for p in lint(load_product(root)).warnings if p.rule == "L15-scope"]
    assert [p.subject for p in found] == ["scope.wiring"]


# ---- the report, the package cover, release.json -------------------------------------------


def test_report_overview_says_the_scope(rig: Path) -> None:
    html = (rig / "build" / "report" / "index.html").read_text(encoding="utf-8")
    line = re.search(r'<p class="scope" id="scope">(.*?)</p>', html)
    assert line is not None
    assert line.group(1) == (
        "<strong>Scope.</strong> Electrical: done elsewhere — the controls come wired from the "
        "supplier (DEC-001); Wiring: later — Wiring comes later (DEC-002)."
    )


def test_release_cover_and_record_carry_the_scope(rig: Path, tmp_path: Path) -> None:
    import zipfile

    from napkin2factory.ecr.release import make_bundle

    product = load_product(rig)
    zip_path = make_bundle(product, rig / "build", "v1.0.0", tmp_path)
    with zipfile.ZipFile(zip_path) as zf:
        cover = zf.read("v1.0.0/README.txt").decode("utf-8")
        record: dict[str, Any] = json.loads(zf.read("v1.0.0/release.json"))
    assert cover.splitlines()[:5] == [
        "Scope fixture rig — Revision v1.0.0",
        "",
        "Scope: Electrical: done elsewhere — the controls come wired from the supplier (DEC-001)",
        "Scope: Wiring: later — Wiring comes later (DEC-002)",
        "",
    ]
    assert record["revision"] == "v1.0.0" and record["product"] == "rig"
    assert [(s["domain"], s["state"], s["decision"]) for s in record["scope"]] == [
        ("electrical", "external", "DEC-001"),
        ("wiring", "later", "DEC-002"),
    ]
    assert record["scope"][0]["stub"] == "asm://controls"


def test_release_cover_without_scope_has_no_scope_line(tmp_path: Path) -> None:
    from napkin2factory.ecr.release import make_bundle, release_record

    root = copy_product(FIXTURES / "ports", tmp_path / "ports", git=False)
    product = load_product(root)
    (root / "build").mkdir()
    zip_path = make_bundle(product, root / "build", "v0.1.0", tmp_path / "out")
    import zipfile

    with zipfile.ZipFile(zip_path) as zf:
        assert "Scope" not in zf.read("v0.1.0/README.txt").decode("utf-8")
    assert release_record(product, "v0.1.0")["scope"] == []


# ---- impact does not change with scope ------------------------------------------------------


def test_impact_is_unchanged_by_scope(rig: Path, tmp_path: Path) -> None:
    edits = [parse_set("req://REQ-002#verify.note=Measure it twice.")]
    with_scope = compute_impact(load_product(rig), edits).to_dict()
    plain = tmp_path / "plain"
    shutil.copytree(rig, plain)
    text = (plain / "n2f.yaml").read_text(encoding="utf-8")
    (plain / "n2f.yaml").write_text(text.split("scope:")[0], encoding="utf-8")
    without = compute_impact(load_product(plain), edits).to_dict()
    assert with_scope == without
    edits = [parse_set("part://frame#name=Big frame")]
    assert (
        compute_impact(load_product(rig), edits).to_dict()
        == compute_impact(load_product(plain), edits).to_dict()
    )


# ---- load cases: the reserved slot ---------------------------------------------------------


def test_load_cases_resolve_and_validate(tmp_path: Path) -> None:
    product = load_product(SCOPE / "external")
    assert product.resolve("load://shelf").acts_on.id == "frame"
    root = copy_product(SCOPE / "external", tmp_path / "rig", git=False)
    _edit(root, "model/requirements.yaml", "frame, load://shelf]", "frame, load://bench]")
    problems = _problems(root)
    assert [f for f, _, _ in problems] == ["model/requirements.yaml"]
    assert "load://bench does not exist" in problems[0][2]
    _edit(root, "model/requirements.yaml", "frame, load://bench]", "frame, load://shelf]")
    _edit(root, "model/loads/shelf.yaml", "acts_on: part://frame", "acts_on: part://beam")
    problems = _problems(root)
    assert [(f, r) for f, r, _ in problems] == [("model/loads/shelf.yaml", "load")]
    _edit(root, "model/loads/shelf.yaml", "acts_on: part://beam", "acts_on: part://frame")
    _edit(root, "model/loads/shelf.yaml", "value: 4 kg", "value: 4 mm")
    problems = _problems(root)
    assert [f for f, _, _ in problems] == ["model/loads/shelf.yaml"]
    assert "mass load" in problems[0][2]


# ---- the kiln -----------------------------------------------------------------------------------


def test_the_kiln_leaves_electrical_for_later() -> None:
    product = load_product(EXAMPLES / "kiln")
    entry = product.manifest.scope["electrical"]
    assert entry.state == "later" and entry.decision in product.decisions
    assert scope_entries(product)[0]["line"] == (
        "Electrical: later — the electrician wires it; the box keeps its cable entries "
        f"({entry.decision})"
    )
    # no kiln requirement belongs to electrical today: the gate leaves nothing out
    assert later_requirements(product) == {"electrical": []}
