"""M2c (W4, S-206): the generic ``structural`` screen reads loads from the site and members
from the massing, and decides a bench's top, legs and tipping and a column's arm.

Cards are the made-up ones in ``tests/fixtures/structural/``. Material numbers are the
shared table's (``calckit/data/materials.yaml``): white oak and southern yellow pine E 12.3 GPa
(yield 55.2 and 49.6 MPa), mild steel E 200 GPa (yield 250 MPa). Each asserted value has its
hand calculation in the comment above it; the Roark and Shigley formulas are the ones in
``calckit/structural.py``.
"""

from __future__ import annotations

import copy
import functools
from typing import Any

import pytest
import yaml

from napkin2factory.calckit import joints
from napkin2factory.concepts.massing import compose
from napkin2factory.concepts.screening import screen
from napkin2factory.concepts.screens import GENERIC_SCREENS, generic_fields
from napkin2factory.core.model import ConceptCard, Screening
from tests.conftest import FIXTURES

CARDS = FIXTURES / "structural"
ROWS = ("deflection", "yield", "buckling", "tip-over")
G = 9.80665


def _data(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load((CARDS / f"{name}.yaml").read_text())
    return loaded


@functools.cache
def _massing(name: str) -> Any:
    return compose(ConceptCard.model_validate(_data(name)), write=False)


def _screen(name: str, drop: tuple[str, ...] = (), **site: str) -> Screening:
    """Screen a fixture card with some site keys changed or (``drop``) removed."""
    data = copy.deepcopy(_data(name))
    data["site"] = {k: v for k, v in {**data.get("site", {}), **site}.items() if k not in drop}
    card = ConceptCard.model_validate(data)
    return screen(card, _massing(name))


def _row(s: Screening, kind: str) -> Any:
    row = s.rule(f"structural-{kind}")
    assert row is not None, [r.id for r in s.rules]
    return row


def _mm(s: Screening, name: str = "deflection") -> float:
    return float(s.computed[name].value.split()[0])


def test_a_weak_softwood_top_fails_the_sag_limit() -> None:
    s = _screen("weak-top")
    # span = frame 1450 mm long - 50 mm leg = 1400 mm; top 800 x 22 mm, pine E 12.3 GPa:
    # I = b h^3 / 12 = 0.8 * (0.022)^3 / 12 = 7.0987e-7 m^4, EI = 8731 N m^2
    # point load: d_P = F L^3 / (48 E I) = 1471.5 * 1.4^3 / (48 * 8731.4) = 9.634 mm
    # self weight: top 1.6 * 0.8 * 0.022 * 590 kg/m^3 = 16.61 kg, W = 162.93 N
    # d_W = 5 W L^3 / (384 E I) = 5 * 162.93 * 1.4^3 / (384 * 8731.4) = 0.667 mm
    # total sag = 9.634 + 0.667 = 10.30 mm
    assert _mm(s) == pytest.approx(10.30, abs=0.01)
    row = _row(s, "deflection")
    assert row.status == "fail" and "2.5 mm limit" in row.message
    assert "FL^3 / (48*E*I)" in row.message and "Roark" in row.message  # formula and source
    assert s.verdict == "red"
    # bending: M = F L / 4 + W L / 8 = 515.0 + 28.5 = 543.5 N m; Z = b h^2 / 6 = 6.453e-5 m^3
    # stress = 543.5 / 6.453e-5 = 8.42 MPa; yield factor = 49.6 / 8.42 = 5.89 against 1.5
    assert float(s.computed["yield_factor"].value) == pytest.approx(5.89, rel=0.01)
    assert _row(s, "yield").status == "pass"
    assert joints.factor_of_safety("yield", "static") == 1.5


def test_a_stiff_apron_card_passes_what_it_can_run() -> None:
    s = _screen("stiff-apron")
    # oak 800 x 40 mm: I = 0.8 * (0.04)^3 / 12 = 4.2667e-6 m^4, E I = 12.3e9 * I = 52480 N m^2
    # the two long top rails (50 x 50 x 2 steel tube, I = (50^4 - 46^4) / 12 = 147712 mm^4) share
    # the span: E I = 200e9 * 1.47712e-7 = 29542 N m^2 each; total 52480 + 2 * 29542 = 111565 N m^2
    # point load: d_P = F L^3 / (48 E I) = 1471.5 * 1.4^3 / (48 * 111565) = 0.7540 mm
    # self weight: top 1.6 * 0.8 * 0.04 * 750 = 38.4 kg, W = 376.58 N
    # d_W = 5 W L^3 / (384 E I) = 5 * 376.58 * 1.4^3 / (384 * 111565) = 0.1206 mm
    # total sag = 0.754 + 0.121 = 0.875 mm
    assert _mm(s) == pytest.approx(0.875, abs=0.005)
    assert "top rails sharing" in _row(s, "deflection").message
    # M = F L / 4 + W L / 8 = 515.0 + 65.9 = 580.9 N m; the top takes 52480 / 111565 = 0.4704:
    # M_top = 273.3 N m; Z = 0.8 * 0.04^2 / 6 = 2.1333e-4 m^3; stress = 1.281 MPa;
    # yield factor = 55.2 / 1.281 = 43.1
    assert float(s.computed["yield_factor"].value) == pytest.approx(43.1, rel=0.01)
    # leg 730 mm tube 50 x 50 x 2 (A = 384 mm^2, I = 147712 mm^4, r = 19.61 mm):
    # unbraced sway K = 2.0 -> KL = 1460 mm, slenderness 74.45 < 125.7 (Johnson, S-207, S-211);
    # sigma_cr = 250 - (250 * 74.45 / 2pi)^2 / 200000 = 206.11 MPa -> P_cr = 79146 N;
    # mass 59.3 kg -> 581.5 N table weight, leg share 145.4 N + applied (1471.5 N point +
    # 490.5 N edge load on the corner leg) = 2107.4 N;
    # factor = 79146 / 2107.4 = 37.56 >= 2.0 (buckling, static)
    row = _row(s, "buckling")
    assert row.status == "pass" and "Johnson" in row.message
    assert float(s.computed["buckling_factor"].value) == pytest.approx(37.56, rel=0.01)
    # tip-over: pivot at the leg line, centre of gravity 750 / 2 - 25 = 350 mm inside it
    # (frame and top are symmetric): FS = m g 0.350 / (490.5 * 0.150)
    mass = _massing("stiff-apron").mass
    expected = mass * G * 0.350 / (490.5 * 0.150)
    assert float(s.computed["tip_over_factor"].value) == pytest.approx(expected, rel=0.01)
    assert expected == pytest.approx(2.77, abs=0.03) and mass == pytest.approx(59.3, abs=0.1)
    assert [_row(s, k).status for k in ROWS] == ["pass", "pass", "pass", "pass"]
    assert s.verdict == "green"


def test_a_tall_thin_leg_buckles_by_euler() -> None:
    s = _screen("tall-slim-legs")
    # tube 25 x 25 x 1.5: I = (25^4 - 22^4) / 12 = 13031 mm^4, A = 625 - 484 = 141 mm^2,
    # r = 9.61 mm; leg 2000 mm, unbraced sway K = 2.0 -> KL = 4000 mm,
    # slenderness = 2.0 * 2000 / 9.61 = 416.2 > 125.7 (Euler holds)
    # Pcr = pi^2 E I / (K L)^2 = 9.8696 * 200e9 * 1.3031e-8 / 4.0^2 = 1607.7 N;
    # bench mass 51.90 kg -> 509.0 N, leg share 127.25 N + 300 N point = 427.25 N;
    # factor = 1607.7 / 427.25 = 3.76, over the 2.0 needed (buckling, static)
    assert float(s.computed["buckling_factor"].value) == pytest.approx(3.76, rel=0.01)
    row = _row(s, "buckling")
    assert row.status == "pass" and "sway" in row.message and "Euler" in row.message
    assert joints.factor_of_safety("buckling", "static") == 2.0


def test_the_weak_top_card_also_tips_below_the_factor() -> None:
    s = _screen("weak-top")
    # 37.5 kg (frame 20.9 + pine top 16.6, from the massing): FS = 37.474 * 9.80665 * 0.35 /
    # 73.575 = 1.748, under the 2.0 of calckit/data/load_cases.yaml (tip_over, edge_load)
    assert float(s.computed["tip_over_factor"].value) == pytest.approx(1.75, abs=0.01)
    row = _row(s, "tip-over")
    assert row.status == "fail" and "below the 2 needed" in row.message


def test_a_narrow_stand_fails_tip_over_and_nothing_else() -> None:
    s = _screen("narrow-stand")
    # frame 300 wide: legs 250 mm apart, centre of gravity 125 mm inside the leg line;
    # 32.55 kg: FS = 32.547 * 9.80665 * 0.125 / 73.575 = 0.542
    assert float(s.computed["tip_over_factor"].value) == pytest.approx(0.542, abs=0.005)
    assert [_row(s, k).status for k in ROWS] == ["pass", "pass", "pass", "fail"]
    # top E I = 12.3e9 * (0.3 * 0.04^3 / 12 = 1.6e-6) = 19680; with the rails (59085):
    # d_P = 400 * 1.4^3 / (48 * 78765) = 0.290 mm
    # self weight: top 1.6 * 0.3 * 0.04 * 750 = 14.4 kg, W = 141.2 N ->
    # d_W = 5 * 141.2 * 1.4^3 / (384 * 78765) = 0.064 mm; total sag = 0.354 mm
    assert _mm(s) == pytest.approx(0.354, abs=0.005)
    assert s.verdict == "red"
    # mass is the cost screen's job: this screen has no mass row
    assert not [r for r in s.rules if r.id.startswith("structural") and "mass" in r.id]


def test_a_distributed_load_alone_uses_the_uniform_formulas() -> None:
    s = _screen("weak-top", drop=("point_load",), distributed_load="1000 N")
    # pine top 162.9 N + distributed load 1000 N = 1162.9 N
    # d = 5 W L^3 / (384 E I) = 5 * 1162.9 * 2.744 / (384 * 12.3e9 * 7.0987e-7) = 4.76 mm
    assert _mm(s) == pytest.approx(4.76, abs=0.01)
    # M = W L / 8 = 1162.9 * 1.4 / 8 = 203.5 N m; stress = 203.5 / 6.453e-5 = 3.15 MPa;
    # factor = 49.6 / 3.15 = 15.7
    assert float(s.computed["yield_factor"].value) == pytest.approx(15.7, rel=0.01)
    assert "384" in _row(s, "deflection").message  # the uniform-load formula


def test_a_column_with_an_arm_deflects_at_its_tip() -> None:
    s = _screen("column-arm")
    # tube 60 x 60 x 4: I = (60^4 - 52^4) / 12 = 470699 mm^4; E I = 9.414e10 N mm^2
    # arm: F L^3 / (3 E I) = 2000 * 150^3 / (3 * 9.414e10) = 0.0239 mm
    # column rotation: F L^2 H / (E I) = 2000 * 150^2 * 400 / 9.414e10 = 0.1912 mm  (H = 400)
    # total 0.2151 mm, over the 0.2 mm limit on the card
    assert _mm(s) == pytest.approx(0.2151, abs=0.0005)
    assert _row(s, "deflection").status == "fail" and s.verdict == "red"
    # M = 2000 * 0.150 = 300 N m; Z = I / 30 mm = 15690 mm^3; stress = 19.12 MPa; 250 / 19.12
    assert float(s.computed["yield_factor"].value) == pytest.approx(13.07, rel=0.01)
    # column 400 mm, fixed-free K 2.1: r = sqrt(470699 / 896) = 22.92 mm, slenderness 36.65
    # < 125.7: Johnson applies (S-207, S-211); sigma_cr = 239.37 MPa, P_cr = 214475 N;
    # tip load 2000 N -> factor 214475 / 2000 = 107.2 >= 2.0 (pass)
    row = _row(s, "buckling")
    assert row.status == "pass" and "Johnson" in row.message
    assert float(s.computed["buckling_factor"].value) == pytest.approx(107, rel=0.01)
    assert not [r for r in s.rules if r.id == "structural-tip-over"]  # no edge load given


def test_a_looser_limit_passes_the_arm() -> None:
    s = _screen("column-arm", max_deflection="0.25 mm")
    assert _row(s, "deflection").status == "pass"
    assert s.verdict == "green"


def test_a_check_missing_an_input_says_which_and_is_not_run() -> None:
    s = _screen("stiff-apron", drop=("edge_offset",))
    row = _row(s, "tip-over")
    assert row.status == "skip" and row.message.startswith("not run:")
    assert "how far beyond the support the edge load acts" in row.message
    assert "tip_over_factor" not in s.computed  # never a guess
    s = _screen("stiff-apron", drop=("max_deflection",))
    row = _row(s, "deflection")
    assert row.status == "skip" and "no max_deflection" in row.message
    assert _mm(s) == pytest.approx(0.875, abs=0.005)  # still reported
    s = _screen("column-arm", drop=("point_load",), edge_load="100 N")
    assert _row(s, "deflection").status == "skip"
    assert "point_load" in _row(s, "deflection").message


def test_a_piece_without_a_material_is_not_run_not_guessed() -> None:
    data = copy.deepcopy(_data("stiff-apron"))
    del data["massing"][1]["material"]
    card = ConceptCard.model_validate(data)
    s = screen(card, compose(card, write=False))
    for kind in ("deflection", "yield"):
        assert _row(s, kind).status == "skip" and "no material" in _row(s, kind).message
    assert _row(s, "tip-over").status == "skip"  # the weight is incomplete
    assert _row(s, "buckling").status == "skip"  # the legs have a material; short column


def test_a_massing_with_no_supports_says_so() -> None:
    data = copy.deepcopy(_data("stiff-apron"))
    data["massing"] = data["massing"][1:]  # the top board alone
    card = ConceptCard.model_validate(data)
    s = screen(card, compose(card, write=False))
    row = _row(s, "support")
    assert row.status == "skip" and "nothing carries the load" in row.message


def test_a_card_without_a_load_gets_no_structural_rows() -> None:
    s = _screen("stiff-apron", drop=("point_load", "edge_load"))
    assert not [r for r in s.rules if r.id.startswith("structural")]
    assert not [k for k in s.given if k.endswith("load")]


def test_cycles_choose_the_cyclic_factors() -> None:
    # narrow card, limit 0.40 mm against the 0.354 mm sag: limit / sag = 1.13, which clears
    # the static 1.0 and misses the cyclic 1.25 (calckit/data/load_cases.yaml, deflection)
    static = _screen("narrow-stand", max_deflection="0.40 mm")
    cyclic = _screen("narrow-stand", max_deflection="0.40 mm", cycles="100000")
    assert joints.factor_of_safety("deflection", "static") == 1.0
    assert joints.factor_of_safety("deflection", "cyclic") == 1.25
    assert _row(static, "deflection").status == "pass"
    assert _row(cyclic, "deflection").status == "fail" and "cyclic case" in (
        _row(cyclic, "deflection").message
    )
    assert any("endurance" in n for n in cyclic.notes) and not static.notes


def test_a_load_of_the_wrong_kind_is_left_out_and_the_rest_runs() -> None:
    s = _screen("stiff-apron", point_load="20 mm")
    assert any("is not a force" in n for n in s.notes)
    assert not [r for r in s.rules if r.id == "structural-deflection"]


def test_the_screen_is_registered_with_package_words_only() -> None:
    assert "structural" in [x.name for x in GENERIC_SCREENS]
    fields = {f.name: f for f in generic_fields()}
    keys = ("point_load", "distributed_load", "edge_load", "edge_offset", "max_deflection")
    assert {f"site.{k}" for k in (*keys, "cycles")} <= set(fields)
    assert not any(fields[f"site.{k}"].hint for k in keys)  # never suggested on a new card


def test_table_spec_c002_reproduces_spec_figures() -> None:
    """Benchmark table C-002 reproduces SPEC §4: 1.58 mm sag and 38.3 leg buckling factor.

    Cites examples/table/SPEC.md §4 (C-002 worked calculations):
    - Top: 1600 x 800 x 30 mm white-oak (E 12.3 GPa, density 750 kg/m^3, mass 28.8 kg).
    - Apron frame: 1500 x 700 x 720 mm, mild steel (E 200 GPa, density 7850 kg/m^3),
      member 50 x 50 x 1.5 mm tube (A 291 mm^2, I 114193 mm^4), top rails true.
    - Span L = 1500 - 50 = 1450 mm.
    - Sag: delta_P = 1.378 mm, delta_W = 0.165 mm -> 1.543 mm (within 2.3 % of SPEC 1.58 mm).
    - Leg buckling (Johnson): KL = 2.0 * 720 = 1440 mm, slenderness 72.7 < 125.7,
      P_cr = 60578 N; load = 1471.5 N + 436.6/4 N = 1580.6 N -> factor 38.32 (SPEC 38.3).
    """
    data = {
        "id": "C-002",
        "title": "Table benchmark C-002 shape",
        "site": {
            "point_load": "1471.5 N",
            "max_deflection": "2.5 mm",
        },
        "massing": [
            {
                "kit": "frame",
                "as": "base",
                "material": "mild steel",
                "args": {
                    "length": "1500 mm",
                    "width": "700 mm",
                    "height": "720 mm",
                    "member": {"profile": "square-tube", "size": "50 mm", "wall": "1.5 mm"},
                    "top_rails": True,
                    "bottom_rails": False,
                },
            },
            {
                "kit": "block",
                "as": "top",
                "material": "white-oak",
                "args": {"length": "1600 mm", "width": "800 mm", "height": "30 mm"},
                "at": {"z": "720 mm"},
            },
        ],
    }
    card = ConceptCard.model_validate(data)
    s = screen(card, compose(card, write=False))
    assert _mm(s) == pytest.approx(1.58, rel=0.05)
    assert float(s.computed["buckling_factor"].value) == pytest.approx(38.3, rel=0.05)
    buckling_row = _row(s, "buckling")
    assert buckling_row.status == "pass"
    assert "Johnson" in buckling_row.message
