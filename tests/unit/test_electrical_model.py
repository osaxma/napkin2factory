"""v0.6 M1: the wiring model and the cable entry (ELECTRICAL_STAGE §5 M1, S-153, S-154).

The electrical domain is installed (``domains/__init__.py``); the product
``tests/fixtures/electrical/minimal`` is a heater and its two-pole switch in a box, fed from
a socket circuit through one cable gland.  It loads and validates; every broken reference is
an error naming its file and the fix; a device whose terminals are not sourced is a warning;
a load or control device nobody wired blocks Design while the wiring is done here (E7); a
``later`` product's content is the core's lint warning; the entry's hole is cut in the box
and matched, the bought gland skipped with the core's sentence, then the entry's own check
runs (S-144); ``n2f doctor`` lists the domain.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from napkin2factory.cli.app import app
from napkin2factory.core import registry as registry_mod
from napkin2factory.core.checks.stage import compute_stage
from napkin2factory.core.graph.runner import run_build
from napkin2factory.core.lint import lint
from napkin2factory.core.loader import Product, load_product, validate
from napkin2factory.core.registry import registry
from napkin2factory.domains import electrical
from napkin2factory.domains.electrical.interfaces import CableEntrySpec, check_cable_entry
from napkin2factory.domains.electrical.model import (
    Connection,
    Device,
    Supply,
    placed,
    wired_devices,
)
from napkin2factory.domains.electrical.owner.gates import design_row, verify_row
from tests.conftest import EXAMPLES, FIXTURES, copy_product

# the module's shared product is built once, on one worker (S-196)
pytestmark = pytest.mark.xdist_group("test_electrical_model")

MINIMAL = FIXTURES / "electrical" / "minimal"
CIRCUIT = "model/electrical/circuits/heater.yaml"


def _copy(tmp_path: Path, name: str = "hb") -> Path:
    return copy_product(MINIMAL, tmp_path / name, git=False)


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


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Path, Product]]:
    """The minimal product built once (no renders)."""
    root = copy_product(
        MINIMAL, tmp_path_factory.mktemp("elec") / "hb", prebuilt=True, render=False
    )
    product = load_product(root)
    run_build(product, render=False, quiet=True)
    yield root, product


# ---- the domain is registered, and the fixture loads -------------------------------------------


def test_every_registry_sees_the_electrical_domain() -> None:
    reg = registry()
    assert "electrical" in [d.name for d in reg.domains]
    folders = {n: reg.model_family(n).folder for n in ("supply", "device", "circuit", "conductor")}
    assert folders == {
        "supply": "model/electrical",
        "device": "model/electrical/devices",
        "circuit": "model/electrical/circuits",
        "conductor": "model/electrical/conductors",
    }
    elec = reg.rule_family("elec")
    assert (elec.after, elec.before, elec.produces) == (("part",), ("doc",), "circuit://")
    assert elec.output_dir == "electrical"
    names = [f.name for f in reg.rule_families()]
    assert names.index("part") < names.index("elec") < names.index("doc")
    assert reg.verify_kind("circuit").target_schemes == ("circuit",)
    assert reg.check_stage("electrical").after == ("interface",)
    assert "Wiring" in [r.title for r in reg.gate_rows("design")]
    assert "Wiring checks" in [r.title for r in reg.gate_rows("verify")]
    assert reg.report_section("wiring").group == "Product"
    for helper in ("circuit", "cable_schedule", "terminal_labels"):
        assert reg.doc_helper(helper) is electrical.DOMAIN.doc_helpers[helper]
    assert reg.vocabulary("owner")["electrical"] == "wiring"
    assert reg.vocabulary("owner")["device"] == "electrical device"
    assert reg.interface_kind("cable-entry").spec is CableEntrySpec
    assert "electrical" in reg.categories()
    assert "electrical" in [c.name for c in reg.context_contributions()]
    assert ("electrical", electrical.DOMAIN.release_files[0]) in reg.release_files()


def test_the_fixture_loads_and_validates() -> None:
    product, problems = validate(MINIMAL)
    assert product is not None
    assert not problems.errors, [str(p) for p in problems.errors]
    assert not [p for p in problems.warnings if p.rule == "electrical"]
    sup = product.families["supply"]["supply"]
    assert isinstance(sup, Supply) and sup.terminal_names() == ["L", "N", "PE"]
    assert str(sup.rating) == "param://supply-rating"
    assert sup.protection.upstream.startswith("the 10 A breaker")
    assert set(product.families["device"]) == {"heater", "switch"}
    assert product.families["device"]["heater"].class_ == "I"
    assert product.files["circuit://heater"].name == "heater.yaml"
    assert wired_devices(product) == {"heater", "switch"}
    assert placed(product, "heater") == 1 and placed(product, "box") == 1


# ---- every validation error names its file and the fix ----------------------------------------


def _bad_part(root: Path) -> None:
    _edit(root, "model/electrical/devices/heater.yaml", "part://heater", "part://nothing")


def _second_device(root: Path) -> None:
    _write(
        root,
        "model/electrical/devices/heater-2.yaml",
        "id: heater-2\npart: part://heater\nrole: load\nterminals: [L, N, PE]\n",
    )


def _unknown_terminal(root: Path) -> None:
    _edit(root, CIRCUIT, 'to: "device://heater#L"', 'to: "device://heater#L9"')


def _ambiguous_shorthand(root: Path) -> None:
    _edit(
        root, "model/assemblies/heated-box.yaml", "part://heater, qty: 1", "part://heater, qty: 2"
    )
    _second_device(root)
    _edit(root, CIRCUIT, 'to: "device://heater#L"', 'to: "part://heater#L"')


def _unknown_conductor(root: Path) -> None:
    _edit(
        root,
        CIRCUIT,
        "conductor: cu-1p5-pvc, length: 0.5 m",
        "conductor: cu-9p9-gold, length: 0.5 m",
    )


def _via_not_passing(root: Path) -> None:
    _edit(root, "model/interfaces/box-entry.yaml", "passes: [circuit://heater]", "passes: []")


def _missing_supply(root: Path) -> None:
    (root / "model/electrical/supply.yaml").unlink()


def _unknown_protection(root: Path) -> None:
    _edit(root, CIRCUIT, "protection: supply", "protection: part://fuse")


def _via_not_an_entry(root: Path) -> None:
    _edit(root, CIRCUIT, "length: 0.5 m, via: iface://box-entry", "length: 0.5 m, via: iface://lid")


def _stub(root: Path, via: str) -> None:
    """A control unit supplied from elsewhere, with one cable entry as its port."""
    _write(
        root,
        "model/assemblies/control-unit.yaml",
        "id: control-unit\nrev: A\nname: Control unit\nbuild: external\n"
        "ports: [iface://box-unit]\n",
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
        "description: The control cable leaves the box for the bought control unit.\n"
        "frames:\n  part://box: {origin: [20, 0, 40], normal: [0, 0, 1], x_axis: [1, 0, 0]}\n"
        "spec: {diameter: 12 mm, passes: [circuit://heater]}\n",
    )
    _edit(
        root,
        CIRCUIT,
        "notes:",
        f'  - {{from: "device://switch#2", to: "asm://control-unit#S1", conductor: cu-1p5-pvc, '
        f"length: 0.3 m, via: {via}}}\nnotes:",
    )


def _missing_port(root: Path) -> None:
    _stub(root, "iface://box-entry")


#: (edit, the problem's file, a phrase of its message, a phrase of its fix)
ERRORS: dict[str, tuple[Callable[[Path], None], str, str, str]] = {
    "bad part": (
        _bad_part,
        "model/electrical/devices/heater.yaml",
        "names part://nothing, which is not a part",
        "add model/parts/nothing.yaml",
    ),
    "too many devices per part": (
        _second_device,
        "model/electrical/devices/heater-2.yaml",
        "2 devices name part://heater (device://heater, device://heater-2), but the product "
        "places it once",
        "keep one device per placed part",
    ),
    "unknown terminal": (
        _unknown_terminal,
        CIRCUIT,
        "device://heater has no terminal 'L9'; its terminals are L, N, PE",
        "write one of device://heater's terminals",
    ),
    "ambiguous part shorthand": (
        _ambiguous_shorthand,
        CIRCUIT,
        "names part://heater, but 2 devices name that part (device://heater, "
        "device://heater-2), so it cannot say which",
        "name the device instead: one of device://heater#L, device://heater-2#L",
    ),
    "unknown conductor": (
        _unknown_conductor,
        CIRCUIT,
        "names conductor 'cu-9p9-gold', which is not on file",
        "add model/electrical/conductors/cu-9p9-gold.yaml with its source",
    ),
    "via not passing": (
        _via_not_passing,
        "model/interfaces/box-entry.yaml",
        "circuit://heater goes through this cable entry",
        "add circuit://heater to `passes:` in model/interfaces/box-entry.yaml",
    ),
    "via not an entry": (
        _via_not_an_entry,
        CIRCUIT,
        "goes via iface://lid, which is not an interface",
        "add model/interfaces/lid.yaml with `kind: cable-entry`",
    ),
    "missing supply": (
        _missing_supply,
        "model/electrical/supply.yaml",
        "1 circuit(s) exist but the product has no supply",
        "add model/electrical/supply.yaml",
    ),
    "unknown protection": (
        _unknown_protection,
        CIRCUIT,
        "its protection names part://fuse, which is not a part",
        "add model/parts/fuse.yaml",
    ),
    "missing port on an external stub": (
        _missing_port,
        "model/assemblies/control-unit.yaml",
        "circuit://heater reaches this module supplied from elsewhere (connection 6 "
        "(device://switch#2 to asm://control-unit#S1)), but goes via iface://box-entry, which "
        "is not one of its ports (iface://box-unit)",
        "add iface://box-entry to `ports:` in model/assemblies/control-unit.yaml",
    ),
}


@pytest.mark.parametrize("case", sorted(ERRORS))
def test_each_validation_error_names_its_file_and_the_fix(case: str, tmp_path: Path) -> None:
    edit, file, message, fix = ERRORS[case]
    root = _copy(tmp_path)
    edit(root)
    _, problems = validate(root)
    hits = [p for p in problems.errors if message in p.message]
    assert len(hits) == 1, [str(p) for p in problems.errors]
    assert Path(hits[0].file) == root / file
    assert fix in hits[0].hint, hits[0].hint


def test_two_devices_for_a_part_placed_twice_are_fine(tmp_path: Path) -> None:
    """S-154 point 1: one device per placement; the part stays one parts-list line."""
    root = _copy(tmp_path)
    _edit(
        root, "model/assemblies/heated-box.yaml", "part://heater, qty: 1", "part://heater, qty: 2"
    )
    _second_device(root)
    product, problems = validate(root)
    assert product is not None and placed(product, "heater") == 2
    assert not [p for p in problems.items if p.rule == "electrical" and "places" in p.message]


def test_a_port_of_the_stub_is_the_way_in(tmp_path: Path) -> None:
    """DoD 5: a conductor reaching a module supplied from elsewhere crosses one of its ports."""
    root = _copy(tmp_path)
    _stub(root, "iface://box-unit")
    _, problems = validate(root)
    assert not problems.errors, [str(p) for p in problems.errors]
    _edit(root, CIRCUIT, "length: 0.3 m, via: iface://box-unit", "length: 0.3 m")
    _, problems = validate(root)
    names_no_via = [p for p in problems.errors if "names no `via:`" in p.message]
    assert [Path(p.file).name for p in names_no_via] == ["control-unit.yaml"]


def test_unsourced_terminals_are_a_warning_never_an_error(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    _edit(
        root,
        "model/electrical/devices/switch.yaml",
        'terminals: ["1", "2", "3", "4"]',
        "terminals: []",
    )
    _edit(root, "model/electrical/devices/switch.yaml", 'through: [["1", "2"], ["3", "4"]]\n', "")
    _, problems = validate(root)
    assert not problems.errors, [str(p) for p in problems.errors]
    (warn,) = [p for p in problems.warnings if p.rule == "electrical"]
    assert warn.subject == "device://switch"
    assert warn.message.startswith("its terminals are not sourced yet")
    assert (
        "read them from the datasheet named on the part (https://example.com/switch)" in warn.hint
    )


@pytest.mark.parametrize(
    ("schema", "data", "words"),
    [
        (Supply, {"voltage": "230 V", "earthing": "XY"}, "no earthing arrangement 'XY' on file"),
        (
            Supply,
            {"voltage": "24 V", "dc": True, "frequency": "50 Hz"},
            "a DC supply has no frequency",
        ),
        (Supply, {"voltage": "16 A"}, "a voltage is a quantity like '230 V'"),
        (Supply, {"voltage": "230 V", "protection": "supply"}, "the supply's protection is"),
        (
            Device,
            {"id": "d", "part": "part://p", "role": "load", "terminals": ["L", "L"]},
            "listed twice",
        ),
        (Device, {"id": "d", "part": "part://p", "role": "lamp"}, "role"),
        (
            Device,
            {"id": "d", "part": "part://p", "role": "control", "terminals": ["A1"], "coil": ["A2"]},
            "terminal 'A2' is not one of the device's terminals (A1)",
        ),
        (
            Device,
            {"id": "d", "part": "part://p", "role": "control", "contact": {"category": "AC-99"}},
            "unknown contact category 'AC-99'; known: resistive, AC-1",
        ),
        (Connection, {"from": "heater#L", "to": "device://x#N"}, "is not a connection end"),
        (Connection, {"from": "device://x#N", "to": "device://x#N"}, "two different terminals"),
    ],
)
def test_the_schemas_refuse_what_cannot_be_read(
    schema: Any, data: dict[str, Any], words: str
) -> None:
    with pytest.raises(ValidationError) as err:
        schema.model_validate(data)
    assert words in str(err.value)


def test_a_rating_plate_class_and_terminal_names_read_as_written() -> None:
    dev = Device.model_validate(
        {
            "id": "d",
            "part": "part://p",
            "role": "control",
            "class": 2,
            "terminals": ["+", "TC-", "13"],
        }
    )
    assert dev.class_ == "II" and dev.terminals == ["+", "TC-", "13"]
    conn = Connection.model_validate({"from": "device://d#TC-", "to": "supply://supply#PE"})
    assert [str(e) for e in conn.ends()] == ["device://d#TC-", "supply://supply#PE"]
    assert Supply.model_validate({"voltage": "400 V", "phases": 3}).terminal_names() == [
        "L1",
        "L2",
        "L3",
        "N",
        "PE",
    ]


# ---- the gate rows (E7) and scope ---------------------------------------------------------------


def _design(root: Path) -> Any:
    return next(g for g in compute_stage(load_product(root)).gates if g.name == "design")


def test_the_design_row_counts_the_wiring(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    state = design_row(load_product(root), root / "build")
    assert state is not None
    assert (state.summary, state.blockers) == ("2 devices, 1 circuit: all wired", [])
    out = _cli("status", "-C", str(root))
    assert "Wiring: 2 devices, 1 circuit: all wired" in out, out


def test_a_device_nobody_wired_blocks_design_while_the_wiring_is_done_here(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    path = root / CIRCUIT
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    path.write_text("".join(ln for ln in lines if "device://heater" not in ln), encoding="utf-8")
    gate = _design(root)
    blocker = (
        "the Heater is not wired yet — connect it in a circuit under model/electrical/circuits/"
    )
    assert blocker in gate.blockers
    assert {"title": "Wiring", "summary": "2 devices, 1 circuit: 1 not wired yet"} in gate.detail[
        "rows"
    ]


def test_the_rows_are_absent_without_wiring(tmp_path: Path) -> None:
    bracket = load_product(EXAMPLES / "bracket")
    assert design_row(bracket, tmp_path) is None and verify_row(bracket, tmp_path) is None
    gates = {g.name: g for g in compute_stage(bracket).gates}
    for name in ("design", "verify"):
        assert not [
            r for r in gates[name].detail.get("rows", []) if r["title"].startswith("Wiring")
        ]


def test_wiring_said_done_here_with_nothing_in_it_blocks_design(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    shutil.rmtree(root / "model/electrical")
    _edit(root, "model/interfaces/box-entry.yaml", "passes: [circuit://heater]", "passes: []")
    state = design_row(load_product(root), root / "build")
    assert state is not None and state.summary == "nothing wired yet"
    assert state.blockers[0].startswith("the wiring is marked done here, but there is no supply")


def test_a_later_products_wiring_is_the_cores_lint_warning(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    _edit(root, "n2f.yaml", "{state: in, decision: DEC-001}", "{state: later, decision: DEC-001}")
    product = load_product(root)
    (warn,) = [p for p in lint(product).warnings if p.rule == "L15-scope"]
    assert "electrical is `later`, but content exists for it (supply://supply" in warn.message
    assert warn.hint.startswith("set scope to in or remove it")
    gate = _design(root)
    # the core drops the domain's row for `later` and says the scope in a row of its own
    (row,) = [r for r in gate.detail.get("rows", []) if r["title"] == "Wiring"]
    assert row["scope"] == "later" and row["summary"].startswith("left for later (DEC-001)")
    assert not [b for b in gate.blockers if "not wired yet" in b]


# ---- the cable entry: cut and matched by the core, then its own check (S-144) ------------------


def test_the_entry_hole_is_cut_in_the_box(built: tuple[Path, Product]) -> None:
    root, _ = built
    features = json.loads((root / "build/parts/box/features.json").read_text())
    (pattern,) = [p for p in features["patterns"] if p["interface"] == "iface://box-entry"]
    assert pattern["diameter"] == pytest.approx(16.5)
    assert pattern["centers"] == [[0.0, 0.0, 40.0]]


def test_the_entry_row_has_the_cores_words_then_its_own(built: tuple[Path, Product]) -> None:
    root, _ = built
    rows = json.loads((root / "build/checks/checks.json").read_text())["results"]
    row = next(r for r in rows if r["id"] == "iface://box-entry")
    assert row["status"] == "pass"
    assert row["message"] == (
        "the hole is cut in box; cable gland has no shape to check it against; "
        "box to cable gland: carries the Heater circuit"
    )
    assert row["detail"]["kind_check"]["status"] == "pass"
    assert row["detail"]["parties"]["part://gland"]["status"] == "skip"


def test_the_entrys_own_check_fails_a_circuit_that_does_not_cross(
    built: tuple[Path, Product], tmp_path: Path
) -> None:
    root, _ = built
    other = _copy(tmp_path)
    path = other / CIRCUIT
    path.write_text(path.read_text().replace(", via: iface://box-entry", ""))
    product = load_product(other)
    report = check_cable_entry(product, product.interfaces["box-entry"], root / "build")
    assert report["status"] == "fail"
    assert (
        "the Heater circuit is listed under `passes:`, but none of its connections goes"
        in (report["message"])
    )
    _edit(other, "model/interfaces/box-entry.yaml", "passes: [circuit://heater]", "passes: []")
    product = load_product(other)
    report = check_cable_entry(product, product.interfaces["box-entry"], root / "build")
    assert (
        report["status"] == "warn"
        and "no circuit passes through this entry yet" in report["message"]
    )


@pytest.mark.parametrize(
    ("spec", "words"),
    [
        ({"diameter": "20 mm", "count": 2}, "a cable entry is one hole (count: 2)"),
        ({"diameter": "20 mm", "pattern": "circle"}, "leave `pattern:` out"),
    ],
)
def test_an_entry_is_one_hole(spec: dict[str, Any], words: str) -> None:
    with pytest.raises(ValidationError) as err:
        CableEntrySpec.model_validate(spec)
    assert words in str(err.value)


# ---- discoverable, and the code hash split (S-153) ----------------------------------------------


def test_doctor_lists_the_electrical_domain() -> None:
    data = json.loads(_cli("doctor", "--json"))
    row = next(d for d in data["domains"] if d["name"] == "electrical")
    assert [v["name"] for v in row["verify_kinds"]] == ["circuit"]
    assert [s["name"] for s in row["check_stages"]] == ["electrical"]
    assert row["rule_families"] == ["elec"] and row["report_sections"] == ["wiring"]


def test_an_edit_of_the_owners_view_does_not_move_the_rule_familys_code(tmp_path: Path) -> None:
    """The ``elec`` family hashes outputs/, model/ and interfaces/ only; the domain all of it."""
    copy = tmp_path / "electrical"
    shutil.copytree(electrical.ROOT, copy, ignore=shutil.ignore_patterns("__pycache__"))
    code = registry().rule_family("elec").code

    def hashes() -> tuple[str, str]:
        registry_mod._tree_hash.cache_clear()
        return registry_mod._tree_hash(str(copy), code), registry_mod._tree_hash(str(copy), ())

    try:
        family, domain = hashes()
        report = copy / "owner" / "report.py"
        report.write_text(report.read_text() + "\n# an edit of the owner's view\n")
        assert hashes() == (family, hashes()[1]) and hashes()[1] != domain
        rules = copy / "outputs" / "rules.py"
        rules.write_text(rules.read_text() + "\n# an edit of the rules\n")
        assert hashes()[0] != family
        schema = copy / "model" / "__init__.py"
        before = hashes()[0]
        schema.write_text(schema.read_text() + "\n# an edit of the schema\n")
        assert hashes()[0] != before
    finally:
        registry_mod._tree_hash.cache_clear()
