"""v0.5 M3 (F8, F10, S-128): the generic screens, a product's own screens and rule packs.

The heated-box screens moved out of the system into ``examples/kiln/model/screens/``; the
system keeps the screens any card can use. These tests pin the seam: the kiln's shipped
screenings come out the same through the kiln's own pack; a card without the pack gets only
the generic screens; a product's screen runs, declares its fields (skeleton, lint) and is
hashed into the concept build; a product's rule pack runs in ``n2f check``; the v0.4 site
keys (``alcove_*``) are read as aliases with a lint note.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

from napkin2factory.concepts.massing import compose
from napkin2factory.concepts.screening import same_screening, screen
from napkin2factory.concepts.screens import GENERIC_SCREENS, card_fields, generic_fields
from napkin2factory.core import concepts as cm
from napkin2factory.core.errors import N2FError
from napkin2factory.core.model import ConceptCard
from tests.conftest import EXAMPLES, copy_product
from tests.unit.test_screening import KILN, KILN_ROOT, SMALL, _card

GENERIC_RULES = [
    "fits-site-width",
    "fits-site-depth",
    "fits-site-height",
    "mass-vs-lift-class",
    "blank-vs-stock-sheet",
    "walls-fit-envelope",
]
KILN_RULES = [
    "circuit-available",
    "controls-not-adjacent-hot-face",
    "skin-vs-touch-limit",
    "chamber-volume-vs-target",
]

OWN_SCREEN = """
from napkin2factory.concepts.screens import CardField, reads
from napkin2factory.core.domain import Screen
from napkin2factory.core.model.concepts import RuleRow
from napkin2factory.core.units import Quantity

VIEW = CardField("site", "view", None, "words", "garden", "what it looks out on")
BALLAST = CardField("envelope", "ballast", "kg", "a mass", "12 kg", "the ballast")


@reads(VIEW, BALLAST, phase="estimate")
def ballast(card, massing, values):
    kg = BALLAST.quantity(card)
    if kg is None:
        return []
    values.estimate.add("ballast_mass", kg, f"{kg.magnitude:g} kg", "from the card", "own")
    values.mass_items.append((kg.to("kg"), "the ballast", "ballast_mass"))
    return [RuleRow(id="ballast-set", title="Ballast", status="pass", message="{MARK}")]


SCREENS = (Screen("ballast", ballast),)
"""


def _own_product(tmp_path: Path, mark: str = "set") -> Path:
    root = tmp_path / "own"
    (root / "model" / "screens").mkdir(parents=True)
    (root / "model" / "screens" / "ballast.py").write_text(OWN_SCREEN.replace("{MARK}", mark))
    return root


# --- the kiln through its own pack ----------------------------------------------------------


@pytest.mark.parametrize("cid", ["C-001", "C-002", "C-003", "C-004"])
def test_the_kilns_shipped_screenings_come_out_the_same(cid: str) -> None:
    """DoD 3: re-screened through the kiln's own pack, each card says what it said."""
    card = cm.load_card(KILN_ROOT, cid)
    again = screen(card, compose(card, write=False), KILN_ROOT)
    assert card.screening is not None and same_screening(card.screening, again)
    # the system's rows first, then the kiln's own (F10)
    assert [r.id for r in again.rules] == GENERIC_RULES + KILN_RULES


def test_a_heated_card_without_the_pack_gets_the_generic_screens_only() -> None:
    card = _card(KILN)
    massing = compose(card, write=False)
    alone, full = screen(card, massing), screen(card, massing, KILN_ROOT)
    assert [r.id for r in alone.rules] == GENERIC_RULES
    assert alone.computed == full.computed  # the space, the mass and the door: the same
    assert not alone.given and "heat_loss" not in alone.estimates
    assert set(alone.estimates) == {"cost_low", "cost_high", "lift_class"}
    walls = next(r for r in alone.rules if r.id == "walls-fit-envelope")
    assert walls.status == "skip"  # no screen shares an inner size and a wall


def test_the_generic_screens_declare_their_fields() -> None:
    names = [s.name for s in GENERIC_SCREENS]
    assert names[:1] == ["fits-the-space"] and "walls-fit-envelope" in names
    keys = {f.name for f in generic_fields()}
    assert {"site.width", "site.depth", "site.height", "envelope.door_swing"} <= keys
    assert not keys & {"envelope.chamber", "envelope.power", "site.circuit"}
    kiln = {f.name for f in card_fields(KILN_ROOT)}
    assert {"envelope.chamber", "envelope.power", "site.circuit", "site.touch_limit"} <= kiln


# --- a product's own screens (F10) --------------------------------------------------------------


def test_a_product_screen_runs_after_the_generic_rows(tmp_path: Path) -> None:
    root = _own_product(tmp_path)
    card = _card(SMALL, envelope={"ballast": "12 kg"})
    s = screen(card, compose(card, write=False), root)
    assert s.estimates["ballast_mass"].value == "12 kg"
    assert s.estimates["total_mass"].source == "the rough shapes plus the ballast"
    assert [r.id for r in s.rules] == [*GENERIC_RULES, "ballast-set"]


def test_its_fields_shape_the_skeleton_and_the_lint(tmp_path: Path) -> None:
    root = _own_product(tmp_path)
    card = cm.new_card(root, "Garden box")
    text = cm.card_path(root, card.id).read_text()
    assert "ballast (a mass, like 12 kg)" in text and "view (like garden)" in text
    assert "chamber" not in text  # no heated box's fields unless its screens are installed
    path = cm.card_path(root, card.id)
    path.write_text(
        text.replace("envelope: {}", "envelope: {ballast: 3 m}").replace(
            "site: {}", "site: {view: sea, ceiling: white}"
        )
    )
    problems = cm.lint_concepts(root)
    assert [p.message for p in problems.errors] == ["envelope.ballast is 3 m, which is not a mass"]
    (warn,) = problems.warnings
    assert warn.rule == "C5-site-keys" and "'ceiling'" in warn.message
    assert "view" in warn.hint


def test_a_broken_screen_module_names_its_file(tmp_path: Path) -> None:
    root = tmp_path / "bad"
    (root / "model" / "screens").mkdir(parents=True)
    (root / "model" / "screens" / "oops.py").write_text("SCREENS = (1,)\n")
    with pytest.raises(N2FError, match=r"model/screens/oops.py"):
        screen(_card(SMALL), None, root)
    (root / "model" / "screens" / "oops.py").write_text("import nothing_here\n")
    with pytest.raises(N2FError, match=r"model/screens/oops.py cannot be loaded"):
        screen(_card(SMALL), None, root)


def test_a_changed_screen_invalidates_the_concept_build(tmp_path: Path) -> None:
    from napkin2factory.concepts.build import build_concept

    root = _own_product(tmp_path)
    data = {**SMALL, "envelope": {"ballast": "12 kg"}}
    cm.write_card(root, ConceptCard.model_validate(data))
    build_concept(root, cm.load_card(root, "C-002"), render=False)
    recorded = json.loads((root / "build/concepts/C-002/screening.json").read_text())
    assert recorded["screens"].startswith("sha256:")
    old = "2026-01-01T00:00:00"
    path = cm.card_path(root, "C-002")
    path.write_text(path.read_text().replace(f"at: '{_at(path)}'", f"at: '{old}'"))
    build_concept(root, cm.load_card(root, "C-002"), render=False)
    assert _at(path) == old  # same screens, same numbers: the card is left alone (S-086)
    pack = root / "model" / "screens" / "ballast.py"
    pack.write_text(pack.read_text() + "\n# tuned\n")
    build_concept(root, cm.load_card(root, "C-002"), render=False)
    assert _at(path) != old  # the screens changed: the old screening is void (F10)
    again = json.loads((root / "build/concepts/C-002/screening.json").read_text())
    assert again["screens"] != recorded["screens"]


def _at(card_path: Path) -> str:
    return str(yaml.safe_load(card_path.read_text())["screening"]["at"]).replace(" ", "T")


# --- the v0.4 site keys --------------------------------------------------------------------------


def test_alcove_keys_are_read_as_the_space_with_a_lint_note(tmp_path: Path) -> None:
    old = _card(SMALL, site={"alcove_width": "800 mm", "alcove_depth": "300 mm"})
    old.site.pop("width")
    new = _card(SMALL, site={"width": "800 mm", "depth": "300 mm"})
    a = screen(old, compose(old, write=False))
    b = screen(new, compose(new, write=False))
    assert same_screening(a, b)
    assert next(r for r in a.rules if r.id == "fits-site-depth").status == "fail"
    d = tmp_path / "concepts"
    d.mkdir()
    (d / "C-001.yaml").write_text("id: C-001\ntitle: t\nsite: {alcove_width: 800 mm}\n")
    (note,) = cm.lint_concepts(tmp_path).items
    assert note.severity == "warn" and note.rule == "C10-renamed-keys"
    assert note.message == "site.alcove_width is read as site.width for this version only"
    assert "rename it to width" in note.hint


# --- a product's own rule pack in `n2f check` (F10) ---------------------------------------------

OWN_PACK = """pack: own-v0
title: The product's own rules
applies_to: {}
rules:
  - id: named
    title: Every part has a name
    severity: fail
    check: has_a_name
    params: {min: 3}
    message: "{part} has a short name"
"""
OWN_CHECKS = """
def has_a_name(part, features, params, product):
    return [] if len(part.name) >= params["min"] else [{"part": part.id}]


CHECKS = {"has_a_name": has_a_name}
"""


def test_a_product_rule_pack_runs_in_check_and_is_hashed(tmp_path: Path) -> None:
    from napkin2factory.core.graph.runner import run_build
    from napkin2factory.core.loader import load_product

    root = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", git=False)
    packs = root / "model" / "rulepacks"
    packs.mkdir()
    (packs / "own.yaml").write_text(OWN_PACK)
    (packs / "own.py").write_text(OWN_CHECKS)
    run_build(load_product(root), render=False, quiet=True)
    rows = json.loads((root / "build/checks/checks.json").read_text())["results"]
    row = next(r for r in rows if r["id"] == "rule://own-v0/named@l-bracket")
    assert row["status"] == "pass"
    (packs / "own.py").write_text(OWN_CHECKS.replace(">= params", "< params"))
    ran = run_build(load_product(root), render=False, quiet=True)["ran"]
    assert "checks" in ran  # the pack's code is an input of the checks rule
    rows = json.loads((root / "build/checks/checks.json").read_text())["results"]
    row = next(r for r in rows if r["id"] == "rule://own-v0/named@l-bracket")
    assert row["status"] == "fail" and row["message"] == "l-bracket has a short name"


def test_a_product_without_packs_keeps_its_checks_key(tmp_path: Path) -> None:
    from napkin2factory.core.packs import pack_inputs

    root = tmp_path / "plain"
    (root / "model").mkdir(parents=True)
    assert pack_inputs(root) == {}
    shutil.copytree(KILN_ROOT / "model" / "screens", root / "model" / "screens")
    assert pack_inputs(root) == {}  # screens are the concept build's, not the checks'
