# Decisions log (system build-out)

Decisions beyond `GRAND_PLAN.md` §2 and `NAPKIN_STAGE.md` §2, with rationale. Convention
(AGENTS.md): one entry per decision, ≤ 10 lines, dated; a later entry that changes an earlier
one names it and the earlier one's index row is updated. `[revisit]` marks ones the owner may
want to reopen; `[verify]` marks engineering numbers taken from published sources that a human
should confirm before relying on them.

Read the index; open an entry only when you change what it decides. Entries of closed versions
live in `docs/decisions/v0.1.md` (S-001–S-054, gates 1–4, kiln) and `docs/decisions/v0.2.md`
(S-055–S-072, gates A, B); the rest, and every new entry, are at the end of this file (S-104).

## Index (status as of 2026-11-01; entries below are never rewritten, only their row here changes)

| id | decision | status |
|---|---|---|
| S-001 | Host platform differs from the plan | in force |
| S-002 | OCP wheel and render path pairing (D2 / D12) | amended by S-059 (section render) |
| S-003 | three.js pinned at r170 (0.170.0), vendored, inlined (D13) | in force |
| S-004 | In-house GLB writer; URIs carried in glTF `extras` | in force |
| S-005 | selectolax lexbor backend | in force |
| S-006 | `rich` and `packaging` added as runtime dependencies | in force |
| S-007 | Expression grammar: hyphenated names, spaced minus | in force |
| S-008 | Lint L1 "measurable" exempts binary verify kinds | in force |
| S-009 | Schema failures do not cascade | in force |
| S-010 | Product-repo common files live in `templates/_common` | in force |
| S-011 | Unattended git identity | in force |
| S-012 | Validate semantics for computed selectors | in force |
| S-013 | Interface bolt patterns are applied by the build, not by each generator | in force |
| S-014 | Per-party interface frames and `param://` in specs | in force |
| S-015 | Assembly instance numbering is global per part URI | in force |
| S-016 | Downstream rules depend on upstream *output hashes*, not keys | in force |
| S-017 | `validate` always reruns when any model file changes, never otherwise | in force |
| S-018 | Interruption safety by atomic manifest writes after each rule | in force |
| S-019 | `--jobs N` builds parts in a spawn pool; assemblies reload from STEP | in force |
| S-020 | Impact before the first build is the conservative static read set | in force |
| S-021 | Manual pages record `depends_on` plus every templated read | in force |
| S-022 | Rule packs are YAML rules bound to named Python checks | in force |
| S-023 | BOM link checks default to offline in `make check` | in force |
| S-024 | Evidence keys (D25) per scheme | amended by S-027, S-040, S-050; role excluded in S-069 |
| S-025 | `count` verify kind semantics | in force |
| S-026 | Safety verdict ladder | in force |
| Gate 1 | Review gate 1 (architecture) — outcome | outcome recorded; blockers fixed, the rest in BACKLOG |
| S-027 | Membership keys `set://…` (gate-1 B1) | in force |
| S-028 | Parts and assemblies record the fields they read (gate-1 B3) | in force |
| S-029 | Outputs are verified, never trusted (gate-1 B2/B4) | in force |
| S-030 | Stable instance numbering and placements in the assembly hash (gate-1 B5) | in force |
| S-031 | Package-tree code hashes (gate-1 B6) | in force |
| S-032 | Report layout and persona toggle (D13, D17) | superseded by S-052 (one layout) |
| S-033 | `n2f serve` is a plain `http.server` | in force |
| S-034 | Interface holes reach the flat pattern through `PartResult.flat_map` | in force |
| S-035 | Parameter edits are line-targeted; other YAML edits round-trip | in force |
| S-036 | Revision bump rule (D7/M6) | in force; compared from before the change request since S-089 |
| S-037 | "Unused parameter → nothing rebuilds" holds for artifacts, not for the report | in force |
| S-038 | Release bundle and frozen site data | in force |
| S-039 | Diff overlays rescale to the newer drawing | in force |
| S-040 | Sign-off evidence for parts is geometry, not the manifest hash | amended by S-050, S-069 |
| S-041 | `n2f check` never changes render state | in force |
| Gate 2 | Review gate 2 (UX) — outcome | outcome recorded; blockers fixed, the rest in BACKLOG |
| S-042 | EXAMPLE sign-offs are visible everywhere and gate releases | in force |
| S-043 | Drawings read features and flat patterns from the part's files | in force |
| S-044 | `kind: reference` parts | in force |
| S-045 | Interface frames may reference parameters | in force |
| S-046 | Interference volume by inclusion–exclusion | in force |
| S-047 | Example sign-offs never read as verification | in force |
| S-048 | First-run notice and `n2f build --offline` | extended by S-057 (kernel warm-up) |
| Gate 3 | Review gate 3 (engineering) — outcome | outcome recorded; blockers fixed, the rest in BACKLOG |
| Gate 4 | Review gate 4 (onboarding) — outcome | outcome recorded; blockers fixed, the rest in BACKLOG |
| S-049 | Parents reload up-to-date sub-assemblies from disk | in force |
| S-050 | Evidence for parts without geometry | in force |
| S-051 | A bolt shared by two interfaces is one hole | in force |
| S-052 | One report layout, no persona toggle (amends D17) | in force; ratified by S-055 |
| S-053 | The viewer renders on demand | in force |
| S-054 | PyPI publishing through trusted publishers | in force; tagging practice amended by S-072 |
| Kiln | Kiln engineering decisions (DEC- entries in `examples/kiln`) | in force |
| S-055 | Owner ratifies S-052 (NAPKIN_STAGE N2): one layout, persona in dialogue | in force |
| S-056 | Version pin across 0.1 → 0.2 (D20): warn, never refuse `[revisit]` | in force [revisit]: strict pin mode; pins now `>=0.3,<0.4` (S-083) |
| S-057 | `n2f init` warms the CAD kernel in the background | in force |
| S-058 | `validate` reports expression errors alongside reference errors | in force |
| S-059 | True plane section render (amends D12) | in force; notes surfaced (S-088) |
| S-060 | Closing a change request waits for human sign-offs | in force |
| S-061 | Owners read model URIs without the scheme prefix | in force |
| S-062 | Concept cards, loader and the optional Napkin stage (M1) | in force [revisit]: released product with a new card reads Napkin |
| S-063 | Massing fidelity in the kit (N3) | in force; frames weighed by members (S-087) |
| S-064 | The calc kit (N4) | in force; fiber k 0.15 / ρ 260 per gate A C4 (materials.yaml) |
| S-065 | Concept screening: computed vs estimate, the concept rule pack, red is information (N5) | in force; door swing by its angle since S-085 |
| S-066 | Styled viewer screenshots, style.yaml presets and six kit aesthetic parameters (N6, N7) | in force [revisit]: z-buffer fallback picture; layout marks and blank retry (S-093) |
| S-067 | The board, promotion and form requirements (N8, N10): the `rule` verify kind and the form pack | in force; supply bound is V·I / 1.2 since gate A B1 (the 0.8·V·I in the entry is superseded) |
| S-068 | The napkin protocol in the PM skill; interpretation cards (N9) | in force |
| Gate A | Review gate A (honesty + architecture) — outcome | outcome recorded; blockers fixed, the rest in BACKLOG |
| S-069 | Kiln retrofit: the napkin story recorded after the fact (M6) | in force |
| S-070 | `make check` runs the tests in parallel (pytest-xdist) | in force; the demos run in parallel too (S-079); long test files split (S-080) |
| Gate B | Review gate B (UX, owner persona) — outcome | outcome recorded; blockers fixed, the rest in BACKLOG |
| S-071 | v0.2 close-out: what is measured, what is the owner's | in force; the release happened (S-072) |
| S-072 | CI never repeats a commit's tests; 0.2.0 released | in force; CI on `main` only since S-097 |
| S-073 | Journal consolidation and model-agnostic agent rules | amended by S-076 (no `CLAUDE.md` copy) |
| S-074 | README for people, agent guide for agents; using vs developing kept apart | in force |
| S-075 | The icon on generated pages; wordmark waits on the font licence | in force; the wordmark is in use (S-081) |
| S-076 | `AGENTS.md` is the only instructions file, here and in product folders | in force |
| S-077 | Generic for any model and client; product roles move to `roles/` | in force |
| S-078 | Gate reports kept in `docs/reviews/`; visual exits judged by the maintainer | in force |
| S-079 | The three demos in `make check-full` run side by side | in force |
| S-080 | No build-once fixture: the long test files are split instead | in force; second round S-084 |
| S-081 | The wordmark is in use: outlined letters, no font file shipped | in force |
| S-082 | `validate.json` names files relative to the product | in force |
| S-083 | 0.3.0: version and the product pin move to `>=0.3,<0.4` | in force |
| S-084 | Second round of test splits: the step is now bound by total work | in force |
| S-085 | Door swing by its angle; the alcove follows the designed door | in force |
| S-086 | Napkin polish: two advisory rules, owner words in notes, `at` only on change | in force |
| S-087 | Frames and tubes are weighed by their material, not their silhouette | in force |
| S-088 | Section-render notes reach the build output | in force |
| S-089 | Revision bumps compare from before the change request was applied | in force |
| S-090 | One meaning of "stage" for people: the stage being worked in | in force |
| S-091 | The flat-area identity is exact once the bend term is counted | in force |
| S-092 | `make lint` covers `examples/` | in force |
| S-093 | Concept pictures draw the layout words; blank captures are retried | in force |
| S-094 | Share mode: `n2f publish` and the online copy | in force |
| S-095 | `release --dry-run` on an existing Revision re-packages it from its own snapshot | in force |
| S-096 | A card number of the wrong kind is a lint error, not a crash | in force |
| S-097 | One trunk, a worktree per task, ids at landing: built for successive agents of any provider | in force |
| S-098 | Task folders hardlink uv's cache so macOS scans native libraries once | in force |
| S-099 | Landing gives placeholders their ids in every task commit, messages included | in force |
| S-100 | The why sits where the thing happens: code cites its decision | in force |
| S-101 | Owners need no uv link-mode setting: one environment, kept across upgrades | in force |
| S-102 | A landing that loses the race starts again with fresh ids | in force |
| S-103 | v0.4 is the product's structure (`PRODUCT_STRUCTURE.md`); electrical, profiles, stack-up move later | in force |
| S-104 | Closed versions' decision entries live in `docs/decisions/` | in force |

---

## S-073 — Journal consolidation and model-agnostic agent rules (2026-11-01)
Owner's ask after v0.2: lower the reading cost for the next agent, whatever model runs it.
`AGENTS.md` is the one place for process rules (CI gate, tagging, staging explicit paths, the
journal convention); `CLAUDE.md` is its identical copy (`make agents-doc`), as in product repos.
`DECISIONS.md` gains the index table with a status per entry; entries are capped at ten lines
and never rewritten. `STATUS.md` is state and pointers; its milestone paragraphs are frozen in
`docs/history/STATUS-through-v0.2.md`. `BACKLOG.md` is the single open-work document: bugs, plan
leftovers (GRAND_PLAN §1.2, NAPKIN_STAGE ⤵ items), risks, with closed rows in their own table.
`make verify-list` prints every unconfirmed number (`verify: true` rows, `[verify]` lines) so the
handoff list is generated, not assembled by hand. The plans' "how to run" sections name no model.

## S-074 — README for people, agent guide for agents (2026-11-01)
Owner's ask: people read the README to start quickly and work through their agent, so it holds
what the tool is, a prompt to paste, the other ways in, and nothing of the CLI or Python setup.
`docs/agent-guide.md` is the agent's start: setup with the owner's consent, the product folder,
handover to that folder's `AGENTS.md` and skills, the kiln showcase, the command reference (the
old README walkthrough, rewritten for agents). A hidden comment atop the README routes agents.
"Using" (an agent making a product for its owner) and "developing" (contributors) are kept
apart: root `AGENTS.md` opens by sending users to the guide, product `AGENTS.md` links the guide
for setup. Every rule in `AGENTS.md` now carries its reason; a rule whose reason is gone is
proposed for deletion. `test_agent_docs.py` holds the README to no commands.

## S-075 — The icon on generated pages (2026-11-01)
B-0050, first part. The report, the board and the diff page carry the small icon as a favicon
and a 20 px footer mark, embedded as a data URI (self-contained, D13, N10; no id clashes). The
README shows the 256 px PNG from `brand/png/`. Only the icon is used: it is drawn, not typeset.
The wordmark and lockup stay out of public places until the font licence is cleared (owner
to-do). `brand/build.py` writes `report/brand/n2f-icon-32.svg`; `test_brand.py` holds them equal.
The "no `<link>`" page checks now reject only links that leave the page. The CLI keeps plain text.

## S-076 — `AGENTS.md` only, no `CLAUDE.md` copy (2026-11-01)
Amends S-073. Owner's call: keep everything generic. The client that once needed a file named
`CLAUDE.md` now reads `AGENTS.md`, so the copy had no remaining reason. Removed: the root copy,
the one in `templates/_common/` (so `n2f init` no longer writes it) and its synced copies, `make
agents-doc`, and the equality tests; tests now assert the copy is absent. `n2f init .` on an older
product folder leaves an existing `CLAUDE.md` alone (it is the owner's file). The agent guide tells
an agent to read `AGENTS.md` itself if its client does not load it. The product role skills still
sit under `.claude/`; a neutral home is B-0057.

## S-077 — Generic for any model and client; roles in `roles/` (2026-11-01)
Owner's rule: everything is generic on both sides. Contributors may use any model (open source),
and owners use whatever agent they have, so the guide tells an agent all it needs to adapt
(new "Adapting to your client" table: no shell, no auto-loaded `AGENTS.md`, no subagents, no
image viewing, no browser, no network). The product roles leave `.claude/` for `roles/pm.md`,
`design.md`, `verifier.md`, `impact-analyst.md`: plain Markdown, the client-specific frontmatter
(a tools list) dropped, the product `AGENTS.md` naming the file to read per role. Closes B-0057.
`n2f init .` on an older folder adds `roles/` and leaves its `.claude/` alone. The rule is a
non-negotiable in `AGENTS.md`; `test_agent_docs.py` fails on per-client files.

## S-078 — Gate reports in the repo; visual exits judged by the maintainer (2026-11-01)
B-0053, B-0056 (docs/improvements.md §1, §4). The full gate reports were scratch files and only
outcomes reached this log; the next gate should start from the last one's questions. Kept in
`docs/reviews/`: v0.2 gates A and B and v0.1 gate 4, copied unedited from the old scratch folders
(local paths replaced); v0.1 gates 1–3 were not kept. `docs/reviews/TEMPLATE.md` holds the
standing reviewer rules and the four question sets (GRAND_PLAN §8.3, NAPKIN_STAGE §5). And: an
exit judged by eye goes to the maintainer as pictures with a one-line question, the answer
recorded as "judged by the maintainer: …" (S-066, S-067, S-069 were the agent's judgment alone).
Both are `AGENTS.md` working-style rules; the next plan's milestone exits should name the second.

## S-079 — The demos in `make check-full` run side by side (2026-11-01)
Amends S-070; B-0054. `demo.sh`, `demo-design.sh` and `demo-napkin.sh` each work in their own temp
copy with nothing shared and no timing assertion, so `make demos` runs them on three workers
(`-n 3`; they are one file, so `--dist loadfile` would have kept them on one). Measured on the
macOS host: 8 min 19 s wall, against ≈ 12 min serial (docs/improvements.md §2, eab10b1). Each
demo slows under the shared load (demo-design 496 s), so the longest sets the pace. Overlapping
the kiln step with the demos was not tried: both are CPU-heavy and it is unmeasured. The timing
tests stay serial (D30).

## S-080 — No build-once fixture; the long test files are split instead (2026-11-01)
B-0055, step 1 (measure) decided it. Timing every `run_build` in the test step (16 workers, no
coverage): 154 builds, 689 s summed, 262 s of it cold builds, many of them the thing under test
(invalidation, broken fixtures); a shared built product would save ≈ 140 s of CPU, ≈ 30 s of wall.
The wall was set by one file, `test_ecr.py` (≈ 290 s on one worker under `--dist loadfile`). Moved
whole tests, unchanged, to `test_ecr_close.py`, `test_signoffs.py` and `test_release_tracking.py`.
Measured: test step 328 → 261 s after the first split (no coverage); `make check` with all three
6 min 52 s, its test step 4 min 49 s (was ≈ 8 min and 5 min 33 s). Next long poles: the 87 s
shared release in `test_release_diff.py`, `test_concept_promote.py`. B-0006 stays open.

## S-081 — The wordmark is in use: outlined letters, no font file shipped (2026-11-01)
Amends S-075; closes B-0050. Owner's call: the wordmark's letters are outlines made by
`brand/build.py` (paths, no `<text>`, no font reference), and no font file is copied into the
repo, the packages or a page, so it may be used. The README header shows the lockup (light or
dark by the reader's theme). The report, the board and the diff page say "generated by" with the
wordmark at text height beside the icon, embedded as a data URI (D13, N10), alt text the name;
`brand/build.py` writes the page copy and `test_brand.py` holds it equal and outline-only. The
font item is gone from `OWNER-TODO.md`; swapping fonts stays one setting each in `build.py`.

## S-082 — `validate.json` names files relative to the product (2026-11-01)
Closes B-0006. Problems recorded by the build's validate rule now carry the path relative to the
product root (`model/parts/lid.yaml`); a file outside the product keeps its path. A built folder
then names no local path and reads the same wherever the product sits. CLI output already
printed relative paths; `n2f validate --json` is unchanged.

## S-083 — 0.3.0: version and the product pin move to `>=0.3,<0.4` (2026-11-01)
Amends S-056's pin values, not its rule (a mismatch warns, never refuses). 0.3 changes no schema:
a 0.2 product loads untouched and only sees the one-line pin notice until its owner moves the
pin. The three version files read 0.3.0 (S-054); templates, examples, test fixtures, the product
CI workflows (`uv tool install "napkin2factory>=0.3,<0.4"`) and the manifest default pin
`>=0.3,<0.4`.

## S-084 — Second round of test splits: the step is now bound by total work (2026-11-01)
Amends S-080. Moved, unchanged, `test_design_ecr_with_patch` to `test_ecr_design.py` and the
red-card override test to `test_concept_override.py` (no shared setup, so no extra work). Tried
and reverted: splitting `test_release_diff.py`, which builds its 87 s shared release twice.
Measured with all three: slowest file 177 s, test step 322 s, total test time 1834 s on 16
workers: no single file sets the pace any more, so more splits cannot help; less work can (fewer
cold builds, renders). Final `make check` test step 310 s (4 min 49 s after S-080: run-to-run
noise is this large). A styled-screenshot test rendered blank once under load (B-0051).

## S-085 — Door swing by its angle; the alcove follows the designed door (2026-11-01)
Closes B-0029, B-0027, B-0023; amends S-065. Screening counts the room beside the hinge as
leaf × max(0, −cos θ) from the card's `envelope.door_swing`; no angle → the leaf fully back, and a
note says so. Kiln C-003, measured: 1698 → 1236 mm (240 mm for the 110° door instead of 702 mm).
Promotion works from the unrounded leaf (702.4 mm, not 703) and rounds once. A requirement's bound
is a plain quantity, so instead of an expression in the bound promotion seeds `door-leaf-width`
and `door-swing-clearance` (an expression on it) and writes two rows: the closed width ≤ alcove −
allowance, and `door-swing-clearance` ≤ allowance; widening the door fails the second (e2e test).
A one-row form needs `param://` bounds in the requirement schema and evaluator: not done.

## S-086 — Napkin polish: two advisory rules, owner words in notes, `at` only on change (2026-11-01)
Closes B-0025, B-0034, B-0031. `concept-v0` gains two warn rules: outer skin vs a touch limit
(the card's `site.touch_limit`, else `calckit/data/touch_limits.yaml`, ISO 13732-1 contact
thresholds, every row `verify: true`) and chamber volume vs the card's `envelope.target_volume`.
The kiln's compact C-002 now lists 91 °C skin and 3.38 L against 8 L instead of "no limitations".
Every screening note is in owner words; a test scans them for field names. A re-screen with the
same content keeps the card's `at` and leaves the file alone. `make kiln` keeps its scratch copy:
building in place would rewrite a stale card and leave the tree with unsaved changes.

## S-087 — Frames and tubes are weighed by their material, not their silhouette (2026-11-01)
Closes B-0021; amends S-063. The frame kit's massing also reports `material_volume` (member
section × cut length, equal to the full weldment's volume), and the tube kit likewise (bore and
rounded corners included); the massing composer weighs a piece
by it when present and by its silhouette otherwise. The shape and its `volume` are unchanged, so
screening reads the same fields. Measured: kiln stand 31.8 → 7.2 kg; C-001's cost band 1130–2747 →
650–2267 USD (estimate). Cost bands themselves stay wide (B-0022, waits on real quotes).

## S-088 — Section-render notes reach the build output (2026-11-01)
Closes B-0019. `Scene.notes` and a new `Scene.uncapped` are written to `renders/notes.json` next
to the pictures, only when there are notes and kept out of `props.json`, so a part's output hash
does not depend on rendering. `n2f build` prints them in owner words with the part's name ("its 3D
surface has a gap, so the cut is drawn open"); `--json` carries `render_notes`. Tested by forcing
an open face through `n2f build`.

## S-089 — Revision bumps compare from before the change request was applied (2026-11-01)
Closes B-0020; amends S-036. `ecr close` diffs declared fields from the snapshot before "Apply
ECR-x" to the latest one; before, it saw only the last snapshot, so `apply`'s own record snapshot
or a sign-off hid a part YAML edit with no geometry change. `apply` always takes its "Apply"
snapshot so that point is exact. `applied.before` holds output hashes, not a snapshot, so the
parent of `applied.snapshot` is used. Open: edits never saved before close are not seen;
overlapping change requests can bump extra parts, never too few. Test: `test_ecr_declared.py`.

## S-090 — One meaning of "stage" for people: the stage being worked in (2026-11-01)
Closes B-0033 (gate B, B5). The status headline, the report badge and `n2f ecr close` all name the
first gate not complete ("ready to release" when only the Revision is missing; "released" once
the snapshot is a Revision, demonstration ones included). `--json` keeps `stage` (last gate
passed, used by scripts and tests) and adds `current_stage`, so no field changes meaning; the
v0.1 status fixture gains that one line. `ecr close` no longer says "stage: verify" or offers
`n2f release` while example sign-offs still block it.

## S-091 — The flat-area identity is exact once the bend term is counted (2026-11-01)
Closes B-0026. The flat pattern was right. The bend solid keeps full thickness (mid-plane at
k = 0.5) while the flat uses the neutral axis, so per 90° bend of length L the solid holds exactly
(π/2)(0.5 − k)·t²·L more than area × t. Measured worst gaps 3.66 % (enclosure t = 3, r = 1,
h = 25) and 3.26 % (bracket t = 4, r = 1); with the term the residual is ≤ 1.4e-14.
`test_kit_sheet.py` compares against the exact value at 1e-6; the 4 % tolerance is gone. No kit
code or golden changed.

## S-092 — `make lint` covers `examples/` (2026-11-01)
Closes B-0028. The kiln's Python is ruff-clean by formatting, wrapping and docstrings. E741 on `I`
is ignored under `examples/*/model/geometry/**` as under `src/…/geometry/**`: `I` is the D5
accessor. Only `examples/*/build` is excluded. No behaviour change: the same AST with docstrings
removed, and a before/after kiln build gave byte-identical part, assembly and check outputs and
equal manifest output hashes.

## S-093 — Concept pictures draw the layout words; blank captures are retried (2026-11-01)
Closes B-0032 (gate B, C16) and B-0051. The styled pictures draw flat, unlit, neutral ink on the
silhouette: a door outline, a heavy hinge edge with knuckles, a handle opposite, and a controls
panel on the face `layout` names; words naming no place draw nothing. Code lives on the
screenshot page only (board, report and shared viewer unchanged); fallback pictures carry no
marks. A capture with < 0.3 % of pixels off the border colour counts as blank and is rendered once
more; a second blank falls back with a note. How often SwiftShader blanks under load: not measured.

## S-094 — Share mode: `n2f publish` and the online copy (2026-11-01)
Closes B-0037 (scope chosen by the maintainer: a folder plus an optional send, no account or
project creation). `n2f publish` copies what exists (latest report, released Revisions with
packages, change pages between them, the board) into `build/publish/` with a branded index; it
builds nothing, names the command for anything missing, refuses over 20 MiB (`--since` trims).
`--online` asks first, then sends the draft line, the Revisions and the folder as a parentless
`gh-pages` snapshot to the existing remote in one atomic send (`core/vcs.py`, D31). Pages come
from `gh-pages`, not CI: `build/` is untracked, a tag job rebuilds only its own Revision and a
deploy replaces the whole site, so the product `release.yml` no longer deploys Pages. Tested
against a local bare repository only; not yet run against GitHub.

## S-095 — `release --dry-run` on an existing Revision re-packages it from its own snapshot (2026-11-01)
Found while building S-094. A product's `release.yml` runs `n2f release <tag> --dry-run` on the
tag it was started by, so the Revision always existed and the step always refused: every
product's release workflow failed before attaching its package. A dry run for an existing
Revision now re-packages it (ZIP and frozen site, not marked as a preview) only when the current
snapshot is that Revision (`Vcs.revision_snapshot`); at any other snapshot, and without
`--dry-run`, it still refuses. Test: `test_release_diff.py::test_dry_run_repackages_…`.

## S-096 — A card number of the wrong kind is a lint error, not a crash (2026-11-01)
Found while closing B-0025. `power: 3 kg` on a card crashed screening with a unit error.
`QUANTITY_KINDS` in `core/concepts.py` names the kind of the 12 card numbers screening reads;
`n2f concept lint` rule C8 makes a mismatch an error with an example ("envelope.power is 3 kg,
which is not a power"); screening leaves such a number out with one note and the rules needing it
skip. The napkin demo now reports 13 parameters already declared: the shipped kiln declares the
door numbers (S-085), its `door-leaf-width` an expression on `door-guard-width`.

## S-097 — One trunk, a worktree per task, ids at landing: built for successive agents of any provider (2026-11-01)
Maintainer: the repo is developed by AI agents of many models and providers, in parallel and one
after another; efficiency matters, with quality kept. Replaces the per-version `v*-build` branches,
which only ever mirrored `main`. Now: `main` is the one trunk (releases stay tags, S-072); each task
is a `task/<slug>` branch in `.worktrees/<slug>` with its own environment (`make task`), committed
freely, landed by rebase + fast-forward (`make land`: journal placeholders `S-NEW<n>`/`B-NEW<n>` get
the next free ids, a one-minute gate, linear history); `make check` once on `main` before a push.
Unfinished work is `WIP:` commits on the task branch, found by `make tasks`. Project rules live in
the repo, not in any one model's memory (one maintainer's personal preferences stay theirs);
`AGENTS.md`'s "start here" no longer runs `make check`. Considered and not taken: Jujutsu (another tool every agent must know), test-impact
selection with pytest-testmon (unreliable with xdist and the build-hash e2e tests).

## S-098 — Task folders hardlink uv's cache so macOS scans native libraries once (2026-11-01)
Measured on the host (macOS 26.7): a task folder's first `import build123d` took 117–190 s with
7 s of CPU; `syspolicyd` was busy meanwhile, and `-X importtime` put 65 s on `OCP.OCP` (143 MB)
and the rest over the environment's other 347 native libraries. macOS registers and scans each
newly written executable file on first load; uv's macOS default installs clones, so every task
folder had all-new files. With `UV_LINK_MODE=hardlink` the files are the cache's own: the first
hardlinked folder still took 179 s, the next 10.2 s. `make task` now syncs with hardlinks (an
explicit `UV_LINK_MODE` wins). Nothing writes into installed files, so the shared cache is safe.

## S-099 — Landing gives placeholders their ids in every task commit, messages included (2026-11-01)
Amends S-097. Found on the first real landing (S-098): ids were assigned in a final "Assign journal
ids" commit, so the task's own commit kept its placeholder in its files and subject on `main`, and
`git bisect run make check` would have blamed that commit for the placeholder check. Now
`scripts/journal_ids.py` rebuilds each task commit from its snapshot with the ids applied to its
changed files and its message (plumbing: `read-tree`, `hash-object`, `commit-tree`; no patch is
replayed, so nothing can conflict). Commit `3d50f7e` on `main` predates this and keeps its
placeholder; history on `main` is never rewritten.

## S-100 — The why sits where the thing happens: code cites its decision (2026-11-01)
Maintainer: fixes should be documented where they happen, so the next agent understands why
things are done the way they are. `AGENTS.md` makes it a rule: a non-obvious line carries a short
comment naming the decision with the full reason. Today's fixes cited closed backlog rows
(`B-0019` …), one hop short of the reason; they now cite their decisions (S-085–S-099), and the
task script, id assignment, `.gitattributes`, CI's trigger, the release dry run and the card
number lint gained the pointer they lacked. Earlier code is left as it is until next touched.

## S-101 — Owners need no uv link-mode setting: one environment, kept across upgrades (2026-11-01)
Follows S-098 (hardlinked task folders). Asked whether owners need the same: no, measured in a
throwaway tool folder. `uv tool install napkin2factory==0.2.0` made one environment whose first
`import build123d` took 125 s (the macOS scan, once); `uv tool install napkin2factory@latest`
(0.2.0 → 0.3.0) kept that environment, the CAD library the same file, and the first import after
it took 7.6 s. Product folders get no environment of their own (`n2f init` makes none), and
`n2f init` already warms the first import (S-057). A dependency upgrade brings new native files
whichever link mode is used, so the agent guide's install step stays as it is.

## S-102 — A landing that loses the race starts again with fresh ids (2026-11-01)
Amends S-097. Found by reading `make land` before testing it: when another task landed between a
task's rebase and its fast-forward, the retry rebased commits whose ids were already given out
against the old `main`, so two tasks could both land as the same `S-` id (union merge keeps both
entries; only the fast gate would notice). Each attempt now resets to the task's own commits
(placeholders intact), rebases, and takes ids afresh; a fast-forward refused while `main` has not
moved (two landings meeting on git's lock) waits and retries. `test_task_script.py` lands one task
inside the other's gate: the old script landed both as S-002, the new one as S-002 and S-003.
## S-103 — v0.4 is the product's structure; electrical, profiles and stack-up move later (2026-11-01)
A modularity review found the kiln built as one flat assembly: 34 child lines at the top, one
sub-assembly (the door), parts placed by hand-computed coordinates, and an interface check that
cannot see a misplaced part. Research into industry practice (middle-out design, module drivers,
interface control, a build plan derived from one tree) and 2026 agent-CAD preprints agreed:
plan the structure and joints as data, let code place and count, check one module at a time.
The maintainer asked for a v0.4 plan covering all five fixes: `PRODUCT_STRUCTURE.md`, decisions
P1–P14. Electrical (B-0035), manufacturer profiles (B-0038) and stack-up (B-0039), earlier slated
for v0.4, move to v0.5 or later; stack-up gains from explicit frame chains.

## S-104 — Closed versions' decision entries live in `docs/decisions/` (2026-11-01)
Maintainer asked whether every agent reads the whole of `DECISIONS.md`: it was 1,181 lines
(≈ 94 KB) with the index in the first 125, and common read tools load ~2,000 lines by default,
so "read the index" loaded everything. S-001–S-054, gates 1–4 and the kiln decisions moved
unchanged to `docs/decisions/v0.1.md`, S-055–S-072 and gates A, B to `v0.2.md`; the index keeps
every row, so ids and statuses are where they were. `DECISIONS.md` is now ≈ 400 lines. The block
was cut from the middle, not the end, so a task appending entries meanwhile (v0.4 was) still
rebases without a conflict. The journal test and `make verify-list` read all three files.
