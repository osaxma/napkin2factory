import pytest
from pydantic import ValidationError

from napkin2factory.core.model import (
    Assembly,
    Decision,
    Ecr,
    Interface,
    Manifest,
    Operator,
    Parameter,
    Part,
    Requirement,
    Signoff,
)


def test_requirement_round_trip():
    r = Requirement.model_validate(
        {
            "id": "REQ-003",
            "title": "Skin",
            "statement": "Below 60 degC.",
            "category": "safety",
            "safety": True,
            "verify": {
                "kind": "calc",
                "target": "calc://thermal.skin_temperature",
                "op": "<",
                "value": "60 degC",
            },
            "allocation": ["part://outer-shell", "param://fiber-thickness"],
        }
    )
    assert r.verify is not None and r.verify.value.to("kelvin").magnitude == pytest.approx(333.15)
    assert r.model_dump()["verify"]["value"] == "60 degC"


@pytest.mark.parametrize(
    "verify, msg",
    [
        (
            {"kind": "param_bound", "target": "part://x", "op": "<", "value": "1 mm"},
            "targets param://",
        ),
        ({"kind": "geometry_prop", "target": "part://x", "op": "<", "value": "1 mm"}, "props"),
        ({"kind": "calc", "target": "calc://a.b"}, "needs 'op' and 'value'"),
        (
            {"kind": "bom_rollup", "target": "bom://rollups", "op": "<", "value": "1 USD"},
            "select a rollup",
        ),
        ({"kind": "nope"}, "kind"),
    ],
)
def test_verify_rules(verify, msg):
    with pytest.raises(ValidationError, match=msg):
        Requirement.model_validate(
            {
                "id": "REQ-001",
                "title": "t",
                "statement": "s",
                "category": "geometry",
                "verify": verify,
            }
        )


def test_unknown_key_is_an_error():
    with pytest.raises(ValidationError, match="Extra inputs"):
        Requirement.model_validate(
            {"id": "REQ-001", "title": "t", "statement": "s", "category": "cost", "prio": "must"}
        )


def test_parameter_value_xor_expr():
    with pytest.raises(ValidationError):
        Parameter.model_validate({"unit": "mm"})
    with pytest.raises(ValidationError):
        Parameter.model_validate({"value": 1, "expr": "a", "unit": "mm"})
    assert Parameter.model_validate({"expr": "a + b", "unit": "mm"}).expr == "a + b"


def test_part_rules():
    base = {"id": "shell", "name": "Shell", "process": "sheet-metal"}
    assert Part.model_validate({**base, "geometry": {"kit": "enclosure", "args": {}}}).has_geometry
    assert not Part.model_validate({**base, "geometry": "none"}).has_geometry
    with pytest.raises(ValidationError, match="only custom parts declare tolerance_class"):
        Part.model_validate({**base, "kind": "cots", "tolerance_class": "ISO2768-m"})
    with pytest.raises(ValidationError, match="kit generator name"):
        Part.model_validate({**base, "geometry": {"kit": "Bracket-L"}})
    with pytest.raises(ValidationError, match="geometry is"):
        Part.model_validate({**base, "geometry": {"foo": 1}})
    with pytest.raises(ValidationError):
        Part.model_validate({**base, "tolerance_class": "ISO2768-x"})


def test_assembly_child_one_of():
    with pytest.raises(ValidationError, match="exactly one"):
        Assembly.model_validate(
            {"id": "a", "name": "A", "children": [{"part": "part://x", "asm": "asm://y"}]}
        )
    a = Assembly.model_validate(
        {"id": "a", "name": "A", "children": [{"part": "part://x", "qty": 3}]}
    )
    assert a.children[0].qty == 3 and a.exploded.spacing.to("mm").magnitude == 80


def test_interface_kinds():
    ok = {
        "id": "mount",
        "kind": "bolt-pattern",
        "parties": ["part://a", "part://b"],
        "spec": {
            "pattern": "rect",
            "count": 4,
            "diameter": "6.6 mm",
            "spacing": ["300 mm", "300 mm"],
        },
    }
    Interface.model_validate(ok)
    with pytest.raises(ValidationError, match="exactly two parties"):
        Interface.model_validate({**ok, "parties": ["part://a"]})
    with pytest.raises(ValidationError, match="width"):
        Interface.model_validate({**ok, "kind": "mating-face"})
    ok_param = {**ok, "spec": {**ok["spec"], "diameter": "param://hole-diameter"}}
    assert str(Interface.model_validate(ok_param).spec.diameter) == "param://hole-diameter"
    assert (
        str(
            Interface.model_validate({**ok, "frames": {"part://a": {"origin": [0, 0, 5]}}})
            .frame_for("part://a")
            .origin[2]
        )
        == "5.0"
    )
    with pytest.raises(ValidationError, match="not one of the parties"):
        Interface.model_validate({**ok, "frames": {"part://zz": {}}})


def test_ecr_state_machine_and_patch_rule():
    e = Ecr.model_validate(
        {"id": "ECR-001", "title": "t", "edits": [{"set": "param://x", "to": "1 mm"}]}
    )
    assert e.can_transition("impact") and not e.can_transition("closed")
    with pytest.raises(ValidationError, match="not a patch"):
        Ecr.model_validate({"id": "ECR-001", "title": "t", "patch": "changes/ECR-001.patch"})
    with pytest.raises(ValidationError, match="needs a selector"):
        Ecr.model_validate(
            {"id": "ECR-001", "title": "t", "edits": [{"set": "req://REQ-001", "to": 1}]}
        )


def test_manifest_operator_signoff_decision():
    m = Manifest.model_validate(
        {"schema": 1, "system": ">=0.1,<0.2", "product": {"id": "kiln", "name": "Kiln"}}
    )
    assert m.schema_version == 1
    with pytest.raises(ValidationError, match="version range"):
        Manifest.model_validate(
            {"schema": 1, "system": "latest", "product": {"id": "kiln", "name": "Kiln"}}
        )
    assert Operator().domains["thermal"] == "novice"
    s = Signoff.model_validate(
        {
            "requirement": "req://REQ-003",
            "by": "x",
            "date": "2026-10-30",
            "statement": "ok",
            "example": True,
        }
    )
    assert s.example
    d = Decision.model_validate(
        {
            "id": "DEC-001",
            "date": "2026-10-30",
            "title": "t",
            "decision": "d",
            "links": ["req://REQ-001"],
        }
    )
    assert str(d.links[0]) == "req://REQ-001"
