# Review gate brief — template

Fill the brackets and hand the reviewer this text plus the file paths, nothing else: not the
builders' conclusions, not the design conversation. Save the report it returns as
`docs/reviews/v<version>-gate-<id>.md` and record the outcome in `DECISIONS.md`
("Review gate <id> — outcome"). The v0.2 briefs these were distilled from produced
`v0.2-gate-a.md` and `v0.2-gate-b.md`; read one before writing a new brief.

## Standing rules (every gate)

You are a fresh-context reviewer for napkin2factory [version] ("[what the version adds]") at
[repo path], branch `[branch]`, reviewing commit [hash] ("[subject]"). You have not seen the
design conversation and are not told the builders' conclusions. Your job is **review gate
[id]: [stance]**.

- Read-only. Change nothing in the repo; do not commit. You may run commands and write under
  [scratch path].
- Work on copies. Copy a product to [scratch path] before building it (`cp -R`, or
  `tests.conftest.copy_product`); never run `n2f build` inside `examples/`.
- Environment: [host facts from `STATUS.md` → Environment, e.g. the `PATH` for `uv`].
- Evidence for every answer: the exact command and the exact output text, or a file:line.
  Quote, do not paraphrase.
- A verdict per question: BLOCKER (must be fixed before the next milestone), CONCERN (goes to
  `BACKLOG.md`) or OK.
- Each blocker and concern: the exact text or behaviour seen, what was wanted, the file:line
  where it lives, and a concrete fix.
- Report: a one-paragraph verdict (READY / NOT READY), one section per question, then the
  numbered blockers and concerns. Under 250 lines. Write it to [scratch path]/gate-[id]-report.md
  and return the same text as the final message.

Persona gates add: play [the persona, e.g. a hobby potter with no engineering background] who
has only `n2f` output, the report and the board to go by. Read `README.md` and the user docs as
that person; do not read source code until the UX findings are formed (afterwards only to point
fixes at file:line).

## Question sets

Use the set for the gate's stance, add the questions the version's plan names, and turn each
into steps the reviewer can run on a copy (the v0.2 reports show the level of detail that
worked).

### Architecture and honesty (v0.1 gate 1, v0.2 gate A)
- Can any rule read model data without going through the recording accessors? Can any
  build-graph rule read `concepts/`? Prove it: build, add cards and a board, build again; nothing
  rebuilt and the manifest identical; delete `concepts/`, build again, same.
- Are post-run keys complete (code hash, rule version, interface specs, selector reads)? Is the
  needs-run logic right on first run, second run and after an interrupted run? Is impact a
  superset of invalidation? Can the manifest be corrupted by interruption?
- Is OCCT state leaking across process-pool workers?
- Is every number traceably given, computed or estimate, and is any estimate presented as
  computed anywhere (board, report, CLI text, JSON, role text)?
- Can a red card reach promotion without a logged decision, including by hand-editing a file?
- Do form and site requirements fail when violated (flip one, check, flip back)?
- Is the calc kit cited and unit-safe throughout (wrong units must raise; every data row has a
  source and `verify`)?
- Are errors actionable (file, id, what to do)? Any `TODO`/`FIXME` without a `B-` id? Any git
  word in a user-facing string?
- Does any change in this diff teach the package a product's noun, field or default (a screen,
  rule, field, default or docstring example only one example needs)? It belongs in that
  product's folder (`model/screens/`, `model/rulepacks/`; F9, F10). The guard
  `tests/unit/test_no_example_identifiers.py` catches exact identifiers; this question, the rest.

### UX in the owner persona (v0.1 gate 2, v0.2 gate B)
- Follow the README's first run literally; note every place where the text and what the
  commands print disagree.
- Run `n2f status`, file a change request, run impact, approve, build, read the report. Is the
  impact text understandable without engineering vocabulary and still precise?
- Is divergence cheap (ask for "like C-00x but taller": how many steps, how many minutes, was it
  obvious which line to edit)?
- Does a red card read as information, not rejection: what is wrong and what it would take?
- Is any git or engineering vocabulary visible, including in error paths (force the
  not-a-folder-under-tracking and unsaved-changes errors and read them)?
- Is the promotion question comprehensible and its consequence clear? Does `n2f status` after
  it name the right stage and next step?
- Can you tell given, computed and estimate apart at a glance on the board and in the report?
- Do the styled pictures look like a product or a debug image?
- Does the owner view lead with cost, pictures and manufacturer instructions; the engineer view
  with the matrix? Is anything safety-relevant hidden behind a toggle (it must not be)?
- Does every refusal say, in plain words, what to do next, with no stack trace? Does the report
  work from `file://` with no console errors?

### Engineering (v0.1 gate 3)
- Are the thermal and power calcs dimensionally correct and cited? Are requirement thresholds
  defensible? Are the safety requirements complete for the product's hazards?
- Is anything presented as verified that is only computed? Are example sign-offs unmistakably
  labelled?
- Role-play the shops (for the kiln: a sheet-metal shop and a brick supplier) reading only the
  manufacturer package: could they quote, what is missing or ambiguous? Keep that read-through
  in the example's `reports/`.

### Onboarding (v0.1 gate 4)
- Follow the README and the agent guide from scratch in a clean environment; time to the first
  report; every command copy-pastable; nothing requires an account.
