# The benchmark oracle

Judges a product folder against the expected outcomes of a benchmark spec (road-to-v1.0 section
4.2, W9, S-209). The same code judges the shipped example in CI and a cold agent's own product
in a trial, so it asserts **outcomes, never ids**: a cold agent names its parts, requirements and
cards differently and must still pass.

```
uv run python -m tests.benchmarks.oracle <product_dir> <SPEC.oracle.yaml> [--json] [--no-build]
```

It runs the n2f commands its rows need inside `product_dir` (`n2f build` only if a row reads the
built product; `n2f concept build --all` only if there are concept rows), prints `PASS`/`FAIL` for
each row with the value it found, then the pending list. `--no-build` trusts the `build/` already
there and does not re-screen the cards. Exit 0: all pass. 1: some FAIL. 2: the oracle or the
product could not be read, or an n2f command failed.

A matcher that finds nothing, finds several candidates, or cannot read what it found makes that
row a FAIL whose text says which (`no requirement is bounded at 99 mm`, `2 cards are rejected`).

## The file

```yaml
oracle: 1
title: ...            # words
spec: SPEC.md
lexicon: {mass: [heavy]}     # optional: extra words that place a failing check in a category
concepts:             # the napkin stage
  count: 3
  promoted: {material: white-oak, kit: frame}      # exactly one card is promoted, and it is this
  promoted_has_no_failure: true                    # default: no failing screening row on it
  rejected:                                        # every other card, each with its reason
    - {by: [structural], not_by: [mass, cost], material: southern-yellow-pine, why: "..."}
    - {by: [mass, cost]}
figures:              # numbers
  - name: c2-sag      # a label for the report, never looked up
    what: plain words
    card: promoted    # only for screen_* finders; or a selector like the ones above
    find: {screen_value: deflection}
    unit: mm
    expect: 1.58      # or a list (any one), plus tol (relative, default 0.05) and abs_tol
    # or: at_least / at_most / range: [lo, hi]
facts:                # about the product
  - {name: x, what: ..., fact: ceremony, equals: lite}
pending:              # stated by the spec, not showable yet; printed, never failing
  - {what: ..., reason: ...}
```

**A card selector** (`CardSel`) names no id: `status` (promoted / rejected), `by` (categories of
failing check it must show), `not_by` (it must not), `material` (a word a rough shape's material
carries; hyphens and spaces alike), `kit` (a shape generator it uses), `pieces`. `why` is for
the report. Rejected entries are matched to rejected cards one to one (every card used once).
A figure's selector must match exactly one card.

**Categories** of a failing screening row: a rule id starting `structural-` is `structural`;
otherwise the first of cost, mass, envelope, structural whose words (see `LEXICON` in
`oracle_match.py`; add yours under `lexicon:`) appear in the rule's id and title, then its message.

**Figure finders** (`find:`, exactly one):

| finder | reads | notes |
|---|---|---|
| `screen_value: name` or `[a, b]` | the card's `screening` given / computed / estimates value of that name (`deflection`, `mass`, `total_mass`, `cost_low`, `cost_high`, `tip_over_factor`, `yield_factor`, `current`, ...) | first name present wins; the text (`14.3 mm`) is converted to `unit` |
| `screen_row: {rule or category, regex}` | one screening row's message; the regex captures `value` (and `unit`) | one row or an error |
| `requirement: {bound, op?, safety?, category?, kind?, words?, not_words?, aggregate?}` | the measured value of every requirement result whose bound equals `bound` in the same dimension (`2.5 mm` = `0.0025 m`) | read from the message `value op bound`; several requirements may share a bound, so the figure passes when one is in tolerance, and is ambiguous when two that differ both are. `words` / `not_words` (regexes, case-insensitive, searched in the requirement's title and message) tell apart two requirements bounded alike, a footprint width from a part's height (`bbox\.[xy]\b`); `aggregate: min` / `max` reduces them to one value, the governing factor when one product covers beam and bolt fatigue by one requirement and another by two (S-230) |
| `rollup: key` | `build/bom/rollups.json`: `total_mass` (kg), `total_cost` (USD), `part_count`, `distinct_parts`, ... | |
| `result: {kind, rule?, path or regex}` | one row of `n2f check --json` `results`: a dotted `path` into it (`detail.load_a`) or a message `regex` | the row is found by `kind` and a substring of its `detail.rule`/id |

**Facts** (`fact:`): `ceremony` (`check --json`), `region` (`n2f.yaml`), `supply` (`none` or
`present`: `model/electrical/supply.yaml`), `supply_voltage` / `supply_frequency` (numbers with
`unit`; a `param://` value is read from `model/parameters.yaml`), `assemblies` (modules in all, the
final one included), `count_requirements` (filters `safety`, `status`, `status_in`, `category`, `words`: a regex over the requirement's title and message, to name "the tip-over requirement" without its id),
`gate_blockers` (`gate`, `matching` regex, `invert`; from `n2f status --json`). The word kinds use
`equals`; the numeric ones the same `expect` / `at_least` / `at_most` / `range` as figures, with
tolerance 0 unless `tol` says otherwise.

## Files

- `oracle_schema.py` the format (pydantic, unknown fields are errors);
- `oracle_evidence.py` the lazy outputs of a product (`Evidence`), commands run once;
- `oracle_match.py` card selection, finders, judging; `oracle.py` the rows and the command;
- `fixtures/` two oracles that pin the real surfaces on shipped examples (bracket, kiln cards).

Unit tests (`tests/unit/test_oracle.py`) use synthetic outputs shaped like n2f's; the end-to-end
tests (`tests/e2e/test_benchmarks.py`, in `make check`) run every `examples/*/SPEC.oracle.yaml`
whose product exists, plus the fixtures. Never loosen a tolerance to make a row pass: fix the spec
or the tool (W9).
