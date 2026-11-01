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


def test_context_contribution(toy_built: tuple[Path, Any, Any]) -> None:
    from napkin2factory.core.context import module_context, render_text

    _, product, _ = toy_built
    ctx = module_context(product, "box")
    assert ctx["domains"][0]["lines"] == ["- toy://widget: Widget on part://plate (glow 3)"]
    assert "## Toy things on its parts" in render_text(ctx)


def test_impact_is_a_superset_of_the_rebuild(toy_built: tuple[Path, Any, Any]) -> None:
    """Gate E: impact still covers what the build reruns, with a registered family."""
    root, _, _ = toy_built
    product = load_product(root)
    run_build(product, render=False, quiet=True)  # `n2f check` above built with renders
    report = compute_impact(product, [parse_set("toy://widget#glow=5")])
    assert "toy:widget" in report.rules and "part:plate" not in report.rules
    thing = root / "model/toy/widget.yaml"
    text = thing.read_text()
    try:
        thing.write_text(text.replace("glow: 3", "glow: 5"))
        product = load_product(root)
        will = {rid for rid, run, _ in explain_build(product, render=False) if run}
        ran = set(run_build(product, render=False, quiet=True)["ran"])
        assert "toy:widget" in ran and "part:plate" not in ran
        assert ran <= set(report.rules), (ran, report.rules)
        assert ran <= will
    finally:
        thing.write_text(text)
        run_build(load_product(root), render=False, quiet=True)


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
        # its own rule, and every rule reading a registry it adds to (gate E)
        assert {"toy:widget", "validate", "doc:guide", "checks", "report"} <= rerun
        assert not {r for r in rerun if r.startswith(("part:", "asm:", "drawing:", "bom"))}
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
    assert set(rules["validate"].inputs) == {"model", "manifest", "operator", "changes"}
    assert rules["bom"].inputs == {"code": _old_package_hash("bom", "catalog")}
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
