"""DoD 2 (first half) and DoD 7 (second half) of v0.5: a step is a folder.

The toy domain (``tests/fixtures/domains/toy/``) registers one of everything through the
domain contract (``core/domain.py``) and is seen by every registry: its rule family runs in
the build after the parts, its verify kind evaluates, its check stage reports, its gate row
shows in ``n2f status``, its report section renders, its doc helper records a read, its
owner word appears, its interface kind validates, its process passes the general rule pack,
its screen runs on a card and its context contribution shows.  It touches no file under
``src/napkin2factory/core/``.  Registering the mechanical domain in place moved no hash.
"""

from __future__ import annotations

import dataclasses
import json
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from napkin2factory.cli.app import app
from napkin2factory.core import registry as registry_mod
from napkin2factory.core.graph.hashing import sha256_file
from napkin2factory.core.graph.impact import compute_impact, parse_set
from napkin2factory.core.graph.rules import build_rules
from napkin2factory.core.graph.runner import explain_build, run_build
from napkin2factory.core.loader import load_product, validate
from napkin2factory.core.registry import UnknownName, installed, registry
from tests.conftest import EXAMPLES, FIXTURES, copy_product
from tests.fixtures.domains import toy

TOY_PRODUCT = FIXTURES / "products" / "toy"
SRC = Path(__file__).resolve().parents[2] / "src" / "napkin2factory"


@pytest.fixture(scope="module")
def toy_built(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Path, Any, Any]]:
    """The toy product built once with the toy domain registered (no renders)."""
    with installed(toy.DOMAIN):
        root = copy_product(TOY_PRODUCT, tmp_path_factory.mktemp("toy") / "toy")
        product = load_product(root)
        summary = run_build(product, render=False, quiet=True)
        yield root, product, summary


def _checks(root: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((root / "build/checks/checks.json").read_text())
    return data


def _row(root: Path, rid: str) -> dict[str, Any]:
    return next(r for r in _checks(root)["results"] if r["id"] == rid)


def _cli(*args: str) -> str:
    result = CliRunner().invoke(app, list(args), env={"COLUMNS": "200"})
    return result.output


def test_every_registry_sees_the_toy(toy_built: tuple[Path, Any, Any]) -> None:
    reg = registry()
    assert reg.rule_family("toy").produces == "toy://"
    assert reg.verify_kind("toy_glow").target_schemes == ("toy",)
    assert reg.check_stage("toy").after == ("interface",)
    assert [r.title for r in reg.gate_rows("verify")] == ["Toy things"]
    assert reg.report_section("toy").group == "Product"
    assert reg.doc_helper("toy") is toy.toy_helper
    assert reg.vocabulary("owner")["toy"] == "toy thing"
    assert reg.interface_kind("toy-joint").spec is toy.ToySpec
    assert reg.processes()["toy-cast"].title == "Toy casting"
    assert "toy-glitter" in reg.finishes()
    assert "fun" in reg.categories()
    assert reg.drivers()["toy-swapped"] == "swapped between toys"
    assert [s.name for s in reg.screens()] == ["toy"]
    assert reg.screens()[0].fields == (toy.TOYS,) and reg.screens()[0].phase == "estimate"
    assert reg.style_roles()["toy-shell"].styled
    assert [c.name for c in reg.context_contributions()] == ["toy"]
    assert reg.model_family("toy").folder == "model/toy"
    assert [d.name for d in reg.domains] == ["mechanical", "toy"]


def test_rule_family_runs_after_the_parts_and_before_the_checks(
    toy_built: tuple[Path, Any, Any],
) -> None:
    root, product, summary = toy_built
    order = [r.id for r in build_rules(product)]
    assert order.index("toy:widget") > order.index("part:plate")
    assert order.index("toy:widget") < order.index("checks")
    ran = summary["ran"]
    assert ran.index("part:plate") < ran.index("toy:widget") < ran.index("checks")
    assert json.loads((root / "build/toy/widget.json").read_text())["glow"] == 3
    # the target table is derived from the families: the toy is checked, not drawn
    assert "toy" in registry().target_kinds()["checks"]
    assert "toy" not in registry().target_kinds()["drawings"]


def test_the_rule_family_is_a_build_target_on_the_command_line(
    toy_built: tuple[Path, Any, Any],
) -> None:
    """B-0074 (S-129): ``n2f build --target`` offers every registered family by its name."""
    from napkin2factory.cli.build import targets

    root, _, _ = toy_built
    assert {"toy", "geometry", "drawings", "docs", "checks", "all"} <= set(targets())
    out = _cli("build", "-C", str(root), "--target", "toy", "--explain", "--json")
    plan = [step["rule"] for step in json.loads(out)["plan"]]
    assert "toy:widget" in plan and "part:plate" in plan  # the family and what it waits for
    assert not [r for r in plan if r.startswith(("drawing:", "doc:", "checks", "report"))]
    unknown = CliRunner().invoke(app, ["build", "-C", str(root), "--target", "glow"])
    assert unknown.exit_code != 0 and "toy" in unknown.output, unknown.output


def test_verify_kind_evaluates(toy_built: tuple[Path, Any, Any]) -> None:
    root, _, _ = toy_built
    row = _row(root, "req://REQ-001")
    assert row["status"] == "pass", row
    assert row["message"] == "glow = 3 >= 2"
    from napkin2factory.core.checks.evidence import evidence_key

    # a sign-off held against the thing compares with the core's key for its scheme
    assert row["evidence_keys"]["toy://widget"] == evidence_key(
        load_product(root), root / "build", "toy://widget"
    )


def test_check_stage_reports(toy_built: tuple[Path, Any, Any]) -> None:
    root, _, _ = toy_built
    row = _row(root, "toy://widget")
    assert (row["kind"], row["status"], row["title"]) == ("toy", "pass", "Widget glows")


def test_gate_row_shows_in_status(toy_built: tuple[Path, Any, Any]) -> None:
    root, _, _ = toy_built
    out = _cli("status", "-C", str(root))
    assert "Toy things: 1 check: 1 OK" in out, out
    verify = next(
        g
        for g in json.loads(_cli("status", "-C", str(root), "--json"))["gates"]
        if g["name"] == "verify"
    )
    assert verify["detail"]["rows"] == [{"title": "Toy things", "summary": "1 check: 1 OK"}]


def test_report_section_renders(toy_built: tuple[Path, Any, Any]) -> None:
    root, _, _ = toy_built
    html = (root / "build/report/index.html").read_text()
    assert '<section class="card" id="toy">' in html and "<td>Widget</td>" in html
    nav = html.split('<nav class="side"', 1)[1].split("</nav>", 1)[0]
    # at the end of its group: after the last Product section, before Verification
    assert nav.index('data-sec="joints"') < nav.index('data-sec="toy"')
    assert nav.index('data-sec="toy"') < nav.index("Verification")
    assert json.loads((root / "build/report/report.json").read_text())["within_budget"]
    reads = json.loads((root / "build/.n2f/manifest.json").read_text())["entries"]["report"][
        "reads"
    ]
    assert "toy://widget#glow" in reads


def test_doc_helper_records_a_read(toy_built: tuple[Path, Any, Any]) -> None:
    root, _, _ = toy_built
    page = (root / "build/docs/guide/page.md").read_text()
    assert "The Widget sits on the Plate." in page
    reads = json.loads((root / "build/docs/guide/reads.json").read_text())
    assert "toy://widget#name" in reads["reads"]
    assert reads["values"]["toy://widget#name"] == "Widget"  # valued, so a change is caught
    assert _row(root, "doc://guide")["status"] == "pass"


def test_vocabulary_word_in_the_owner_view(toy_built: tuple[Path, Any, Any]) -> None:
    root, _, _ = toy_built
    out = _cli("check", "-C", str(root), "--all")
    assert "toy thing widget" in out, out


def test_interface_kind_validates(toy_built: tuple[Path, Any, Any]) -> None:
    root, product, _ = toy_built
    iface = product.interfaces["plate-peg"]
    assert iface.kind == "toy-joint" and isinstance(iface.spec, toy.ToySpec)
    row = _row(root, "iface://plate-peg")
    assert (row["status"], row["message"]) == ("pass", "it snaps firm")
    bad = root.parent / "bad-kind"
    shutil.copytree(root, bad, ignore=shutil.ignore_patterns("build", ".git"))
    path = bad / "model/interfaces/plate-peg.yaml"
    path.write_text(path.read_text().replace("toy-joint", "glue-joint"))
    _, problems = validate(bad)
    text = " ".join(p.message for p in problems.errors)
    assert "unknown interface kind 'glue-joint'" in text and "toy-joint" in text, text


def test_process_passes_the_general_rule_pack(toy_built: tuple[Path, Any, Any]) -> None:
    root, product, _ = toy_built
    assert product.parts["plate"].process == "toy-cast"
    assert _row(root, "rule://general-v0/custom-part-complete@plate")["status"] == "pass"


def test_screen_runs_on_a_card(toy_built: tuple[Path, Any, Any]) -> None:
    from napkin2factory.concepts.screening import screen
    from napkin2factory.core.model import ConceptCard

    card = ConceptCard.model_validate(
        {"id": "C-001", "title": "Toy chest", "status": "exploring", "envelope": {"toys": 5}}
    )
    result = screen(card, None)
    assert result.estimates["toy_count"].value == "5 toys"
    assert [r.id for r in result.rules][-1] == "toy-count"


def test_screen_declares_its_fields_and_phase(toy_built: tuple[Path, Any, Any]) -> None:
    """B-0089 (S-129): ``Screen(fields=…, phase=…)`` is the contract, no decorator needed."""
    from napkin2factory.concepts.screens import card_fields, fields_of, phase_of
    from napkin2factory.core.concepts import render_card
    from napkin2factory.core.domain import Screen

    screen = registry().screens()[0]
    assert fields_of(screen) == (toy.TOYS,) and phase_of(screen) == "estimate"
    assert "envelope.toys" in [f.name for f in card_fields()]
    skeleton = render_card({"id": "C-001", "title": "Toy chest"})
    assert "toys (like 5)" in skeleton, skeleton
    with pytest.raises(ValueError, match="unknown phase 'later'; known: measure, estimate"):
        Screen("late", toy.toy_screen, phase="later")


def test_style_role_is_a_role_while_the_domain_is_installed(
    toy_built: tuple[Path, Any, Any],
) -> None:
    """B-0089 (S-129): a domain's style role validates, is styled, and keys a palette."""
    from napkin2factory.core.model import Part
    from napkin2factory.core.model.style import (
        ROLE_ALIASES,
        STYLE_ROLES,
        STYLED_ROLES,
        StyleFile,
        canonical_role,
    )

    _, product, _ = toy_built
    assert STYLE_ROLES[-1] == "toy-shell" and "toy-shell" in STYLED_ROLES  # live views
    assert ROLE_ALIASES["casing"] == "toy-shell" and canonical_role("casing") == "toy-shell"
    part = Part.model_validate({"id": "x", "name": "x", "role": "casing"})
    assert part.role == "casing"
    style = StyleFile.model_validate({"palette": {"toy-shell": "#123456"}})
    assert style.colour("toy-shell") == "#123456"
    assert StyleFile().colour("toy-shell") == StyleFile().colour("default")
    # a part naming the role reads the domain's code; the toy's own parts do not
    product.parts["plate"].role = "toy-shell"
    try:
        rules = {r.id: r for r in build_rules(product, render=False)}
        assert "domain:toy" in rules["part:plate"].inputs
    finally:
        product.parts["plate"].role = None
    rules = {r.id: r for r in build_rules(product, render=False)}
    assert "domain:toy" not in rules["part:plate"].inputs
    assert "domain:toy" in rules["validate"].inputs


def test_a_role_no_domain_registers_lists_the_known_ones() -> None:
    from napkin2factory.core.model import Part

    with pytest.raises(ValidationError) as err:
        Part.model_validate({"id": "x", "name": "x", "role": "glow-panel"})
    assert "unknown style role 'glow-panel'; known: body, opening" in str(err.value)


def test_context_contribution(toy_built: tuple[Path, Any, Any]) -> None:
    from napkin2factory.core.context import module_context, render_text

    _, product, _ = toy_built
    ctx = module_context(product, "box")
    assert ctx["domains"][0]["lines"] == ["- toy://widget: Widget on part://plate (glow 3)"]
    assert "## Toy things on its parts" in render_text(ctx)


#: An edit of every field of the toy thing (``widget.yaml``: the line before, the line after,
#: the value ``--set`` gives) and of the toy interface.  The toy rule must rerun for each field
#: and its output change (D5, gate E B2); impact must name every rule the rebuild runs (gate E
#: B1, C14).  ``test_every_toy_field_is_edited`` fails when the schema gains a field this table
#: does not edit.
TOY_EDITS: dict[str, tuple[str, str, str, str]] = {
    "glow": ("model/toy/widget.yaml", "glow: 3", "glow: 5", "5"),
    "name": ("model/toy/widget.yaml", "name: Widget", "name: Gadget", "Gadget"),
    "part": ("model/toy/widget.yaml", "part: part://plate", "part: part://peg", "part://peg"),
}
IFACE_EDIT = ("model/interfaces/plate-peg.yaml", "snap: firm", "snap: loose", "loose")


def test_every_toy_field_is_edited() -> None:
    assert set(TOY_EDITS) == set(toy.ToyThing.model_fields) - {"id"}


@pytest.mark.parametrize(
    ("uri", "edit"),
    [*((f"toy://widget#{f}", e) for f, e in sorted(TOY_EDITS.items()))]
    + [("iface://plate-peg#spec.snap", IFACE_EDIT)],
)
def test_impact_is_a_superset_of_the_rebuild(
    toy_built: tuple[Path, Any, Any], uri: str, edit: tuple[str, str, str, str]
) -> None:
    """Gate E: impact covers what the build reruns, for every field a domain's object has."""
    root, _, _ = toy_built
    rel, old, new, value = edit
    product = load_product(root)
    run_build(product, render=False, quiet=True)  # `n2f check` above built with renders
    report = compute_impact(product, [parse_set(f"{uri}={value}")])
    file = root / rel
    text = file.read_text()
    try:
        assert text.count(old) == 1
        file.write_text(text.replace(old, new))
        product = load_product(root)
        will = {rid for rid, run, _ in explain_build(product, render=False) if run}
        ran = set(run_build(product, render=False, quiet=True)["ran"])
        assert ran <= set(report.rules), sorted(ran - set(report.rules))
        assert ran <= will
        if uri.startswith("toy://"):
            # the toy rule read the field through its recording accessor, so it reran (B2)
            field = uri.split("#", 1)[1]
            assert "toy:widget" in ran and "part:plate" not in ran
            record = json.loads((root / "build/toy/widget.json").read_text())
            assert str(record[field]) == value
        else:
            assert "part:plate" in ran  # the joint's party reads the interface
    finally:
        file.write_text(text)
        run_build(load_product(root), render=False, quiet=True)


def test_a_stage_and_a_section_record_the_fields_they_read(
    toy_built: tuple[Path, Any, Any],
) -> None:
    """B2: a check stage and a report section read through their context's recording accessor."""
    root, _, _ = toy_built
    entries = json.loads((root / "build/.n2f/manifest.json").read_text())["entries"]
    assert {"toy://widget#name", "toy://widget#part", "toy://widget#glow"} <= set(
        entries["checks"]["reads"]
    )
    assert {"toy://widget#name", "toy://widget#glow"} <= set(entries["report"]["reads"])
    assert {"toy://widget#name", "toy://widget#part", "toy://widget#glow"} <= set(
        entries["toy:widget"]["reads"]
    )


def test_a_domain_code_change_reruns_its_rules_only(
    toy_built: tuple[Path, Any, Any], tmp_path: Path
) -> None:
    """Gate E: every registry is hashed into the rules that read it, and nothing else."""
    root, _, _ = toy_built
    copy = tmp_path / "toy_domain"
    shutil.copytree(toy.ROOT, copy, ignore=shutil.ignore_patterns("__pycache__"))
    moved = dataclasses.replace(toy.DOMAIN, root=copy)
    registry_mod.unregister("toy")
    try:
        registry_mod.register(moved)
        product = load_product(root)
        run_build(product, render=False, quiet=True)  # the new root's hash, once
        (copy / "toy.html.j2").write_text((copy / "toy.html.j2").read_text() + "\n")
        registry_mod._tree_hash.cache_clear()
        rerun = {rid for rid, run, _ in explain_build(product, render=False) if run}
        # its own rule, and every rule reading a registry it adds to (gate E): the bom too,
        # since its build plan prints the toy's driver words and interface-kind title (S-138)
        assert {"toy:widget", "validate", "bom", "doc:guide", "checks", "report"} <= rerun
        assert not {r for r in rerun if r.startswith(("part:", "asm:", "drawing:"))}
    finally:
        registry_mod.unregister("toy")
        registry_mod.register(toy.DOMAIN)
        registry_mod._tree_hash.cache_clear()


def test_the_toy_touches_no_core_file() -> None:
    """The count of DoD 2: no file of the package names the toy domain's identifiers."""
    words = ("toy_glow", "toy-joint", "toy://", "toy-cast", "ToyThing")
    hits = [
        str(p.relative_to(SRC))
        for p in SRC.rglob("*")
        if p.is_file()
        and p.suffix in (".py", ".yaml", ".j2")
        and any(w in p.read_text(encoding="utf-8") for w in words)
    ]
    assert hits == []


# ---- DoD 7 (second half): unknown names are errors that list the known values ----------------


def test_an_uninstalled_verify_kind_lists_the_installed_ones() -> None:
    from napkin2factory.core.model import Verify

    with pytest.raises(ValidationError) as err:
        Verify.model_validate({"kind": "wiring_load", "target": "part://x", "op": "<", "value": 1})
    text = str(err.value)
    assert "unknown verify kind 'wiring_load'" in text
    for kind in ("param_bound", "geometry_prop", "calc", "manual", "rule"):
        assert kind in text


def test_a_product_naming_an_uninstalled_kind_fails_validation(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", git=False)
    reqs = root / "model/requirements.yaml"
    reqs.write_text(reqs.read_text().replace("kind: geometry_prop", "kind: wiring_load", 1))
    _, problems = validate(root)
    text = " ".join(p.message for p in problems.errors)
    assert "unknown verify kind 'wiring_load'; known: param_bound" in text, text


@pytest.mark.parametrize(
    ("lookup", "name", "known"),
    [
        (lambda r, n: r.rule_family(n), "wiring", "part"),
        (lambda r, n: r.verify_kind(n), "wiring", "calc"),
        (lambda r, n: r.check_stage(n), "wiring", "interference"),
        (lambda r, n: r.report_section(n), "wiring", "overview"),
        (lambda r, n: r.doc_helper(n), "wiring", "build_step"),
        (lambda r, n: r.interface_kind(n), "wiring", "bolt-pattern"),
        (lambda r, n: r.model_family(n), "wiring", "known:"),
        (lambda r, n: r.domain(n), "wiring", "mechanical"),
        (lambda r, n: r.gate_rows(n), "wiring", "verify"),
        (
            lambda r, n: (
                r.target_kinds()[n]
                if n in r.target_kinds()
                else __import__("napkin2factory.core.graph.rules", fromlist=["x"]).rules_for_target(
                    [], n
                )
            ),
            "wiring",
            "geometry",
        ),
    ],
)
def test_every_lookup_error_names_the_known_values(lookup: Any, name: str, known: str) -> None:
    with pytest.raises(UnknownName) as err:
        lookup(registry(), name)
    assert f"'{name}'" in str(err.value) and known in str(err.value)


def test_table_values_list_the_known_ones() -> None:
    from napkin2factory.core.model import Part

    with pytest.raises(ValidationError) as err:
        Part.model_validate({"id": "x", "name": "x", "process": "anodising"})
    assert "unknown process 'anodising'; known: sheet-metal" in str(err.value)


# ---- registering in place moved nothing (FOUNDATION §7 risk 1) -------------------------------


def _old_package_hash(*subdirs: str) -> str:
    """The subtree hash rules used before the registry (core/graph/rules.py at v0.4)."""
    from napkin2factory import __version__
    from napkin2factory.core.graph.hashing import sha256_text, sha256_tree

    parts = {
        d: sha256_tree(SRC / d, (".py", ".js", ".html", ".css", ".yaml", ".j2")) for d in subdirs
    }
    parts["version"] = __version__
    return sha256_text("\n".join(f"{k}={v}" for k, v in sorted(parts.items())))


@pytest.fixture
def mechanical_only() -> Iterator[None]:
    """The installed domains alone, for the duration of a test (the toy set aside)."""
    toy_on = any(d.name == "toy" for d in registry().domains)
    if toy_on:
        registry_mod.unregister("toy")
    try:
        yield
    finally:
        if toy_on:
            registry_mod.register(toy.DOMAIN)


def test_mechanical_family_hashes_equal_the_old_subtree_hashes(mechanical_only: None) -> None:
    old = {
        "drawing": ("drawings",),
        "bom": ("bom", "catalog"),
        "asmsheet": ("drawings", "bom"),
        "doc": ("docs",),
        # moved on purpose: the checks family hashes the calc kit since B-0078 (S-126)
        "checks": ("core/checks", "rulepacks", "bom", "catalog", "calckit"),
        "report": ("report", "docs"),
        "site": ("report",),
    }
    reg = registry()
    for name, subdirs in old.items():
        assert reg.family_hash(reg.rule_family(name)) == _old_package_hash(*subdirs), name
    product = load_product(EXAMPLES / "bracket")
    rules = {r.id: r for r in build_rules(product)}
    # moved on purpose, once: the core's open-set tables are inputs of the rules that read
    # them since gate E B4 (S-138); the family code hashes above did not move
    tables = {
        "table:interface_kinds",
        "table:processes",
        "table:finishes",
        "table:requirement_categories",
        "table:drivers",
        "table:style_roles",
    }
    assert set(rules["validate"].inputs) == {"model", "manifest", "operator", "changes"} | tables
    assert rules["bom"].inputs == {
        "code": _old_package_hash("bom", "catalog"),
        "table:drivers": sha256_file(registry_mod.DATA / "drivers.yaml"),
        "table:interface_kinds": sha256_file(registry_mod.DATA / "interface_kinds.yaml"),
    }
    assert [r.kind for r in build_rules(product)] == [
        "validate",
        "part",
        "asm",
        "drawing",
        "bom",
        "asmsheet",
        "doc",
        "doc",
        "checks",
        "report",
        "site",
    ]


def test_a_calc_kit_change_reruns_the_checks_and_no_part(
    mechanical_only: None, tmp_path: Path
) -> None:
    """B-0078 (S-126): editing a calc-kit formula changes the ``checks`` rule's code input.

    Calc requirements and the ``calc-case`` rows run the kit's code inside the checks rule;
    the parts, assemblies and every other rule do not, so their inputs stay put.  The edit is
    made in a copy of the package, which the code hashes are pointed at.
    """
    copy = tmp_path / "napkin2factory"
    shutil.copytree(SRC, copy, ignore=shutil.ignore_patterns("__pycache__"))
    product = load_product(EXAMPLES / "bracket")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(registry_mod, "SYSTEM_ROOT", copy)
        try:
            registry_mod.package_hash.cache_clear()
            before = {r.id: dict(r.inputs) for r in build_rules(product, render=False)}
            kit = copy / "calckit" / "power.py"
            kit.write_text(kit.read_text() + "\n# a formula edit\n")
            registry_mod.package_hash.cache_clear()
            after = {r.id: dict(r.inputs) for r in build_rules(product, render=False)}
        finally:
            registry_mod.package_hash.cache_clear()
    assert before.keys() == after.keys()
    assert any(rid.startswith("part:") for rid in before)
    assert any(rid.startswith("asm:") for rid in before)
    moved = {rid for rid in before if before[rid] != after[rid]}
    assert moved == {"checks"}
    assert before["checks"]["code"] != after["checks"]["code"]
