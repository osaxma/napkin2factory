"""M3a: ``n2f concept fork-from-model`` — the built design becomes a card (R11)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from napkin2factory.concepts import board as board_mod
from napkin2factory.concepts import build as build_mod
from napkin2factory.concepts.fork import fork_from_model
from napkin2factory.core import checkpoints as cps
from napkin2factory.core import concepts as cm
from napkin2factory.core.errors import GateBlocked
from napkin2factory.core.vcs import Vcs
from tests.conftest import EXAMPLES, copy_product

pytestmark = pytest.mark.xdist_group("test_concept_fork")


@pytest.fixture
def table(tmp_path: Path) -> Path:
    """A fresh tracked copy of the built table (C-002 promoted)."""
    return copy_product(EXAMPLES / "table", tmp_path / "table", prebuilt=True)


def test_fork_writes_the_card_with_computed_built_figures(table: Path) -> None:
    result = fork_from_model(table)
    assert result.card_id == "C-004"
    assert result.checkpoint is not None
    card = cm.load_card(table, result.card_id)
    assert card.status == "exploring"
    assert card.based_on == "C-002"
    # every computed number is labelled computed and named after the checkpoint it was
    # measured on (the saved state just before the fork's own checkpoint, R11).
    computed = card.screening.computed
    assert set(computed) >= {"width", "depth", "height", "mass", "cost"}
    assert all(lv.label == "computed" for lv in computed.values())
    base = result.checkpoint.number - 1
    assert all(
        lv.source == f"from the built design (checkpoint #{base})" for lv in computed.values()
    )
    # the built block records the same saved state and the measured mass and cost.
    assert card.built is not None
    assert card.built.event == "forked"
    assert card.built.number == base
    assert card.built.mass is not None and card.built.cost is not None
    # the card file holds the built block; the fork is its own checkpoint (R4).
    text = (table / "concepts" / "C-004.yaml").read_text(encoding="utf-8")
    assert "built: {event: forked" in text
    log = cps.read(Vcs(table))
    assert log[0].label == f"Forked {result.card_id} from the built design"
    base_cp = next(c for c in log if c.number == base)
    assert card.built.checkpoint == base_cp.id


def test_fork_refuses_a_stale_build(table: Path) -> None:
    params = table / "model" / "parameters.yaml"
    params.write_text(
        re.sub(
            r"(table-length:\s*\{value:\s*)1600", r"\g<1>1700", params.read_text(encoding="utf-8")
        ),
        encoding="utf-8",
    )
    with pytest.raises(GateBlocked, match="out of date"):
        fork_from_model(table)


def test_board_marks_a_forked_card_apart(table: Path) -> None:
    result = fork_from_model(table)
    card = cm.load_card(table, result.card_id)
    style, _ = build_mod.product_style(table)
    data = board_mod.gather_card(table, card, style)
    assert data["origin"] == "built"
    assert data["built_line"] is None  # a forked card is not parked
    napkin = cm.load_card(table, "C-002")
    assert board_mod.gather_card(table, napkin, style)["origin"] == "napkin"


def test_concept_build_refuses_a_forked_card(table: Path) -> None:
    result = fork_from_model(table)
    card = cm.load_card(table, result.card_id)
    with pytest.raises(GateBlocked) as exc:
        build_mod.build_concept(table, card, render=False)
    assert "holds the built design's figures" in str(exc.value)
    assert f"n2f concept new --based-on {card.id}" in str(exc.value)
    # build-all skips it with that line (no CAD kernel is loaded for the refusal).
    built, errors = build_mod.build_concepts(table, [card], render=False)
    assert built == []
    assert errors[0]["id"] == card.id
    assert "holds the built design's figures" in errors[0]["error"]


def test_render_card_prints_built_and_it_reads_back() -> None:
    """B-0278: a new card file keeps its built figures; one without them reads as before."""
    from napkin2factory.core.concept_render import render_card
    from napkin2factory.core.model.concepts import ConceptCard

    built = {
        "event": "forked",
        "checkpoint": "abc123",
        "number": 4,
        "mass": "24.7 kg",
        "cost": "640 USD",
        "at": "2026-11-05T11:39:55",
    }
    data = {"id": "C-009", "title": "Forked", "built": built}
    text = render_card(data, [])
    card = ConceptCard.model_validate(yaml.safe_load(text))
    assert card.built is not None
    assert (card.built.event, card.built.number, card.built.mass) == ("forked", 4, "24.7 kg")
    assert card.built.cost == "640 USD" and card.built.checkpoint == "abc123"
    assert "\nbuilt:" not in render_card({"id": "C-009", "title": "Plain"}, [])
