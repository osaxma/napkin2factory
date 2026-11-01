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
    UNAPPLIED,
    ChoiceError,
    Option,
    append_decision,
    choice_blockers,
    decision_entry,
    find_choice,
    offer,
    parse_decision,
    pick_option,
    resolve,
    write_choices,
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
        'source: {vendor: Example, mpn: SP-1, url: "https://example.com/sp-1"}\n'
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
    units = BuildUnits(product)
    rows = hardware_checks(product, units) + spacer_bolt_checks(product, units)
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
    # gate F, concern 11: one name for the part, the sums explained, plain thread words
    assert (
        row.title
        == "Bolts into both ends of each spacer (M6 female-female hex standoff, 25 mm, steel)"
    )
    assert "the two bolts reach 14.5 and 15.0 mm into the spacer" in row.message
    assert "its 16 mm less the sheet it passes through" in row.message
    assert "standoff" not in row.message and "standoff" not in str(row.detail["options"])
    assert len(row.detail["joints"]) == 4
    opts = {o["id"]: o for o in row.detail["options"]}
    assert list(opts) == ["shorter-bolts", "through-bolt"]
    assert opts["shorter-bolts"]["summary"].endswith("M6 x 12")
    assert opts["shorter-bolts"]["what_it_takes"].startswith(
        "32 M6 x 12 bolts in place of the 32 M6 x 16 bolts"
    )
    shorter = opts["shorter-bolts"]["what_it_takes"]
    assert "each bolt goes 10.5 to 11.0 mm into the spacer" in shorter
    assert "threaded all the way through" in shorter and "tapped" not in shorter
    assert "does not say how deep the listed spacer's thread goes" in shorter
    assert "16 M6 x 35 bolts and 16 M6 nuts" in opts["through-bolt"]["what_it_takes"]
    assert "tapped" not in opts["through-bolt"]["what_it_takes"]
    assert opts["through-bolt"]["cost_delta"].startswith("about 4.80 USD less (estimate")
    # the controller's 40 mm standoffs take the same bolts and are fine (DEC-022)
    assert _row(rows, "fastening://m6-standoff-40/m6x16-bolt").status == "pass"
    # the hardware counts are untouched (still three rows, all of kind "hardware")
    counts = hardware_checks(product)
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
    # gate F, concern 12: runnable as printed (no `a | b`), by number
    assert held["design"] == [
        'a choice is waiting on you: T design — `n2f decide x://design --pick 1 --by "<your '
        'name>"` for a, or `--pick 2` for b'
    ]


def test_a_decided_pick_not_yet_made_holds_the_release(tmp_path: Path) -> None:
    """Gate E B3, gate F blocker 1 (S-139): decided but not in the model holds the release.

    A pick that holds nothing (``blocks: none``) does not.
    """
    build = tmp_path / "build"
    (build / "checks").mkdir(parents=True)
    opts = [{"id": "a", "summary": "do a", "what_it_takes": "x"}, {"id": "b", "summary": "b"}]
    rows: list[dict[str, Any]] = [
        {
            "id": f"x://{g}",
            "title": f"T {g}",
            "status": "pass",
            "blocks": g,
            "options": opts,
            "decision": "DEC-007",
            "decided": {"id": "DEC-007", "option": "a", "by": "Ada"},
        }
        for g in ("design", "none")
    ]
    (build / "checks/choices.json").write_text(json.dumps(rows), encoding="utf-8")
    held = choice_blockers(build)
    assert held == {
        "released": [
            f"{UNAPPLIED}: T design — you chose do a (DEC-007), but the design and its parts "
            "list do not show it yet; your agent makes the change (x), then builds and checks"
        ]
    }


def test_the_option_number_picks_it() -> None:
    """Gate F, concern 12: ``--pick 1`` is the first option `n2f status` lists."""
    row = {"id": "x://a", "detail": {"options": [{"id": "a"}, {"id": "b"}]}}
    assert pick_option(row, "2") == "b" and pick_option(row, "a") == "a"
    with pytest.raises(ChoiceError, match=r"by its number or id: 1 \(a\), 2 \(b\)"):
        pick_option(row, "3")


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
    # gate F, concern 12: one runnable line per option, on one line
    for o in ("shorter-bolts", "through-bolt"):
        assert f'to pick it: n2f decide {CHOICE} --pick {o} --by "<your name>"\n' in out
    assert "|" not in out.split("Waiting on you")[1]
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


def test_release_refuses_an_open_choice_that_holds_it(built: Path) -> None:
    """B-0092 (S-133): ``n2f release`` names the choice and the command that records it."""
    from napkin2factory.ecr.release import gate_blockers

    blockers = gate_blockers(load_product(built))
    assert [b for b in blockers if b.startswith("a choice is waiting on you: ")] == [
        "a choice is waiting on you: Bolts into both ends of each spacer (M4 female-female hex "
        f'spacer, 10 mm, steel) — `n2f decide {CHOICE} --pick 1 --by "<your name>"` for shorter '
        "bolts at both ends: M4 x 6, or `--pick 2` for one bolt right through each spacer, with "
        "a nut: M4 x 20"
    ]
    r = CliRunner().invoke(
        app,
        ["release", "v1.0.0", "--dry-run", "--no-render", "--allow-example-signoffs"]
        + ["--dir", str(built)],
        env={"COLUMNS": "200"},
    )
    assert r.exit_code == 3, r.output
    assert "a choice is waiting on you" in r.output and f"n2f decide {CHOICE}" in r.output


def test_the_report_lists_what_is_waiting_on_you(built: Path) -> None:
    """B-0093 (S-133): owner words for a choice row and the open choices with their options."""
    from napkin2factory.report.builder import VOCAB, gather, render_report

    assert VOCAB["owner"]["choice"] == "a choice waiting on you"
    product = load_product(built)
    waiting = gather(product, built / "build", "today")["waiting"]
    assert [(c["id"], c["holds"]) for c in waiting] == [(CHOICE, "it holds the release")]
    assert [o["id"] for o in waiting[0]["options"]] == ["shorter-bolts", "through-bolt"]
    assert "Two ways to fix it" not in waiting[0]["found"]
    html = render_report(product, built / "build", "today")
    assert "<h3>Waiting on you: 1 choice</h3>" in html
    assert "shorter bolts at both ends: M4 x 6 — 8 M4 x 6 bolts" in html
    for o in ("shorter-bolts", "through-bolt"):  # gate F, concern 12: runnable, per option
        assert f'n2f decide {CHOICE} --pick {o} --by "&lt;your name&gt;"' in html
    assert 'title="choice">a choice waiting on you</span>' in html  # the rule row's badge


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
    # gate F, concern 13: what happens next, and who does it
    assert out["next"].startswith("your agent makes the change: 4 M4 x 20 bolts")
    assert out["next"].endswith("until then the design stays open and the release waits for it")
    choices = json.loads((built / "build/checks/choices.json").read_text())
    assert [(c["status"], c["decision"]) for c in choices] == [("pass", "DEC-003")]
    status = runner.invoke(app, ["status", "--dir", str(built)], env={"COLUMNS": "200"}).output
    assert "Waiting on you" not in status
    again = runner.invoke(
        app, ["decide", CHOICE, "--pick", "through-bolt", "--by", "Ada", "--dir", str(built)]
    )
    assert again.exit_code != 0 and "already decided (DEC-003)" in again.output


def test_a_decided_choice_not_yet_applied_holds_the_release(built: Path) -> None:
    """Gate E B3, gate F blocker 1 (S-139); was B-0095's "the release is not held" (S-133).

    The row reads ``pass``; the Design gate says the change is still to make, and the
    release is held until the rule passes on the model itself.  One refusal lists every
    reason (gate F, concern 14).  Runs after the decide test above (same module fixture).
    """
    from napkin2factory.ecr.release import gate_blockers
    from napkin2factory.report.builder import gather

    product = load_product(built)
    rep = compute_stage(product)
    design = next(g for g in rep.gates if g.name == "design")
    assert not design.ok and design.blockers == [] and design.open_only_by_caveats
    assert design.caveats == [
        "Bolts into both ends of each spacer (M4 female-female hex spacer, 10 mm, steel): "
        "decided in DEC-003 (one bolt right through each spacer, with a nut: M4 x 20), not yet "
        "in the design — your agent makes the change: 4 M4 x 20 bolts and 4 M4 nuts in place "
        "of the 8 " + design.caveats[0].split("in place of the 8 ", 1)[1]
    ]
    held = [b for b in gate_blockers(product) if b.startswith(UNAPPLIED)]
    assert held == [
        f"{UNAPPLIED}: Bolts into both ends of each spacer (M4 female-female hex spacer, 10 mm, "
        "steel) — you chose one bolt right through each spacer, with a nut: M4 x 20 (DEC-003), "
        "but the design and its parts list do not show it yet; your agent makes the change "
        "(4 M4 x 20 bolts and 4 M4 nuts in place of the 8 "
        + held[0].split("in place of the 8 ", 1)[1]
    ]
    assert rep.current == "design" and rep.next_step == held[0]
    assert gather(product, built / "build", "today")["waiting"] == []
    # the refusal: the pick, the missing sign-off and nothing tagged, in one message
    r = CliRunner().invoke(
        app, ["release", "v1.0.0", "--no-render", "--dir", str(built)], env={"COLUMNS": "200"}
    )
    assert r.exit_code == 3, r.output
    assert "you chose one bolt right through each spacer" in r.output
    assert "your agent makes the change" in r.output and "needs a human sign-off" in r.output


def test_the_pick_made_releases_with_the_released_report(built: Path) -> None:
    """Applied, the rule passes on the model and the release goes through (S-139).

    Gate F blocker 2: the package's ``report.html`` is the released one, not the draft; and
    the cover says the Revision is a demonstration and lists the choice made (concern 17).
    """
    import zipfile

    from napkin2factory.core.vcs import Vcs

    runner = CliRunner()
    # the agent makes DEC-003's pick: one M4 x 20 bolt right through each spacer, with a nut
    model = built / "model"
    (model / "parts/m4-nut.yaml").write_text(
        "id: m4-nut\nrev: A\nname: M4 hex nut\nkind: cots\nprocess: none\ngeometry: none\n"
        'source: {vendor: Example, mpn: NUT-4, url: "https://example.com/nut-4"}\n'
        "cost: {unit: 0.05 USD, basis: estimate}\n",
        encoding="utf-8",
    )
    _swap(model / "parts/m4x10-screw.yaml", "M4 x 10 pan", "M4 x 20 pan")
    _swap(
        model / "interfaces/lid-base-mount.yaml",
        "{part: part://m4x10-screw, per_hole: 2}",
        "{part: part://m4x10-screw, per_hole: 1}, {part: part://m4-nut, per_hole: 1}",
    )
    _swap(
        model / "assemblies/enclosure.yaml",
        "  - {part: part://m4x10-screw, qty: 8}\n",
        "  - {part: part://m4x10-screw, qty: 4}\n  - {part: part://m4-nut, qty: 4}\n",
    )
    Vcs(built).snapshot("the agent makes the pick: M4 x 20 through each spacer")
    r = runner.invoke(app, ["check", "--dir", str(built)])
    assert r.exit_code == 0, r.output
    assert compute_stage(load_product(built)).gates[1].caveats == []
    assert not (built / "build/checks/choices.json").is_file()  # the rule passes on the model
    r = runner.invoke(
        app,
        ["signoff", "REQ-004", "--by", "Example Reviewer", "--statement", "Edges checked."]
        + ["--example", "--dir", str(built)],
    )
    assert r.exit_code == 0, r.output
    # without the demonstration flag: the example sign-off is the one reason left
    r = runner.invoke(app, ["release", "v1.0.0", "--no-render", "--dir", str(built)])
    assert r.exit_code == 3 and "REQ-004 (" in r.output and "EXAMPLES" in r.output
    r = runner.invoke(
        app,
        ["release", "v1.0.0", "--no-render", "--allow-example-signoffs", "--dir", str(built)],
    )
    assert r.exit_code == 0, r.output
    with zipfile.ZipFile(built / "build/release/enclosure-v1.0.0.zip") as zf:
        report = zf.read("v1.0.0/report.html").decode("utf-8")
        cover = zf.read("v1.0.0/README.txt").decode("utf-8")
        record = json.loads(zf.read("v1.0.0/release.json"))
    assert "Released v1.0.0" in report and "no Revision for the current snapshot" not in report
    assert cover.index("DEMONSTRATION") < cover.index("Contents:")
    assert "EXAMPLE sign-offs, which are not reviews, for: REQ-004 (" in cover
    assert "Choices made:\n- Bolts into both ends of each spacer" in cover
    assert "(DEC-003, chosen by Ada)" in cover
    assert record["example_signoffs"] == ["REQ-004"]
    assert record["choices"] == [
        {"check": CHOICE, "decision": "DEC-003", "option": "through-bolt", "by": "Ada"}
    ]


# ---- the kiln's pick (gate E B3, kiln-shaped) ---------------------------------------------


def apply_shorter_bolts(root: Path) -> None:
    """Make the kiln's "shorter bolts" pick in the model, as ``demo.sh`` does (S-139).

    A new M6 x 12 bolt on the parts list; the joints that put a bolt into each end of a 25 mm
    spacer take it; the units' quantities move with them.
    """
    model = root / "model"
    (model / "parts/m6x12-bolt.yaml").write_text(
        "id: m6x12-bolt\nrev: A\nname: M6 x 12 socket-head cap screw\nkind: cots\n"
        "process: none\ngeometry: none\n"
        "source: {vendor: McMaster-Carr, mpn: ISO 4762 M6 x 12, verified: false}\n"
        "cost: {unit: 0.40 USD, basis: estimate, note: priced like the M6 x 16}\n",
        encoding="utf-8",
    )
    for name in ("guard-standoff-top", "guard-standoff-left", "guard-standoff-right"):
        _swap(
            model / f"interfaces/{name}.yaml", "m6x16-bolt, per_hole: 2", "m6x12-bolt, per_hole: 2"
        )
    _swap(
        model / "interfaces/door-guard-standoff.yaml",
        "m6x16-bolt, per_hole: 2",
        "m6x12-bolt, per_hole: 2",
    )
    _swap(
        model / "assemblies/kiln.yaml",
        "  - {part: part://m6x16-bolt, qty: 38}\n",
        "  - {part: part://m6x16-bolt, qty: 14}\n  - {part: part://m6x12-bolt, qty: 24}\n",
    )
    _swap(model / "assemblies/door.yaml", "m6x16-bolt, qty: 8}", "m6x12-bolt, qty: 8}")


def _swap(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, (path, old)
    path.write_text(text.replace(old, new), encoding="utf-8")


def _kiln_choices(root: Path) -> dict[str, list[str]]:
    """The kiln's spacer rows, resolved and written as ``n2f check`` would; the gate blockers."""
    product = load_product(root)
    rows = spacer_bolt_checks(product) + hardware_checks(product)
    resolve(product, root / "build", rows)
    write_choices(root / "build", [r.to_dict() for r in rows])
    return choice_blockers(root / "build")


def test_the_kiln_release_waits_for_the_pick_to_be_made(tmp_path: Path) -> None:
    """Gate E B3 on the kiln: decided "shorter bolts", the release waits until the model has it."""
    root = copy_product(EXAMPLES / "kiln", tmp_path / "kiln", git=False)
    assert [b.split(":", 1)[0] for b in _kiln_choices(root)["released"]] == [
        "a choice is waiting on you"
    ]
    product = load_product(root)
    row = _row(spacer_bolt_checks(product), KILN_CHOICE)
    resolve(product, root / "build", [row])
    entry = decision_entry(product, row.to_dict(), "1", "Owner")  # the option's number
    append_decision(product.paths.decisions, entry)
    held = _kiln_choices(root)["released"]
    assert held == [
        f"{UNAPPLIED}: Bolts into both ends of each spacer (M6 female-female hex standoff, "
        f"25 mm, steel) — you chose shorter bolts at both ends: M6 x 12 ({entry['id']}), but the "
        "design and its parts list do not show it yet; your agent makes the change (32 M6 x 12 "
        "bolts in place of the 32 M6 x 16 bolts " + held[0].split("M6 x 16 bolts ", 1)[1]
    ]
    apply_shorter_bolts(root)
    assert _kiln_choices(root) == {}
    product = load_product(root)
    rows = {r.id: r for r in spacer_bolt_checks(product) + hardware_checks(product)}
    assert KILN_CHOICE not in rows
    assert rows["fastening://m6-standoff-25/m6x12-bolt"].status == "pass"
    assert rows["fastening://m6-standoff-40/m6x16-bolt"].status == "pass"
    assert {k: r.status for k, r in rows.items() if k.startswith("hardware://")} == dict.fromkeys(
        ("hardware://controls", "hardware://door", "hardware://kiln"), "pass"
    )
