"""v0.6 M6: a control box supplied from elsewhere, the scope words, the diff's sections.

``tests/fixtures/scope/external-box`` is a warming box: a heater and a probe in a box whose
control box is bought wired (``build: external``, two cable entries as its ``ports:``, no
children) while the wiring inside the box is designed here (``scope.electrical: in``).
ELECTRICAL_STAGE DoD 5: it validates; each circuit's diagram draws the control box as a
dashed boundary with the terminals that cross into it and nothing inside; removing a port
fails validation naming the module's file and the port.

Then the same box with its wiring done elsewhere and left for later: ``n2f status``, the
report and the release cover say each state in the core's words (S-148, S-152), and the
diff between a Revision that left the wiring for later and one that designed it says
"Wiring: added" (DoD 4's diff half, S-169).

Golden: ``N2F_UPDATE_GOLDENS=1 uv run pytest tests/unit/test_scope_external.py -k golden``
rewrites ``tests/golden/goldens/diff-sections.json``; log it in
``tests/golden/REGENERATION_LOG.md``.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import jinja2
import pytest
from typer.testing import CliRunner

from napkin2factory.cli.app import app
from napkin2factory.core.graph.runner import run_build
from napkin2factory.core.loader import load_product, validate
from napkin2factory.core.model.manifest import scope_words
from napkin2factory.ecr.diff import (
    SECTIONS_FILE,
    compute_diff,
    diff,
    page_sections,
    section_delta,
    sections_block,
)
from napkin2factory.ecr.release import export_data, make_bundle
from tests.conftest import FIXTURES, copy_product

BOX = FIXTURES / "scope" / "external-box"
STUB = "model/assemblies/control-box.yaml"
GOLDENS = Path(__file__).resolve().parents[1] / "golden" / "goldens"
SVG = "{http://www.w3.org/2000/svg}"
LATER_DECISION = (
    "  - id: DEC-003\n    date: 2026-11-02\n    title: The wiring comes later\n"
    "    decision: Design the wiring after the box is made.\n"
)


def _edit(root: Path, rel: str, old: str, new: str) -> None:
    path = root / rel
    text = path.read_text(encoding="utf-8")
    assert old in text, (rel, old)
    path.write_text(text.replace(old, new), encoding="utf-8")


def _cli(*args: str) -> str:
    result = CliRunner().invoke(app, list(args), env={"COLUMNS": "200"})
    return result.output


def _without_wiring(root: Path, scope: str) -> Path:
    """The box with ``model/electrical/`` taken out and the wiring's scope set to ``scope``."""
    shutil.rmtree(root / "model" / "electrical")
    for entry in ("mains-entry", "control-entry"):
        rel = f"model/interfaces/{entry}.yaml"
        text = (root / rel).read_text(encoding="utf-8")
        (root / rel).write_text(re.sub(r"passes: \[[^\]]*\]", "passes: []", text), "utf-8")
    _edit(root, "n2f.yaml", "electrical: {state: in, decision: DEC-001}", scope)
    with (root / "model" / "decisions.yaml").open("a", encoding="utf-8") as f:
        f.write(LATER_DECISION)
    return root


def _scope_line(html: str) -> str:
    found = re.search(r'<p class="scope" id="scope">(.*?)</p>', html)
    assert found is not None
    return found.group(1)


def _report(root: Path) -> str:
    return (root / "build" / "report" / "index.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """The box as the fixture has it (wiring designed here), built once without renders."""
    root = copy_product(BOX, tmp_path_factory.mktemp("box") / "box", git=False)
    run_build(load_product(root), render=False, quiet=True)
    yield root


@pytest.fixture(scope="module")
def elsewhere(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """The wiring done elsewhere: the control box stands for all of it."""
    root = copy_product(BOX, tmp_path_factory.mktemp("elsewhere") / "box", git=False)
    _without_wiring(
        root,
        "electrical: {state: external, decision: DEC-002, stub: asm://control-box, "
        'note: "the control box comes wired from its maker"}',
    )
    run_build(load_product(root), render=False, quiet=True)
    yield root


@pytest.fixture(scope="module")
def later(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """The wiring left for later."""
    root = copy_product(BOX, tmp_path_factory.mktemp("later") / "box", git=False)
    _without_wiring(root, "electrical: {state: later, decision: DEC-003}")
    run_build(load_product(root), render=False, quiet=True)
    yield root


# ---- DoD 5: the control box supplied from elsewhere -----------------------------------------


def test_the_box_validates() -> None:
    product, problems = validate(BOX)
    assert product is not None and not problems.errors, [str(p) for p in problems.errors]
    stub = product.assemblies["control-box"]
    assert stub.build == "external" and not stub.children
    assert [str(p) for p in stub.ports] == ["iface://mains-entry", "iface://control-entry"]
    assert {i.kind for i in product.interfaces.values()} == {"cable-entry"}


def _inside(x: float, y: float, box: tuple[float, float, float, float]) -> bool:
    x0, y0, x1, y1 = box
    eps = 1e-6
    return x0 + eps < x < x1 - eps and y0 + eps < y < y1 - eps


def _drawn_points(tree: ET.Element) -> list[tuple[float, float]]:
    """Every text anchor, pin, line end and path point of a diagram."""
    points: list[tuple[float, float]] = []
    for el in tree.iter():
        tag = el.tag.removeprefix(SVG)
        if tag == "text":
            points.append((float(el.get("x", 0)), float(el.get("y", 0))))
        elif tag == "circle":
            points.append((float(el.get("cx", 0)), float(el.get("cy", 0))))
        elif tag == "line":
            for a, b in (("x1", "y1"), ("x2", "y2")):
                points.append((float(el.get(a, 0)), float(el.get(b, 0))))
        elif tag == "path" and el.get("d"):
            nums = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", el.get("d", ""))]
            points += list(zip(nums[::2], nums[1::2], strict=True))
    return points


@pytest.mark.parametrize(
    ("circuit", "terminals", "entry"),
    [
        ("power", "L, N, PE", "iface://mains-entry"),
        ("control", "C1, C2", "iface://control-entry"),
    ],
)
def test_each_diagram_draws_the_boundary_and_nothing_inside(
    built: Path, circuit: str, terminals: str, entry: str
) -> None:
    words = f"to the external control box, supplied, not built here: {terminals}"
    out = built / "build" / "electrical" / circuit
    record = json.loads((out / "connections.json").read_text(encoding="utf-8"))
    assert record["boundary"] == [
        {"assembly": "asm://control-box", "name": "External control box", "words": words}
    ]
    assert [(e["uri"], e["external"]) for e in record["entries"]] == [(entry, True)]
    # every conductor crosses the box's wall through the entry, to the module
    assert all(w["via"] == entry for w in record["wires"])
    assert all("asm://control-box#" in (w["from"] + w["to"]) for w in record["wires"])
    tree = ET.fromstring((out / "diagram.svg").read_text(encoding="utf-8"))
    (boundary,) = [g for g in tree.iter(f"{SVG}g") if g.get("id", "").startswith("boundary-")]
    rect = boundary.find(f"{SVG}rect")
    assert rect is not None and rect.get("stroke-dasharray")
    assert words in [t.text for t in boundary.iter(f"{SVG}text")]
    x0, y0 = float(rect.get("x", 0)), float(rect.get("y", 0))
    box = (x0, y0, x0 + float(rect.get("width", 0)), y0 + float(rect.get("height", 0)))
    assert not [p for p in _drawn_points(tree) if _inside(*p, box)], "drawn inside the boundary"
    # and the report's Wiring section says it under the diagram
    assert f'<p class="small">{words}</p>' in _report(built)


def test_both_circuits_are_said_together(built: Path) -> None:
    """DoD 5's sentence, across the two diagrams: L, N, PE and two control conductors."""
    crossing = []
    for circuit in ("power", "control"):
        path = built / "build" / "electrical" / circuit / "connections.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        crossing += record["boundary"][0]["words"].split(": ", 1)[1].split(", ")
    assert crossing == ["L", "N", "PE", "C1", "C2"]


@pytest.mark.parametrize(
    ("port", "circuit", "terminal"),
    [("iface://mains-entry", "power", "L"), ("iface://control-entry", "control", "C1")],
)
def test_removing_a_port_names_the_module_file_and_the_port(
    tmp_path: Path, port: str, circuit: str, terminal: str
) -> None:
    root = copy_product(BOX, tmp_path / "box", git=False)
    _edit(root, STUB, f"{port}, " if port.endswith("mains-entry") else f", {port}", "")
    product, problems = validate(root)
    assert problems.errors
    ours = [
        p
        for p in problems.errors
        if Path(p.file) == root / STUB and port in p.message and f"circuit://{circuit}" in p.message
    ]
    assert ours, [str(p) for p in problems.errors]
    assert f"asm://control-box#{terminal}" in ours[0].message
    assert "which is not one of its ports" in ours[0].message
    assert f"add {port} to `ports:` in {STUB}" in ours[0].hint
    # every error names the module's file: nothing else in the box is wrong
    assert {Path(p.file) for p in problems.errors} == {root / STUB}


def test_the_stand_in_is_supplied_not_built_here(built: Path) -> None:
    plan = json.loads((built / "build" / "bom" / "build-plan.json").read_text(encoding="utf-8"))
    step = plan["units"]["warming-box"]
    assert step["supplied"] == [
        {
            "asm": "asm://control-box",
            "id": "control-box",
            "joints": ["Heater cable to the control box", "Probe cable to the control box"],
            "name": "External control box",
            "ports": ["iface://mains-entry", "iface://control-entry"],
            "qty": 1,
            "words": "supplied, not built here",
        }
    ]
    sides = [s for j in step["joints"] for s in j["sides"] if s["part"] == "asm://control-box"]
    assert [s["supplied"] for s in sides] == ["supplied, not built here"] * 2
    # the joint is said by its interface's description (S-152)
    assert sorted(j["how"] for j in step["joints"]) == [
        "The heater's cable leaves the box through the gland in its back, to the control box.",
        "The probe's cable leaves the box through the small gland in its back, to the control box.",
    ]
    html = _report(built)
    assert "<h3>Supplied, not built here</h3>" in html
    assert "<tr><td>External control box</td>" in html


def test_the_wiring_designed_here_is_done_here(built: Path) -> None:
    assert _scope_line(_report(built)) == (
        f"<strong>Scope.</strong> Wiring: {scope_words('in')} — The wiring inside the box is "
        "designed here (DEC-001)."
    )
    out = _cli("status", "--dir", str(built))
    assert "Wiring: done here — The wiring inside the box is designed here (DEC-001)" in out


def test_the_first_build_with_wiring_raises_the_supply_choice(built: Path) -> None:
    """The owner session's premise (``intake-transcripts/wiring-session.md``, DoD 7).

    The heater's 1200 W draws 5.2 A of the 10 A socket circuit: more than half, with a
    larger class on file for the region, so the check offers the owner a choice (E11).
    """
    checks = json.loads((built / "build" / "checks" / "checks.json").read_text("utf-8"))
    (row,) = [r for r in checks["results"] if r["id"] == "elec-rule://supply-headroom@supply"]
    assert row["status"] == "choice"
    assert row["message"].startswith("5.2 A of the 10 A circuit")
    assert [o["id"] for o in row["detail"]["options"]] == ["dedicated", "larger"]


# ---- the scope words: done elsewhere, left for later (S-148, S-152) -------------------------


def test_done_elsewhere_reads_the_cores_words(elsewhere: Path) -> None:
    line = (
        "Wiring: done elsewhere (supplied, not built here) — the control box comes wired from "
        "its maker (DEC-002)"
    )
    assert scope_words("external") == "done elsewhere (supplied, not built here)"
    assert line in _cli("status", "--dir", str(elsewhere))
    html = _report(elsewhere)
    assert _scope_line(html) == f"<strong>Scope.</strong> {line}."
    wiring = html.split('<section class="card" id="wiring">', 1)[1].split("</section>", 1)[0]
    assert line in wiring
    assert "<h3>Supplied, not built here</h3>" in html
    data = json.loads(_cli("status", "--dir", str(elsewhere), "--json"))
    assert [(s["domain"], s["state"]) for s in data["scope"]] == [("electrical", "external")]


def test_left_for_later_reads_the_cores_words(later: Path) -> None:
    line = "Wiring: left for later (not designed here yet) — The wiring comes later (DEC-003)"
    assert scope_words("later") == "left for later (not designed here yet)"
    out = _cli("status", "--dir", str(later))
    assert line in out
    assert "left for later with it: REQ-002 (The heater fits the supply)" in out
    html = _report(later)
    assert _scope_line(html) == (
        f"<strong>Scope.</strong> {line}; left for later with it: REQ-002 (The heater fits the "
        "supply)."
    )
    wiring = html.split('<section class="card" id="wiring">', 1)[1].split("</section>", 1)[0]
    assert line in wiring


def test_the_release_cover_says_what_is_not_included(later: Path, tmp_path: Path) -> None:
    package = make_bundle(load_product(later), later / "build", "v1.0.0", tmp_path)
    with zipfile.ZipFile(package) as zf:
        cover = zf.read("v1.0.0/README.txt").decode("utf-8")
        record: dict[str, Any] = json.loads(zf.read("v1.0.0/release.json"))
    assert cover.splitlines()[:6] == [
        "Warming box — Revision v1.0.0",
        "",
        "Not included in this package:",
        "- Wiring (left for later, not designed here yet; DEC-003 — The wiring comes later). "
        "Left for later with it: REQ-002 (The heater fits the supply). About safety, and still "
        "to be signed off: REQ-001 (Wired by a licensed electrician).",
        "",
        "Scope: Wiring: left for later (not designed here yet) — The wiring comes later (DEC-003)",
    ]
    assert "licensed electrician" not in cover.splitlines()[-1]
    assert [(s["domain"], s["state"]) for s in record["scope"]] == [("electrical", "later")]


def test_the_later_to_in_release_cover_says_so(
    later: Path, built: Path, elsewhere: Path, tmp_path: Path
) -> None:
    """Gate H C7 & gate G 3 (S-180): v1.1.0 says Wiring is included where v1.0.0 left it out."""
    from napkin2factory.domains.electrical import DOMAIN as ELECTRICAL

    assert ELECTRICAL.disclaimer is None  # one disclaimer, the README's (S-193)
    make_bundle(load_product(later), later / "build", "v1.0.0", tmp_path)
    pkg = make_bundle(load_product(built), built / "build", "v1.1.0", tmp_path)
    with zipfile.ZipFile(pkg) as zf:
        cover = zf.read("v1.1.0/README.txt").decode("utf-8")
    assert (
        "Scope: Wiring: included in this Revision; left for later in v1.0.0 — The wiring inside "
        "the box is designed here (DEC-001)"
    ) in cover
    assert "to local code" not in cover
    assert "to local code" not in _report(built)


# ---- the diff page: a section the later Revision adds or drops (DoD 4, S-169) ---------------


def _freeze(root: Path, site: Path, ref: str) -> Path:
    """Lay out ``site/<ref>/`` as ``n2f release`` freezes it: page, data, package."""
    frozen = site / ref
    frozen.mkdir(parents=True)
    shutil.copyfile(root / "build" / "report" / "index.html", frozen / "index.html")
    export_data(load_product(root), root / "build", frozen / "data")
    make_bundle(load_product(root), root / "build", ref, frozen)
    return frozen / "data"


def test_the_page_lists_its_sections_from_its_side_index(built: Path, later: Path) -> None:
    designed = page_sections(built / "build" / "report" / "index.html")
    assert designed is not None and {"id": "wiring", "label": "Wiring"} in designed
    # a wiring left for later still has its section: it says so (show_wiring)
    left = page_sections(later / "build" / "report" / "index.html")
    assert left is not None and {"id": "wiring", "label": "Wiring"} in left
    assert page_sections(later / "nowhere.html") is None


def test_wiring_left_for_later_then_designed_reads_wiring_added(
    built: Path, later: Path, elsewhere: Path, tmp_path: Path
) -> None:
    site = tmp_path / "site"
    first, second = _freeze(later, site, "v1.0.0"), _freeze(built, site, "v1.1.0")
    delta = compute_diff(first, second)
    assert delta["sections"] == [
        {"id": "wiring", "label": "Wiring", "state": "added", "words": "Wiring: added"}
    ]
    back = compute_diff(second, first)
    assert [s["words"] for s in back["sections"]] == ["Wiring: removed"]
    # done elsewhere is not in the package either (the cover's "Not included"): designing
    # the wiring here adds it too
    outside = _freeze(elsewhere, tmp_path / "site2", "v1.0.0")
    assert [s["words"] for s in compute_diff(outside, second)["sections"]] == ["Wiring: added"]
    assert compute_diff(second, second)["sections"] == []


def test_the_diff_page_says_wiring_added_against_the_working_model(
    built: Path, later: Path, tmp_path: Path
) -> None:
    root = copy_product(BOX, tmp_path / "box", git=False)
    run_build(load_product(root), render=False, quiet=True)
    _freeze(later, root / "build" / "site", "v1.0.0")
    result = diff(load_product(root), "v1.0.0", "working", out=tmp_path / "page")
    assert [s["words"] for s in result["delta"]["sections"]] == ["Wiring: added"]
    html = Path(result["page"]).read_text(encoding="utf-8")
    block = html.split('<section id="sections">', 1)[1].split("</section>", 1)[0]
    assert '<strong class="new">Wiring: added</strong>' in block
    assert html.index('id="sections"') < html.index('id="3d"')
    written = json.loads((tmp_path / "page" / "diff.json").read_text(encoding="utf-8"))
    assert written["sections"][0]["words"] == "Wiring: added"


def test_no_section_change_leaves_the_page_as_it_was(built: Path, tmp_path: Path) -> None:
    data = _freeze(built, tmp_path / "site", "v1.0.0")
    assert compute_diff(data, data)["sections"] == []
    # unknown pages (data with no page beside it) claim nothing
    bare = tmp_path / "bare"
    export_data(load_product(built), built / "build", bare)
    assert compute_diff(bare, data)["sections"] == []
    env = jinja2.Environment(autoescape=True)
    assert sections_block(env, "v1.0.0", "v1.1.0", []) == ""


def test_any_domains_section_is_said_by_its_label() -> None:
    """Generic: a section of no installed domain counts as in; scope only drops its own."""
    a = {"sections": [{"id": "parts", "label": "Parts"}], "scope": {}}
    b = {
        "sections": [{"id": "gadgets", "label": "Gadgets"}, {"id": "wiring", "label": "Wiring"}],
        "scope": {"electrical": "external"},
    }
    assert [s["words"] for s in section_delta(a, b)] == ["Gadgets: added", "Parts: removed"]
    assert section_delta(None, b) == []


def test_golden_diff_sections(tmp_path: Path) -> None:
    """The diff page's block and record for one section added and one removed."""
    a = tmp_path / "a"
    b = tmp_path / "b"
    for d, record in (
        (a, {"sections": [{"id": "parts", "label": "Parts"}], "scope": {}}),
        (
            b,
            {
                "sections": [{"id": "wiring", "label": "Wiring"}],
                "scope": {"electrical": "in"},
            },
        ),
    ):
        d.mkdir()
        (d / SECTIONS_FILE).write_text(json.dumps(record), encoding="utf-8")
    delta = compute_diff(a, b)
    env = jinja2.Environment(autoescape=True)
    got = (
        json.dumps(
            {
                "sections": delta["sections"],
                "block": sections_block(env, "v1.0.0", "v1.1.0", delta["sections"]),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    path = GOLDENS / "diff-sections.json"
    if os.environ.get("N2F_UPDATE_GOLDENS") == "1" or not path.exists():
        path.write_text(got, encoding="utf-8")
        if os.environ.get("N2F_UPDATE_GOLDENS") != "1":
            pytest.skip("golden diff-sections.json recorded for the first time; re-run to compare")
    assert got == path.read_text(encoding="utf-8"), "diff-sections.json drifted from its golden"
