"""Judge a product folder against a benchmark's expected outcomes (W9, road-to-v1.0 section 4.2).

    uv run python -m tests.benchmarks.oracle <product_dir> <oracle.yaml> [--json] [--no-build]

Runs the n2f commands the oracle's rows need in ``product_dir`` (``--no-build`` trusts the
``build/`` already there and does not re-screen the concept cards), prints PASS or FAIL for
each row with the value found, and exits 0 when all pass, 1 when any fails, 2 when the oracle
or the product cannot be read. The same code judges the shipped example in CI and a cold
agent's own product in a trial; no row names an id (``README.md`` in this folder).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from tests.benchmarks import oracle_change
from tests.benchmarks.oracle_evidence import Evidence, EvidenceError
from tests.benchmarks.oracle_match import (
    Found,
    MatchError,
    assign,
    convert,
    describe,
    expectation,
    failing_categories,
    impact_value,
    judge,
    matches,
    number_and_unit,
    number_ok,
    pick_card,
    requirement_rows,
    requirement_values,
    result_value,
    rollup_value,
    screen_row,
    screen_values,
)
from tests.benchmarks.oracle_schema import Concepts, Fact, Figure, Oracle, load_oracle

FIGURE_TOL = 0.05  # a figure without its own tol: the spec's usual +-5 %


@dataclass
class Row:
    """One judged assertion."""

    group: str
    what: str
    passed: bool
    found: str
    expected: str


def _row(group: str, what: str, passed: bool, found: str, expected: str) -> Row:
    return Row(group, what, passed, found, expected)


def _guard(group: str, what: str, expected: str, fn: Any) -> Row:
    """Run a judging function; a matcher that finds nothing or too much is a FAIL row."""
    try:
        passed, found = fn()
        return _row(group, what, passed, found, expected)
    except (MatchError, EvidenceError, KeyError, ValueError) as exc:
        return _row(group, what, False, f"not judged: {exc}", expected)


# --- concepts ----------------------------------------------------------------------------


def judge_concepts(c: Concepts, ev: Evidence, extra: Any) -> list[Row]:
    """The napkin stage: one promoted card, and each other card rejected for its reason."""
    try:
        cards = ev.cards()
    except EvidenceError as exc:
        return [_row("concept", "the concept cards", False, f"not judged: {exc}", "")]
    rows = [
        _row(
            "concept",
            "problems building the cards",
            not ev.problems,
            "; ".join(ev.problems) or "none",
            "none",
        )
    ]
    if c.count is not None:
        rows.append(
            _row("concept", "number of cards", len(cards) == c.count, str(len(cards)), str(c.count))
        )
    promoted = [x for x in cards if x.status == "promoted"]
    rows.append(
        _row("concept", "exactly one card is promoted", len(promoted) == 1, str(len(promoted)), "1")
    )
    if len(promoted) == 1:
        p = promoted[0]
        sel = c.promoted.model_copy(update={"status": "promoted"})
        rows.append(
            _row(
                "concept",
                f"the promoted card is {describe(sel)}",
                matches(p, sel, extra),
                _card_words(p, extra),
                describe(sel),
            )
        )
        if c.promoted_has_no_failure:
            bad = [r.get("title", "") for r in p.rules if r.get("status") == "fail"]
            rows.append(
                _row(
                    "concept",
                    "the promoted card passes every screening check",
                    not bad,
                    "; ".join(bad) or "no failing check",
                    "no failing check",
                )
            )
    rejected = [x for x in cards if x.status == "rejected"]
    sels = [s.model_copy(update={"status": "rejected"}) for s in c.rejected]
    order = assign(rejected, sels, extra)
    n = f"{len(rejected)} rejected, {len(sels)} expected"
    rows.append(
        _row(
            "concept",
            "every other card is rejected for the reason given",
            order is not None,
            n if order is None else "all matched",
            f"{len(sels)} rejected",
        )
    )
    if order is None:
        for s in sels:
            hit = any(matches(x, s, extra) for x in rejected)
            rows.append(
                _row(
                    "concept",
                    f"a card is {describe(s)}",
                    hit,
                    "found" if hit else "none matches",
                    s.why,
                )
            )
    else:
        for s, card in zip(sels, order, strict=True):
            rows.append(
                _row("concept", f"a card is {describe(s)}", True, _card_words(card, extra), s.why)
            )
    return rows


def _card_words(card: Any, extra: Any) -> str:
    cats = sorted(failing_categories(card, extra))
    return f'{card.status}, failing {", ".join(cats) if cats else "nothing"}, "{card.title}"'


# --- figures -----------------------------------------------------------------------------


def find_figure(
    fig: Figure, ev: Evidence, extra: Any, impact: dict[str, Any] | None = None
) -> tuple[Found, str]:
    """Read the number of a figure from its surface; returns it and a words note."""
    f, unit = fig.find, fig.unit
    if f.screen_value is not None:
        assert fig.card is not None
        names = [f.screen_value] if isinstance(f.screen_value, str) else f.screen_value
        card = pick_card(ev.cards(), fig.card, extra)
        return screen_values(card, names, unit), describe(fig.card)
    if f.screen_row is not None:
        assert fig.card is not None
        card = pick_card(ev.cards(), fig.card, extra)
        return screen_row(card, f.screen_row, unit, extra), describe(fig.card)
    if f.requirement is not None:
        return requirement_values(ev.check(), f.requirement, unit), ""
    if f.rollup is not None:
        return rollup_value(ev.rollups(), f.rollup, unit), ""
    if f.impact is not None:
        return impact_value(impact, f.impact, unit), ""
    assert f.result is not None
    return result_value(ev.check(), f.result, unit), ""


def judge_figure(
    fig: Figure, ev: Evidence, extra: Any, impact: dict[str, Any] | None = None
) -> Row:
    """One figure: found without ids, then compared within its tolerance."""
    want = expectation(fig, FIGURE_TOL)

    def run() -> tuple[bool, str]:
        found, _ = find_figure(fig, ev, extra, impact)
        return judge(found, fig, FIGURE_TOL)

    return _guard("figure", fig.what, want, run)


# --- facts -------------------------------------------------------------------------------


def _quantity_fact(text: Any, unit: str | None) -> float:
    v, u = number_and_unit(str(text))
    return convert(v, u, unit)


def fact_value(fact: Fact, ev: Evidence, impact: dict[str, Any] | None = None) -> str | float:
    """The product's value for a fact: a word for the word kinds, else a number."""
    k = fact.fact
    if k == "ceremony":
        got = ev.check().get("ceremony")
        if got is None:
            raise MatchError("check printed no ceremony (the product's tool is older than M3a)")
        return str(got)
    if k == "signoffs_lost":
        if not impact:
            raise MatchError("the request kept no impact")
        invalidated = impact.get("signoffs_invalidated") or []
        removed = impact.get("signoffs_removed") or []
        return float(len(invalidated) + len(removed))
    if k == "region":
        return str(ev.manifest().get("region", "none"))
    if k == "supply":
        return "none" if ev.supply() is None else "present"
    if k in ("supply_voltage", "supply_frequency"):
        supply = ev.supply()
        if supply is None:
            raise MatchError("the product has no supply")
        v = supply.get("voltage" if k == "supply_voltage" else "frequency")
        if isinstance(v, str) and v.startswith("param://"):
            p = ev.parameters().get(v.removeprefix("param://"))
            if not p or "value" not in p:
                raise MatchError(f"supply {v} is not a plain parameter value")
            v = f"{p['value']} {p.get('unit', '')}"
        return _quantity_fact(v, fact.unit)
    if k == "assemblies":
        mods = ev.check().get("matrix", {}).get("modules", [])
        return float(len([m for m in mods if m.get("id")]))
    if k == "count_requirements":
        n = 0
        for r in requirement_rows(ev.check()):
            if fact.safety is not None and bool(r.get("safety")) != fact.safety:
                continue
            if fact.status is not None and r.get("status") != fact.status:
                continue
            if fact.status_in is not None and r.get("status") not in fact.status_in:
                continue
            if fact.category is not None and r.get("category") != fact.category:
                continue
            if fact.words is not None and not re.search(
                fact.words, f"{r.get('title', '')} {r.get('message', '')}", re.I
            ):
                continue
            n += 1
        return float(n)
    gates = {g["name"]: g for g in ev.status().get("gates", [])}
    if fact.gate not in gates:
        raise MatchError(f"no gate named {fact.gate} (gates: {', '.join(gates)})")
    blockers = [str(b) for b in gates[fact.gate].get("blockers", [])]
    if fact.matching is not None:
        blockers = [b for b in blockers if bool(re.search(fact.matching, b, re.I)) != fact.invert]
    return float(len(blockers))


def judge_fact(fact: Fact, ev: Evidence, impact: dict[str, Any] | None = None) -> Row:
    """One fact: a word that must be equal, or a number judged like a figure (tol 0)."""
    if fact.equals is not None:
        want = fact.equals

        def run_word() -> tuple[bool, str]:
            got = str(fact_value(fact, ev, impact))
            return got.lower() == want.lower(), got

        return _guard("fact", fact.what, want, run_word)

    def run() -> tuple[bool, str]:
        got = fact_value(fact, ev, impact)
        assert not isinstance(got, str)
        return number_ok(got, fact, 0.0), f"{got:g}" + (f" {fact.unit}" if fact.unit else "")

    return _guard("fact", fact.what, expectation(fact, 0.0), run)


# --- change rows -------------------------------------------------------------------------


def _change_rows(change: Any, ev: Evidence, extra: Any, replay: bool) -> list[Row]:
    """Judge one ``changes:`` row on a scratch copy of the product, never the folder given."""
    product = ev.product
    if product is None:
        raise EvidenceError("a change row needs a product folder to replay in")
    prefix = f"{change.name}: "
    with tempfile.TemporaryDirectory(prefix="n2f-oracle-") as tmp:
        copy = Path(tmp) / product.name
        shutil.copytree(product, copy)
        try:
            impact = oracle_change.obtain_impact(change, copy, replay)
        except (oracle_change.ChangeFailure, MatchError) as exc:
            if isinstance(exc, oracle_change.ChangeFailure) and exc.whole:
                names = (
                    ["outcome"] + [f.name for f in change.figures] + [f.name for f in change.facts]
                )
            else:
                names = ["replay"]
            return [
                _row("change", f"{prefix}{name}", False, f"not judged: {exc}", "") for name in names
            ]
        evc = Evidence(copy)
        expected = (
            "no requirement fails"
            if change.outcome == "accepted"
            else f"the failing requirement(s) named by {', '.join(change.fails)}"
        )
        rows = [
            _guard(
                "change",
                f"{prefix}outcome",
                expected,
                lambda: oracle_change.outcome_failures(change, evc.check()),
            )
        ]
        rows += [
            _row(
                "change",
                f"{prefix}{r.what}",
                r.passed,
                r.found,
                r.expected,
            )
            for r in (judge_figure(f, evc, extra, impact) for f in change.figures)
        ]
        rows += [
            _row(
                "change",
                f"{prefix}{r.what}",
                r.passed,
                r.found,
                r.expected,
            )
            for r in (judge_fact(f, evc, impact) for f in change.facts)
        ]
        return rows


# --- the whole oracle --------------------------------------------------------------------


def evaluate(oracle: Oracle, ev: Evidence, replay: bool = False) -> list[Row]:
    """Every row of an oracle judged against the product's evidence."""
    extra = oracle.lexicon
    rows: list[Row] = []
    if oracle.concepts is not None:
        rows += judge_concepts(oracle.concepts, ev, extra)
    rows += [judge_figure(f, ev, extra) for f in oracle.figures]
    rows += [judge_fact(f, ev) for f in oracle.facts]
    rows += [r for change in oracle.changes for r in _change_rows(change, ev, extra, replay)]
    return rows


def render(rows: list[Row], oracle: Oracle) -> str:
    """The rows as text, one line each, then the totals."""
    lines = []
    for r in rows:
        mark = "PASS" if r.passed else "FAIL"
        want = f"  [expected {r.expected}]" if r.expected and not r.passed else ""
        lines.append(f"{mark}  {r.group:<7} {r.what} — {r.found}{want}")
    failed = sum(not r.passed for r in rows)
    lines.append(f"\n{len(rows) - failed} passed, {failed} failed, {len(oracle.pending)} pending")
    for p in oracle.pending:
        lines.append(f"PEND  {p.what} — {p.reason}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """The command line: exit 0 all pass, 1 any FAIL, 2 unreadable oracle or product."""
    ap = argparse.ArgumentParser(prog="python -m tests.benchmarks.oracle", description=__doc__)
    ap.add_argument("product", type=Path, help="the product folder (holds n2f.yaml)")
    ap.add_argument("oracle", type=Path, help="the SPEC.oracle.yaml to judge it by")
    ap.add_argument("--json", action="store_true", help="print the rows as JSON")
    ap.add_argument("--no-build", action="store_true", help="trust the build/ already there")
    ap.add_argument(
        "--replay",
        action="store_true",
        help="always replay a change row instead of looking for the agent's own request",
    )
    args = ap.parse_args(argv)
    try:
        oracle = load_oracle(args.oracle)
    except (OSError, ValueError) as exc:
        print(f"cannot read the oracle {args.oracle}: {exc}", file=sys.stderr)
        return 2
    if not (args.product / "n2f.yaml").is_file():
        print(f"{args.product} is not a product folder (no n2f.yaml)", file=sys.stderr)
        return 2
    try:
        rows = evaluate(oracle, Evidence(args.product, build=not args.no_build), replay=args.replay)
    except EvidenceError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    failed = sum(not r.passed for r in rows)
    if args.json:
        doc = {
            "passed": len(rows) - failed,
            "failed": failed,
            "rows": [asdict(r) for r in rows],
            "pending": [p.model_dump() for p in oracle.pending],
        }
        print(json.dumps(doc, indent=2))
    else:
        print(render(rows, oracle))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
