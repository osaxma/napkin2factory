# v0.6 overseer handoff (TEMPORARY — delete this folder when v0.6 closes)

Written 2026-11-02 by the v0.6 overseer at the end of wave 2, for the next overseer, a fresh
session that remembers nothing. It carries what lives only in the first overseer's session:
the briefs, decisions not yet in the journals, measured times, the count so far, what waits on
the maintainer. Everything else is in the journals (`STATUS.md`, `DECISIONS.md`,
`BACKLOG.md`); read those as `AGENTS.md` says, then this file.

**Resuming a cut-off run? Read `PROGRESS.md` here first: it is the ledger of the second
overseer's run (what is done, what is in flight, the exact next step).**

## First steps for the next overseer, in order
1. Read `AGENTS.md`, `STATUS.md`, this file, then `ELECTRICAL_STAGE.md` §5 M5–M7 and §8.
2. `make tasks` (expect none) and `git log --oneline -25` (main should be at or after the commit
   that landed this folder).
3. **The budget:** `make check` measured 10 min 53 s after wave 2 (§3), over 10 min 4 s. Re-run
   it on an idle host; if still over, a small task moves the slowest end-to-end files behind
   `-m full` (find them with `pytest --durations=25`), and record the times in STATUS.md.
4. Check the latest scheduled CI run (§0, Linux).
5. **The maintainer's green light was given on 2026-11-02 (second session)**; hand out `brief-m5.md` (first) and
   `brief-m6.md` with `brief-common.md`; then write M7's brief from plan §5 M7 and §0 here.

## 0. The maintainer's standing instructions (from the run's opening brief)
- Run the whole release, M0–M7, and stop only when v0.6 is closed: every milestone landed,
  gates G and H closed with reports in `docs/reviews/`, the owner simulation run and its
  transcript saved, `HANDOFF-REPORT-v0.6.md` with the count as its first line, version files
  and product pins bumped (`>=0.6,<0.7`), `make check` green on main. **Do not push, do not tag.**
- You oversee; subagents build (one per milestone, each in its own `make task` worktree,
  landing with `make land`). You write briefs, read landed diffs, run `make check` on main
  between waves, keep the journals. You do not edit code inside a wave you supervise.
- **The count** (the point of the release): the electrical domain's own commits change nothing
  under `src/napkin2factory/core/`, `report/builder.py`, `docs/engine.py`, `cli/check.py`. A
  subagent that needs a core edit stops with a `WIP:` commit naming the file and the reason; you
  open a separate seam task (B-NEW row + decision entry naming the seam), then resume the
  domain task. After each wave run `git log --stat` over the landed tasks; record core edits.
- Every brief contains: ELECTRICAL_STAGE.md §0 and §2, the milestone's section, owned files,
  forbidden files, the DoD items, the placeholder-id rule, the E10 rule, and "if you need a
  file you do not own, stop and commit WIP: saying what you need". `brief-common.md` here
  carries the shared part; hand it with every brief.
- Where the plan is silent, decide like a senior engineer, write it in DECISIONS.md with its
  reason, `[revisit]` if the maintainer may reopen it; never stop to ask.
- Measure, don't claim. Budgets: `make check` ≤ 10 min 4 s (no slack: move the slowest
  end-to-end files behind `-m full` if needed); `make check-full` ≤ 29 min 14 s + the new
  demo's own time. Record wave times in STATUS.md.
- Gates G and H: fresh-context subagents briefed from `docs/reviews/TEMPLATE.md`; they see the
  repo and the brief only. Gate G's reviewer plays a licensed electrician reading only the
  manufacturer package and the wiring outputs, never the model files; keep that read-through in
  `examples/kiln/reports/`. Fix blockers; concerns go to BACKLOG.
- Linux: at each wave boundary look at the latest scheduled CI run
  (`set -a && . ./.env && set +a && gh run list --workflow ci --limit 5`); a red one on a
  sign-off → a task that fixes it (B-0073 reopened) before the next wave, said in STATUS.md.
- Visual exits (one wiring diagram, the report's Wiring section): send the maintainer the
  pictures with one question, record "judged by the agent; the maintainer's judgment pending",
  continue; list everything waiting on the maintainer in the handoff report's last section.
- Talk in plain words; an id never travels alone (pair it with its short title).
- **New, mid-run: the maintainer held M5 and M6 ("don't start them until I give a green
  light") and moved them to this new session.** Start them only with the maintainer's go.

## 1. Where things stand (main at e72704b, 2026-11-02 09:56)
| step | state | commits | decisions |
|---|---|---|---|
| M0 baseline and tables | landed | df8db88, f916013 | S-145 (E5: no parts-list seam, [revisit]), S-146 (tables), S-147 (baseline) |
| M0 seam tasks | landed | 958172b, 0910d58, a2ff7a8, dcc4498/72a9c68/4358ba6 | S-142, S-143, S-144, S-148–S-152 |
| M1 the family and the joint | landed | a8d1798, 9bd5b3f | S-153, S-154 (overseer's decisions), S-155 |
| M2 the rule family and outputs | landed | f8bd098 | S-156 (`elec-schedule`), S-157 |
| M3 checks, verify kind, choice | landed | a196024 | S-158 |
| M4 the owner's view | landed | 9559335, 1dea28d, fc7e347, e72704b (M4b, E8) | S-159, S-168 |
| wave-2 seam tasks | landed | dd34f32, cc2e32a | S-160–S-164, S-165–S-167 |
| **M5 the kiln, wired** | **in progress (task `m5-kiln`, from 13:39; follow-up `wiring-headroom` for B-0149, B-0151)** | — | brief: `brief-m5.md` |
| M6 external, scope, script | landed | b5530ef | brief: `brief-m6.md` |
| M7 docs, simulation, gates G/H, close-out | **M7a docs in progress (task `m7-docs`, from 14:17)** | — | briefs: `brief-m7.md`, `brief-gate-g.md`, `brief-gate-h.md` |

Wave 3 = M5 + M6 at once (start M5 first: it is the long one). Then M7.

## 2. The count so far (verified by the overseer, not claimed by subagents)
- **The domain's own commits (M1, M2, M3, M4, M4b): 0 files** under `core/`, `report/builder.py`,
  `docs/engine.py`, `cli/check.py`. Check: `for c in $(git log --format=%h 4358ba6..main
  --grep="^M[0-9]"); do git show --name-only --format= $c | grep -E
  "src/napkin2factory/(core/|report/builder.py|docs/engine.py|cli/check.py)"; done` prints nothing.
- **Seam tasks, listed apart** (v0.5 defects, fixed in their own tasks; all core edits are here):
  1. Known in the plan, opened by M0: B-0099 release files (S-142); B-0115–B-0119 scope words
     (S-148–S-152).
  2. Found by the overseer reading the code in M0, before any domain code: interfaces treated
     by spec type (S-144, B-0126; E4 named this case); a family running `before=` another
     (S-143, B-0125; the manual would read last build's wiring).
  3. **Found by the domain tasks during wave 2 (the E10 path proper — the honest headline):**
     M3 → a family's membership key and interface field reads (S-165, S-166; B-0140, B-0136)
     plus contract docs (S-167; B-0135, B-0139, B-0147); M4's WIP → a card field's `param`
     from any declaration, the screens import order (S-160, S-161; B-0145, B-0146, B-0129),
     every status worded in a gate row (S-162; B-0143), a public scope line (S-163; B-0144),
     a helper's build folder (S-164; B-0142). Two seam tasks, both landed before the domain
     task resumed (the M4 WIP is the one E10 stop; it resumed as M4b).
  - Not built, decided: the parts-list seam (E5, S-145, B-0128).
- One non-public core import was used and then replaced: the Wiring section imported
  `core.checks.stage.scope_entries` (B-0144) → now the public `scope_entry` (S-163, M4b).

## 3. Measured (host, 2026-11-02)
- Wave times: M0 (baseline + five seam tasks at once) 07:00–07:43 last land; M1 07:56–08:24;
  wave 2 08:40–09:56 (M2 08:57, M3 09:06, M4 09:16, seams 09:34 and 09:51, M4b 09:56).
- `make check` on main: 9 min 34 s at 4358ba6 (1,135 passed); 9 min 40 s at 9bd5b3f
  (1,173 passed); **10 min 53 s at e72704b (after wave 2, 1,290 passed) — over the 10 min 4 s budget**, maybe on a busy host (a subagent's background work may have overlapped): re-measured by the second overseer on an idle host at 1f81117: **7 min 39 s**, green (1,290 passed, 141 goldens): under budget, nothing moved.
- `make check-full`: not re-run; v0.5's 29 min 14 s stands (S-147: code identical at M0).
- Kiln (before wiring): cold build 69.1 s, report 3,796,445 bytes (S-147). Minimal wiring
  fixture: build 8–12 s, report 1,722,207 bytes with the Wiring section (S-159).
- Land gates (`make check-fast`): 140–240 s each; M4b's 359 s (with the rebase).
- Linux: push run on 7f4d8d0 green on ubuntu and macOS; latest scheduled run (2026-11-01
  10:28) is the known pre-S-121 red; none since (checked at 07:56). Check again at each wave.

## 4. Facts the next tasks need (not obvious from the code)
- Verify targets are `circuit://<id>#props.<figure>` (S-158, S-167): `load_current`,
  `supply_margin`, `conductor_margin`, `earth_paths`. A requirement's `value` is a quantity,
  never `param://` (ELECTRICAL_STAGE §3's example is wrong); compare `#props.supply_margin`
  with `0 A`.
- A cable entry's spec has no `pattern:` (M1 refuses `pattern: circle` without a pitch circle;
  §3's example is wrong): `count: 1`, `diameter`, `passes`.
- The schedule rule is `elec-schedule` (key `rule:elec-schedule`), not `elec:_schedule` (S-156).
- Connection ends are `device://<id>#<terminal>` (S-154 point 1); `part://x#T` only when one
  device names the part.
- The supply-headroom choice (E11) triggers above 50 % of the supply rating (NEC 210.23(A)(2),
  [verify]); the kiln (10.9 A of 16 A) raises it; options "a dedicated 16 A circuit" / a larger
  circuit (S-158).
- The supply screen is the domain's now (`circuit-available`, phase `check`, S-168); the
  kiln's pack keeps only its thermal screens; `tests/golden/goldens/kiln-board.json` unchanged.
- Terminal markings for the kiln's devices were sourced after the survey: `terminals.md`
  here (the maker's documents via third-party hosts; `[verify]` each). M5 copies them into
  `docs/v06-baseline.md` §2.
- The limit controller's relay has no inductive (AC-15) rating on file: the contact-on-coil
  warn on the kiln is the honest result, not a bug.
- The diff page's agreed words for a section new in the later Revision: "<label>: added" (M6
  writes it in `ecr/diff.py`, M5's demo asserts "Wiring: added").

## 5. Open items for M7 and the close-out (from the subagents' reports)
- `docs/domains.md`: the wave-2 seams amended it (S-143, S-144, S-161–S-167); M7 reads it once
  against the domain as built (the electrical package is now the third worked example).
- ELECTRICAL_STAGE.md §3's examples (`param://` value, `pattern: circle`): a note in the
  handoff report, or a dated amendment line in the plan; never rewrite the plan's text silently.
- Open rows from this release: B-0127, B-0128, B-0130–B-0134, B-0137, B-0138, B-0141, B-0148.
- `[revisit]` decisions to list for the maintainer: S-145 (no parts-list seam), S-146 (silicone
  ampacity at the PVC floor), S-148 (REQ-007/-016/-021 untagged), S-156, S-157, S-158 (how a
  limit device is judged; AC-3 accepted for inductive loads), B-0131.

## 6. Waiting on the maintainer
- ~~Green light for M5 and M6.~~ Given 2026-11-02 (second session), with: do not push, do not tag.
- Visual judgment (S-078), sent 2026-11-02 with one question ("is this diagram style the one to
  carry to the kiln's three circuits, or should the layout change first?"):
  `docs/reviews/v0.6-diagram-power.png`, `docs/reviews/v0.6-diagram-external.png`,
  `docs/reviews/v0.6-report-wiring.png` (the last captured before M3's rows existed). Agent's
  judgment: the power diagram and the section read clearly; the external variant has crossing
  tracks and may crowd at kiln size — re-judge on the kiln's diagrams in M5. Record the answer
  in S-157/S-159's follow-up entry.
- From v0.5, still pending: the visual judgment of `docs/reviews/v0.5-*.png`, push, the first
  Linux nightly after S-121, the `v0.5.0` tag.

## 7. Files in this folder
- `brief-common.md` — the shared part of every brief (hand it with each one).
- `brief-wave2-common.md` — the build-file contract between the domain's subfolders (still the
  reference for what `build/electrical/` holds).
- `brief-m1.md` … `brief-m4.md` — the briefs as given (for their shape; done).
- `overseer-decisions-m1.md` — the decisions now recorded as S-154.
- `brief-m5.md`, `brief-m6.md` — ready to hand out (start M5 first). Not yet written: M7.
- `terminals.md` — the sourced terminal markings (its local file copies were not kept).
