"""D5: every read through P/I is recorded; interface specs resolve param refs and record them."""

from napkin2factory.core.loader import load_product
from napkin2factory.geometry.accessors import make_accessors, resolve_interface
from napkin2factory.geometry.build import resolve_args
from tests.conftest import EXAMPLES


def test_param_reads_are_recorded():
    p = load_product(EXAMPLES / "enclosure")
    P, I, log = make_accessors(p)
    assert P.mm("box-length") == 200.0
    assert P["lid-length"].to("mm").magnitude == 224.0  # expression: records only the expr param
    assert log.keys == ["param://box-length", "param://lid-length"]
    assert "param://lid-width" not in log


def test_interface_read_records_iface_and_its_params():
    p = load_product(EXAMPLES / "enclosure")
    P, I, log = make_accessors(p)
    iface = I["lid-base-mount"]
    assert iface.spec.diameter.to("mm").magnitude == 4.5
    assert log.keys == ["iface://lid-base-mount", "param://screw-clearance"]
    assert iface.frame_for("part://base").origin[2] == 80.0
    assert iface.frame_for("part://lid").origin[2] == 0.0
    assert iface.frame_for("part://zzz").origin == [0.0, 0.0, 0.0]
    # the stored model is untouched
    assert str(p.interfaces["lid-base-mount"].spec.diameter) == "param://screw-clearance"
    assert resolve_interface(p, p.interfaces["lid-base-mount"]).spec.depth.to("mm").magnitude == 10


def test_resolve_args_reads_params_and_parses_quantities():
    p = load_product(EXAMPLES / "enclosure")
    P, I, log = make_accessors(p)
    args = resolve_args(
        {
            "a": "param://box-width",
            "b": "15 mm",
            "c": [1, "param://lip-width"],
            "d": {"e": "hello"},
            "f": 3,
        },
        P,
        I,
    )
    assert args["a"].to("mm").magnitude == 150 and args["b"].to("mm").magnitude == 15
    assert args["c"][1].to("mm").magnitude == 12 and args["d"]["e"] == "hello" and args["f"] == 3
    assert log.keys == ["param://box-width", "param://lip-width"]


def test_unknown_param_is_actionable():
    p = load_product(EXAMPLES / "bracket")
    P, I, log = make_accessors(p)
    try:
        P["nope"]
    except KeyError as exc:
        assert "param://nope does not exist" in str(exc) and "known parameters" in str(exc)
    else:
        raise AssertionError("expected KeyError")
