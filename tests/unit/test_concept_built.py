"""M3a seam: a card's built figures, ``Vcs.files``, the parked lint, decision links (S-263)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

from napkin2factory.core import concepts as cm
from napkin2factory.core.loader import validate
from napkin2factory.core.model import ConceptCard
from napkin2factory.core.vcs import Vcs, VcsError
from tests.conftest import EXAMPLES

BUILT: dict[str, Any] = {
    "event": "parked",
    "checkpoint": "3f2a",
    "number": 14,
    "mass": "23.1 kg",
    "cost": "180 USD",
    "at": "2026-11-06T10:12:00",
}


def _card(**over: object) -> dict[str, object]:
    return {"id": "C-001", "title": "t", **over}


def test_built_round_trips_and_is_left_out_when_none() -> None:
    card = ConceptCard.model_validate(_card(status="parked", built=BUILT))
    dumped = card.model_dump(mode="json", by_alias=True)
    assert dumped["built"]["number"] == 14 and dumped["built"]["event"] == "parked"
    assert ConceptCard.model_validate(dumped) == card
    plain = ConceptCard.model_validate(_card()).model_dump(mode="json", by_alias=True)
    assert "built" not in plain


def test_update_status_sets_and_clears_built_and_new_card_never_copies_it(tmp_path: Path) -> None:
    cm.new_card(tmp_path, "First")
    card = cm.update_card_status(
        tmp_path, "C-001", "parked", {"reason": "set aside", "at": "x"}, built=BUILT
    )
    assert card.built is not None and card.built.number == 14
    assert "\nbuilt: {event: parked" in "\n" + cm.card_path(tmp_path, "C-001").read_text()
    copy = cm.new_card(tmp_path, "Copy", based_on="C-001")
    assert copy.built is None and copy.screening is None
    card = cm.update_card_status(tmp_path, "C-001", "exploring", clear_built=True)
    assert card.built is None
    assert "\nbuilt:" not in "\n" + cm.card_path(tmp_path, "C-001").read_text()


def test_parked_card_needs_a_reason(tmp_path: Path) -> None:
    d = tmp_path / "concepts"
    d.mkdir()
    (d / "C-001.yaml").write_text("id: C-001\ntitle: t\nstatus: parked\n")
    (d / "C-002.yaml").write_text(
        "id: C-002\ntitle: t\nstatus: parked\ndecision: {reason: set aside for C-003, at: x}\n"
    )
    messages = [p.message for p in cm.lint_concepts(tmp_path).errors]
    assert messages == ["C-001 is parked and says nothing about why it was set aside"]


def test_files_lists_a_saved_state_sorted_and_relative(tmp_path: Path) -> None:
    root = tmp_path / "prod"
    root.mkdir()
    (root / ".gitignore").write_text("build/\n")
    vcs = Vcs(root)
    vcs.init()
    (root / "b").mkdir()
    (root / "b" / "z.txt").write_text("z")
    (root / "a.txt").write_text("one")
    first = vcs.snapshot("one")
    (root / "c.txt").write_text("two")
    vcs.snapshot("two")
    assert vcs.files(first) == [".gitignore", "a.txt", "b/z.txt"]
    assert vcs.files() == [".gitignore", "a.txt", "b/z.txt", "c.txt"]
    with pytest.raises(VcsError):
        vcs.files("nonesuch")


def test_a_decision_link_that_no_longer_resolves_warns(tmp_path: Path) -> None:
    root = tmp_path / "bracket"
    shutil.copytree(EXAMPLES / "bracket", root, ignore=shutil.ignore_patterns("build"))
    path = root / "model" / "decisions.yaml"
    text = path.read_text()
    assert "links: [req://REQ-002," in text
    path.write_text(
        text.replace("links: [req://REQ-002,", "links: [req://REQ-002, part://gone,", 1)
    )
    _, problems = validate(root)
    assert not [p for p in problems.errors if "part://gone" in p.message]
    (warn,) = [p for p in problems.warnings if "part://gone" in p.message]
    assert warn.rule == "uri"
    assert warn.message == "decision cites removed or unknown part://gone"
    assert warn.hint == "a decision is history; it keeps its links as written"
