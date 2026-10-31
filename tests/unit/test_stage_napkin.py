"""M1 (v0.2): the optional Napkin gate (N11) — hidden without concepts, first when present."""

from __future__ import annotations

import inspect
from pathlib import Path

from napkin2factory.core import concepts as cm
from napkin2factory.core.checks.stage import STAGES, compute_stage, napkin_gate
from napkin2factory.core.loader import load_product
from napkin2factory.core.model.concepts import Screening
from napkin2factory.core.vcs import Vcs

V01_GATES = ["intake", "design", "verify", "released"]


def _names(root: Path, **kw: bool) -> list[str]:
    return [g.name for g in compute_stage(load_product(root), **kw).gates]


def test_without_concepts_the_gates_are_the_v01_gates(bracket: Path) -> None:
    assert list(STAGES) == V01_GATES
    product = load_product(bracket)
    rep = compute_stage(product)
    assert [g.name for g in rep.gates] == V01_GATES
    assert set(rep.to_dict()) == {"stage", "gates", "next_step"}
    assert rep.to_dict() == compute_stage(product, napkin=False).to_dict()
    assert napkin_gate(bracket) is None
    # an empty concepts/ folder is still "no concepts"
    (bracket / "concepts").mkdir()
    assert compute_stage(load_product(bracket)).to_dict() == rep.to_dict()


def test_exploring_cards_put_napkin_first(bracket: Path) -> None:
    before = compute_stage(load_product(bracket)).to_dict()
    cm.new_card(bracket, "Squared shell")
    cm.new_card(bracket, "Round shell")
    Vcs(bracket).snapshot("Two concepts")  # cards are tracked files like any other
    rep = compute_stage(load_product(bracket))
    assert [g.name for g in rep.gates] == ["napkin", *V01_GATES]
    gate = rep.gates[0]
    assert rep.stage == "napkin" and not gate.ok
    assert gate.blockers == [
        "2 concepts exploring, none chosen yet — `n2f concept build --all` first"
    ]
    assert "`n2f concept build --all`" in rep.next_step
    assert gate.detail == {
        "cards": 2,
        "exploring": 2,
        "rejected": 0,
        "promoted": None,
        "unreadable": 0,
    }
    # the later gates are computed exactly as without concepts
    assert [g.__dict__ for g in rep.gates[1:]] == before["gates"]
    # build outputs ask for the stage without the Napkin gate (N1)
    assert compute_stage(load_product(bracket), napkin=False).to_dict() == before


def test_screened_cards_point_to_the_board(bracket: Path) -> None:
    cm.new_card(bracket, "Squared shell")
    card = cm.load_card(bracket, "C-001").model_copy(
        update={"screening": Screening(verdict="green")}
    )
    cm.write_card(bracket, card)
    rep = compute_stage(load_product(bracket))
    assert rep.next_step == (
        "1 concept exploring, none chosen yet — `n2f concept board` to compare them, "
        "then `n2f concept promote C-00x`"
    )


def test_a_promoted_card_completes_napkin(bracket: Path) -> None:
    without = compute_stage(load_product(bracket))
    cm.new_card(bracket, "Squared shell")
    cm.new_card(bracket, "Round shell")
    cm.update_card_status(bracket, "C-001", "promoted", {"dec": "DEC-009", "at": "now"})
    cm.update_card_status(bracket, "C-002", "rejected", {"reason": "round", "at": "now"})
    rep = compute_stage(load_product(bracket))
    assert rep.gates[0].name == "napkin" and rep.gates[0].ok
    assert rep.gates[0].detail["promoted"] == "C-001"
    assert rep.stage == without.stage != "napkin"
    assert rep.next_step == without.next_step


def test_all_rejected_and_unreadable_cards(bracket: Path) -> None:
    cm.new_card(bracket, "Squared shell")
    cm.update_card_status(bracket, "C-001", "rejected", {"reason": "no", "at": "now"})
    (bracket / "concepts" / "C-002.yaml").write_text("id: C-002\nstatus: maybe\n")
    gate = compute_stage(load_product(bracket)).gates[0]
    assert gate.name == "napkin" and not gate.ok
    assert gate.blockers[0].startswith("every concept so far is rejected")
    assert gate.blockers[1] == "C-002.yaml cannot be read — `n2f concept lint` says why"
    assert gate.detail["unreadable"] == 1


def test_the_report_never_shows_the_napkin_gate() -> None:
    from napkin2factory.report import builder

    assert "compute_stage(product, build_dir, napkin=False)" in inspect.getsource(builder)
