"""M4 (v0.2): ``n2f concept promote`` — gates, seeding, requirements, style, decision (N8).

The product is the bracket example with the M2 cards (C-001 red, C-002 green) and the M4
cards (C-003 green with a style and a supply circuit, C-004 red on a 300 mm alcove), built
once per module without pictures and copied per test. Goldens under
``tests/fixtures/concepts/promote-golden/`` are the four model files after promoting C-003
on 2026-10-31 12:00; regenerate with ``N2F_PROMOTE_GOLDEN=1`` after an intended change and
review the diff.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from napkin2factory.concepts.promote import PromotionResult, promote
from napkin2factory.core import concepts as cm
from napkin2factory.core.checks.evaluators import NO_APPLICABLE_PART, EvalContext, rule_verdict
from napkin2factory.core.checks.results import CheckResult
from napkin2factory.core.errors import GateBlocked, N2FError
from napkin2factory.core.loader import load_product
from napkin2factory.core.model import Requirement
from napkin2factory.core.vcs import Vcs
from tests.conftest import EXAMPLES, FIXTURES, copy_product, n2f

NOW = dt.datetime(2026, 10, 31, 12, 0, 0)
GOLDEN = FIXTURES / "concepts" / "promote-golden"
CARD_SETS = (
    FIXTURES / "concepts" / "product-green-red" / "concepts",
    FIXTURES / "concepts" / "promote-cards" / "concepts",
)
MODEL_FILES = {
    "parameters.yaml": "model/parameters.yaml",
    "requirements.yaml": "model/requirements.yaml",
    "decisions.yaml": "model/decisions.yaml",
    "style.yaml": "style.yaml",
}


#: The heated-box screens the fixture cards are screened with: the kiln's own (F8, F10).
HEATED_SCREENS = EXAMPLES / "kiln" / "model" / "screens"


def overlay_cards(root: Path) -> None:
    """Copy both fixture card sets into ``root/concepts`` and the kiln's screens beside."""
    for cards in CARD_SETS:
        shutil.copytree(cards, root / "concepts", dirs_exist_ok=True)
    shutil.copytree(HEATED_SCREENS, root / "model" / "screens", dirs_exist_ok=True)


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    from napkin2factory.concepts.build import build_concepts

    root = copy_product(EXAMPLES / "bracket", tmp_path_factory.mktemp("built") / "bracket")
    overlay_cards(root)
    cards = list(cm.load_concepts(root).values())
    done, errors = build_concepts(root, cards, render=False)
    assert errors == [] and len(done) == 4
    Vcs(root).snapshot("Concepts built")
    return root


@pytest.fixture
def product(built: Path, tmp_path: Path) -> Path:
    dest = tmp_path / "bracket"
    shutil.copytree(built, dest, ignore=shutil.ignore_patterns("build"))
    return dest


def _digest(root: Path) -> str:
    h = hashlib.sha256()
    for folder in ("model", "concepts"):
        for p in sorted((root / folder).rglob("*")):
            if p.is_file():
                h.update(p.relative_to(root).as_posix().encode())
                h.update(p.read_bytes())
    style = root / "style.yaml"
    h.update(style.read_bytes() if style.is_file() else b"<none>")
    return h.hexdigest()


def _card(root: Path, cid: str) -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load((root / "concepts" / f"{cid}.yaml").read_text())
    return data


def _decisions(root: Path) -> list[dict[str, Any]]:
    data: dict[str, Any] = yaml.safe_load((root / "model" / "decisions.yaml").read_text())
    return list(data["decisions"])


# --- the green path and its golden diff -----------------------------------------------


def test_promote_green_card_writes_the_expected_model(product: Path) -> None:
    root = product
    head = Vcs(root).head()
    result = promote(root, "C-003", now=NOW)
    assert isinstance(result, PromotionResult)
    for name, rel in MODEL_FILES.items():
        text = (root / rel).read_text(encoding="utf-8")
        golden = GOLDEN / name
        if os.environ.get("N2F_PROMOTE_GOLDEN") == "1":
            golden.parent.mkdir(parents=True, exist_ok=True)
            golden.write_text(text, encoding="utf-8")
        assert text == golden.read_text(encoding="utf-8"), f"{rel} differs from {golden}"
    assert result.summary() == (
        "C-003 is now the design direction (DEC-002). Seeded 7 parameters, 6 requirements "
        "(3 about form, 2 about the alcove, 1 about the supply), wrote style.yaml. C-001, "
        "C-002 and C-004 are kept as alternatives. Next: `n2f build && n2f check`."
    )
    # the cards flipped; the chosen one names the decision
    chosen = _card(root, "C-003")
    assert chosen["status"] == "promoted" and chosen["decision"]["dec"] == "DEC-002"
    for cid in ("C-001", "C-002", "C-004"):
        card = _card(root, cid)
        assert card["status"] == "rejected"
        assert card["decision"]["reason"] == "set aside when C-003 was chosen (DEC-002)"
    # a snapshot, and nothing left unsaved
    vcs = Vcs(root)
    assert vcs.head() != head and result.snapshot == vcs.head() and vcs.is_clean()
    assert "Promote C-003: Appliance-style compact kiln" in vcs._git("log", "-1").stdout
    # the model loads, every new requirement validates and the ids are all in the JSON
    model = load_product(root)
    assert [f"req://REQ-00{i}" for i in range(4, 10)] == [
        r["uri"] for r in result.to_dict()["requirements"]
    ]
    kinds = {r.id: r.verify.kind for r in model.requirements.values() if r.verify}
    assert [kinds[f"REQ-00{i}"] for i in range(4, 10)] == [
        "geometry_prop",
        "param_bound",  # the door's room beside the hinge, a parameter (B-0023)
        "param_bound",
        "rule",
        "rule",
        "rule",
    ]
    dec = model.decisions["DEC-002"]
    assert dec.verify is True and dec.made_by == "agent"
    assert set(dec.sources) == {f"concepts/C-00{i}.yaml" for i in range(1, 5)}
    assert {str(u) for u in dec.links} >= {"req://REQ-004", "param://element-power"}


def test_promote_records_a_human_choice(product: Path) -> None:
    result = promote(product, "3", by="Osama", now=NOW)
    dec = _decisions(product)[-1]
    assert dec["made_by"] == "human" and "by Osama" in dec["context"]
    assert result.to_dict()["dec"] == "DEC-002"


def test_rationale_keeps_every_label(product: Path) -> None:
    promote(product, "C-003", now=NOW)
    dec = _decisions(product)[-1]
    card = cm.load_card(product, "C-003")
    assert card.screening is not None
    for name, lv in {**card.screening.computed, **card.screening.estimates}.items():
        quoted = f"{name.replace('_', ' ')} {lv.value} ({lv.label})"
        if name in ("width", "total_mass", "heat_up_time", "cost_low"):
            assert quoted in dec["rationale"]
    assert "(computed)" in dec["rationale"] and "(estimate)" in dec["rationale"]


# --- gates ---------------------------------------------------------------------------------


def test_red_card_is_refused_and_nothing_is_written(product: Path) -> None:
    before = _digest(product)
    with pytest.raises(GateBlocked) as exc:
        promote(product, "C-001", now=NOW)
    text = str(exc.value)
    assert text.startswith("C-001 — this direction has problems: it needs 1245 mm of width")
    assert 'Promote anyway with --override --reason "…"' in text
    assert "the reason is recorded as a decision" in text
    assert exc.value.exit_code == 3
    with pytest.raises(GateBlocked, match="--override needs --reason"):
        promote(product, "C-001", override=True, now=NOW)
    assert _digest(product) == before


def test_red_card_with_override_records_why(product: Path) -> None:
    result = promote(
        product, "C-001", override=True, reason="the owner accepts a wider alcove", now=NOW
    )
    dec = _decisions(product)[-1]
    assert dec["title"] == "Design direction: The v0.1 kiln as built, despite screening"
    assert dec["verify"] is True
    assert (
        "Promoted despite screening, which says: fits-site-width: it needs 1245 mm"
        in (dec["context"])
    )
    assert "blank-vs-stock-sheet:" in dec["context"]
    assert "Reason given for --override: the owner accepts a wider alcove." in dec["context"]
    names = {p.name for p in result.params}
    assert {"chamber-width", "brick-thickness", "fiber-clearance", "element-power"} <= names
    # an unstyled card still gets the one form requirement that applies, and says so
    assert [r.about for r in result.requirements].count("form") == 1
    assert any(n.startswith("1 form requirement applies") for n in result.notes)
    assert not any("corner_radius" in n or "fastener_visibility" in n for n in result.notes)
    load_product(product)


def test_unbuilt_card_and_second_promotion_are_refused(product: Path) -> None:
    fresh = cm.new_card(product, "Not built")
    with pytest.raises(GateBlocked, match=f"build it first: `n2f concept build {fresh.id}`"):
        promote(product, fresh.id, now=NOW)
    promote(product, "C-003", now=NOW)
    before = _digest(product)
    with pytest.raises(GateBlocked, match="C-003 is already the chosen direction"):
        promote(product, "C-002", now=NOW)
    with pytest.raises(GateBlocked, match="C-003 is already the chosen direction"):
        promote(product, "C-003", now=NOW)
    assert _digest(product) == before


def test_parameter_collision_refuses_then_reconciles(product: Path) -> None:
    params = product / "model" / "parameters.yaml"
    original = params.read_text()
    params.write_text(original + "  chamber-width: {value: 999, unit: mm}\n")
    before = _digest(product)
    with pytest.raises(GateBlocked) as exc:
        promote(product, "C-003", now=NOW)
    assert "chamber-width is 999 mm in the model but 150 mm on C-003" in str(exc.value)
    assert "Nothing was written" in str(exc.value)
    assert _digest(product) == before
    # an equal value (in another unit) is reconciled, not duplicated
    params.write_text(original + "  chamber-width: {value: 15, unit: cm}\n")
    result = promote(product, "C-003", now=NOW)
    status = {p.name: p.status for p in result.params}
    assert status["chamber-width"] == "declared" and status["chamber-depth"] == "new"
    assert "Seeded 6 parameters (1 already declared)" in result.summary()
    assert params.read_text().count("chamber-width:") == 1


def test_parameter_collision_with_override_overwrites_and_logs(product: Path) -> None:
    params = product / "model" / "parameters.yaml"
    params.write_text(params.read_text() + "  chamber-width: {value: 999, unit: mm}\n")
    result = promote(product, "C-003", override=True, reason="the card wins", now=NOW)
    assert "  chamber-width: {value: 150, unit: mm}\n" in params.read_text()
    assert {p.name: p.was for p in result.params}["chamber-width"] == "999 mm"
    dec = _decisions(product)[-1]
    assert (
        "Overwrote existing parameters: chamber-width (was 999 mm, now 150 mm)" in (dec["context"])
    )
    assert "(1 overwritten)" in result.summary()


def test_product_without_an_assembly_allocates_unallocated(product: Path) -> None:
    (product / "model" / "assemblies" / "bracket.yaml").unlink()
    result = promote(product, "C-003", now=NOW)
    model = load_product(product)
    alcove = model.requirements["REQ-004"]
    assert alcove.allocation == "unallocated"
    assert alcove.verify is not None and alcove.verify.kind == "manual"
    assert model.requirements["REQ-007"].allocation == "unallocated"  # a form row
    assert any("no assembly yet" in n for n in result.notes)


def test_existing_style_moves_to_the_cards_preset(product: Path) -> None:
    from napkin2factory.cli.init import write_style

    path = write_style(product, "industrial")
    text = path.read_text().replace("trim: '#8c9196'", "trim: '#123456'")
    path.write_text(text)
    result = promote(product, "C-003", now=NOW)
    style = yaml.safe_load(path.read_text())
    assert style["preset"] == "appliance" and style["palette"]["body"] == "#efede8"
    assert style["palette"]["trim"] == "#123456"  # a hand edit is kept, and said so
    assert style["corner_radius"] == "8 mm" and style["fastener_visibility"] == "hidden-front"
    assert style["layout"] == {"load": "front", "door": "hinged-right", "controls": "side-right"}
    assert path.read_text().startswith("# style.yaml: how the product looks")
    assert any("kept your own palette.trim" in n for n in result.notes)
    assert "updated style.yaml" in result.summary()


def test_invalid_model_is_refused_before_writing(product: Path) -> None:
    reqs = product / "model" / "requirements.yaml"
    reqs.write_text(reqs.read_text().replace("category: mass", "category: weightiness"))
    before = _digest(product)
    with pytest.raises(N2FError, match="the product model has problems"):
        promote(product, "C-003", now=NOW)
    assert _digest(product) == before


# --- the `rule` verify kind -----------------------------------------------------------------


def test_rule_verify_kind_schema() -> None:
    from pydantic import ValidationError

    base = {"id": "REQ-009", "title": "t", "statement": "s", "category": "usability"}
    ok = Requirement.model_validate(
        {**base, "verify": {"kind": "rule", "target": "rule://form-v0/form-corner-radius"}}
    )
    assert ok.verify is not None and ok.verify.kind == "rule"
    with pytest.raises(ValidationError, match="targets rule://"):
        Requirement.model_validate({**base, "verify": {"kind": "rule", "target": "part://x"}})
    with pytest.raises(ValidationError, match="takes a target only"):
        Requirement.model_validate(
            {
                **base,
                "verify": {
                    "kind": "rule",
                    "target": "rule://form-v0/form-corner-radius",
                    "op": "<",
                    "value": "1 mm",
                },
            }
        )


def _row(rule: str, part: str, status: str, message: str = "m") -> CheckResult:
    return CheckResult(
        id=f"rule://form-v0/{rule}@{part}",
        subject=f"part://{part}",
        status=status,
        message=message,
        kind="rule",
    )


def test_rule_verdict_reads_the_rows_of_the_run() -> None:
    product = load_product(EXAMPLES / "bracket")
    ctx = EvalContext(product, EXAMPLES / "bracket" / "build")
    target = "rule://form-v0/form-corner-radius"
    ctx.rule_results = [
        _row("form-corner-radius", "shell", "pass"),
        _row("form-corner-radius", "door", "fail", "bend B1 is 4 mm"),
        _row("form-fasteners-hidden-front", "door", "fail"),
    ]
    status, message, subjects = rule_verdict(ctx, target)
    assert (status, message) == ("fail", "door: bend B1 is 4 mm")
    assert subjects == ["part://door", "part://shell"]
    ctx.rule_results = [
        _row("form-corner-radius", "shell", "pass"),
        _row("form-corner-radius", "door", "warn", "close"),
    ]
    assert rule_verdict(ctx, target)[0] == "warn"
    ctx.rule_results = [_row("form-corner-radius", "shell", "pass")]
    assert rule_verdict(ctx, target)[:2] == ("pass", "1 part(s) meet it (shell)")
    ctx.rule_results = [_row("form-corner-radius", "shell", "skip", "not built yet")]
    assert rule_verdict(ctx, target)[:2] == ("skip", f"{NO_APPLICABLE_PART} (shell: not built yet)")
    ctx.rule_results = []
    assert rule_verdict(ctx, target)[:2] == ("skip", NO_APPLICABLE_PART)
    status, message, _ = rule_verdict(ctx, "rule://form-v0/no-such-rule")
    assert status == "fail" and "no rule 'no-such-rule'" in message


# --- review gate A, B1: one supply margin for the napkin and the factory ---------------------


def _supply_verdict(root: Path, card_id: str, override: bool) -> str:
    """Promote ``card_id`` and evaluate its supply requirement through the real evaluator."""
    from napkin2factory.core.checks.evaluators import evaluate_requirement

    result = promote(
        root, card_id, override=override, reason="gate A" if override else None, now=NOW
    )
    supply = [r for r in result.requirements if r.about == "supply"]
    assert len(supply) == 1, result.notes
    model = load_product(root)
    req = model.requirements[supply[0].id]
    status: str = evaluate_requirement(EvalContext(model, root / "build"), req).status
    return status


def test_green_circuit_row_implies_passing_supply_requirement(built: Path, tmp_path: Path) -> None:
    from napkin2factory.concepts.build import build_concepts

    root = tmp_path / "base"
    shutil.copytree(built, root, ignore=shutil.ignore_patterns("build"))
    # a card whose circuit row fails: C-003 at 3.5 kW on its 230V-16A circuit
    text = (root / "concepts" / "C-003.yaml").read_text()
    text = text.replace("id: C-003", "id: C-005").replace("power: 1.5 kW", "power: 3.5 kW")
    (root / "concepts" / "C-005.yaml").write_text(text)
    done, errors = build_concepts(root, [cm.load_card(root, "C-005")], render=False)
    assert errors == [] and len(done) == 1
    Vcs(root).snapshot("C-005 built")
    seen: dict[str, str] = {}
    for card in cm.load_concepts(root).values():
        if card.site.get("circuit") is None or card.envelope.get("power") is None:
            continue
        assert card.screening is not None
        row = next(r for r in card.screening.rules if r.id == "circuit-available")
        dest = tmp_path / card.id
        shutil.copytree(root, dest)
        verdict = _supply_verdict(dest, card.id, override=card.verdict == "red")
        assert verdict == ("pass" if row.status == "pass" else "fail"), (card.id, row)
        seen[card.id] = row.status
    # C-001: 2.5 kW on 240V-13A — 12.5 A with 1.2 headroom fits 13 A (it failed at 0.8 × V·I)
    assert seen == {"C-001": "pass", "C-003": "pass", "C-005": "fail"}


# --- review gate A, B2: a `promoted` typed by hand does not complete the stage ---------------


def test_hand_edited_promotion_is_a_blocker_and_can_be_undone(product: Path) -> None:
    import json

    path = product / "concepts" / "C-002.yaml"
    path.write_text(path.read_text().replace("\nstatus: exploring", "\nstatus: promoted", 1))
    # lint names it
    r = n2f("concept", "lint", "--json", cwd=product)
    assert r.returncode == 1, r.stdout + r.stderr
    rows = [p for p in json.loads(r.stdout)["problems"] if p["rule"] == "C7-promoted-has-decision"]
    assert [p["message"] for p in rows] == ["C-002 says promoted but no decision records it"]
    # the Napkin gate stays open with that blocker
    st = json.loads(n2f("status", "--json", cwd=product).stdout)
    gate = st["gates"][0]
    assert gate["name"] == "napkin" and gate["ok"] is False and st["stage"] == "napkin"
    assert gate["blockers"] == [
        "C-002 says promoted but no decision records it — `n2f concept lint`"
    ]
    # it can be set aside (it was never promoted by the tool) …
    r = n2f("concept", "reject", "C-002", "--reason", "typed by hand", cwd=product)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _card(product, "C-002")["status"] == "rejected"
    # … and another card can then be promoted, which completes the stage
    result = promote(product, "C-003", now=NOW)
    assert result.dec_id == "DEC-002"
    assert n2f("concept", "lint", cwd=product).returncode == 0
    st = json.loads(n2f("status", "--json", cwd=product).stdout)
    assert st["gates"][0]["ok"] is True and st["gates"][0]["detail"]["promoted"] == "C-003"


def test_promoting_over_a_hand_edited_card_rejects_it(product: Path) -> None:
    path = product / "concepts" / "C-002.yaml"
    path.write_text(path.read_text().replace("\nstatus: exploring", "\nstatus: promoted", 1))
    result = promote(product, "C-003", now=NOW)
    assert "C-002" in result.rejected and _card(product, "C-002")["status"] == "rejected"
    assert cm.lint_concepts(product).errors == []


# --- review gate B: the owner's words after a promotion ----------------------------------


def test_summary_when_nothing_was_seeded_says_so() -> None:
    """Gate B, B4: no "Seeded 0 parameters, 0 requirements"."""
    result = PromotionResult("C-001", "Bracket", "DEC-002", False, rejected=["C-002", "C-003"])
    assert result.summary() == (
        "C-001 is now the design direction (DEC-002). The card had no sizes or site limits, "
        "so no numbers or requirements were added; the look is recorded in style.yaml. "
        "C-002 and C-003 are kept as alternatives. Next: `n2f build && n2f check`."
    )
    one = PromotionResult("C-001", "Bracket", "DEC-002", False, rejected=["C-002"])
    assert "C-002 is kept as an alternative." in one.summary()


def test_no_form_requirement_needs_no_note() -> None:
    """Gate B, B4: the note only when exactly one form requirement applies, in words."""
    from napkin2factory.concepts.promote import form_requirements
    from napkin2factory.core.model.style import StyleFile

    card = cm.ConceptCard.model_validate({"id": "C-001", "title": "Plain"})
    notes: list[str] = []
    assert form_requirements(card, StyleFile().resolved(), None, notes) == []
    assert notes == []
    sideways = card.model_copy(update={"layout": {"controls": "side-right"}})
    assert len(form_requirements(sideways, StyleFile().resolved(), None, notes)) == 1
    assert notes == [
        "1 form requirement applies: the style chose no corner radius and fasteners visible — "
        "give the card's style a corner radius or hidden front fasteners for more"
    ]


def test_cli_promotion_prints_snapshot_saved_and_plain_refusals(product: Path) -> None:
    """Gate B, B4 (C13) and C14: the promise in the PM skill holds; no bare acronym."""
    r = n2f("concept", "promote", "C-003", cwd=product)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "\n  snapshot saved\n" in r.stdout
    r = n2f("concept", "promote", "C-002", cwd=product)
    assert r.returncode == 3
    assert (
        "changing direction after promotion is a change request: "
        "`n2f ecr new --kind design --title …`"
    ) in r.stderr
    r = n2f("concept", "new", "Taller", "--from", "C-002", cwd=product)
    assert r.returncode == 0, r.stderr
    assert (
        "C-003 is already the design direction; this card can be compared on the board, "
        "but choosing it instead is a change request."
    ) in r.stdout
