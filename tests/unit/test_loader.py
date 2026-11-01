"""Loader and validate: the bracket loads; every invalid fixture fails with its expected text."""

from __future__ import annotations

from pathlib import Path

import pytest

from napkin2factory.core import lint as lint_mod
from napkin2factory.core.errors import ModelError
from napkin2factory.core.loader import load_product, validate
from tests.conftest import EXAMPLES, FIXTURES

INVALID = sorted(p for p in (FIXTURES / "invalid").iterdir() if p.is_dir())


def test_bracket_loads():
    p = load_product(EXAMPLES / "bracket")
    assert p.id == "bracket"
    assert set(p.parts) == {"l-bracket"}
    assert p.parameter_value("envelope-max").to("mm").magnitude == 128
    assert p.select("req://REQ-001#verify.value").to("mm").magnitude == 150
    assert p.select("part://l-bracket#cost.unit").magnitude == 12
    assert p.docs["installation"].anchors == [
        "installation",
        "fixing-to-the-wall",
        "manufacturer-note",
    ]
    assert p.exists("doc://installation#manufacturer-note")


def test_select_props_is_not_declared():
    p = load_product(EXAMPLES / "bracket")
    with pytest.raises(KeyError, match="computed by the build"):
        p.select("part://l-bracket#props.mass")
    with pytest.raises(KeyError, match="does not exist"):
        p.resolve("part://nope")


@pytest.mark.parametrize("fixture", INVALID, ids=[p.name for p in INVALID])
def test_invalid_fixture(fixture: Path):
    # EXPECT: line 1 is the command; line 2 the expected text; any further non-empty
    # lines are additional texts that must all appear in the same run (B-0018).
    kind, *expects = [ln for ln in fixture.joinpath("EXPECT").read_text().split("\n") if ln]
    expect = expects[0]
    product, problems = validate(fixture)
    if kind == "validate":
        assert problems.errors, f"{fixture.name}: expected validate to fail"
        text = "\n".join(p.format() for p in problems.errors) + "\n".join(
            p.rule for p in problems.errors
        )
        for want in expects:
            assert want in text, text
        for p in problems.errors:
            assert p.file and p.message, "every problem names a file and says what is wrong"
    else:
        assert not problems.errors, "\n".join(p.format() for p in problems.errors)
        assert product is not None
        findings = lint_mod.lint(product)
        rules = {p.rule for p in findings.errors}
        assert expect in rules, f"{fixture.name}: lint errors {rules}"


def test_load_product_raises_with_all_problems():
    with pytest.raises(ModelError) as ei:
        load_product(FIXTURES / "invalid" / "bad-uri-target")
    assert "part://missing" in str(ei.value)


def test_expression_and_reference_errors_reported_together():
    """B-0018: a bad reference elsewhere no longer hides expression errors (cycle included)."""
    _, problems = validate(FIXTURES / "invalid" / "expr-and-ref-together")
    rules = [p.rule for p in problems.errors]
    msgs = "\n".join(p.message for p in problems.errors)
    assert "uri" in rules and "expr" in rules
    assert "unknown parameter 'depth'" in msgs
    assert "parameter cycle" in msgs
    assert "part://missing" in msgs


def test_broken_file_does_not_cascade():
    _, problems = validate(FIXTURES / "invalid" / "unknown-key")
    msgs = [p.message for p in problems.errors]
    assert len(msgs) == 1 and "prio" in msgs[0]


def test_bracket_lint_is_clean():
    p = load_product(EXAMPLES / "bracket")
    assert not lint_mod.lint(p).errors


def test_an_asm_party_listed_as_a_port_gets_one_piece_of_advice(tmp_path: Path) -> None:
    """Gate C, C1: the party error says "list it under ports"; no second error says "remove it"."""
    import shutil

    root = tmp_path / "p"
    shutil.copytree(FIXTURES / "invalid" / "iface-asm-party", root)
    pod = root / "model/assemblies/pod.yaml"
    pod.write_text(
        pod.read_text().replace("[iface://clip-rail]", "[iface://clip-rail, iface://pod-mount]")
    )
    _, problems = validate(root)
    text = "\n".join(p.format() for p in problems.errors)
    assert "names asm://pod as a party" in text
    assert "remove iface://pod-mount" not in text, text
