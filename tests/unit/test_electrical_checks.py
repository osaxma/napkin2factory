"""v0.6 M3: the wiring checks, the ``circuit`` verify kind and the supply-headroom choice.

ELECTRICAL_STAGE E6 (as S-154 refines it), E11, DoD 3 and 8.  The six fixtures under
``tests/fixtures/electrical/`` are each the minimal heated box with one fault: a load above
the supply, a conductor too thin for its current, a steel box nothing earths and a circuit
with no protective device fail; an interlock that does not break the load and a 5 V loop
through the mains' cable entry warn.  Every failure names the part, the circuit and what to
do, in owner words.  The choice is raised above half the supply's rating, decided with
``n2f decide``, and reopens when what it was decided on changes.  The verify kind compares a
circuit's figures and keys its evidence on the circuit's ``elec:`` output.
"""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from napkin2factory.cli.app import app
from napkin2factory.core.checks.engine import collect_results
from napkin2factory.core.checks.evaluators import EvalContext, evaluate_requirement
from napkin2factory.core.checks.evidence import evidence_key
from napkin2factory.core.checks.results import CheckResult
from napkin2factory.core.graph.manifest import Manifest
from napkin2factory.core.graph.runner import run_build
from napkin2factory.core.loader import Product, load_product, validate
from napkin2factory.domains.electrical.checks.calcs import conducts, read_wiring
from napkin2factory.domains.electrical.checks.pack import rules
from napkin2factory.domains.electrical.checks.stage import ROW_KIND
from napkin2factory.domains.electrical.checks.verify import SELECTORS, figure
from tests.conftest import EXAMPLES, FIXTURES, copy_product
from tests.unit.test_no_example_identifiers import forbidden

# the module's shared product is built once, on one worker (S-196)
pytestmark = pytest.mark.xdist_group("test_electrical_checks")

ELEC = FIXTURES / "electrical"
MINIMAL = ELEC / "minimal"
CIRCUIT = "model/electrical/circuits/heater.yaml"
HEATER = "model/electrical/devices/heater.yaml"
HEADROOM = "elec-rule://supply-headroom@supply"


def _copy(tmp_path: Path, src: Path = MINIMAL, name: str = "hb", git: bool = False) -> Path:
    return copy_product(src, tmp_path / name, git=git)


def _edit(root: Path, rel: str, old: str, new: str) -> None:
    path = root / rel
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, (rel, old)
    path.write_text(text.replace(old, new), encoding="utf-8")


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _rows(root: Path, within: str | None = None) -> dict[str, CheckResult]:
    """The wiring rows of a product's checks (no build needed), by id."""
    product = load_product(root)
    rows, _ = collect_results(product, root / "build", within=within)
    return {r.id: r for r in rows if r.kind == ROW_KIND}


def _cots(root: Path, pid: str, name: str) -> None:
    _write(
        root,
        f"model/parts/{pid}.yaml",
        f"id: {pid}\nrev: A\nname: {name}\nkind: cots\nprocess: none\ngeometry: none\n"
        f'source: {{vendor: Maker, mpn: {pid.upper()}, url: "https://example.com/{pid}", '
        "verified: true}\ncost: {unit: 2 USD, basis: catalog}\nlead_time: 1 d\nmass: 20 g\n",
    )
    _edit(
        root,
        "model/assemblies/heated-box.yaml",
        "  - {part: part://switch, qty: 1}",
        f"  - {{part: part://switch, qty: 1}}\n  - {{part: part://{pid}, qty: 1}}",
    )


# ---- the minimal product ------------------------------------------------------------------------


def test_the_minimal_product_passes_or_warns_as_expected() -> None:
    rows = _rows(MINIMAL)
    assert {i: r.status for i, r in rows.items()} == {
        "elec-rule://upstream-protection@supply": "warn",
        "elec-rule://supply-load@supply": "pass",
        HEADROOM: "pass",
        "elec-rule://protection@heater": "pass",
        "elec-rule://conductor-current@heater": "pass",
        "elec-rule://conductor-protection@heater": "pass",
        "elec-rule://entry-voltage@box-entry": "pass",
    }
    load = rows["elec-rule://supply-load@supply"]
    # DoD 8: the current from the calc kit's power pack (500 W / 230 V), labelled computed
    assert "2.2 A (the Heater: 2.2 A, computed from 500 W at 230 V)" in load.message
    assert "of the supply's 10 A (given)" in load.message
    up = rows["elec-rule://upstream-protection@supply"]
    assert up.message.endswith("a licensed electrician decides.")
    assert rows[HEADROOM].message.startswith("2.2 A of the 10 A circuit: no more than half")
    assert all(r.detail["rule"].startswith("electrical-v0/") for r in rows.values())


def test_every_rule_cites_its_numbers_and_every_warn_defers_to_an_electrician() -> None:
    pack = rules()
    assert {r.severity for r in pack.values()} == {"fail", "warn", "choice"}
    for r in pack.values():
        for p in r.params.values():
            assert p["verify"] is True and p["source"].strip()
        if r.severity == "warn" and r.id not in ("terminals-unsourced",):
            assert r.fix.endswith("a licensed electrician decides"), r.id
    assert pack["supply-headroom"].param("fraction") == 0.5
    assert "NEC 210.23(A)(2)" in pack["supply-headroom"].params["fraction"]["source"]


# ---- DoD 3: the six faults ----------------------------------------------------------------------

FAULTS = {
    # fixture: (row id, status, words the message must hold: part, circuit, what to do)
    "over-supply": (
        "elec-rule://supply-load@supply",
        "fail",
        ("the Heater: 12.2 A, computed from 2800 W at 230 V", "The Heater circuit draws", "above the supply's 10 A", "What to do: lower the load"),  # noqa: E501
    ),
    "thin-conductor": (
        "elec-rule://conductor-current@heater",
        "fail",
        ("Switch terminal 2 to Heater terminal L", "The Heater circuit carries 8.7 A", "0.75 mm² PVC, rated 8.5 A", "What to do: use a thicker conductor"),  # noqa: E501
    ),
    "unearthed": (
        "elec-rule://earth-path@box",
        "fail",
        ("The Box is mild steel, which conducts", "the Heater circuit", "What to do: run an earth conductor"),  # noqa: E501
    ),
    "unprotected": (
        "elec-rule://protection@heater",
        "fail",
        ("The Heater circuit (feeding the Heater) names no protective device", "What to do: name the breaker or fuse"),  # noqa: E501
    ),
    "interlock": (
        "elec-rule://interlock-series@guard-switch",
        "warn",
        ("With the Guard switch open, the Heater (the Heater circuit) still gets power", "What to do: put the interlock in series", "a licensed electrician decides."),  # noqa: E501
    ),
    "shared-entry": (
        "elec-rule://entry-voltage@box-entry",
        "warn",
        ("extra-low-voltage conductors (the Temperature reading circuit) beside mains ones (the Heater circuit)", "Supply cable into the box", "a licensed electrician decides."),  # noqa: E501
    ),
}  # fmt: skip


@pytest.mark.parametrize("fixture", sorted(FAULTS))
def test_each_fault_is_caught_and_said(fixture: str) -> None:
    rid, status, words = FAULTS[fixture]
    _, problems = validate(ELEC / fixture)
    assert not problems.errors, [str(p) for p in problems.errors]
    rows = _rows(ELEC / fixture)
    row = rows[rid]
    assert row.status == status, row.message
    for said in words:
        assert said in row.message, (said, row.message)
    fails = sorted(i for i, r in rows.items() if r.status == "fail")
    if status == "warn":
        assert fails == [], fails  # a code's judgment never fails (E6)
    else:
        assert rid in fails


def test_over_supply_also_fails_the_circuits_protection() -> None:
    row = _rows(ELEC / "over-supply")["elec-rule://protection@heater"]
    assert row.status == "fail"
    assert "draws 12.2 A (computed from 2800 W at 230 V), above the rating of the 10 A" in (
        row.message
    )


# ---- owner words ---------------------------------------------------------------------------------


def test_no_row_text_holds_a_uri_scheme_or_an_example_id() -> None:
    banned = forbidden()
    for fixture in ["minimal", "thin-under-breaker", "class-two-metal", *FAULTS]:
        for row in _rows(ELEC / fixture).values():
            text = f"{row.title} {row.message} {json.dumps(row.detail.get('options', []))}"
            assert "://" not in text, (fixture, text)
            assert not re.search(r"\b(?:REQ|DEC|ECR)-\d{3}\b", text), text
            hits = [i for i in banned if re.search(rf"(?<![\w-]){re.escape(i)}(?![\w-])", text)]
            assert not hits, (fixture, hits, text)


# ---- no wiring, or wiring left for later: no row (E12, F11) --------------------------------------


def test_a_product_without_wiring_has_no_electrical_row(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "b", git=False)
    product = load_product(root)
    rows, _ = collect_results(product, root / "build")
    assert rows and not [r for r in rows if r.kind == ROW_KIND]


def test_wiring_left_for_later_has_no_row(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    _edit(root, "n2f.yaml", "electrical: {state: in, decision: DEC-001}", "electrical: {state: later, decision: DEC-001}")  # fmt: skip  # noqa: E501
    assert _rows(root) == {}


# ---- --scope asm://<id>: a circuit's rows belong where its devices sit ---------------------------


def test_scope_keeps_the_circuits_whose_devices_sit_in_the_module(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    _edit(
        root,
        "model/assemblies/heated-box.yaml",
        "  - {part: part://heater, qty: 1}\n  - {part: part://switch, qty: 1}\n",
        "  - {asm: asm://heater-unit, qty: 1}\n",
    )
    _write(
        root,
        "model/assemblies/heater-unit.yaml",
        "id: heater-unit\nrev: A\nname: Heater unit\nchildren:\n"
        "  - {part: part://heater, qty: 1}\n  - {part: part://switch, qty: 1}\n",
    )
    _, problems = validate(root)
    assert not problems.errors, [str(p) for p in problems.errors]
    whole = _rows(root)
    assert whole["elec-rule://protection@heater"].subject == "asm://heater-unit"
    assert whole["elec-rule://protection@heater"].module == "heater-unit"
    unit = _rows(root, within="heater-unit")
    assert sorted(unit) == [
        "elec-rule://conductor-current@heater",
        "elec-rule://conductor-protection@heater",
        "elec-rule://protection@heater",
    ]
    # the supply's rows are the whole product's; the entry closes in the top assembly
    top = _rows(root, within="heated-box")
    assert "elec-rule://entry-voltage@box-entry" in top
    assert "elec-rule://supply-load@supply" not in top


# ---- earth paths ---------------------------------------------------------------------------------


def _steel_box(tmp_path: Path) -> Path:
    root = _copy(tmp_path, ELEC / "unearthed")
    return root


def test_an_earth_conductor_to_the_box_passes(tmp_path: Path) -> None:
    root = _steel_box(tmp_path)
    _write(
        root,
        "model/electrical/devices/box.yaml",
        "id: box\npart: part://box\nrole: earth\nterminals: [PE]\n",
    )
    _edit(
        root,
        CIRCUIT,
        "notes: The switch",
        '  - {from: "device://heater#PE", to: "device://box#PE", conductor: cu-1p5-pvc, '
        "length: 0.1 m}\nnotes: The switch",
    )
    row = _rows(root)["elec-rule://earth-path@box"]
    assert row.status == "pass"
    assert row.message == "The Box reaches earth through an earth conductor of the Heater circuit."


def test_a_bonded_joint_is_a_claim_and_a_bond_to_nothing_fails(tmp_path: Path) -> None:
    root = _steel_box(tmp_path)
    _edit(
        root,
        CIRCUIT,
        "notes: The switch",
        "earth:\n  - {part: part://box, bonded_via: [iface://box-entry]}\nnotes: The switch",
    )
    row = _rows(root)["elec-rule://earth-path@box"]
    assert row.status == "fail"
    assert "bonds it through Supply cable into the box, but no part on the other side" in (
        row.message
    )
    # the gland on the other side of the joint is earthed: the bond is a claim to verify
    _write(
        root,
        "model/electrical/devices/gland.yaml",
        "id: gland\npart: part://gland\nrole: earth\nterminals: [PE]\n",
    )
    _edit(
        root,
        CIRCUIT,
        "earth:\n",
        '  - {from: "supply://supply#PE", to: "device://gland#PE", conductor: cu-1p5-pvc, '
        "length: 0.1 m}\nearth:\n",
    )
    rows = _rows(root)
    assert "elec-rule://earth-path@box" not in rows
    bonded = rows["elec-rule://earth-bonded@box"]
    assert bonded.status == "warn"
    assert bonded.message.startswith(
        "The Box reaches earth only through Supply cable into the box (bonded to the Cable "
        "gland), as the Heater circuit says."
    )
    assert bonded.message.endswith("a licensed electrician decides.")


def test_a_material_nobody_can_place_asks_a_person(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    _edit(root, "model/parts/box.yaml", 'name: polycarbonate, spec: "PC"', "name: unobtainium")
    row = _rows(root)["elec-rule://earth-path@box"]
    assert row.status == "warn"
    assert "Whether the Box conducts is not known (its material (unobtainium))" in row.message


def test_class_two_devices_in_a_plastic_box_need_no_earth(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    _edit(root, HEATER, "class: I\n", "class: II\n")
    rows = _rows(root)
    assert "elec-rule://earth-path@box" not in rows
    row = rows["elec-rule://earth-path@product"]
    assert row.status == "pass"
    assert "and no part made here conducts, so no part needs a path to earth" in row.message


def test_class_two_devices_in_a_metal_box_ask_an_electrician() -> None:
    """Gate G blocker 2 (S-178): the product's own mains wiring runs in the steel box."""
    rows = _rows(ELEC / "class-two-metal")
    assert "elec-rule://earth-path@product" not in rows
    row = rows["elec-rule://earth-path@box"]
    assert row.status == "warn", row.message  # a code's judgment, never a fail (E6)
    assert row.message.startswith(
        "Every device is Class II or III, but the Box is mild steel, which conducts, and the "
        "product's own mains conductors pass through it (the Heater circuit at the cable "
        "entry “Supply cable into the box”): whether the product as a whole is Class II is a "
        "licensed electrician's call."
    )
    assert "or run an earth conductor to it" in row.message
    assert row.message.endswith("a licensed electrician decides.")
    assert not [i for i, r in rows.items() if r.status == "fail"]


def test_class_two_in_metal_with_no_entry_through_it_still_asks(tmp_path: Path) -> None:
    """Where the model cannot tell where the conductors run, a conductive part still warns."""
    root = _copy(tmp_path, ELEC / "class-two-metal")
    _edit(root, "model/parts/box.yaml", 'name: mild steel, spec: "DC01"', "name: polycarbonate")
    _write(
        root,
        "model/parts/frame.yaml",
        "id: frame\nrev: A\nname: Frame\nkind: custom\nprocess: cut-block\n"
        'material: {name: aluminium, spec: "6061-T6"}\nfinish: none\n'
        "tolerance_class: ISO2768-m\n"
        "geometry: {kit: block, args: {length: 40 mm, width: 20 mm, height: 10 mm}}\n"
        "cost: {unit: 3 USD, basis: estimate}\nlead_time: 2 d\n",
    )
    _edit(
        root,
        "model/assemblies/heated-box.yaml",
        "  - {part: part://switch, qty: 1}",
        "  - {part: part://switch, qty: 1}\n  - {part: part://frame, qty: 1}",
    )
    _, problems = validate(root)
    assert not problems.errors, [str(p) for p in problems.errors]
    row = _rows(root)["elec-rule://earth-path@frame"]
    assert row.status == "warn"
    assert (
        "the Frame is aluminium, which conducts, and nothing in the wiring says that the "
        "product's own mains conductors (the Heater circuit) stay out of it" in row.message
    )


def test_class_two_at_extra_low_voltage_needs_no_earth(tmp_path: Path) -> None:
    root = _copy(tmp_path, ELEC / "class-two-metal")
    _edit(root, "model/electrical/supply.yaml", "voltage: 230 V", "voltage: 24 V")
    _edit(root, HEATER, "voltage: 230 V", "voltage: 24 V")
    row = _rows(root)["elec-rule://earth-path@product"]
    assert row.status == "pass"
    assert "and every circuit runs at extra-low voltage" in row.message


# ---- gate G blocker 1: each conductor against the device that protects it ----------------------


def test_a_conductor_below_its_breaker_fails() -> None:
    """The reviewer's case: every conductor 0.75 mm² (8.5 A) on a 32 A breaker (S-178)."""
    _, problems = validate(ELEC / "thin-under-breaker")
    assert not problems.errors, [str(p) for p in problems.errors]
    rows = _rows(ELEC / "thin-under-breaker")
    # the load is small, so the load check passes: that is what hid the fault
    assert rows["elec-rule://conductor-current@heater"].status == "pass"
    row = rows["elec-rule://conductor-protection@heater"]
    assert row.status == "fail"
    for said in (
        "In the Heater circuit, connection 1 (the supply's L to Switch terminal 1)",
        "connection 4 (Switch terminal 4 to Heater terminal N) are 0.75 mm² PVC, rated 8.5 A "
        "(from the table), below the 32 A breaker of the site circuit that protects them "
        "(32 A, given)",
        "What to do: use conductors rated at least 32 A, or a protective device rated no "
        "more than 8.5 A; a licensed electrician decides.",
    ):
        assert said in row.message, (said, row.message)
    assert "connection 5" not in row.message  # the earth conductor carries no load current
    assert row.detail["circuit"] == "heater"


def test_the_thin_conductor_also_fails_its_breaker() -> None:
    row = _rows(ELEC / "thin-conductor")["elec-rule://conductor-protection@heater"]
    assert row.status == "fail"
    assert "connection 3 (Switch terminal 2 to Heater terminal L) is 0.75 mm² PVC" in row.message
    assert "connection 1 " not in row.message


def _fused(tmp_path: Path, rating: str | None) -> Path:
    """The minimal box with its own fuse in the line, rated ``rating`` (or not rated)."""
    root = _copy(tmp_path)
    _cots(root, "fuse", "Fuse")
    rated = f"rating: {{voltage: 250 V, current: {rating}}}\n" if rating else ""
    _write(
        root,
        "model/electrical/devices/fuse.yaml",
        f"id: fuse\npart: part://fuse\nrole: protection\n{rated}"
        'terminals: ["1", "2"]\nthrough: [["1", "2"]]\n',
    )
    _edit(root, CIRCUIT, "protection: supply", "protection: device://fuse")
    _edit(
        root,
        CIRCUIT,
        '  - {from: "supply://supply#L", to: "device://switch#1", conductor: cu-1p5-pvc',
        '  - {from: "supply://supply#L", to: "device://fuse#1", conductor: cu-1p5-pvc, '
        "length: 0.1 m, via: iface://box-entry}\n"
        '  - {from: "device://fuse#2", to: "device://switch#1", conductor: cu-0p75-pvc',
    )
    _, problems = validate(root)
    assert not problems.errors, [str(p) for p in problems.errors]
    return root


def test_a_fuse_with_no_rating_asks_an_electrician(tmp_path: Path) -> None:
    rows = _rows(_fused(tmp_path, None))
    row = rows["elec-rule://conductor-protection@heater"]
    assert row.status == "warn"
    assert row.message.startswith(
        "The Heater circuit is protected by the Fuse, whose rating is not given, so whether "
        "it protects its conductors is not checked."
    )
    assert row.message.endswith("a licensed electrician decides.")
    assert not [i for i, r in rows.items() if r.status == "fail"]


def test_a_fuse_judges_what_it_feeds_and_the_supply_its_lead(tmp_path: Path) -> None:
    rows = _rows(_fused(tmp_path, "6 A"))
    row = rows["elec-rule://conductor-protection@heater"]
    assert row.status == "pass", row.message
    # the 0.75 mm² lead after the fuse is the closest; the 1.5 mm² lead before it is the
    # supply's (10 A): neither is below its device
    assert "connection 2 (Fuse terminal 2 to Switch terminal 1) is 0.75 mm² PVC" in row.message
    assert "under the Fuse, rated 6 A, given" in row.message
    rows = _rows(_fused(tmp_path / "b", "10 A"))
    row = rows["elec-rule://conductor-protection@heater"]
    assert row.status == "fail"
    assert "connection 2 (Fuse terminal 2 to Switch terminal 1) is 0.75 mm² PVC" in row.message
    assert "connection 1 " not in row.message  # 1.5 mm² before the fuse, under the 10 A supply


@pytest.mark.parametrize(
    ("material", "conductive"),
    [
        ("mild steel", True),
        ("Stainless steel 304", True),
        ("polycarbonate", False),
        ("carbon fibre", True),
        ("glass-filled nylon", False),
        ("unobtainium", None),
    ],
)
def test_which_materials_conduct(material: str, conductive: bool | None) -> None:
    assert conducts(material) is conductive


# ---- interlocks, limits, contact ratings (E6, S-154 point 6) -------------------------------------


def _controlled(tmp_path: Path, independent: bool) -> Path:
    """The heater switched by a relay its thermostat drives, with a cut-out for over-temperature.

    ``independent``: the cut-out drives a second relay in the heater's line; otherwise it
    sits in the thermostat's coil path and breaks the same relay.
    """
    root = _copy(tmp_path, name="ctl" + ("-ok" if independent else ""))
    for pid, name in (
        ("relay", "Relay"),
        ("thermostat", "Thermostat"),
        ("cutout", "Over-temperature cut-out"),
        ("backup", "Backup relay"),
    ):
        _cots(root, pid, name)
    relay = (
        "role: control\nrating: {voltage: 230 V, current: 16 A}\nterminals: [A1, A2, '1', '2']\n"
        "class: II\ncontact: {current: 16 A, category: AC-1}\ncoil: [A1, A2]\n"
        "through: [['1', '2']]\n"
    )
    _write(root, "model/electrical/devices/relay.yaml", "id: relay\npart: part://relay\n" + relay)
    _write(
        root, "model/electrical/devices/backup.yaml", "id: backup\npart: part://backup\n" + relay
    )
    _write(
        root,
        "model/electrical/devices/thermostat.yaml",
        "id: thermostat\npart: part://thermostat\nrole: control\nterminals: ['1', '2']\n"
        "class: II\ncontact: {current: 2 A, category: AC-1}\nthrough: [['1', '2']]\n",
    )
    _write(
        root,
        "model/electrical/devices/cutout.yaml",
        "id: cutout\npart: part://cutout\nrole: control\nterminals: ['1', '2']\nclass: II\n"
        "contact: {current: 2 A, category: AC-15}\nsafety: limit\nthrough: [['1', '2']]\n",
    )
    line = (
        '  - {from: "device://switch#2", to: "device://backup#1", conductor: cu-1p5-pvc}\n'
        '  - {from: "device://backup#2", to: "device://relay#1", conductor: cu-1p5-pvc}\n'
        if independent
        else '  - {from: "device://switch#2", to: "device://relay#1", conductor: cu-1p5-pvc}\n'
    )
    _edit(
        root,
        CIRCUIT,
        '  - {from: "device://switch#2", to: "device://heater#L", conductor: cu-1p5-pvc, '
        "length: 0.2 m}\n",
        line + '  - {from: "device://relay#2", to: "device://heater#L", conductor: cu-1p5-pvc}\n',
    )
    coils = (
        '  - {from: "device://switch#2", to: "device://thermostat#1", conductor: cu-1p0-pvc}\n'
        '  - {from: "device://thermostat#2", to: "device://relay#A1", conductor: cu-1p0-pvc}\n'
        '  - {from: "device://relay#A2", to: "device://switch#4", conductor: cu-1p0-pvc}\n'
        '  - {from: "device://switch#2", to: "device://cutout#1", conductor: cu-1p0-pvc}\n'
        '  - {from: "device://cutout#2", to: "device://backup#A1", conductor: cu-1p0-pvc}\n'
        '  - {from: "device://backup#A2", to: "device://switch#4", conductor: cu-1p0-pvc}\n'
        if independent
        else '  - {from: "device://switch#2", to: "device://thermostat#1", conductor: cu-1p0-pvc}\n'
        '  - {from: "device://thermostat#2", to: "device://cutout#1", conductor: cu-1p0-pvc}\n'
        '  - {from: "device://cutout#2", to: "device://relay#A1", conductor: cu-1p0-pvc}\n'
        '  - {from: "device://relay#A2", to: "device://switch#4", conductor: cu-1p0-pvc}\n'
    )
    if not independent:
        _edit(root, "model/assemblies/heated-box.yaml", "  - {part: part://backup, qty: 1}\n", "")
        (root / "model/parts/backup.yaml").unlink()
        (root / "model/electrical/devices/backup.yaml").unlink()
    _write(
        root,
        "model/electrical/circuits/coils.yaml",
        "id: coils\npurpose: control\nname: Relay coils\nprotection: supply\nconnections:\n"
        + coils,
    )
    _, problems = validate(root)
    assert not problems.errors, [str(p) for p in problems.errors]
    return root


def test_a_limit_device_breaking_the_controllers_relay_warns(tmp_path: Path) -> None:
    rows = _rows(_controlled(tmp_path, independent=False))
    row = rows["elec-rule://limit-independent@cutout"]
    assert row.status == "warn"
    assert row.message.startswith(
        "With the Relay and the Thermostat stuck on (the controller's side), opening the "
        "Over-temperature cut-out leaves the Heater (the Heater circuit) with power"
    )
    # the cut-out's AC-15 contact drives the relay's coil
    assert rows["elec-rule://contact-category@cutout"].status == "pass"
    assert "elec-rule://contact-category@thermostat" not in rows  # a contact sits between


def test_a_limit_device_with_a_relay_of_its_own_passes(tmp_path: Path) -> None:
    rows = _rows(_controlled(tmp_path, independent=True))
    row = rows["elec-rule://limit-independent@cutout"]
    assert row.status == "pass", row.message
    assert row.message == (
        "Opening the Over-temperature cut-out stops the Heater even with the controller's "
        "side stuck on."
    )
    assert rows["elec-rule://contact-category@cutout"].status == "pass"
    assert not [r for r in rows.values() if r.status == "fail"], rows
    # the thermostat's AC-1 contact drives the relay's coil: it needs AC-15 or DC-13
    contact = rows["elec-rule://contact-category@thermostat"]
    assert contact.status == "warn"
    assert "switches the coil of the Relay and is rated AC-1" in contact.message
    assert "needs AC-15 or DC-13" in contact.message


def test_an_interlock_in_the_load_path_passes(tmp_path: Path) -> None:
    root = _copy(tmp_path, ELEC / "interlock")
    _edit(
        root,
        CIRCUIT,
        '  - {from: "device://switch#2", to: "device://heater#L", conductor: cu-1p5-pvc, '
        "length: 0.2 m}\n",
        "",
    )
    row = _rows(root)["elec-rule://interlock-series@guard-switch"]
    assert row.status == "pass"
    assert row.message == "Opening the Guard switch stops the Heater."


def test_unsourced_terminals_warn(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    _cots(root, "lamp", "Lamp")
    _write(root, "model/electrical/devices/lamp.yaml", "id: lamp\npart: part://lamp\nrole: load\n")
    row = _rows(root)["elec-rule://terminals-unsourced@lamp"]
    assert row.status == "warn"
    assert row.message.startswith("The Lamp's terminals are not listed yet")


# ---- the supply-headroom choice (E11) ------------------------------------------------------------


def test_above_half_the_rating_the_owner_chooses(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    _edit(root, HEATER, "power: 500 W", "power: 1500 W")
    row = _rows(root)[HEADROOM]
    assert row.status == "choice"
    assert row.detail["blocks"] == "none"
    assert row.message.startswith(
        "6.5 A of the 10 A circuit (the Heater: 6.5 A, computed from 1500 W at 230 V): more "
        "than half of it."
    )
    assert [o["id"] for o in row.detail["options"]] == ["dedicated", "larger"]
    assert row.detail["options"][0]["summary"] == (
        "a dedicated 10 A circuit; nothing else may be plugged into it"
    )
    assert row.detail["options"][1]["summary"] == (
        "a 16 A dedicated circuit: room for a bigger load later; the electrician fits thicker cable"
    )
    assert all("cost_delta" not in o for o in row.detail["options"])
    assert row.detail["evidence"] == [
        "supply://supply",
        "param://supply-rating",
        "circuit://heater",
        "device://heater",
    ]
    # the larger circuit, applied: the rule passes on the model itself
    _edit(root, "model/parameters.yaml", "{value: 10, unit: A", "{value: 16, unit: A")
    assert _rows(root)[HEADROOM].status == "pass"


def test_no_larger_circuit_on_file_is_a_warning_not_a_choice(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    _edit(root, HEATER, "power: 500 W", "power: 1500 W")
    _edit(root, HEATER, "power: 1500 W", "power: 2500 W")
    _edit(root, "model/electrical/supply.yaml", "region: EU", "region: AU")
    _edit(root, "model/parameters.yaml", "{value: 10, unit: A", "{value: 20, unit: A")
    row = _rows(root)[HEADROOM]
    assert row.status == "warn"
    assert "the one way left is to keep this circuit for the product alone" in row.message


@pytest.fixture(scope="module")
def chosen(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """The minimal product with a 1500 W heater, built, the choice decided with `n2f decide`."""
    root = copy_product(
        MINIMAL, tmp_path_factory.mktemp("elec") / "hb", prebuilt=True, render=False
    )
    _edit(root, HEATER, "power: 500 W", "power: 1500 W")
    run_build(load_product(root), render=False, quiet=True)
    r = CliRunner().invoke(
        app,
        ["decide", HEADROOM, "--pick", "dedicated", "--by", "Ada", "--dir", str(root), "--json"],
    )
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert out["status"] == "pass" and out["decision"]["id"] == "DEC-002"
    yield root


def test_decided_the_row_reads_pass_with_its_decision(chosen: Path) -> None:
    dec = load_product(chosen).decisions["DEC-002"]
    assert dec.made_by == "human"
    assert dec.sources[0] == f"choice {HEADROOM}: option dedicated, chosen by Ada"
    row = _rows(chosen)[HEADROOM]
    assert row.status == "pass"
    assert row.detail["decision"] == {"id": "DEC-002", "option": "dedicated", "by": "Ada"}


def test_a_bigger_heater_reopens_the_choice(chosen: Path, tmp_path: Path) -> None:
    root = _clone(chosen, tmp_path / "again")
    _edit(root, HEATER, "power: 1500 W", "power: 1600 W")
    row = _rows(root)[HEADROOM]
    assert row.status == "choice"
    assert row.detail["reopened"]["changed"] == ["device://heater"]


def _clone(root: Path, dst: Path) -> Path:
    """A copy with its build (copy_product leaves the build out)."""
    shutil.copytree(root, dst, ignore=shutil.ignore_patterns(".git"))
    return dst


def _elec_built(root: Path) -> bool:
    return "elec:heater" in Manifest.load(root / "build").entries


def test_an_edited_power_connection_reopens_the_choice(chosen: Path, tmp_path: Path) -> None:
    root = _clone(chosen, tmp_path / "again")
    assert _elec_built(root), "the elec: rules did not build circuit://heater"  # B-0247
    _edit(root, CIRCUIT, 'heater#L", conductor: cu-1p5-pvc', 'heater#L", conductor: cu-2p5-pvc')
    run_build(load_product(root), render=False, quiet=True)
    row = _rows(root)[HEADROOM]
    assert row.status == "choice"
    assert "circuit://heater" in row.detail["reopened"]["changed"]


# ---- the circuit verify kind ---------------------------------------------------------------------


REQS = """
  - id: REQ-003
    title: The heater draws little
    statement: The heater circuit draws less than {limit}.
    category: electrical
    priority: must
    verify: {{kind: circuit, target: "circuit://heater#props.{sel}", op: "{op}", value: {value}}}
    allocation: [part://heater]
"""


def _write_req(root: Path, sel: str, op: str, value: str) -> None:
    text = (root / "model/requirements.yaml").read_text(encoding="utf-8")
    text = text.split("\n  - id: REQ-003")[0].rstrip("\n") + "\n"
    (root / "model/requirements.yaml").write_text(
        text + REQS.format(sel=sel, op=op, value=value, limit="10 A"), encoding="utf-8"
    )


def _req(root: Path, sel: str, op: str, value: str) -> Product:
    _write_req(root, sel, op, value)
    return load_product(root)


def _evaluate(product: Product, root: Path) -> CheckResult:
    return evaluate_requirement(
        EvalContext(product, root / "build"), product.requirements["REQ-003"]
    )


@pytest.mark.parametrize(
    ("sel", "op", "value", "status", "said"),
    [
        ("load_current", "<", "10 A", "pass", "the Heater circuit's load current is 2.2 A"),
        ("load_current", "<", "2 A", "fail", "(computed from 500 W at 230 V); the requirement: < 2.0 A"),  # noqa: E501
        ("supply_margin", ">", "0 A", "pass", "supply margin is 7.8 A (10.0 A rating less 2.2 A load)"),  # noqa: E501
        ("conductor_margin", ">", "0 A", "pass", "smallest conductor margin is 10.9 A (1.5 mm² PVC, rated 13.1 A"),  # noqa: E501
        ("earth_paths", ">=", "1", "pass", "parts it earths is 1 (counted from the connections)"),
        ("earth_paths", ">=", "2", "fail", "parts it earths is 1"),
    ],
)  # fmt: skip
def test_the_verify_kind_compares_each_figure(
    tmp_path: Path, sel: str, op: str, value: str, status: str, said: str
) -> None:
    root = _copy(tmp_path)
    product = _req(root, sel, op, value)
    _, problems = validate(root)
    assert not problems.errors, [str(p) for p in problems.errors]
    res = _evaluate(product, root)
    assert res.status == status, res.message
    assert said in res.message, res.message
    assert "circuit://heater" in res.evidence_keys


def test_every_selector_has_a_figure() -> None:
    w = read_wiring(load_product(MINIMAL))
    assert {s: figure(w, "heater", s) is not None for s in SELECTORS} == dict.fromkeys(
        SELECTORS, True
    )


def test_an_unknown_figure_is_refused_with_the_four(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    _write_req(root, "load_curent", "<", "10 A")
    _, problems = validate(root)
    errors = " ".join(str(p) for p in problems.errors)
    assert "a circuit requirement selects one of its figures" in errors
    for s in SELECTORS:
        assert f"circuit://heater#props.{s}" in errors


def test_an_unknown_load_skips_never_fails(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    _edit(root, HEATER, "rating: {voltage: 230 V, power: 500 W}\n", "")
    res = _evaluate(_req(root, "load_current", "<", "10 A"), root)
    assert res.status == "skip"
    assert "is not known" in res.message


def test_a_safety_requirement_is_refused(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    product = _req(root, "load_current", "<", "10 A")
    req = product.requirements["REQ-003"].model_copy(update={"safety": True})
    res = evaluate_requirement(EvalContext(product, root / "build"), req)
    assert res.status == "fail"
    assert "check it with `verify: {kind: manual}`" in res.message


def test_the_evidence_key_follows_the_circuit_not_an_unrelated_part(tmp_path: Path) -> None:
    root = _copy(tmp_path, git=True)
    product = _req(root, "load_current", "<", "10 A")
    run_build(product, render=False, quiet=True)
    assert _elec_built(root), "the elec: rules did not build circuit://heater"  # B-0247
    first = _evaluate(load_product(root), root).evidence_keys["circuit://heater"]
    assert first == evidence_key(load_product(root), root / "build", "circuit://heater")
    _edit(root, "model/parts/gland.yaml", "unit: 0.5 USD", "unit: 0.6 USD")
    run_build(load_product(root), render=False, quiet=True)
    assert _evaluate(load_product(root), root).evidence_keys["circuit://heater"] == first
    _edit(root, CIRCUIT, "length: 0.2 m}\n  - {from: \"device://switch#4\"", "length: 0.3 m}\n  - {from: \"device://switch#4\"")  # fmt: skip  # noqa: E501
    run_build(load_product(root), render=False, quiet=True)
    assert _evaluate(load_product(root), root).evidence_keys["circuit://heater"] != first


def test_parameter_of_wrong_dimension_raises_validation_error(tmp_path: Path) -> None:
    """B-0163: a param:// of wrong dimension raises a validation error naming param and field."""
    root = _copy(tmp_path)
    params_file = root / "model" / "parameters.yaml"
    params_file.write_text(
        params_file.read_text(encoding="utf-8")
        + "  heater-power: {value: 500, unit: kg, description: Heater rating in kg}\n",
        encoding="utf-8",
    )
    _edit(root, HEATER, "power: 500 W", "power: param://heater-power")
    product = load_product(root)
    with pytest.raises(ValueError) as exc:
        read_wiring(product)
    msg = str(exc.value)
    assert "heater-power" in msg
    assert "power" in msg

    # None/missing stays None
    _edit(root, HEATER, "power: param://heater-power", "power: param://missing-param")
    w_missing = read_wiring(load_product(root))
    assert w_missing.devices["heater"].power is None

    _edit(root, HEATER, "power: param://missing-param", "")
    w_none = read_wiring(load_product(root))
    assert w_none.devices["heater"].power is None


def test_branch_conductors_carry_downstream_loads_and_fan_branch_passes(tmp_path: Path) -> None:
    """S-214: conductors carry what they feed; fan on thin branch passes."""
    branch_src = ELEC / "branch-loads"
    root = _copy(tmp_path, src=branch_src, name="branch")
    rows = _rows(root)
    rule_row = rows["elec-rule://conductor-current@heater"]
    assert rule_row.status == "pass"
    assert "every conductor is rated for it (the least margin: 3.1 A" in rule_row.message

    # Conductor margin selector on branch circuit
    w = read_wiring(load_product(root))
    from napkin2factory.domains.electrical.checks.calcs import conductor_margin
    from napkin2factory.domains.electrical.checks.nets import topology

    t = topology(w)
    cm = conductor_margin(w, "heater", t.earth, t)
    assert cm is not None
    assert "1.5 mm² PVC, rated 13.1 A, at connection 3" in cm.words

    # When the heater branch uses a thin conductor, it fails against 10 A (not the 10.2 A total)
    _edit(
        root,
        CIRCUIT,
        'to: "device://heater#L", conductor: cu-1p5-pvc',
        'to: "device://heater#L", conductor: cu-0p75-pvc',
    )
    rows_thin = _rows(root)
    fail_row = rows_thin["elec-rule://conductor-current@heater"]
    assert fail_row.status == "fail"
    assert (
        "connection 3 (Switch terminal 2 to Heater terminal L) is 0.75 mm² PVC, "
        "rated 8.5 A (carries 10.0 A)"
    ) in fail_row.message
    # The fan branch (also 0.75 mm² PVC) carries 0.2 A, so it is NOT in the failure list
    assert "Fan" not in fail_row.message


# ---- protective earth is no load current (B-0236, S-233) -----------------------------------


def _pump_on_its_own_circuit(tmp_path: Path, bond_in_mains: bool) -> Path:
    """The minimal box plus a 10 A pump on a circuit of its own; its earth is bonded either in
    its own circuit or, as the test-stand trial wrote it, in the mains circuit (S-233)."""
    root = _copy(tmp_path)
    _cots(root, "pump", "Pump")
    _write(
        root,
        "model/electrical/devices/pump.yaml",
        "id: pump\npart: part://pump\nrole: load\nrating: {voltage: 230 V, power: 2300 W}\n"
        "terminals: [L, N, PE]\nclass: I\n",
    )
    own = [
        '  - {from: "supply://supply#L", to: "device://pump#L", conductor: cu-1p5-pvc, '
        "length: 0.4 m}",
        '  - {from: "supply://supply#N", to: "device://pump#N", conductor: cu-1p5-pvc, '
        "length: 0.4 m}",
    ]
    bond = (
        '  - {from: "supply://supply#PE", to: "device://pump#PE", conductor: cu-1p5-pvc, '
        "length: 0.5 m, colour: green-and-yellow}"
    )
    _write(
        root,
        "model/electrical/circuits/pump.yaml",
        "id: pump\npurpose: power\nname: Pump\nprotection: supply\nconnections:\n"
        + "\n".join(own + ([] if bond_in_mains else [bond]))
        + "\n",
    )
    if bond_in_mains:
        text = (root / CIRCUIT).read_text(encoding="utf-8")
        (root / CIRCUIT).write_text(text.replace("notes:", bond + "\nnotes:", 1), encoding="utf-8")
    return root


def test_a_mains_circuit_bonding_another_loads_earth_is_not_charged_its_current(
    tmp_path: Path,
) -> None:
    # the heater draws 500 W / 230 V = 2.17 A; the pump 2300 W / 230 V = 10 A on its own
    # circuit; the mains breaker of the minimal product is 10 A
    for bond_in_mains in (False, True):
        rows = _rows(_pump_on_its_own_circuit(tmp_path / str(bond_in_mains), bond_in_mains))
        row = rows["elec-rule://protection@heater"]
        assert row.status == "pass", (bond_in_mains, row.message)
        assert "Pump" not in row.message
        assert rows["elec-rule://conductor-current@heater"].status != "fail"
