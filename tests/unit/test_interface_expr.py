"""P2: interface frames and offsets as expressions over parameters; every slug is a read."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from napkin2factory.core.graph.impact import compute_impact, parse_set
from napkin2factory.core.loader import load_product, validate
from napkin2factory.core.model import FrameExpr, Interface
from napkin2factory.geometry.accessors import ReadLog, resolve_interface
from tests.conftest import EXAMPLES, copy_product


def _iface(**extra: object) -> dict[str, object]:
    return {
        "id": "ab",
        "kind": "mating-face",
        "parties": ["part://a", "part://b"],
        "spec": {"width": "10 mm", "depth": "10 mm"},
        **extra,
    }


def test_schema_accepts_expressions_and_round_trips() -> None:
    i = Interface.model_validate(
        _iface(
            frames={"part://a": {"origin": [{"expr": "-w / 2", "unit": "mm"}, 0, "param://h"]}},
            offset={"expr": "gap + t"},
        )
    )
    origin = i.frames["part://a"].origin
    assert isinstance(origin[0], FrameExpr) and origin[0].slugs == ["w"]
    assert isinstance(i.offset, FrameExpr) and i.offset.unit == "mm"
    assert i.expression_slugs() == ["w", "gap", "t"]
    dumped = i.model_dump(mode="json")
    assert dumped["offset"] == {"expr": "gap + t", "unit": "mm"}
    assert Interface.model_validate(dumped) == i
    # P14: no offset → the dump is the v0.3 dump (sign-off keys on it stay valid)
    assert "offset" not in Interface.model_validate(_iface()).model_dump(mode="json")


def test_schema_rejects_unsafe_expressions() -> None:
    with pytest.raises(ValidationError, match="calls something other than"):
        Interface.model_validate(_iface(offset={"expr": "__import__('os')"}))


def test_kiln_frame_expressions_resolve_and_are_recorded() -> None:
    product = load_product(EXAMPLES / "kiln")
    log = ReadLog()
    iface = resolve_interface(product, product.interfaces["guard-standoff-left"], log)
    shell = iface.frame_for("part://outer-shell")
    width = product.parameter_value("shell-outer-width").to("mm").magnitude
    assert shell.origin[0] == pytest.approx(-width / 2)
    assert iface.offset == pytest.approx(26.0)  # guard-gap + guard-thickness (M0)
    for slug in ("shell-outer-width", "shell-outer-depth", "guard-outer-width", "guard-gap"):
        assert f"param://{slug}" in log, slug
    # the 18 frame-only helper parameters are gone (DoD 2)
    assert not [s for s in product.parameters if "-half-" in s]
    assert "controller-mount-y" not in product.parameters


def test_changing_shell_outer_width_rebuilds_both_parties(tmp_path: Path) -> None:
    """Before any build, impact reads the slugs inside frame expressions (P2, S-020)."""
    root = copy_product(EXAMPLES / "kiln", tmp_path / "kiln", git=False)
    rep = compute_impact(load_product(root), [parse_set("param://shell-outer-width=500mm")])
    assert {"part:outer-shell", "part:guard-shell", "asm:kiln"} <= set(rep.rules)
    assert "guard-standoff-left" in rep.interfaces


def _enclosure_with_lift(tmp_path: Path, expr: str) -> Path:
    """The enclosure with a parameter read only by the base's frame expression."""
    root = copy_product(EXAMPLES / "enclosure", tmp_path / "enc", git=False)
    params = root / "model/parameters.yaml"
    params.write_text(
        params.read_text().rstrip("\n")
        + "\n  lid-lift:          {value: 0, unit: mm, description: Test only}\n"
    )
    iface = root / "model/interfaces/lid-base-mount.yaml"
    iface.write_text(
        iface.read_text().replace("param://box-height]", f'{{expr: "{expr}", unit: mm}}]')
    )
    return root


def test_a_slug_read_only_by_a_frame_rebuilds_both_parties(tmp_path: Path) -> None:
    from napkin2factory.geometry.build import build_part

    root = _enclosure_with_lift(tmp_path, "box-height + lid-lift")
    product = load_product(root)
    rep = compute_impact(product, [parse_set("param://lid-lift=5mm")])
    assert {"part:base", "part:lid", "asm:enclosure"} <= set(rep.rules)
    assert "part:bracket" not in rep.rules
    assert rep.interfaces == ["lid-base-mount"]
    for pid in ("base", "lid"):
        built = build_part(product, pid, root / "build", render=False)
        assert "param://lid-lift" in built.reads, pid


def test_unknown_slug_in_an_expression_is_a_validation_error(tmp_path: Path) -> None:
    root = _enclosure_with_lift(tmp_path, "box-height + lid-lfit")
    _, problems = validate(root)
    errs = [p for p in problems.items if "lid-lfit" in p.message]
    assert len(errs) == 1
    assert errs[0].file.endswith("lid-base-mount.yaml") and errs[0].subject == (
        "iface://lid-base-mount"
    )
    assert errs[0].severity == "error" and errs[0].rule == "expr"


def test_expression_in_the_wrong_unit_is_a_validation_error(tmp_path: Path) -> None:
    root = _enclosure_with_lift(tmp_path, "box-height * lid-lift")
    _, problems = validate(root)
    assert any("cannot be expressed in mm" in p.message for p in problems.items)
