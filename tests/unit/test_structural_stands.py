"""S-235: the structural screen judges bare legs, trestle ends and a cross member (B-0239).

The four fixture cards in ``tests/fixtures/structural/`` are shaped like the three candidates
of ``examples/table/SPEC.md`` section 4 (pine on four legs, an oak top on a steel frame with a
cross rail, plate trestles). The asserted figures are the spec's, worked by hand there; the cards
carry no hardware, so the tip-over factors sit a little below the spec's (which counts 0.56 kg of
glides and inserts), hence 5 % rather than 1 %.
"""

from __future__ import annotations

import functools
from typing import Any

import pytest
import yaml

from napkin2factory.concepts.massing import compose
from napkin2factory.concepts.screening import screen
from napkin2factory.core.model import ConceptCard, Screening
from tests.conftest import FIXTURES

CARDS = FIXTURES / "structural"
TOLERANCE = 0.05


def _data(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load((CARDS / f"{name}.yaml").read_text())
    return loaded


def _run(data: dict[str, Any]) -> Screening:
    card = ConceptCard.model_validate(data)
    return screen(card, compose(card, write=False))


@functools.cache
def _screen(name: str) -> Screening:
    return _run(_data(name))


def _num(s: Screening, name: str) -> float:
    return float(s.computed[name].value.split()[0])


def _row(s: Screening, kind: str) -> Any:
    row = s.rule(f"structural-{kind}")
    assert row is not None, [r.id for r in s.rules]
    return row


def test_four_corner_legs_reproduce_the_specs_pine_table() -> None:
    # SPEC 4.2: sag 14.25 mm (13.3 + 0.922), yield factor 5.28, tip-over 9.38 (front edge)
    s = _screen("corner-legs")
    assert _num(s, "deflection") == pytest.approx(14.25, rel=TOLERANCE)
    assert _num(s, "deflection_along") == _num(s, "deflection")  # no cross member
    assert _num(s, "yield_factor") == pytest.approx(5.28, rel=TOLERANCE)
    assert _num(s, "tip_over_factor") == pytest.approx(9.38, rel=TOLERANCE)
    assert _row(s, "deflection").status == "fail"  # 14.3 mm against 2.5
    assert _row(s, "yield").status == "pass" and _row(s, "tip-over").status == "pass"
    assert s.verdict == "red"


def test_leg_buckling_takes_the_centre_load_not_the_edge_load() -> None:
    # B-0217: P = 1471.5 N + a quarter of the weight; adding the 490.5 N edge load would put the
    # factor near 29 (the old figure), the spec's 38.2 for the 720 mm leg is the centre load only
    s = _screen("corner-legs")
    with_edge = _num(s, "buckling_factor")
    assert with_edge > 33
    data = _data("corner-legs")
    data["site"]["edge_load"] = "4905 N"
    assert _num(_run(data), "buckling_factor") == pytest.approx(with_edge, rel=0.001)


def test_a_frame_without_rails_is_the_same_table_as_four_tubes() -> None:
    # the frame kit with top_rails and bottom_rails false is four bare legs (B-0214)
    four, framed = _screen("corner-legs"), _screen("frame-bare-legs")
    for name in ("deflection", "yield_factor", "buckling_factor"):
        assert _num(framed, name) == pytest.approx(_num(four, name), rel=0.02), name
    # no glides drawn: the feet are the legs' own faces, a little inside the glides' centres
    assert _num(framed, "tip_over_factor") == pytest.approx(9.38, rel=0.08)
    assert "cross_member_dip" not in framed.computed


def test_a_cross_member_adds_its_dip_to_the_sag_along_the_length() -> None:
    # SPEC 4.1: 1.599 along + 0.106 dip = 1.705 mm; top yield 33.6, cross rail yield 11.1,
    # leg buckling 38.2, tip-over 4.09 (front edge)
    s = _screen("cross-member")
    assert _num(s, "deflection_along") == pytest.approx(1.599, rel=TOLERANCE)
    assert _num(s, "cross_member_dip") == pytest.approx(0.106, rel=TOLERANCE)
    assert _num(s, "deflection") == pytest.approx(1.705, rel=TOLERANCE)
    assert _num(s, "deflection") == pytest.approx(
        _num(s, "deflection_along") + _num(s, "cross_member_dip"), abs=0.01
    )
    assert _num(s, "yield_factor") == pytest.approx(33.6, rel=TOLERANCE)
    assert _num(s, "cross_member_yield_factor") == pytest.approx(11.1, rel=TOLERANCE)
    assert _num(s, "buckling_factor") == pytest.approx(38.2, rel=TOLERANCE)
    assert _num(s, "tip_over_factor") == pytest.approx(4.09, rel=TOLERANCE)
    assert s.verdict == "green"


def test_a_tube_that_is_not_under_the_top_is_not_a_cross_member() -> None:
    # the same tube moved down to the legs' middle carries nothing from the top: ignored
    data = _data("cross-member")
    for call in data["massing"]:
        if call.get("as") == "cross-rail":
            call["at"]["z"] = "300 mm"
    s = _run(data)
    assert "cross_member_dip" not in s.computed and "cross_member_yield_factor" not in s.computed
    assert s.rule("structural-cross-member") is None
    assert _num(s, "deflection") == _num(s, "deflection_along")
    assert _num(s, "deflection") == pytest.approx(1.599, rel=TOLERANCE)


def test_plate_trestles_reproduce_the_specs_oak_table() -> None:
    # SPEC 4.3: sag 0.837 mm (0.709 + 0.128), tip-over 10.2; the trestles themselves are not judged
    s = _screen("plate-trestles")
    assert _num(s, "deflection") == pytest.approx(0.837, rel=TOLERANCE)
    assert _num(s, "tip_over_factor") == pytest.approx(10.2, rel=TOLERANCE)
    assert _row(s, "deflection").status == "pass"
    assert s.rule("structural-buckling") is None
    assert s.verdict == "green"


def test_trestles_without_glides_tip_over_their_foot_bars() -> None:
    # the foot bars are 700 mm across: their edges (y = +-350) are the tipping edges, so the
    # restoring arm is longer than with glides at y = +-310 and the factor higher
    glided = _num(_screen("plate-trestles"), "tip_over_factor")
    data = _data("plate-trestles")
    data["massing"] = [c for c in data["massing"] if not c["as"].startswith("glide")]
    bare = _run(data)
    assert _row(bare, "tip-over").status == "pass"
    assert _num(bare, "tip_over_factor") > glided
    assert _num(bare, "tip_over_factor") == pytest.approx(glided * 350 / 310, rel=0.05)
    assert _num(bare, "deflection") == _num(_screen("plate-trestles"), "deflection")
