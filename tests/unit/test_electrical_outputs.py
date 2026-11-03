"""v0.6 M2: the ``elec`` rule family and its outputs (ELECTRICAL_STAGE §5 M2, E5, DoD 2 and 5).

The minimal product (``tests/fixtures/electrical/minimal``: a heater and its two-pole switch
fed through one cable gland) builds ``build/electrical/heater/connections.json``,
``diagram.svg`` and ``heater.kicad_sch``, then ``schedule.csv``, ``labels.csv`` and
``cables.csv`` (the wave-2 contract); the diagram is a byte-for-byte golden; a changed
conductor reruns the circuit's rule and the schedule and no mechanical rule, and
``n2f impact`` names them for every field the rule reads; a module supplied from elsewhere
is a dashed boundary with its words and nothing inside; the release package ships the
diagrams and the tables (S-142).

Golden: ``N2F_UPDATE_GOLDENS=1 uv run pytest tests/unit/test_electrical_outputs.py -k golden``
rewrites ``tests/golden/goldens/electrical-minimal-heater.{svg,json}``; log it in
``tests/golden/REGENERATION_LOG.md``.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from napkin2factory.core.graph.impact import compute_impact, parse_set
from napkin2factory.core.graph.runner import explain_build, run_build
from napkin2factory.core.loader import Product, load_product, validate
from napkin2factory.core.registry import registry
from napkin2factory.domains.electrical.model import Circuit, Connection
from napkin2factory.domains.electrical.outputs import RELEASE_FILES
from napkin2factory.domains.electrical.outputs.diagram import circuit_svg
from napkin2factory.domains.electrical.outputs.export_kicad import kicad_schematic
from napkin2factory.domains.electrical.outputs.rules import (
    SCHEDULE_KEY,
    SCHEDULE_RULE,
    elec_static_reads,
)
from napkin2factory.domains.electrical.outputs.schedule import (
    CABLE_COLUMNS,
    LABEL_COLUMNS,
    SCHEDULE_COLUMNS,
)
from tests.conftest import FIXTURES, copy_product

MINIMAL = FIXTURES / "electrical" / "minimal"
CIRCUIT = "model/electrical/circuits/heater.yaml"
GOLDENS = Path(__file__).resolve().parents[1] / "golden" / "goldens"
OUT = "build/electrical"
#: Rules an electrical edit must never rerun: the mechanical model is not the wiring's.
MECHANICAL = ("part:", "asm:", "drawing:", "bom", "asmsheet:")


def _edit(root: Path, rel: str, old: str, new: str) -> None:
    path = root / rel
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, (rel, old)
    path.write_text(text.replace(old, new), encoding="utf-8")


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    text = path.read_text(encoding="utf-8")
    reader = csv.DictReader(io.StringIO(text))
    return list(reader.fieldnames or []), list(reader)


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Path, Product, Any]]:
    """The minimal product built once (no renders)."""
    root = copy_product(MINIMAL, tmp_path_factory.mktemp("elec-out") / "hb", git=True)
    product = load_product(root)
    summary = run_build(product, render=False, quiet=True)
    yield root, product, summary


# ---- the files of the contract ------------------------------------------------------------


def test_the_rules_run_after_the_parts_and_before_the_manuals(
    built: tuple[Path, Product, Any],
) -> None:
    _, _, summary = built
    ran = summary["ran"]
    assert ran.index("elec:heater") < ran.index(SCHEDULE_RULE) < ran.index("checks")
    assert ran.index("part:box") < ran.index("elec:heater")


def test_every_file_of_the_contract_exists_and_parses(built: tuple[Path, Product, Any]) -> None:
    root, _, _ = built
    out = root / OUT
    for rel in ("heater/connections.json", "heater/diagram.svg", "heater/heater.kicad_sch"):
        assert (out / rel).is_file(), rel
    for name in ("schedule.csv", "labels.csv", "cables.csv"):
        assert (out / name).is_file(), name
    json.loads((out / "heater/connections.json").read_text(encoding="utf-8"))
    ET.fromstring((out / "heater/diagram.svg").read_text(encoding="utf-8"))


def test_the_record_matches_the_model(built: tuple[Path, Product, Any]) -> None:
    root, product, _ = built
    record = json.loads((root / OUT / "heater/connections.json").read_text(encoding="utf-8"))
    assert list(record)[:6] == ["circuit", "name", "purpose", "voltage_v", "dc", "protection"]
    assert record["circuit"] == "heater" and record["name"] == "Heater"
    assert record["purpose"] == "power" and record["voltage_v"] == 230.0
    assert record["protection"] == {
        "ref": "supply",
        "words": "the 10 A breaker of the socket circuit",
    }
    assert [d["uri"] for d in record["devices"]] == ["device://switch", "device://heater"]
    heater = record["devices"][1]
    assert heater == {
        "uri": "device://heater",
        "part": "part://heater",
        "name": "Heater",
        "instance": None,
        "role": "load",
        "terminals": ["L", "N", "PE"],
    }
    conns = product.families["circuit"]["heater"].connections
    assert [w["id"] for w in record["wires"]] == [f"heater-{n}" for n in range(1, 6)]
    for wire, conn in zip(record["wires"], conns, strict=True):
        assert (wire["from"], wire["to"]) == (conn.from_, conn.to)
        assert wire["conductor"] == conn.conductor == "cu-1p5-pvc"
        assert wire["csa_mm2"] == 1.5
        assert wire["via"] == (None if conn.via is None else str(conn.via))
    first, pe = record["wires"][0], record["wires"][4]
    assert first["from_words"] == "the supply terminal L"
    assert first["to_words"] == "Switch terminal 1"
    assert first["length_m"] == 0.4 and first["colour"] == "brown"  # the region's line colour
    assert first["via_words"] == "Supply cable into the box"
    assert pe["colour"] == "green-and-yellow"  # the connection's own
    assert [w["colour"] for w in record["wires"][1:4]] == ["blue", "brown", "blue"]
    assert record["entries"] == [
        {"uri": "iface://box-entry", "name": "Supply cable into the box", "external": False}
    ]
    assert record["boundary"] == []


def test_the_csv_headers_are_the_contracts(built: tuple[Path, Product, Any]) -> None:
    root, _, _ = built
    out = root / OUT
    first = {
        name: (out / name).read_text(encoding="utf-8").splitlines()[0]
        for name in ("schedule.csv", "labels.csv", "cables.csv")
    }
    assert first == {
        "schedule.csv": "wire,circuit,from,to,conductor,cross_section_mm2,length_m,colour,via",
        "labels.csv": "label,device,terminal,wire,circuit",
        "cables.csv": "conductor,label,cross_section_mm2,insulation,total_length_m,wires",
    }
    assert tuple(first["schedule.csv"].split(",")) == SCHEDULE_COLUMNS
    assert tuple(first["labels.csv"].split(",")) == LABEL_COLUMNS
    assert tuple(first["cables.csv"].split(",")) == CABLE_COLUMNS


def test_the_schedule_and_labels_list_every_wire(built: tuple[Path, Product, Any]) -> None:
    root, _, _ = built
    _, schedule = _csv(root / OUT / "schedule.csv")
    assert [r["wire"] for r in schedule] == [f"heater-{n}" for n in range(1, 6)]
    assert schedule[2] == {
        "wire": "heater-3",
        "circuit": "heater",
        "from": "Switch terminal 2",
        "to": "Heater terminal L",
        "conductor": "cu-1p5-pvc",
        "cross_section_mm2": "1.5",
        "length_m": "0.2",
        "colour": "brown",
        "via": "",
    }
    _, labels = _csv(root / OUT / "labels.csv")
    assert len(labels) == 10  # one per wire end
    assert labels[0] == {
        "label": "heater-1 supply:L",
        "device": "the supply",
        "terminal": "L",
        "wire": "heater-1",
        "circuit": "heater",
    }
    assert labels[1]["label"] == "heater-1 switch:1" and labels[1]["device"] == "Switch"


def test_the_cables_to_buy_total_each_conductor(built: tuple[Path, Product, Any]) -> None:
    root, _, _ = built
    _, cables = _csv(root / OUT / "cables.csv")
    assert cables == [
        {
            "conductor": "cu-1p5-pvc",
            "label": "1.5 mm² PVC",
            "cross_section_mm2": "1.5",
            "insulation": "PVC, 70 °C (H07V-K class)",
            "total_length_m": "1.7",  # 0.4 + 0.4 + 0.2 + 0.2 + 0.5
            "wires": "heater-1 heater-2 heater-3 heater-4 heater-5",
        }
    ]


def test_an_unknown_length_makes_the_total_not_given(tmp_path: Path) -> None:
    root = copy_product(MINIMAL, tmp_path / "hb", git=False)
    _edit(root, CIRCUIT, "conductor: cu-1p5-pvc, length: 0.5 m, via", "conductor: cu-2p5-pvc, via")
    _edit(
        root,
        CIRCUIT,
        'to: "device://switch#3", conductor: cu-1p5-pvc, length: 0.4 m',
        'to: "device://switch#3", conductor: cu-1p5-pvc',
    )
    run_build(load_product(root), target="elec", render=False, quiet=True)
    _, cables = _csv(root / OUT / "cables.csv")
    assert [(c["conductor"], c["total_length_m"]) for c in cables] == [
        ("cu-1p5-pvc", "not given"),
        ("cu-2p5-pvc", "not given"),
    ]
    _, schedule = _csv(root / OUT / "schedule.csv")
    assert schedule[1]["length_m"] == "not given"


# ---- the golden diagram ----------------------------------------------------------------------


def _golden(name: str, got: str) -> None:
    path = GOLDENS / name
    if os.environ.get("N2F_UPDATE_GOLDENS") == "1" or not path.exists():
        path.write_text(got, encoding="utf-8")
        if os.environ.get("N2F_UPDATE_GOLDENS") != "1":
            pytest.skip(f"golden {name} recorded for the first time; re-run to compare")
    assert got == path.read_text(encoding="utf-8"), f"{name} drifted from its golden"


def test_golden_diagram_of_the_minimal_product(built: tuple[Path, Product, Any]) -> None:
    root, _, _ = built
    _golden(
        "electrical-minimal-heater.svg",
        (root / OUT / "heater/diagram.svg").read_text(encoding="utf-8"),
    )


def test_golden_record_of_the_minimal_product(built: tuple[Path, Product, Any]) -> None:
    root, _, _ = built
    _golden(
        "electrical-minimal-heater.json",
        (root / OUT / "heater/connections.json").read_text(encoding="utf-8"),
    )


def test_the_diagram_is_drawn_from_the_record_alone(built: tuple[Path, Product, Any]) -> None:
    """Deterministic and self-contained: the same record gives the same bytes, no outside refs."""
    root, _, _ = built
    record = json.loads((root / OUT / "heater/connections.json").read_text(encoding="utf-8"))
    svg = (root / OUT / "heater/diagram.svg").read_text(encoding="utf-8")
    assert circuit_svg(record) == svg
    assert not re.search(r"(href|url\()", svg)
    tree = ET.fromstring(svg)
    ids = {g.get("id") for g in tree.iter("{http://www.w3.org/2000/svg}g")}
    assert {"device-switch", "device-heater", "supply-supply", "entry-box-entry"} <= ids
    assert {f"wire-heater-{n}" for n in range(1, 6)} <= ids
    texts = [t.text for t in tree.iter("{http://www.w3.org/2000/svg}text")]
    assert "heater-3 · 1.5 mm² · brown" in texts  # each wire: its id, size and colour
    assert {"Switch", "Heater", "Supply cable into the box", "PE", "4"} <= set(texts)
    entry = next(
        g
        for g in tree.iter("{http://www.w3.org/2000/svg}g")
        if g.get("id", "").startswith("entry-")
    )
    rect = entry.find("{http://www.w3.org/2000/svg}rect")
    assert rect is not None and rect.get("stroke-dasharray")  # the entry is a dashed boundary


def test_an_empty_circuit_says_so() -> None:
    svg = circuit_svg({"circuit": "spare", "name": "Spare", "purpose": "control", "wires": []})
    assert "No connections yet." in svg
    ET.fromstring(svg)


# ---- the text schematic export (E1) --------------------------------------------------------------


def _sexpr(text: str) -> list[Any]:
    """Parse s-expressions (quoted strings with escapes); raise on an unbalanced file."""
    tokens = re.findall(r'"(?:\\.|[^"\\])*"|\(|\)|[^\s()"]+', text)
    stack: list[list[Any]] = [[]]
    for tok in tokens:
        if tok == "(":
            stack.append([])
        elif tok == ")":
            done = stack.pop()
            assert stack, "a ')' closes nothing"
            stack[-1].append(done)
        else:
            stack[-1].append(tok)
    assert len(stack) == 1, "unbalanced: an '(' is never closed"
    return stack[0]


def _all(tree: list[Any], head: str) -> list[list[Any]]:
    out = []
    for item in tree:
        if isinstance(item, list):
            if item and item[0] == head:
                out.append(item)
            out += _all(item, head)
    return out


def test_the_text_schematic_parses_with_its_symbols_and_wires(
    built: tuple[Path, Product, Any],
) -> None:
    root, _, _ = built
    text = (root / OUT / "heater/heater.kicad_sch").read_text(encoding="utf-8")
    (top,) = _sexpr(text)
    assert top[0] == "kicad_sch"
    placed = [s for s in top if isinstance(s, list) and s[0] == "symbol"]
    assert len(placed) == 3  # the supply, the switch, the heater
    values = {
        p[2] for s in placed for p in s if isinstance(p, list) and p[:2] == ["property", '"Value"']
    }
    assert values == {'"Supply"', '"Switch"', '"Heater"'}
    assert len([s for s in top if isinstance(s, list) and s[0] == "wire"]) == 10
    labels = [s[1] for s in top if isinstance(s, list) and s[0] == "label"]
    assert sorted(set(labels)) == [f'"heater-{n}"' for n in range(1, 6)]
    assert all(labels.count(lab) == 2 for lab in labels)  # both ends of each wire, by name
    assert len(_all(top, "pin")) == 4 + 3 + 3  # switch, heater, the supply's L, N, PE
    record = json.loads((root / OUT / "heater/connections.json").read_text(encoding="utf-8"))
    assert kicad_schematic(record) == text


# ---- invalidation and impact -------------------------------------------------------------------


def _second_circuit(root: Path) -> None:
    """A lamp on its own circuit, so an edit of one circuit can leave the other alone."""
    _write(
        root,
        "model/parts/lamp.yaml",
        "id: lamp\nrev: A\nname: Lamp\nkind: cots\nprocess: none\ngeometry: none\n"
        'source: {vendor: Lamp maker, mpn: LAMP-1, url: "https://example.com/lamp", '
        "verified: true}\ncost: {unit: 1 USD, basis: catalog}\nlead_time: 1 d\nmass: 20 g\n",
    )
    _edit(
        root,
        "model/assemblies/heated-box.yaml",
        "  - {part: part://switch, qty: 1}\n",
        "  - {part: part://switch, qty: 1}\n  - {part: part://lamp, qty: 1}\n",
    )
    _write(
        root,
        "model/electrical/devices/lamp.yaml",
        "id: lamp\npart: part://lamp\nrole: load\nterminals: [L, N]\nclass: II\n",
    )
    _write(
        root,
        "model/electrical/circuits/lamp.yaml",
        "id: lamp\npurpose: power\nname: Lamp\nprotection: supply\nconnections:\n"
        '  - {from: "supply://supply#L", to: "device://lamp#L", conductor: cu-0p75-pvc, '
        "length: 0.3 m}\n"
        '  - {from: "supply://supply#N", to: "device://lamp#N", conductor: cu-0p75-pvc, '
        "length: 0.3 m}\n",
    )


def test_a_changed_conductor_length_reruns_its_circuit_and_the_schedule_only(
    tmp_path: Path,
) -> None:
    root = copy_product(MINIMAL, tmp_path / "hb", git=False)
    _second_circuit(root)
    product = load_product(root)
    first = run_build(product, render=False, quiet=True)["ran"]
    assert {"elec:heater", "elec:lamp", SCHEDULE_RULE} <= set(first)
    _, cables = _csv(root / OUT / "cables.csv")
    assert [(c["conductor"], c["total_length_m"]) for c in cables] == [
        ("cu-1p5-pvc", "1.7"),
        ("cu-0p75-pvc", "0.6"),
    ]
    report = compute_impact(
        load_product(root), [parse_set("circuit://heater#connections.4.length=0.9 m")]
    )
    _edit(root, CIRCUIT, "length: 0.5 m", "length: 0.9 m")
    product = load_product(root)
    will = {rid for rid, run, _ in explain_build(product, render=False) if run}
    ran = run_build(product, render=False, quiet=True)["ran"]
    assert "elec:heater" in ran and SCHEDULE_RULE in ran
    assert "elec:lamp" not in ran  # the other circuit's rule is skipped
    assert not [r for r in ran if r.startswith(MECHANICAL)], ran
    assert set(ran) <= set(report.rules) and set(ran) <= will
    _, schedule = _csv(root / OUT / "schedule.csv")
    assert schedule[4]["length_m"] == "0.9"
    _, cables = _csv(root / OUT / "cables.csv")
    assert cables[0]["total_length_m"] == "2.1"
    # an edit of the other circuit leaves this one's rule skipped
    _edit(
        root, "model/electrical/circuits/lamp.yaml", "length: 0.3 m}\n  - ", "length: 0.4 m}\n  - "
    )
    ran = run_build(load_product(root), render=False, quiet=True)["ran"]
    assert "elec:lamp" in ran and SCHEDULE_RULE in ran and "elec:heater" not in ran
    # a circuit removed: its rule and folder go, the schedule reruns without it
    (root / "model/electrical/circuits/lamp.yaml").unlink()
    ran = run_build(load_product(root), render=False, quiet=True)["ran"]
    assert SCHEDULE_RULE in ran and not (root / OUT / "lamp").exists()
    _, schedule = _csv(root / OUT / "schedule.csv")
    assert {r["circuit"] for r in schedule} == {"heater"}


#: field → (file, old text, new text, the value for `--set`): one edit per field the
#: circuit's rule reads (every Circuit field but `earth` and `notes`, every Connection field).
CIRCUIT_EDITS: dict[str, tuple[str, str, str, str]] = {
    "name": (CIRCUIT, "name: Heater", "name: Warmer", "circuit://heater#name=Warmer"),
    "purpose": (CIRCUIT, "purpose: power", "purpose: control", "circuit://heater#purpose=control"),
    "protection": (
        CIRCUIT,
        "protection: supply",
        "protection: part://switch",
        "circuit://heater#protection=part://switch",
    ),
    "voltage": (
        CIRCUIT,
        "name: Heater",
        "name: Heater\nvoltage: 120 V",
        "circuit://heater#voltage=120 V",
    ),
    "dc": (CIRCUIT, "purpose: power", "purpose: power\ndc: true", "circuit://heater#dc=true"),
    "connections.from": (
        CIRCUIT,
        'from: "device://switch#4"',
        'from: "device://switch#2"',
        "circuit://heater#connections.3.from=device://switch#2",
    ),
    "connections.to": (
        CIRCUIT,
        'to: "device://heater#N"',
        'to: "device://switch#3"',
        "circuit://heater#connections.3.to=device://switch#3",
    ),
    "connections.conductor": (
        CIRCUIT,
        "conductor: cu-1p5-pvc, length: 0.5 m",
        "conductor: cu-2p5-pvc, length: 0.5 m",
        "circuit://heater#connections.4.conductor=cu-2p5-pvc",
    ),
    "connections.length": (
        CIRCUIT,
        "length: 0.5 m",
        "length: 0.7 m",
        "circuit://heater#connections.4.length=0.7 m",
    ),
    "connections.via": (
        CIRCUIT,
        "length: 0.5 m, via: iface://box-entry, colour",
        "length: 0.5 m, colour",
        "circuit://heater#connections.4.via=none",
    ),
    "connections.colour": (
        CIRCUIT,
        "colour: green-and-yellow",
        "colour: green",
        "circuit://heater#connections.4.colour=green",
    ),
}
#: Edits of what else the rule reads: a device, a part's name, the supply, the entry.
OTHER_EDITS: dict[str, tuple[str, str, str, str]] = {
    "device": (
        "model/electrical/devices/heater.yaml",
        "class: I",
        "class: I\ninstance: the lower element",
        "device://heater#instance=the lower element",
    ),
    "part name": (
        "model/parts/switch.yaml",
        "name: Switch",
        "name: Toggle",
        "part://switch#name=Toggle",
    ),
    "supply": (
        "model/electrical/supply.yaml",
        "region: EU",
        "region: US",
        "supply://supply#region=US",
    ),
    "entry": (
        "model/interfaces/box-entry.yaml",
        "name: Supply cable into the box",
        "name: Mains into the box",
        "iface://box-entry#name=Mains into the box",
    ),
}


def test_every_field_the_rule_reads_is_edited() -> None:
    read = {f for f in Circuit.model_fields if f not in ("id", "earth", "notes", "connections")}
    read |= {f"connections.{f.rstrip('_')}" for f in Connection.model_fields}
    assert set(CIRCUIT_EDITS) == read


@pytest.mark.parametrize(("case", "edit"), sorted({**CIRCUIT_EDITS, **OTHER_EDITS}.items()))
def test_impact_names_the_circuits_rule_and_covers_the_rebuild(
    built: tuple[Path, Product, Any], case: str, edit: tuple[str, str, str, str]
) -> None:
    """Gate E: impact ⊇ rebuild for each field the circuit's rule reads (like the toy's table)."""
    root, _, _ = built
    rel, old, new, setting = edit
    product = load_product(root)
    run_build(product, render=False, quiet=True)
    report = compute_impact(product, [parse_set(setting)])
    assert "elec:heater" in report.rules and SCHEDULE_RULE in report.rules
    file = root / rel
    text = file.read_text(encoding="utf-8")
    try:
        _edit(root, rel, old, new)
        product, problems = validate(root)
        assert product is not None and not problems.errors, [str(p) for p in problems.errors]
        will = {rid for rid, run, _ in explain_build(product, render=False) if run}
        ran = set(run_build(product, render=False, quiet=True)["ran"])
        assert "elec:heater" in ran
        assert ran <= set(report.rules), sorted(ran - set(report.rules))
        assert ran <= will
    finally:
        file.write_text(text, encoding="utf-8")
        run_build(load_product(root), render=False, quiet=True)


def test_a_note_reruns_no_wiring_rule(built: tuple[Path, Product, Any]) -> None:
    """The rule reads no `notes` (nor `earth`): an edit of them leaves the diagram alone."""
    root, _, _ = built
    file = root / CIRCUIT
    text = file.read_text(encoding="utf-8")
    try:
        _edit(root, CIRCUIT, "notes: The switch", "notes: The two-pole switch")
        ran = run_build(load_product(root), render=False, quiet=True)["ran"]
        assert not [r for r in ran if r.startswith("elec")], ran
    finally:
        file.write_text(text, encoding="utf-8")
        run_build(load_product(root), render=False, quiet=True)


def test_static_reads_cover_the_recorded_ones(built: tuple[Path, Product, Any]) -> None:
    """Before the first build, `n2f impact` assumes at least what the rule records."""
    root, product, _ = built
    entries = json.loads((root / "build/.n2f/manifest.json").read_text(encoding="utf-8"))["entries"]
    rules = {r.id: r for r in registry().rule_family("elec").make_rules(_rule_build(product))}
    for rid in ("elec:heater", SCHEDULE_RULE):
        static = set(elec_static_reads(product, rules[rid]))
        recorded = set(entries[rid]["reads"])
        missing = {
            k
            for k in recorded
            if not any(k == s or k.startswith((s + "#", s + ".")) for s in static)
        }
        assert not missing, (rid, sorted(missing))
    assert rules[SCHEDULE_RULE].produces == SCHEDULE_KEY == "rule:elec-schedule"


def _rule_build(product: Product) -> Any:
    from napkin2factory.core.graph.rules import build_rules

    class _B:
        def __init__(self) -> None:
            self.product = product
            self.rules = build_rules(product, render=False)

    return _B()


def test_the_schedule_key_is_valued_as_its_rules_output(built: tuple[Path, Product, Any]) -> None:
    """S-156: `rule:elec-schedule` is the schedule rule's output hash, never "unbuilt"."""
    from napkin2factory.core.graph.manifest import Manifest
    from napkin2factory.core.graph.values import value_of

    root, product, _ = built
    manifest = Manifest.load(root / "build")
    value = value_of(product, manifest, root / "build", SCHEDULE_KEY)
    assert value == manifest.entries[SCHEDULE_RULE].output_hash
    circuit = value_of(product, manifest, root / "build", "circuit://heater")
    assert circuit == manifest.entries["elec:heater"].output_hash


# ---- a module supplied from elsewhere (DoD 5) ------------------------------------------------


def _external(root: Path) -> None:
    """The heater is switched by a control unit bought complete, reached through one port."""
    _write(
        root,
        "model/assemblies/control-unit.yaml",
        "id: control-unit\nrev: A\nname: Control unit\nbuild: external\nports: [iface://box-unit]\n",
    )
    _edit(
        root,
        "model/assemblies/heated-box.yaml",
        "children:\n",
        "children:\n  - {asm: asm://control-unit}\n",
    )
    _edit(
        root,
        "model/parts/box.yaml",
        "interfaces: [iface://box-entry]",
        "interfaces: [iface://box-entry, iface://box-unit]",
    )
    _write(
        root,
        "model/interfaces/box-unit.yaml",
        "id: box-unit\nkind: cable-entry\nparties: [part://box, asm://control-unit]\n"
        "name: Control cable to the control unit\n"
        "frames:\n  part://box: {origin: [20, 0, 40], normal: [0, 0, 1], x_axis: [1, 0, 0]}\n"
        "spec: {diameter: 12 mm, passes: [circuit://heater]}\n",
    )
    _edit(
        root,
        CIRCUIT,
        '  - {from: "device://switch#2", to: "device://heater#L", conductor: cu-1p5-pvc, '
        "length: 0.2 m}\n",
        '  - {from: "device://switch#2", to: "asm://control-unit#S1", conductor: cu-1p5-pvc, '
        "length: 0.3 m, via: iface://box-unit}\n"
        '  - {from: "asm://control-unit#S2", to: "device://heater#L", conductor: cu-1p5-pvc, '
        "length: 0.3 m, via: iface://box-unit}\n"
        '  - {from: "device://heater#PE", to: "asm://control-unit#PE", conductor: cu-1p5-pvc, '
        "length: 0.3 m, via: iface://box-unit}\n",
    )


def _inside(x: float, y: float, box: tuple[float, float, float, float]) -> bool:
    x0, y0, x1, y1 = box
    eps = 1e-6
    return x0 + eps < x < x1 - eps and y0 + eps < y < y1 - eps


def test_a_module_from_elsewhere_is_a_dashed_boundary_with_nothing_inside(tmp_path: Path) -> None:
    root = copy_product(MINIMAL, tmp_path / "hb", git=False)
    _external(root)
    product, problems = validate(root)
    assert product is not None and not problems.errors, [str(p) for p in problems.errors]
    run_build(product, target="elec", render=False, quiet=True)
    record = json.loads((root / OUT / "heater/connections.json").read_text(encoding="utf-8"))
    assert record["boundary"] == [
        {
            "assembly": "asm://control-unit",
            "name": "Control unit",
            "words": "to the control unit, supplied, not built here: S1, S2, PE",
        }
    ]
    assert {
        "uri": "iface://box-unit",
        "name": "Control cable to the control unit",
        "external": True,
    } in record["entries"]
    svg = (root / OUT / "heater/diagram.svg").read_text(encoding="utf-8")
    ns = "{http://www.w3.org/2000/svg}"
    tree = ET.fromstring(svg)
    (boundary,) = [g for g in tree.iter(f"{ns}g") if g.get("id", "").startswith("boundary-")]
    rect = boundary.find(f"{ns}rect")
    assert rect is not None and rect.get("stroke-dasharray")
    x0, y0 = float(rect.get("x", 0)), float(rect.get("y", 0))
    box = (x0, y0, x0 + float(rect.get("width", 0)), y0 + float(rect.get("height", 0)))
    words = [t.text for t in boundary.iter(f"{ns}text")]
    assert "to the control unit, supplied, not built here: S1, S2, PE" in words
    # nothing anywhere in the drawing lies inside the boundary: no text, pin or line
    points: list[tuple[float, float]] = []
    for el in tree.iter():
        tag = el.tag.removeprefix(ns)
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
    assert not [p for p in points if _inside(*p, box)], "something is drawn inside the boundary"
    # the three conductors reach it, on its edge
    pins = [(float(c.get("cx", 0)), float(c.get("cy", 0))) for c in boundary.iter(f"{ns}circle")]
    assert len(pins) == 3 and all(x in (box[0], box[2]) for x, _ in pins)


# ---- the release package and the report ----------------------------------------------------------


def test_the_release_package_ships_the_diagrams_and_tables(
    built: tuple[Path, Product, Any], tmp_path: Path
) -> None:
    from napkin2factory.ecr.release import make_bundle

    root, product, _ = built
    zip_path = make_bundle(product, root / "build", "v0.1.0", tmp_path)
    with zipfile.ZipFile(zip_path) as zf:
        names = sorted(n for n in zf.namelist() if n.startswith("v0.1.0/electrical/"))
        cover = zf.read("v0.1.0/README.txt").decode("utf-8")
        packed = zf.read("v0.1.0/electrical/heater/diagram.svg")
    assert names == [
        "v0.1.0/electrical/cables.csv",
        "v0.1.0/electrical/heater/diagram.svg",
        "v0.1.0/electrical/labels.csv",
        "v0.1.0/electrical/schedule.csv",
    ]
    assert packed == (root / OUT / "heater/diagram.svg").read_bytes()
    assert "electrical/ (wiring diagrams, cable schedule, terminal labels)" in cover
    assert [r.folder for r in RELEASE_FILES] == ["electrical"]


def test_the_report_stays_small(built: tuple[Path, Product, Any]) -> None:
    root, _, _ = built
    size = (root / "build/report/index.html").stat().st_size
    assert size < 20 * 1024 * 1024  # D13, N10
