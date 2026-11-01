"""v0.2 leftovers: the door's opening angle (B-0029), the skin and chamber-volume advisories
(B-0025), notes in the owner's words (B-0034) and an unchanged re-screen keeping its
timestamp (B-0031).
"""

from __future__ import annotations

import datetime as dt
import math
import re
from pathlib import Path

import pytest

from napkin2factory.concepts.screening import keep_unchanged_at, same_screening
from napkin2factory.core.model import Screening
from napkin2factory.rulepacks.concept_checks import (
    concept_packs,
    swing_factor,
    touch_limit_default,
)
from tests.unit.test_screening import KILN, SMALL, _card, _q, _rule, _screen

# --- B-0029: the door's opening angle --------------------------------------------------


def test_swing_factor_follows_the_opening_angle() -> None:
    assert swing_factor(None) == 1.0 and swing_factor(None, 0.5) == 0.5
    assert swing_factor(60) == 0.0 and swing_factor(90) == pytest.approx(0.0, abs=1e-12)
    assert swing_factor(110) == pytest.approx(-math.cos(math.radians(110)))
    assert swing_factor(180) == pytest.approx(1.0)
    # beyond 180° the leaf has passed 180° on its way: the widest reach counts
    assert swing_factor(270) == pytest.approx(1.0)


def test_a_110_degree_door_counts_a_third_of_its_leaf() -> None:
    wide = _card(KILN, envelope={**KILN["envelope"], "door_swing": "110 degree"})
    s = _screen(wide)
    term = 250 * -math.cos(math.radians(110))  # 85.5 mm
    assert _q(s, "computed", "footprint_with_door_swing", "mm") == pytest.approx(995 + term, abs=1)
    row = _rule(s, "fits-site-width")
    assert "the 250 mm door leaf opened to 110°" in row.message
    assert s.computed["footprint_with_door_swing"].source == (
        "the body plus what the door leaf, opened to 110°, reaches past the hinge"
    )
    assert not any("how far the door opens" in n for n in s.notes)
    assert s.computed["door_leaf"].value == "250.0 mm"


def test_a_door_that_opens_to_90_degrees_stays_in_front() -> None:
    s = _screen(_card(KILN, envelope={**KILN["envelope"], "door_swing": "90 degree"}))
    assert _q(s, "computed", "footprint_with_door_swing", "mm") == pytest.approx(995, abs=1)
    assert "stays in front of the body" in s.computed["footprint_with_door_swing"].source


def test_an_unreadable_angle_keeps_the_widest_case() -> None:
    s = _screen(_card(KILN, envelope={**KILN["envelope"], "door_swing": "110 mm"}))
    assert _q(s, "computed", "footprint_with_door_swing", "mm") == pytest.approx(1245, abs=1)
    assert any("does not say how far the door opens" in n for n in s.notes)


# --- B-0025: skin and chamber volume, advisory -----------------------------------------


def test_the_new_rules_are_warnings() -> None:
    rules = {r["id"]: r for p in concept_packs() for r in p.rules}
    assert rules["skin-vs-touch-limit"]["severity"] == "warn"
    assert rules["chamber-volume-vs-target"]["severity"] == "warn"


def test_touch_limit_default_is_cited() -> None:
    found = touch_limit_default("1 min")
    assert found is not None
    limit, words = found
    assert limit.to("degC").magnitude == pytest.approx(51)
    assert "ISO 13732-1" in words and "to be checked" in words
    assert touch_limit_default("3 s") is None


def test_skin_against_the_cards_touch_limit_and_the_default() -> None:
    hot = _card(SMALL, site={"touch_limit": "60 degC"})  # 100 mm of fiber board
    s = _screen(hot)
    skin = _q(s, "e", "skin_temperature", "degC")
    row = _rule(s, "skin-vs-touch-limit")
    assert row.relies_on == ["estimate", "given"]
    if skin > 60:
        assert row.status == "warn"
        assert "above the 60 degC touch limit (on the card)" in row.message
    else:
        assert row.status == "pass"
    cool = _screen(_card(SMALL, site={"touch_limit": "200 degC"}))
    assert _rule(cool, "skin-vs-touch-limit").status == "pass"
    assert (
        "under the 200 degC touch limit (on the card)" in _rule(cool, "skin-vs-touch-limit").message
    )
    default = _screen(_card(SMALL))
    row = _rule(default, "skin-vs-touch-limit")
    assert (
        "51 degC touch limit (the 1-minute burn threshold for metal in ISO 13732-1" in row.message
    )
    assert row.relies_on == ["estimate"]
    assert default.verdict == "green", "an advisory never reddens"


def test_skin_rule_skips_without_an_estimate() -> None:
    s = _screen(_card(SMALL).model_copy(update={"envelope": {}}))
    assert _rule(s, "skin-vs-touch-limit").status == "skip"


def test_chamber_volume_against_the_target() -> None:
    short = _screen(_card(SMALL, envelope={**SMALL["envelope"], "target_volume": "8 L"}))
    row = _rule(short, "chamber-volume-vs-target")
    assert row.status == "warn" and row.severity == "warn"
    assert (
        row.message
        == "the 150 × 150 × 150 mm chamber holds 3.38 L, less than the 8 L the card aims for"
    )
    assert short.verdict == "green"
    ok = _screen(_card(SMALL, envelope={**SMALL["envelope"], "target_volume": "3 L"}))
    assert _rule(ok, "chamber-volume-vs-target").status == "pass"
    none = _screen(_card(SMALL))
    assert _rule(none, "chamber-volume-vs-target").message == "no target volume on the card"


# --- B-0034: owner words --------------------------------------------------------------

FIELD_WORDS = re.compile(r"\b(envelope|site|layout|massing)\.|[a-z]+_[a-z]+|\[\{")


@pytest.mark.parametrize(
    "card",
    [
        _card(SMALL).model_copy(update={"envelope": {}}),
        _card(SMALL, envelope={**SMALL["envelope"], "insulation": ["50 mm", "50 mm"]}),
        _card(SMALL, envelope={**SMALL["envelope"], "insulation": [{"name": "x"}]}),
        _card(
            SMALL,
            envelope={**SMALL["envelope"], "insulation": [{"name": "m", "thickness": "9 mm"}]},
        ),
        _card(SMALL, site={"circuit": "two sockets", "region": "XX"}),
        _card(SMALL, massing=[{**m, "material": None} for m in SMALL["massing"]]),
    ],
)
def test_notes_name_no_fields(card: object) -> None:
    s = _screen(card)  # type: ignore[arg-type]
    assert s.notes
    for note in s.notes:
        assert not FIELD_WORDS.search(note), note


# --- B-0031: the timestamp moves only with the content ----------------------------------


def test_an_unchanged_screen_keeps_its_timestamp(tmp_path: Path) -> None:
    card = _card(SMALL)
    first = _screen(card)
    first.at = dt.datetime(2026, 1, 1, 12, 0, 0)
    again = _screen(card)
    assert same_screening(first, again)
    assert keep_unchanged_at(first, again) and again.at == first.at
    changed = _screen(_card(SMALL, site={"alcove_width": "700 mm"}))
    assert not same_screening(first, changed)
    stamp = changed.at
    assert not keep_unchanged_at(first, changed) and changed.at == stamp
    assert not keep_unchanged_at(None, again)
    assert not same_screening(None, Screening())
