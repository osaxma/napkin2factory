"""B-0033: one reading of "the stage" for people (the first gate not complete).

``StageReport.current`` drives the ``n2f status`` headline, the report badge and
``n2f ecr close``; ``--json`` carries it as ``current_stage`` next to the older ``stage``
(the last gate passed).
"""

from __future__ import annotations

from napkin2factory.core.checks.stage import STAGE_WORDS, Gate, StageReport

EXAMPLE = ["replace the 1 example sign-off (not a review) with a real one"]


def _report(stage: str, *gates: Gate) -> StageReport:
    return StageReport(stage=stage, gates=list(gates), next_step="next")


def _gates(intake: bool, design: bool, verify: Gate, released: bool) -> list[Gate]:
    return [
        Gate("intake", intake, [] if intake else ["x"]),
        Gate("design", design, [] if design else ["x"]),
        verify,
        Gate("released", released, [] if released else ["no Revision"]),
    ]


def test_current_is_the_first_gate_not_complete() -> None:
    open_verify = Gate("verify", False, ["checks have not run"])
    rep = _report("intake", *_gates(True, False, open_verify, False))
    assert rep.current == rep.headline == "design" and rep.stage == "intake"
    rep = _report("design", *_gates(True, True, open_verify, False))
    assert rep.current == "verify"
    rep = _report("verify", *_gates(True, True, Gate("verify", True), False))
    assert rep.current == "ready" and rep.current_words == "ready to release"
    rep = _report("released", *_gates(True, True, Gate("verify", True), True))
    assert rep.current == "released"
    napkin = Gate("napkin", False, ["1 concept exploring, none chosen yet"])
    assert _report("napkin", napkin, *_gates(False, False, open_verify, False)).current == "napkin"


def test_example_signoffs_keep_verify_until_a_demonstration_revision() -> None:
    held = Gate("verify", False, [], caveats=EXAMPLE)
    assert held.open_only_by_caveats
    assert _report("verify", *_gates(True, True, held, False)).current == "verify"
    # released with --allow-example-signoffs: a Revision is a Revision
    assert _report("released", *_gates(True, True, held, True)).current == "released"


def test_json_keeps_stage_and_adds_current_stage() -> None:
    rep = _report("intake", *_gates(True, False, Gate("verify", False, ["x"]), False))
    data = rep.to_dict()
    assert list(data) == ["stage", "current_stage", "gates", "next_step"]
    assert (data["stage"], data["current_stage"]) == ("intake", "design")


def test_every_current_value_has_owner_words() -> None:
    assert set(STAGE_WORDS) == {"napkin", "intake", "design", "verify", "ready", "released"}
