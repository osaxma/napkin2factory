"""v0.5 M5, DoD 6: choices (FOUNDATION F12, F13; S-130).

A check returns ``choice`` only when every option it offers is a valid design; a failure
stays a failure (§7, gate E).  The kiln's first real choice is DEC-022's: the M6 x 16 bolts
meet inside the 25 mm standoffs.  ``n2f check`` never decides; ``n2f decide`` writes a ``DEC-``
entry naming the check, the option and the evidence keys; the row then reads ``pass`` with
its decision, and a changed evidence key reopens it (D25).  Owner text: "a choice", "waiting
on you".
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from napkin2factory.cli.app import app
from napkin2factory.cli.check import render_summary
from napkin2factory.core.build_units import BuildUnits
from napkin2factory.core.checks.choices import (
    ChoiceError,
    Option,
    append_decision,
    choice_blockers,
    decision_entry,
    find_choice,
    offer,
    parse_decision,
    resolve,
)
from napkin2factory.core.checks.hardware import (
    _part_name,
    hardware_checks,
    screw_size,
    spacer_bolt_checks,
    spacer_size,
)
from napkin2factory.core.checks.results import OWNER_WORDS, CheckResult, summarize
from napkin2factory.core.checks.stage import compute_stage
from napkin2factory.core.loader import load_product
from tests.conftest import EXAMPLES, copy_product

KILN_CHOICE = "fastening://m6-standoff-25/m6x16-bolt"
CHOICE = "fastening://m4-spacer/m4x10-screw"


def _spacer_product(
    dst: Path, spacer_mm: float = 10, screw: str = "M4 x 10", thread: int = 4, git: bool = False
) -> Path:
    """The enclosure with a spacer between lid and base and a screw into each end of it."""
    root = copy_product(EXAMPLES / "enclosure", dst, git=False)
    (root / "model/parts/m4-spacer.yaml").write_text(
        "id: m4-spacer\nrev: A\n"
        f"name: M{thread} female-female hex spacer, {spacer_mm} mm, steel\n"
        "kind: cots\nprocess: none\ngeometry: none\n"
        "source: {vendor: Example, mpn: SP-1}\n"
        "cost: {unit: 0.30 USD, basis: estimate}\n",
        encoding="utf-8",
    )
    screw_yaml = root / "model/parts/m4x10-screw.yaml"
    text = screw_yaml.read_text(encoding="utf-8")
    screw_yaml.write_text(
        text.replace("name: M4 x 10 pan-head screw", f"name: {screw} pan-head screw"),
        encoding="utf-8",
    )
    iface = root / "model/interfaces/lid-base-mount.yaml"
    iface.write_text(
        iface.read_text(encoding="utf-8").replace(
            "fastener: part://m4x10-screw",
            "hardware: [{part: part://m4-spacer, per_hole: 1}, "
            "{part: part://m4x10-screw, per_hole: 2}]",
        ),
        encoding="utf-8",
    )
    asm = root / "model/assemblies/enclosure.yaml"
    asm.write_text(
        asm.read_text(encoding="utf-8").replace(
            "  - {part: part://m4x10-screw, qty: 4}",
            "  - {part: part://m4x10-screw, qty: 8}\n  - {part: part://m4-spacer, qty: 4}",
        ),
        encoding="utf-8",
    )
    if git:
        from napkin2factory.core.vcs import Vcs

        v = Vcs(root)
        v.init()
        v.snapshot("Start")
    return root


def _row(rows: list[CheckResult], rid: str) -> CheckResult:
    return next(r for r in rows if r.id == rid)


def _checked(root: Path) -> list[CheckResult]:
    """The hardware stage's rows with the engine's choice handling (no build needed)."""
    product = load_product(root)
    rows = hardware_checks(product, BuildUnits(product))
    resolve(product, root / "build", rows)
    return rows


# ---- the kiln's choice (DoD 6) ------------------------------------------------------------


def test_kiln_offers_the_bolt_length_choice() -> None:
    """DEC-022 as a rule: both fixes valid, with hardware counts; it holds the release."""
    product = load_product(EXAMPLES / "kiln")
    rows = spacer_bolt_checks(product)
    row = _row(rows, KILN_CHOICE)
    assert row.status == "choice" and row.detail["blocks"] == "release"
    assert "14.8 + 15.0 = 29.8 mm of bolt in 25 mm" in row.message
    assert "14.5 + 15.0 = 29.5 mm" in row.message  # the door's tray is 1.5 mm
    assert len(row.detail["joints"]) == 4
    opts = {o["id"]: o for o in row.detail["options"]}
    assert list(opts) == ["shorter-bolts", "through-bolt"]
    assert opts["shorter-bolts"]["summary"].endswith("M6 x 12")
    assert opts["shorter-bolts"]["what_it_takes"].startswith(
        "32 M6 x 12 bolts in place of the 32 M6 x 16 bolts"
    )
    assert "16 M6 x 35 bolts and 16 M6 nuts" in opts["through-bolt"]["what_it_takes"]
    assert opts["through-bolt"]["cost_delta"].startswith("about -4.80 USD (estimate")
    # the controller's 40 mm standoffs take the same bolts and are fine (DEC-022)
    assert _row(rows, "fastening://m6-standoff-40/m6x16-bolt").status == "pass"
    # the four hardware counts are untouched (kind "hardware" stays three rows)
    counts = [r for r in hardware_checks(product) if r.kind == "hardware"]
    assert {r.id: r.status for r in counts} == dict.fromkeys(
        ("hardware://controls", "hardware://door", "hardware://kiln"), "pass"
    )


@pytest.mark.parametrize("name", ["bracket", "enclosure"])
def test_no_choice_where_no_bolt_meets_a_spacer(name: str) -> None:
    """The rule does not apply to the golden products: they gain no row."""
    product = load_product(EXAMPLES / name)
    assert spacer_bolt_checks(product) == []


def test_sizes_from_names() -> None:
    assert screw_size("M6 x 16 socket-head cap screw") == (6.0, 16.0)
    assert screw_size("M4×10 pan head") == (4.0, 10.0)
    assert screw_size("Hex nut") is None
    assert spacer_size("M6 female-female hex standoff, 25 mm, steel") == (6.0, 25.0)
    assert spacer_size("M6 x 16 socket-head cap screw") is None  # a bolt is not a spacer


# ---- a failure stays a failure (§7, gate E) ----------------------------------------------


def test_choice_with_two_valid_fixes(tmp_path: Path) -> None:
    rows = _checked(_spacer_product(tmp_path / "p"))
    row = _row(rows, CHOICE)
    assert row.status == "choice"
    assert [o["id"] for o in row.detail["options"]] == ["shorter-bolts", "through-bolt"]
    assert row.detail["options"][0]["summary"].endswith("M4 x 6")
    assert row.detail["options"][1]["summary"].endswith("M4 x 20")
    assert set(row.evidence_keys) >= {
        "iface://lid-base-mount",
        "part://m4x10-screw",
        "part://m4-spacer",
        "param://sheet-thickness",
        "param://lid-thickness",
    }


def test_one_valid_fix_is_a_failure_naming_it(tmp_path: Path) -> None:
    """A 4 mm spacer: no shorter screw both stays apart and engages 4 mm, so only one fix."""
    row = _row(_checked(_spacer_product(tmp_path / "p", spacer_mm=4)), CHOICE)
    assert row.status == "fail"
    assert "The one fix that works: one bolt right through each spacer" in row.message
    assert row.detail["fix"]["id"] == "through-bolt" and "options" not in row.detail
    assert row.detail["not_offered"][0]["id"] == "shorter-bolts"


def test_no_valid_fix_is_a_failure(tmp_path: Path) -> None:
    """An M7 thread: no nut height is known and no shorter screw engages enough."""
    root = _spacer_product(tmp_path / "p", spacer_mm=4, screw="M7 x 10", thread=7)
    row = _row(_checked(root), "fastening://m4-spacer/m4x10-screw")
    assert row.status == "fail" and "No fix this check knows works" in row.message


def test_long_enough_spacer_passes(tmp_path: Path) -> None:
    row = _row(_checked(_spacer_product(tmp_path / "p", spacer_mm=25)), CHOICE)
    assert row.status == "pass" and "stay 8.0 mm or more apart" in row.message


def test_offer_only_with_two_valid_options() -> None:
    def res() -> CheckResult:
        return CheckResult(id="x://a", subject="part://a", status="pass", message="")

    a = Option("a", "do a", "it takes a")
    b = Option("b", "do b", "it takes b")
    bad = Option("c", "do c", "", invalid="does not fit")
    assert offer(res(), [a, b], blocks="verify", problem="P.").status == "choice"
    one = offer(res(), [a, bad], blocks="verify", problem="P.")
    assert one.status == "fail" and one.detail["fix"]["id"] == "a"
    with pytest.raises(ValueError):
        offer(res(), [a, b], blocks="sometime", problem="P.")


def test_a_rule_pack_choice_lifts_its_options_and_needs_two(tmp_path: Path) -> None:
    """A rule-pack check (``severity: choice``) says its options in its violation."""
    product = load_product(EXAMPLES / "bracket")
    opts = [
        {"id": "a", "summary": "do a", "what_it_takes": "x"},
        {"id": "b", "summary": "do b", "what_it_takes": "y"},
    ]
    two = CheckResult(
        id="rule://p/r@l-bracket",
        subject="part://l-bracket",
        status="choice",
        message="m",
        kind="rule",
        detail={"violations": [{"options": opts, "blocks": "verify"}]},
    )
    one = CheckResult(
        id="rule://p/s@l-bracket",
        subject="part://l-bracket",
        status="choice",
        message="m",
        kind="rule",
        detail={"violations": [{"options": opts[:1]}]},
    )
    resolve(product, tmp_path / "build", [two, one])
    assert two.status == "choice" and two.detail["blocks"] == "verify"
    assert two.detail["options"] == opts and set(two.evidence_keys) == {"part://l-bracket"}
    assert one.status == "fail" and "without two designs" in one.message


# ---- decided, then reopened (D25) --------------------------------------------------------


def test_decided_reads_pass_and_an_evidence_change_reopens_it(tmp_path: Path) -> None:
    root = _spacer_product(tmp_path / "p")
    product = load_product(root)
    row = _row(_checked(root), CHOICE)
    entry = decision_entry(product, row.to_dict(), "shorter-bolts", "Ada", note="cheapest")
    assert entry["id"] == "DEC-003" and entry["made_by"] == "human"
    assert entry["sources"][0] == f"choice {CHOICE}: option shorter-bolts, chosen by Ada"
    append_decision(product.paths.decisions, entry)
    product = load_product(root)
    rec = parse_decision(product.decisions["DEC-003"])
    assert rec is not None and rec.evidence_keys == row.evidence_keys
    decided = _row(_checked(root), CHOICE)
    assert decided.status == "pass"
    assert decided.detail["decision"] == {"id": "DEC-003", "option": "shorter-bolts", "by": "Ada"}
    assert decided.message.startswith("decided in DEC-003: shorter bolts at both ends: M4 x 6")
    # a changed evidence key reopens it, exactly like a sign-off
    params = root / "model/parameters.yaml"
    text = params.read_text(encoding="utf-8")
    params.write_text(
        text.replace("lid-thickness:     {value: 1.5", "lid-thickness:     {value: 2.0"),
        encoding="utf-8",
    )
    reopened = _row(_checked(root), CHOICE)
    assert reopened.status == "choice"
    assert reopened.detail["reopened"]["changed"] == ["param://lid-thickness"]
    assert reopened.message.startswith("reopened: lid-thickness changed since DEC-003")
    # the designer applies the pick: the rule passes on the model itself, no decision needed
    params.write_text(text, encoding="utf-8")
    screw = root / "model/parts/m4x10-screw.yaml"
    screw.write_text(
        screw.read_text(encoding="utf-8").replace("M4 x 10 pan", "M4 x 6 pan"), encoding="utf-8"
    )
    applied = _row(_checked(root), CHOICE)
    assert applied.status == "pass" and "decision" not in applied.detail


def test_decide_refuses_what_it_cannot_record(tmp_path: Path) -> None:
    root = _spacer_product(tmp_path / "p")
    product = load_product(root)
    row = _row(_checked(root), CHOICE).to_dict()
    with pytest.raises(ChoiceError, match="not an option"):
        decision_entry(product, row, "glue", "Ada")
    with pytest.raises(ChoiceError, match="owner's to decide"):
        decision_entry(product, row, "shorter-bolts", "agent", agent=True)
    with pytest.raises(ChoiceError, match="no check"):
        find_choice([row], "nothing://here")
    assert find_choice([row], "m4-spacer/m4x10-screw") is row
    done = {**row, "status": "pass", "detail": {"decision": {"id": "DEC-009"}}}
    with pytest.raises(ChoiceError, match="already decided"):
        find_choice([done], CHOICE)


# ---- the gates and the owner's words ------------------------------------------------------


def test_choice_blockers_name_their_gate(tmp_path: Path) -> None:
    build = tmp_path / "build"
    (build / "checks").mkdir(parents=True)
    opts = [{"id": "a", "summary": "a", "what_it_takes": "x"}, {"id": "b", "summary": "b"}]
    rows: list[dict[str, Any]] = [
        {"id": f"x://{g}", "title": f"T {g}", "status": "choice", "blocks": g, "options": opts}
        for g in ("design", "verify", "release", "none")
    ]
    rows.append({"id": "x://done", "status": "pass", "blocks": "design", "decision": "DEC-001"})
    (build / "checks/choices.json").write_text(json.dumps(rows), encoding="utf-8")
    held = choice_blockers(build)
    assert sorted(held) == ["design", "released", "verify"]
    assert held["design"] == [
        'a choice is waiting on you: T design — `n2f decide x://design --pick a | b --by "<name>"`'
    ]


def test_owner_words() -> None:
    assert OWNER_WORDS["choice"] == "a choice waiting on you"
    rows = [CheckResult(id="x://a", subject="s", status="choice", message="m")]
    assert summarize(rows)["choice"] == 1
    assert "1 choice waiting on you" in render_summary(summarize(rows), "owner")
    assert "2 choices waiting on you" in render_summary({"choice": 2}, "engineer")


def test_a_stub_party_is_named_not_its_uri() -> None:
    """B-0082 (S-127): the hardware row says a ``build: external`` stub by its name."""
    product = load_product(EXAMPLES / "enclosure")
    assert _part_name(product, "asm://enclosure") == "Enclosure with lid and wall brackets"
    assert _part_name(product, "part://lid") == "Lid"


# ---- the commands, end to end on a built product -----------------------------------------


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = _spacer_product(tmp_path_factory.mktemp("choice") / "p", git=True)
    runner = CliRunner()
    before = (root / "model/decisions.yaml").read_bytes()
    r = runner.invoke(app, ["check", "--dir", str(root)])
    assert "choice waiting on you" in r.output, r.output
    # `n2f check` never writes a decision
    assert (root / "model/decisions.yaml").read_bytes() == before
    return root


def test_status_lists_the_choice_under_waiting_on_you(built: Path) -> None:
    runner = CliRunner()
    out = runner.invoke(app, ["status", "--dir", str(built)], env={"COLUMNS": "200"}).output
    assert "Waiting on you: 1 choice" in out
    assert "(it holds the release)" in out
    assert "1. shorter bolts at both ends: M4 x 6 — 8 M4 x 6 bolts" in out
    assert f"n2f decide {CHOICE} --pick shorter-bolts | through-bolt" in out
    data = json.loads(runner.invoke(app, ["status", "--dir", str(built), "--json"]).output)
    assert [c["id"] for c in data["waiting_on_you"]] == [CHOICE]
    released = next(g for g in data["gates"] if g["name"] == "released")
    assert any(b.startswith("a choice is waiting on you: ") for b in released["blockers"])
    choices = json.loads((built / "build/checks/choices.json").read_text())
    assert [(c["id"], c["status"], c["decision"]) for c in choices] == [(CHOICE, "choice", None)]


def test_a_choice_that_holds_design_blocks_the_design_gate(built: Path) -> None:
    path = built / "build/checks/choices.json"
    saved = path.read_text()
    data = json.loads(saved)
    data[0]["blocks"] = "design"
    path.write_text(json.dumps(data))
    try:
        design = compute_stage(load_product(built)).gates[1]
        assert design.name == "design" and not design.ok
        assert any("a choice is waiting on you" in b for b in design.blockers)
    finally:
        path.write_text(saved)


def test_decide_records_a_decision_and_the_row_reads_pass(built: Path) -> None:
    runner = CliRunner()
    r = runner.invoke(
        app,
        ["decide", CHOICE, "--pick", "through-bolt", "--by", "Ada", "--dir", str(built), "--json"],
    )
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert out["status"] == "pass" and out["decision"]["id"] == "DEC-003"
    dec = load_product(built).decisions["DEC-003"]
    assert dec.made_by == "human" and dec.title.endswith(
        "one bolt right through each spacer, with a nut: M4 x 20"
    )
    rec = parse_decision(dec)
    assert rec is not None and rec.option == "through-bolt" and rec.by == "Ada"
    choices = json.loads((built / "build/checks/choices.json").read_text())
    assert [(c["status"], c["decision"]) for c in choices] == [("pass", "DEC-003")]
    status = runner.invoke(app, ["status", "--dir", str(built)], env={"COLUMNS": "200"}).output
    assert "Waiting on you" not in status
    again = runner.invoke(
        app, ["decide", CHOICE, "--pick", "through-bolt", "--by", "Ada", "--dir", str(built)]
    )
    assert again.exit_code != 0 and "already decided (DEC-003)" in again.output
