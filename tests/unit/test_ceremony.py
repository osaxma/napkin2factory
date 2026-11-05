"""The derived ceremony (W6, S-205): each way up, each relaxation, and the notice.

Products are copies of the shipped examples and fixtures, edited in a temp folder; only the
integration tests build (from a prebuilt copy, S-196).
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from napkin2factory.core.ceremony import (
    default_tolerance,
    derive_ceremony,
    hazard_table,
    manuals_problem,
    note_level,
    tolerance_label,
)
from napkin2factory.core.lint import lint
from napkin2factory.core.loader import load_product
from napkin2factory.core.model import Manifest
from napkin2factory.core.yamlio import dump_roundtrip, load_roundtrip
from napkin2factory.domains.electrical.owner.hazards import hazards
from napkin2factory.report.builder_common import sections
from tests.conftest import EXAMPLES, FIXTURES, copy_product, n2f

MINIMAL = FIXTURES / "electrical" / "minimal"  # a heated box: mechanical + wiring, 230 V AC


def _edit(path: Path, fn) -> None:  # type: ignore[no-untyped-def]
    data = load_roundtrip(path)
    fn(data)
    dump_roundtrip(path, data)


def _bracket(tmp_path: Path) -> Path:
    return copy_product(EXAMPLES / "bracket", tmp_path / "p", git=False)


def _add_requirement(root: Path, **extra: object) -> None:
    def add(data) -> None:  # type: ignore[no-untyped-def]
        data["requirements"].append(
            {
                "id": "REQ-090",
                "title": "Stays upright",
                "statement": "The product withstands a 50 N push at its top without tipping.",
                "category": "safety",
                "allocation": "unallocated",
                "verify": {"kind": "manual", "note": "push it"},
                **extra,
            }
        )

    _edit(root / "model" / "requirements.yaml", add)


# ---- the derivation: each way up -------------------------------------------------------------


def test_one_domain_no_hazard_is_lite(tmp_path: Path) -> None:
    c = derive_ceremony(load_product(_bracket(tmp_path)))
    assert (c.level, c.reasons) == ("lite", ())


def test_mains_supply_raises_with_its_voltage(tmp_path: Path) -> None:
    product = load_product(copy_product(MINIMAL, tmp_path / "p", git=False))
    assert hazards(product) == [
        "it runs on mains: the supply is 230 V AC (given), above extra-low voltage"
    ]
    c = derive_ceremony(product)
    assert c.level == "standard"
    assert c.reasons[0].startswith("it runs on mains")


def test_extra_low_voltage_supply_is_no_hazard() -> None:
    """24 V DC is below the 120 V DC limit and 24 V AC below the 50 V AC one (IEC 61140)."""
    from napkin2factory.domains.electrical.model import Supply

    def product(**fields: object) -> SimpleNamespace:
        return SimpleNamespace(families={"supply": {"supply": Supply(**fields)}})  # type: ignore[arg-type]

    assert hazards(product(voltage="24 V", dc=True)) == []
    assert hazards(product(voltage="24 V")) == []
    assert hazards(product(voltage="100 V", dc=True)) == []  # DC limit is 120 V
    assert hazards(product(voltage="100 V")) != []  # AC limit is 50 V
    assert hazards(product(voltage="150 V", dc=True)) != []
    assert hazards(SimpleNamespace(families={})) == []  # no supply, no hazard


def test_a_second_domain_raises_even_without_a_hazard(tmp_path: Path) -> None:
    product = load_product(copy_product(MINIMAL, tmp_path / "p", git=False))
    reasons = derive_ceremony(product).reasons
    assert "the product has work in more than one field (mechanical and electrical)" in reasons


@pytest.mark.parametrize(
    ("kind", "level"),
    [
        ("high-temperature", "standard"),
        ("moving-machinery", "standard"),
        ("stored-energy", "standard"),
        ("mains", "standard"),
        ("tip-over", "lite"),
        ("sharp-edge", "lite"),
        ("pinch", "lite"),
    ],
)
def test_hazard_tag_raises_only_for_raising_kinds(tmp_path: Path, kind: str, level: str) -> None:
    root = _bracket(tmp_path)
    _add_requirement(root, safety=True, tags=[f"hazard:{kind}"])
    c = derive_ceremony(load_product(root))
    assert c.level == level
    if level == "standard":
        assert hazard_table()[kind].title.lower() in c.reasons[0]
        assert "Stays upright" in c.reasons[0]  # the requirement's own words, no example words


def test_every_hazard_row_cites_a_source() -> None:
    for haz in hazard_table().values():
        assert haz.source.strip() and haz.verify, haz.id


def test_manifest_can_raise_but_never_lower(tmp_path: Path) -> None:
    root = _bracket(tmp_path)
    _edit(root / "n2f.yaml", lambda d: d.update(ceremony="standard"))
    c = derive_ceremony(load_product(root))
    assert (c.level, c.reasons) == ("standard", ("n2f.yaml asks for the standard ceremony",))
    with pytest.raises(ValidationError, match="ceremony can only be raised"):
        Manifest.model_validate({"product": {"id": "x", "name": "X"}, "ceremony": "lite"})


# ---- lint: a safety requirement names its hazard ---------------------------------------------


def test_safety_requirement_without_hazard_tag_is_a_lint_error(tmp_path: Path) -> None:
    root = _bracket(tmp_path)
    _add_requirement(root, safety=True)
    errors = [p for p in lint(load_product(root)).errors if p.rule == "L4-hazard-tag"]
    assert len(errors) == 1
    assert errors[0].subject == "req://REQ-090"
    assert "tip-over" in errors[0].hint and "mains" in errors[0].hint  # lists the kinds


def test_unknown_hazard_kind_is_a_lint_error_listing_the_known_ones(tmp_path: Path) -> None:
    root = _bracket(tmp_path)
    _add_requirement(root, tags=["hazard:laser"])
    errors = [p for p in lint(load_product(root)).errors if p.rule == "L4-hazard-tag"]
    assert [e.message for e in errors] == ["unknown hazard kind 'laser'"]
    assert "sharp-edge" in errors[0].hint


# ---- lite relaxations ------------------------------------------------------------------------


def _drop_tolerance(root: Path) -> None:
    _edit(root / "model" / "parts" / "l-bracket.yaml", lambda d: d.pop("tolerance_class"))


def test_lite_accepts_a_missing_tolerance_class_where_the_process_has_a_default(
    tmp_path: Path,
) -> None:
    root = _bracket(tmp_path)
    _drop_tolerance(root)
    product = load_product(root)
    part = product.parts["l-bracket"]
    ceremony = derive_ceremony(product)
    assert default_tolerance(product, part, ceremony) == "ISO2768-m"  # sheet metal's default
    assert tolerance_label(part, "ISO2768-m") == "ISO2768-m (default)"
    assert not [p for p in lint(product).errors if p.rule == "L8-tolerance-class"]


def test_standard_still_wants_the_tolerance_class(tmp_path: Path) -> None:
    root = _bracket(tmp_path)
    _drop_tolerance(root)
    _edit(root / "n2f.yaml", lambda d: d.update(ceremony="standard"))
    product = load_product(root)
    assert default_tolerance(product, product.parts["l-bracket"], derive_ceremony(product)) is None
    assert [p.rule for p in lint(product).errors] == ["L8-tolerance-class"]


def test_lite_without_a_process_default_still_wants_it(tmp_path: Path) -> None:
    root = _bracket(tmp_path)
    _drop_tolerance(root)
    # an undeclared process has no default (and its own error)
    _edit(root / "model" / "parts" / "l-bracket.yaml", lambda d: d.update(process="none"))
    rules = {p.rule for p in lint(load_product(root)).errors}
    assert "L8-tolerance-class" in rules


def test_one_build_and_care_page_stands_for_the_manual_set(tmp_path: Path) -> None:
    root = _bracket(tmp_path)
    docs = root / "model" / "docs"
    (docs / "safety.md").rename(docs / "build-and-care.md")
    text = (docs / "build-and-care.md").read_text(encoding="utf-8")
    (docs / "build-and-care.md").write_text(
        text.replace("id: safety", "id: build-and-care"), encoding="utf-8"
    )
    product = load_product(root)
    assert manuals_problem(product, derive_ceremony(product)) is None
    _edit(root / "n2f.yaml", lambda d: d.update(ceremony="standard"))
    product = load_product(root)
    problem = manuals_problem(product, derive_ceremony(product))
    assert problem is not None and "safety.md" in problem[1]
    assert any(p.rule == "L18-manuals" for p in lint(product).items)


def test_lite_report_leaves_out_empty_sections_and_standard_keeps_them(tmp_path: Path) -> None:
    root = _bracket(tmp_path)
    product = load_product(root)
    lite = {sid for sid, _, _ in sections(product)}
    assert "changes" not in lite and "joints" not in lite  # no change request, one unit
    assert "signoffs" not in lite  # none recorded yet
    product.signoffs["REQ-001"] = object()  # type: ignore[assignment]
    assert "signoffs" in {sid for sid, _, _ in sections(product)}  # a sign-off is never hidden
    assert {"overview", "safety", "requirements", "parts"} <= lite
    _edit(root / "n2f.yaml", lambda d: d.update(ceremony="standard"))
    standard = {sid for sid, _, _ in sections(load_product(root))}
    assert {"changes", "joints", "signoffs"} <= standard


def test_the_kiln_derives_standard(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "kiln", tmp_path / "kiln", prebuilt=True)
    product = load_product(root)
    c = derive_ceremony(product)
    assert c.level == "standard"
    assert any(r.startswith("it runs on mains") for r in c.reasons)
    out = n2f("check", "--json", cwd=root)
    data = json.loads(out.stdout)
    assert data["ceremony"] == "standard" and data["ceremony_reasons"] == list(c.reasons)


# ---- n2f check names the ceremony; a rise is said once ----------------------------------------


def test_lite_product_that_gains_mains_is_told_once(tmp_path: Path) -> None:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "p", prebuilt=True)
    first = json.loads(n2f("check", "--json", cwd=root).stdout)
    assert first["ceremony"] == "lite" and first["ceremony_reasons"] == []
    assert "ceremony_raised" not in first
    assert json.loads((root / "build" / ".n2f" / "ceremony.json").read_text())["level"] == "lite"

    # the owner adds a hazard: a requirement that names mains
    _add_requirement(root, safety=True, tags=["hazard:mains"])
    shown = n2f("check", cwd=root).stdout
    assert "Ceremony: standard" in shown and "now standard" in shown
    assert "tolerance class" not in shown or "custom part" in shown  # what it now requires
    # the first run recorded the new level, so the second says nothing of a rise
    again = json.loads(n2f("check", "--json", cwd=root).stdout)
    assert again["ceremony"] == "standard" and "ceremony_raised" not in again


def test_note_level_reports_a_rise_only_from_lite(tmp_path: Path) -> None:
    root = _bracket(tmp_path)
    product = load_product(root)
    assert note_level(product) is None  # no record yet: nothing to compare
    _add_requirement(root, safety=True, tags=["hazard:stored-energy"])
    rose = note_level(load_product(root))
    assert rose is not None and rose["from"] == "lite" and rose["to"] == "standard"
    assert note_level(load_product(root)) is None  # said once


# ---- a mains tag with no supply modelled is said (S-241) ------------------------------------


def test_a_mains_requirement_with_no_supply_is_said(tmp_path: Path) -> None:
    from napkin2factory.core.ceremony import unmodelled_hazard_note

    root = _bracket(tmp_path)
    assert unmodelled_hazard_note(load_product(root)) is None
    _add_requirement(root, safety=True, tags=["hazard:mains"])
    note = unmodelled_hazard_note(load_product(root))
    assert note is not None and "models no supply" in note and "scope" in note
    # a tag whose hazard has no model domain behind it is not this line's business
    root2 = _bracket(tmp_path / "other")
    _add_requirement(root2, safety=True, tags=["hazard:high-temperature"])
    assert unmodelled_hazard_note(load_product(root2)) is None


def test_scoping_the_wiring_for_later_silences_the_mains_line(tmp_path: Path) -> None:
    from napkin2factory.core.ceremony import unmodelled_hazard_note

    root = _bracket(tmp_path)
    _add_requirement(root, safety=True, tags=["hazard:mains"])
    _edit(root / "n2f.yaml", lambda d: d.update(scope={"electrical": {"state": "later"}}))
    assert unmodelled_hazard_note(load_product(root)) is None


def test_finish_missing_is_a_lint_error(tmp_path: Path) -> None:
    root = _bracket(tmp_path)
    _edit(root / "model" / "parts" / "l-bracket.yaml", lambda d: d.pop("finish"))
    assert [p.rule for p in lint(load_product(root)).errors] == ["L8-custom-finish"]
