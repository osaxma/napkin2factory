"""M1 (v0.2): concept card schema, loader, writer and lint rules C1–C6 (NAPKIN_STAGE §3)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from napkin2factory.core import concepts as cm
from napkin2factory.core.errors import ModelError, N2FError
from napkin2factory.core.model import ConceptCard, MassingCall, StyleFile
from napkin2factory.core.model.concepts import Screening
from napkin2factory.core.units import parse_quantity
from tests.conftest import FIXTURES

CONCEPTS = FIXTURES / "concepts"
SECTION3 = CONCEPTS / "valid" / "concepts" / "C-003.yaml"


def _copy(name: str, tmp_path: Path) -> Path:
    dst = tmp_path / name
    shutil.copytree(CONCEPTS / name, dst)
    return dst


def _card(**over: object) -> dict[str, object]:
    return {"id": "C-001", "title": "t", **over}


# --- schema -------------------------------------------------------------------------------


def test_section3_example_validates_and_round_trips() -> None:
    card = ConceptCard.model_validate(yaml.safe_load(SECTION3.read_text()))
    assert card.id == "C-003" and card.status == "exploring" and card.based_on == "C-001"
    assert card.envelope["chamber"] == [parse_quantity("200 mm")] * 3
    assert card.envelope["insulation"] == parse_quantity("170 mm")
    assert card.site["alcove_width"] == parse_quantity("800 mm")
    assert card.site["circuit"] == "240V-13A" and card.site["region"] == "SA"
    assert [m.kit for m in card.massing] == ["enclosure", "block", "frame"]
    assert card.massing[0].as_ == "body" and card.massing[1].at is not None
    assert card.screening is None and card.decision is None and card.verdict is None
    dumped = card.model_dump(mode="json", by_alias=True)
    assert dumped["massing"][0]["as"] == "body"
    assert dumped["envelope"]["chamber"] == ["200 mm", "200 mm", "200 mm"]
    assert ConceptCard.model_validate(dumped) == card


@pytest.mark.parametrize(
    "data, fragment",
    [
        (_card(id="C-1"), r"does not match C-\d{3}"),
        (_card(status="maybe"), "'exploring', 'rejected' or 'promoted'"),
        (_card(colour="red"), "Extra inputs are not permitted"),
        (_card(envelope={"insulation": "lots mm"}), "is not a quantity"),
        (_card(massing=[{"as": "body", "args": {}}]), "massing.0.kit"),
        (_card(based_on="nine"), r"does not match C-\d{3}"),
    ],
)
def test_invalid_cards_fail_readably(data: dict[str, object], fragment: str) -> None:
    with pytest.raises(ValidationError) as exc:
        ConceptCard.model_validate(data)
    text = str(exc.value)
    assert fragment in text, text


def test_massing_call_accepts_alias_and_field_name() -> None:
    assert MassingCall.model_validate({"kit": "plate", "as": "a"}).as_ == "a"
    assert MassingCall.model_validate({"kit": "plate", "as_": "a"}).as_ == "a"


def test_site_values_keep_words_and_flags() -> None:
    card = ConceptCard.model_validate(_card(site={"outdoor": True, "floor_load": 200}))
    assert card.site["outdoor"] is True and card.site["floor_load"].magnitude == 200
    with pytest.raises(ValidationError, match="expected a quantity"):
        ConceptCard.model_validate(_card(site={"region": ["SA"]}))


def test_verdict_reads_screening() -> None:
    card = ConceptCard.model_validate(_card(screening={"verdict": "red"}))
    assert card.verdict == "red"
    assert ConceptCard.model_validate(_card(screening={"rules": []})).verdict is None


def test_style_file_defaults() -> None:
    s = StyleFile()
    assert s.preset == "industrial" and s.palette == {} and s.finish == {}
    assert s.radius_scale == 1.0 and s.fastener_visibility == "visible"
    assert s.reveal == parse_quantity("2 mm")
    assert s.model_dump(mode="json")["reveal"] == "2 mm"
    with pytest.raises(ValidationError):
        StyleFile.model_validate({"preset": "baroque"})
    with pytest.raises(ValidationError):
        StyleFile.model_validate({"radius_scale": 0})


# --- loader -------------------------------------------------------------------------------


def test_next_concept_id(tmp_path: Path) -> None:
    assert cm.next_concept_id(tmp_path) == "C-001"
    (tmp_path / "concepts").mkdir()
    for name in ("C-001", "C-004", "notes"):
        (tmp_path / "concepts" / f"{name}.yaml").write_text("id: x\n")
    assert cm.next_concept_id(tmp_path) == "C-005"
    (tmp_path / "concepts" / "C-999.yaml").write_text("id: x\n")
    with pytest.raises(N2FError, match="C-999"):
        cm.next_concept_id(tmp_path)


def test_normalize_concept_id() -> None:
    assert cm.normalize_concept_id("c-2") == "C-002"
    assert cm.normalize_concept_id("12") == "C-012"
    assert cm.normalize_concept_id("C-003") == "C-003"
    assert cm.normalize_concept_id("door") == "door"


def test_load_concepts_sorts_and_collects_errors(tmp_path: Path) -> None:
    d = tmp_path / "concepts"
    d.mkdir()
    (d / "C-002.yaml").write_text("id: C-002\ntitle: b\n")
    (d / "C-001.yaml").write_text("id: C-001\ntitle: a\n")
    (d / "C-003.yaml").write_text("id: C-003\ntitle: c\nstatus: maybe\n")
    (d / "C-004.yaml").write_text("id: C-004\ntitle: [unclosed\n")
    (d / "C-005.yaml").write_text("- just\n- a list\n")
    problems = cm.Problems()
    cards = cm.load_concepts(tmp_path, problems)
    assert list(cards) == ["C-001", "C-002"]
    by_file = {Path(p.file).name: p for p in problems.errors}
    assert set(by_file) == {"C-003.yaml", "C-004.yaml", "C-005.yaml"}
    assert by_file["C-003.yaml"].subject == "C-003" and "status" in by_file["C-003.yaml"].message
    assert "exploring, rejected, promoted" in by_file["C-003.yaml"].hint
    assert "not readable YAML" in by_file["C-004.yaml"].message
    assert all(p.rule == "C0-schema" for p in problems.errors)
    with pytest.raises(ModelError):
        cm.load_concepts(tmp_path)


def test_load_concepts_without_folder_is_empty(tmp_path: Path) -> None:
    assert cm.load_concepts(tmp_path) == {} and not cm.has_concepts(tmp_path)


def test_load_card_missing_is_actionable(tmp_path: Path) -> None:
    with pytest.raises(N2FError, match="no concepts yet"):
        cm.load_card(tmp_path, "C-001")
    root = _copy("valid", tmp_path)
    with pytest.raises(N2FError, match="known: C-001, C-003"):
        cm.load_card(root, "C-002")
    assert cm.load_card(root, "3").id == "C-003"


def test_new_card_skeleton_and_from(tmp_path: Path) -> None:
    root = _copy("valid", tmp_path)
    card = cm.new_card(root, "Taller", based_on="C-003")
    assert card.id == "C-004" and card.based_on == "C-003" and card.status == "exploring"
    text = cm.card_path(root, "C-004").read_text()
    for section in ("refs:", "layout:", "envelope:", "site:", "style:", "massing:", "notes:"):
        assert f"\n{section}" in text, section
    assert "screening: null" in text and "decision: null" in text
    assert "# the card this one started from" in text
    src = cm.load_card(root, "C-003")
    assert card.layout == src.layout and card.envelope == src.envelope
    assert card.massing == src.massing and card.notes == src.notes and card.refs == []
    assert "  - {kit: enclosure, as: body, args: {length: 540 mm" in text
    plain = cm.new_card(root, "  Blank  ")
    assert plain.title == "Blank" and plain.based_on is None and plain.massing == []
    with pytest.raises(N2FError, match="short title"):
        cm.new_card(root, " ")


def test_new_card_creates_the_folder(tmp_path: Path) -> None:
    card = cm.new_card(tmp_path, "First")
    assert card.id == "C-001" and cm.card_path(tmp_path, "C-001").is_file()
    assert cm.lint_concepts(tmp_path).items == []


def test_update_status_keeps_comments_and_order(tmp_path: Path) -> None:
    root = _copy("valid", tmp_path)
    path = cm.card_path(root, "C-003")
    # the §3 example's ``{...}`` placeholders are not real content; give them real values
    path.write_text(path.read_text().replace("{...}", "{width: 10 mm}"))
    before = path.read_text().splitlines()
    card = cm.update_card_status(root, "C-003", "rejected", {"reason": "too big", "at": "x"})
    assert card.status == "rejected" and card.decision is not None
    assert card.decision.model_dump(mode="json") == {"reason": "too big", "at": "x"}
    after = path.read_text().splitlines()
    changed = [(a, b) for a, b in zip(before, after, strict=True) if a != b]
    assert len(changed) == 2, changed
    assert changed[0][1].startswith("status: rejected") and "# exploring |" in changed[0][1]
    assert changed[1][1].startswith("decision: {reason: too big")
    with pytest.raises(ValidationError):
        cm.update_card_status(root, "C-003", "maybe")
    assert cm.load_card(root, "C-003").status == "rejected"


def test_write_card_new_and_in_place(tmp_path: Path) -> None:
    card = ConceptCard.model_validate(_card(envelope={"w": "1 m"}))
    path = cm.write_card(tmp_path, card)
    assert cm.load_card(tmp_path, "C-001") == card and "# Concept card C-001" in path.read_text()
    path.write_text(path.read_text().replace("title: t", "title: t  # mine"))
    cm.write_card(tmp_path, card.model_copy(update={"screening": Screening(verdict="green")}))
    text = path.read_text()
    assert "title: t  # mine" in text and yaml.safe_load(text)["screening"] == {"verdict": "green"}
    assert cm.load_card(tmp_path, "C-001").verdict == "green"
    # a minimal hand-written card gains no empty sections
    path.write_text("id: C-001\ntitle: t\n")
    cm.write_card(tmp_path, ConceptCard.model_validate(_card(status="rejected")))
    assert path.read_text() == "id: C-001\ntitle: t\nstatus: rejected\n"


# --- lint ---------------------------------------------------------------------------------


def test_valid_fixture_lints_clean(tmp_path: Path) -> None:
    assert cm.lint_concepts(_copy("valid", tmp_path)).items == []


@pytest.mark.parametrize(
    "rule, fragment",
    [
        ("C1-id-matches-file", "does not match the file name C-001.yaml"),
        ("C2-refs-exist", "'refs/missing.jpg' not found"),
        ("C3-kit-known", "'blob' is not a kit generator"),
        ("C4-based-on-exists", "based_on C-009: there is no such card"),
        ("C6-one-promoted", "more than one card is promoted (C-001, C-002)"),
        ("C7-promoted-has-decision", "C-001 says promoted but no decision records it"),
    ],
)
def test_each_rule_has_a_failing_fixture(rule: str, fragment: str) -> None:
    problems = cm.lint_concepts(CONCEPTS / rule)
    assert problems.errors, rule
    assert all(p.rule == rule for p in problems.items), problems.items
    assert any(fragment in p.message for p in problems.errors), problems.items
    assert all(p.hint and p.file.endswith(".yaml") for p in problems.items)


def test_site_keys_rule_only_warns() -> None:
    problems = cm.lint_concepts(CONCEPTS / "C5-site-keys")
    assert not problems.errors
    (warn,) = problems.warnings
    assert warn.rule == "C5-site-keys" and "'ceiling_colour'" in warn.message
    assert "alcove_width" in warn.hint


def test_lint_flags_odd_file_names_refs_outside_and_self_lineage(tmp_path: Path) -> None:
    d = tmp_path / "concepts"
    d.mkdir()
    (tmp_path / "secret.jpg").write_text("x")
    (d / "sketch.yaml").write_text("id: C-001\ntitle: misnamed\n")
    (d / "C-002.yaml").write_text("id: C-002\ntitle: t\nbased_on: C-002\nrefs: [../secret.jpg]\n")
    problems = cm.lint_concepts(tmp_path)
    messages = [(p.rule, p.message) for p in problems.errors]
    assert ("C1-id-matches-file", "the file name sketch.yaml is not a concept id") in messages
    assert any(r == "C2-refs-exist" and "outside concepts/" in m for r, m in messages)
    assert ("C4-based-on-exists", "based_on names the card itself") in messages


def test_kit_list_matches_the_kit_and_loads_no_cad_kernel() -> None:
    from napkin2factory.geometry.kit import GENERATORS

    assert cm.kit_generators() == GENERATORS
    code = (
        "import sys; from pathlib import Path; from napkin2factory.core import concepts; "
        f"concepts.lint_concepts(Path({str(CONCEPTS / 'C3-kit-known')!r})); "
        "assert 'build123d' not in sys.modules and 'OCP' not in sys.modules"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_promoted_needs_a_decision_on_record_and_rejected_a_reason(tmp_path: Path) -> None:
    """Review gate A, B2: C7 reads ``model/decisions.yaml`` for the promoted card's id."""
    d = tmp_path / "concepts"
    d.mkdir()
    (tmp_path / "model").mkdir()
    (tmp_path / "model" / "decisions.yaml").write_text("decisions:\n  - {id: DEC-002}\n")
    (d / "C-001.yaml").write_text(
        "id: C-001\ntitle: a\nstatus: promoted\nscreening: {verdict: green}\n"
        "decision: {dec: DEC-009}\n"
    )
    (d / "C-002.yaml").write_text("id: C-002\ntitle: b\nstatus: rejected\n")
    (d / "C-003.yaml").write_text("id: C-003\ntitle: c\nstatus: exploring\n")
    messages = {p.subject: p.message for p in cm.lint_concepts(tmp_path).errors}
    assert messages == {
        "C-001": "C-001 says promoted by DEC-009, but model/decisions.yaml has no DEC-009",
        "C-002": "C-002 is rejected but says nothing about why",
    }
    # unscreened, even with a real decision
    (d / "C-001.yaml").write_text(
        "id: C-001\ntitle: a\nstatus: promoted\ndecision: {dec: DEC-002}\n"
    )
    (d / "C-002.yaml").write_text("id: C-002\ntitle: b\nstatus: rejected\ndecision: {reason: no}\n")
    (err,) = cm.lint_concepts(tmp_path).errors
    assert err.message == "C-001 says promoted but was never built (no screening)"
