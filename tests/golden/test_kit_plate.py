import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from napkin2factory.geometry.kit import KitContext, KitError, run


def test_plate_basic(check_golden):
    r = run(
        "plate",
        {"width": "100 mm", "depth": 80, "thickness": "3 mm", "holes": {"diameter": "6.6 mm"}},
        KitContext("p"),
    )
    fp = check_golden("plate", "basic", r)
    assert fp["features"]["holes"] == 4
    expected = 100 * 80 * 3 - 4 * math.pi * 3.3**2 * 3
    assert abs(r.shape.volume - expected) < 1.0
    # D: flat pattern developed area × thickness == volume within 1 %
    assert abs(r.flat_pattern.area * 3 - r.shape.volume) / r.shape.volume < 0.01
    assert r.shape.label == "part://p"
    assert {d.label for d in r.dims} >= {"width", "depth", "thickness"}


def test_plate_rejects_bad_args():
    with pytest.raises(KitError):
        run("plate", {"width": "100 mm", "depth": 80}, KitContext("p"))  # missing thickness
    with pytest.raises(KitError):
        run("plate", {"width": "100 mm", "depth": 80, "thickness": 3, "bogus": 1}, KitContext("p"))
    with pytest.raises(ValueError, match="breaks the plate edge"):
        run(
            "plate",
            {"width": 20, "depth": 20, "thickness": 3, "holes": {"diameter": 12, "inset": 2}},
            KitContext("p"),
        )


@settings(max_examples=8, deadline=None)
@given(
    w=st.floats(20, 400),
    d=st.floats(20, 400),
    t=st.floats(0.5, 10),
    r=st.one_of(st.just(0.0), st.floats(0.5, 5)),
)
def test_plate_properties(w, d, t, r):
    res = run(
        "plate", {"width": w, "depth": d, "thickness": t, "corner_radius": r}, KitContext("p")
    )
    bb = res.shape.bounding_box().size
    assert res.shape.volume > 0
    assert abs(bb.X - w) < 1e-3 and abs(bb.Y - d) < 1e-3 and abs(bb.Z - t) < 1e-3
