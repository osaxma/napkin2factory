"""v0.6 M4: the owner's view of the wiring (ELECTRICAL_STAGE §5 M4, E7, E8, E12; S-159).

The electrical domain is installed (``domains/__init__.py``).  On the minimal fixture (a
heater and its switch in a box): the report's "Wiring" section shows each circuit's diagram
inline (made page-safe), its wires, the cable schedule, the cable to buy and the wiring check
rows; a product with no wiring has no section and no gate row; a product whose wiring is left
for later shows the core's scope line.  The manual-page helpers record what they read, so a
page is stale after a wire edit and fresh after one build.  The owner reads words, not
schemes.  ``n2f context`` lists the module's own circuits and entries, not another's.

The ``elec`` rules (M2) write the build files the section reads; the tests that need their
contents write a sample of the agreed shape (the wave-2 contract) so they hold whichever
order the wave lands in, and the end-to-end ones assert what holds either way.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from napkin2factory.cli.app import app
from napkin2factory.core.checks.engine import doc_staleness
from napkin2factory.core.checks.stage import compute_stage
from napkin2factory.core.context import module_context, render_text
from napkin2factory.core.domain import SectionContext
from napkin2factory.core.graph.runner import run_build
from napkin2factory.core.loader import Product, load_product
from napkin2factory.core.registry import registry
from napkin2factory.core.uris import display_uri
from napkin2factory.domains.electrical.owner.common import SCHEDULE_KEY
from napkin2factory.domains.electrical.owner.gates import design_row, verify_row
from napkin2factory.domains.electrical.owner.report import show_wiring, wiring_report_data
from napkin2factory.domains.electrical.owner.svg import inline_svg
from napkin2factory.report.builder import render_report, sections
from tests.conftest import EXAMPLES, FIXTURES, copy_product

MINIMAL = FIXTURES / "electrical" / "minimal"
CIRCUIT = "model/electrical/circuits/heater.yaml"

#: A manual page using every helper (F5).
PAGE = """---
id: wiring
title: Wiring
audience: [owner]
---
# Wiring

The {{ circuit("heater").name }} circuit is a {{ circuit("heater").purpose }} circuit,
protected by {{ circuit("heater").protection }}.

{% for d in circuit("heater").devices %}- {{ d.name }} ({{ d.role }}): {{ d.terminals }}
{% endfor %}
{{ circuit("heater").table }}
Schedule rows: {{ cable_schedule() | length }}; labels: {{ terminal_labels() | length }};
cables: {{ cables_to_buy() | length }}.
"""


def _copy(tmp_path: Path, name: str = "hb", git: bool = False) -> Path:
    return copy_product(MINIMAL, tmp_path / name, git=git)


def _edit(root: Path, rel: str, old: str, new: str) -> None:
    path = root / rel
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, (rel, old)
    path.write_text(text.replace(old, new), encoding="utf-8")


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _cli(*args: str) -> str:
    return CliRunner().invoke(app, list(args), env={"COLUMNS": "200"}).output


def _section(html: str) -> str:
    start = html.index('<section class="card" id="wiring">')
    return html[start : html.index("</section>", start)]


def _write_sample_outputs(build: Path) -> None:
    """Build files of the agreed shape (brief-wave2-common), as ``elec`` writes them."""
    out = build / "electrical"
    (out / "heater").mkdir(parents=True, exist_ok=True)
    record = {
        "circuit": "heater",
        "name": "Heater",
        "purpose": "power",
        "voltage_v": 230.0,
        "protection": {"ref": "supply", "words": "the site's 10 A breaker"},
        "devices": [
            {
                "uri": "device://switch",
                "part": "part://switch",
                "name": "Switch",
                "instance": None,
                "role": "control",
                "terminals": ["1", "2", "3", "4"],
            }
        ],
        "wires": [
            {
                "id": "heater-1",
                "from": "supply://supply#L",
                "from_words": "supply terminal L",
                "to": "device://switch#1",
                "to_words": "Switch terminal 1",
                "conductor": "cu-1p5-pvc",
                "conductor_label": "1.5 mm² PVC",
                "csa_mm2": 1.5,
                "length_m": 0.4,
                "colour": "brown",
                "via": "iface://box-entry",
                "via_words": "Supply cable into the box",
            }
        ],
        "entries": [{"uri": "iface://box-entry", "name": "Supply cable into the box"}],
        "boundary": [],
    }
    (out / "heater" / "connections.json").write_text(json.dumps(record), encoding="utf-8")
    (out / "heater" / "diagram.svg").write_text(
        '<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200">'
        '<style>text{fill:#000}</style><defs><marker id="dot"><circle r="2"/></marker></defs>'
        '<script>alert(1)</script><a href="https://example.com/x"><text>link</text></a>'
        '<rect width="10" height="10" onclick="evil()" style="fill:url(#dot)"/>'
        '<text x="10" y="20">SWITCH-PANEL</text><use href="#dot"/></svg>\n',
        encoding="utf-8",
    )
    (out / "schedule.csv").write_text(
        "wire,circuit,from,to,conductor,cross_section_mm2,length_m,colour,via\n"
        "heater-1,heater,supply://supply#L,device://switch#1,cu-1p5-pvc,1.5,0.4,brown,"
        "iface://box-entry\n",
        encoding="utf-8",
    )
    (out / "labels.csv").write_text(
        "label,device,terminal,wire,circuit\nheater-1,supply,L,heater-1,heater\n"
        "heater-1,switch,1,heater-1,heater\n",
        encoding="utf-8",
    )
    (out / "cables.csv").write_text(
        "conductor,label,cross_section_mm2,insulation,total_length_m,wires\n"
        "cu-1p5-pvc,1.5 mm² PVC,1.5,PVC 70 °C,1.7,heater-1 heater-2 heater-3 heater-4 heater-5\n",
        encoding="utf-8",
    )


def _add_check_row(build: Path, status: str = "warn") -> None:
    path = build / "checks" / "checks.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["results"].append(
        {
            "id": "circuit://heater#earth",
            "subject": "circuit://heater",
            "status": status,
            "kind": "electrical",
            "title": "The heater's metal case reaches earth",
            "message": "through its PE terminal; a licensed electrician decides",
        }
    )
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Path, Product]]:
    """The minimal product with a wiring page, built once (no renders)."""
    root = copy_product(MINIMAL, tmp_path_factory.mktemp("elec-owner") / "hb", git=True)
    _write(root, "model/docs/wiring.md", PAGE)
    product = load_product(root)
    run_build(product, render=False, quiet=True)
    yield root, product


# ---- the report's Wiring section (DoD 2) ---------------------------------------------------------


def test_the_section_is_in_the_report_and_its_index(built: tuple[Path, Product]) -> None:
    root, product = built
    html = (root / "build/report/index.html").read_text(encoding="utf-8")
    section = _section(html)
    assert "Supply cable into the box" in section and "Switch terminal 1" in section
    assert "not reviewed by a licensed electrician" in section
    # the diagram is inline exactly when the elec rule drew one (M2), whichever lands first
    drawn = (root / "build/electrical/heater/diagram.svg").is_file()
    assert ("<svg" in section) == drawn
    nav = html.split('<nav class="side"', 1)[1].split("</nav>", 1)[0]
    assert nav.index('data-sec="joints"') < nav.index('data-sec="wiring"')
    assert nav.index('data-sec="wiring"') < nav.index("Verification")
    assert json.loads((root / "build/report/report.json").read_text())["within_budget"]
    reads = json.loads((root / "build/.n2f/manifest.json").read_text())["entries"]["report"][
        "reads"
    ]
    # the model fields it shows (through the proxy) and the elec outputs (D5)
    assert {"circuit://heater#name", "circuit://heater#purpose"} <= set(reads)
    assert {"circuit://heater", SCHEDULE_KEY} <= set(reads)


def test_the_section_shows_the_diagram_tables_and_rows(
    built: tuple[Path, Product], tmp_path: Path
) -> None:
    root, product = built
    build = tmp_path / "build"
    import shutil

    shutil.copytree(root / "build", build)
    _write_sample_outputs(build)
    _add_check_row(build)
    data = wiring_report_data(SectionContext(product, build))
    (c,) = data["circuits"]
    assert c["protection"] == "the site's 10 A breaker" and c["built"]
    assert c["wires"][0]["csa"] == "1.5 mm²" and c["wires"][0]["colour"] == "brown"
    assert data["schedule"][0]["from"] == "the supply terminal L"  # an end said in words
    assert data["schedule"][0]["to"] == "Switch terminal 1"
    assert data["schedule"][0]["via"] == "Supply cable into the box"
    assert data["cables"] == [
        {
            "label": "1.5 mm² PVC",
            "csa": "1.5 mm²",
            "insulation": "PVC 70 °C",
            "total": "1.7 m",
            "wires": "5",
        }
    ]
    assert data["labels"] == 2
    assert data["rows"][0]["title"] == "The heater's metal case reaches earth"
    section = _section(render_report(product, build, "2026-11-02"))
    assert "SWITCH-PANEL" in section and 'id="wiring-heater-dot"' in section
    assert "url(#wiring-heater-dot)" in section and 'href="#wiring-heater-dot"' in section
    assert "#wiring-heater text{fill:#000}" in section  # its style stays inside it
    assert "<script" not in section and 'onclick="evil' not in section
    assert "https://example.com" not in section and "<?xml" not in section
    assert "1.5 mm² PVC" in section and "1.7 m" in section  # the cable to buy
    assert "worth a look" in section or "warn" in section  # the row's badge, in words
    assert "a licensed electrician decides" in section


def test_a_diagram_is_made_safe_to_inline() -> None:
    svg = inline_svg(
        '<svg width="120" height="40"><foreignObject><p>x</p></foreignObject>'
        "<style>@import url(https://example.com/a.css);</style>"
        "<image xlink:href=\"file:///etc/passwd\"/><g id='a'><use xlink:href='#a'/></g></svg>",
        "wiring-x",
    )
    assert svg.startswith('<svg width="120" height="40" id="wiring-x" viewBox="0 0 120 40"')
    assert "min-width:96px" in svg  # never below 0.8 of its own size: the card scrolls
    assert "foreignObject" not in svg and "@import" not in svg and "file:" not in svg
    assert 'id="wiring-x-a"' in svg and 'xlink:href="#wiring-x-a"' in svg
    assert inline_svg("not a drawing", "wiring-x") == ""


def test_a_product_without_wiring_has_no_section(tmp_path: Path) -> None:
    bracket = load_product(EXAMPLES / "bracket")
    assert not show_wiring(bracket)
    assert "wiring" not in [sid for sid, _, _ in sections(bracket)]
    html = render_report(bracket, tmp_path / "build", "2026-11-02")
    assert 'id="wiring"' not in html and 'data-sec="wiring"' not in html
    assert "Wiring" not in html


def test_a_later_product_shows_the_scope_line(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    _edit(root, "n2f.yaml", "{state: in, decision: DEC-001}", "{state: later, decision: DEC-001}")
    product = load_product(root)
    data = wiring_report_data(SectionContext(product, root / "build"))
    line = data["scope_line"]
    assert (
        line
        == "Wiring: left for later (not designed here yet) — The wiring is designed here (DEC-001)"
    )
    # no wiring at all, only the scope entry: the section still says where it stands
    import shutil

    shutil.rmtree(root / "model/electrical")
    _edit(root, "model/interfaces/box-entry.yaml", "passes: [circuit://heater]", "passes: []")
    product = load_product(root)
    assert show_wiring(product)
    section = _section(render_report(product, root / "build", "2026-11-02"))
    assert line in section and "No wiring yet" not in section


# ---- the manual page's helpers (F5, S-143) ----------------------------------------------------


def test_the_helpers_print_the_wiring_and_record_their_reads(built: tuple[Path, Product]) -> None:
    root, _ = built
    page = (root / "build/docs/wiring/page.md").read_text(encoding="utf-8")
    assert "The Heater circuit is a power circuit" in page
    assert "protected by the supply's own protective device" in page
    assert "- Switch (switching device): 1, 2, 3, 4" in page
    assert "- Heater (load): L, N, PE" in page
    assert (
        "| Wire | From | To |" in page
        and "| heater-3 | Switch terminal 2 | Heater terminal L |" in page
    )
    reads = json.loads((root / "build/docs/wiring/reads.json").read_text(encoding="utf-8"))
    assert {"circuit://heater#name", "circuit://heater#connections"} <= set(reads["reads"])
    assert {"circuit://heater", SCHEDULE_KEY, "part://heater#name"} <= set(reads["reads"])
    assert reads["values"]["circuit://heater#name"] == "Heater"
    rows = {
        r["id"]: r for r in json.loads((root / "build/checks/checks.json").read_text())["results"]
    }
    assert rows["doc://wiring"]["status"] == "pass"


def test_a_page_is_stale_after_a_wire_edit_and_fresh_after_one_build(tmp_path: Path) -> None:
    root = _copy(tmp_path, git=True)
    _write(root, "model/docs/wiring.md", PAGE)
    run_build(load_product(root), render=False, quiet=True)
    _edit(
        root,
        CIRCUIT,
        'to: "device://heater#L", conductor: cu-1p5-pvc, length: 0.2 m}',
        'to: "device://heater#L", conductor: cu-1p5-pvc, length: 0.3 m}',
    )
    product = load_product(root)
    (row,) = [r for r in doc_staleness(product, root / "build") if r.id == "doc://wiring"]
    assert row.status == "fail" and "circuit://heater" in row.message, row.message
    run_build(product, render=False, quiet=True)
    (row,) = [
        r for r in doc_staleness(load_product(root), root / "build") if r.id == "doc://wiring"
    ]
    assert row.status == "pass", row.message
    assert "0.3 m" in (root / "build/docs/wiring/page.md").read_text(encoding="utf-8")


def test_a_helper_naming_no_circuit_says_which_exist(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    _write(
        root, "model/docs/wiring.md", PAGE.replace('circuit("heater").name', 'circuit("fan").name')
    )
    product = load_product(root)
    from napkin2factory.docs.engine import DocRenderError, render_doc

    with pytest.raises(DocRenderError, match=r"circuit\('fan'\) does not exist; circuits: heater"):
        render_doc(product, product.docs["wiring"])


# ---- gate rows (E7, F4, F11) --------------------------------------------------------------------


def _rows(product: Product, gate: str) -> list[dict[str, Any]]:
    g = next(g for g in compute_stage(product).gates if g.name == gate)
    return list(g.detail.get("rows", []))


def test_the_verify_row_counts_the_wiring_checks(
    built: tuple[Path, Product], tmp_path: Path
) -> None:
    root, product = built
    import shutil

    build = tmp_path / "build"
    shutil.copytree(root / "build", build)
    _add_check_row(build, "warn")
    _add_check_row(build, "pass")
    state = verify_row(product, build)
    assert state is not None
    assert state.summary.endswith(": 1 OK, 1 for an electrician to confirm"), state.summary


def test_the_rows_say_not_checked_before_the_checks(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    product = load_product(root)
    state = verify_row(product, root / "build")
    assert state is not None and state.summary == "not checked yet"
    assert {"title": "Wiring checks", "summary": "not checked yet"} in _rows(product, "verify")


def test_the_rows_need_wiring_or_a_scope_entry(tmp_path: Path) -> None:
    import shutil

    bracket = load_product(EXAMPLES / "bracket")
    assert design_row(bracket, tmp_path) is None and verify_row(bracket, tmp_path) is None
    root = _copy(tmp_path)
    shutil.rmtree(root / "model/electrical")
    _edit(root, "model/interfaces/box-entry.yaml", "passes: [circuit://heater]", "passes: []")
    said_in = load_product(root)  # the scope says the wiring is done here: both rows stay
    assert design_row(said_in, root / "build") is not None
    assert verify_row(said_in, root / "build") is not None
    _edit(root, "n2f.yaml", "scope:\n  electrical: {state: in, decision: DEC-001}\n", "")
    unsaid = load_product(root)
    assert design_row(unsaid, root / "build") is None
    assert verify_row(unsaid, root / "build") is None
    assert not [r for r in _rows(unsaid, "verify") if r["title"].startswith("Wiring")]


# ---- the owner's words (F1 §3.8, S-150) ---------------------------------------------------------


def test_the_owner_reads_words_not_schemes(built: tuple[Path, Product]) -> None:
    owner = registry().vocabulary("owner")
    assert owner["electrical"] == "wiring" and owner["cable-entry"] == "cable entry"
    assert display_uri("circuit://heater", "owner") == "circuit heater"
    assert display_uri("device://switch", "owner") == "electrical device switch"
    assert display_uri("conductor://cu-x", "owner") == "conductor cu-x"
    assert display_uri("supply://supply", "owner") == "supply"  # never "supply supply"
    assert display_uri("circuit://heater", "engineer") == "circuit://heater"
    root, _ = built
    assert "Wiring checks:" in _cli("status", "-C", str(root))


# ---- the module context (F1, S-116) ------------------------------------------------------------

LAMP_PART = """id: lamp
rev: A
name: Lamp
kind: cots
process: none
geometry: none
source: {vendor: Lamp maker, mpn: LAMP-1, url: "https://example.com/lamp", verified: true}
cost: {unit: 3 USD, basis: catalog}
lead_time: 1 d
mass: 50 g
"""
LAMP_DEVICE = """id: lamp
part: part://lamp
role: load
rating: {voltage: 230 V, power: 10 W}
terminals: [L, N]
class: II
"""
LAMP_CIRCUIT = """id: lamp
purpose: power
name: Lamp
protection: supply
connections:
  - {from: "supply://supply#L", to: "device://lamp#L", conductor: cu-1p5-pvc, length: 0.6 m}
  - {from: "supply://supply#N", to: "device://lamp#N", conductor: cu-1p5-pvc, length: 0.6 m}
"""
LAMP_UNIT = """id: lamp-unit
rev: A
name: Lamp unit
build: unit
children:
  - {part: part://lamp, qty: 1}
"""


def test_the_context_lists_the_modules_own_wiring_only(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    _write(root, "model/parts/lamp.yaml", LAMP_PART)
    _write(root, "model/electrical/devices/lamp.yaml", LAMP_DEVICE)
    _write(root, "model/electrical/circuits/lamp.yaml", LAMP_CIRCUIT)
    _write(root, "model/assemblies/lamp-unit.yaml", LAMP_UNIT)
    _edit(
        root,
        "model/assemblies/heated-box.yaml",
        "  - {part: part://switch, qty: 1}\n",
        "  - {part: part://switch, qty: 1}\n  - {asm: asm://lamp-unit, qty: 1}\n",
    )
    product = load_product(root)
    box = module_context(product, "heated-box")
    (lines,) = [d["lines"] for d in box["domains"] if d["title"] == "Wiring in this module"]
    assert lines[0] == (
        "- circuit://heater: Heater (power circuit), in model/electrical/circuits/heater.yaml"
    )
    assert "  - Switch terminal 2 to Heater terminal L — cu-1p5-pvc, 0.2 m" in lines
    assert any(ln.startswith("- iface://box-entry: Supply cable into the box") for ln in lines)
    assert not [ln for ln in lines if "lamp" in ln.lower()]
    assert "## Wiring in this module" in render_text(box)
    lamp = module_context(product, "lamp-unit")
    (lines,) = [d["lines"] for d in lamp["domains"] if d["title"] == "Wiring in this module"]
    assert lines[0].startswith("- circuit://lamp: Lamp (power circuit)")
    assert not [ln for ln in lines if "heater" in ln.lower() or "box-entry" in ln]
