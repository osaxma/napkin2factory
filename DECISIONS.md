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
| S-040 | Sign-off evidence for parts is geometry, not the manifest hash | amended by S-050, S-069; keyed on invariants since S-121 |
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
| S-105 | v0.4 M0 baseline: kiln frames meet, one to rewrite; hardware reconciled, shared-hole rule (`docs/v04-baseline.md`) | in force |
| S-106 | v0.4 M1: interfaces place parts (`place_by`), frame expressions, alignment checked in the assembly | in force |
| S-107 | v0.4 M2: sub-assemblies have ports; a part's home; `place_by` places sub-assemblies | in force |
| S-111 | v0.5 is the foundation (the seams), v0.6 the first domain (electrical) as its proof; an independent trial brief after v0.6 | in force |
| S-108 | A styled screenshot whose shader fails under load is rendered once more | in force |
| S-109 | A landing that stops after giving out ids puts the task's own commits back | in force |
| S-110 | v0.4 M3a: build units and phantoms, the build plan derived from the tree, joint hardware counted | in force; its plan reads have values since S-117 (gate C, B1) |
| S-112 | v0.4 M5: promotion keeps the napkin's modules (stubs, size budgets) or suggests them; start flat | in force |
| S-113 | v0.4 M3b: the kiln built from units, door and controls hung by their ports, lining a phantom | in force |
| S-114 | v0.4 M4: parameters have a scope, a module's context is a command, checks per module | in force |
| S-115 | v0.4 M6: joints between units in the plan and the report, two-level review roles, the DoD 5 simulation protocol | in force; run in S-116 |
| S-116 | v0.4 DoD 5: a fresh agent changed the door from its context alone; all four criteria met | in force |
| S-117 | The build plan is a valued read; the checks record the assembly fields the hardware stage reads | in force |
| Gate C | Review gate C (architecture and honesty) — outcome | outcome recorded; blockers fixed, the rest in BACKLOG |
| S-118 | Joints in owner words: an optional `name:` and `closed_in:` on interfaces, joints in build order, sheet text never below 2.2 mm | in force |
| Gate D | Review gate D (UX, owner persona) — outcome | outcome recorded; blockers fixed, the rest in BACKLOG |
| S-119 | v0.4 closed: version 0.4.0, product pins `>=0.4,<0.5`, handoff report | in force |
| S-120 | The v0.5 and v0.6 plans reconciled with what v0.4 shipped; the Linux evidence-key defect opened as B-0073 | in force |
| S-121 | Sign-off evidence keys are tolerance-compared invariants, not the mesh (closes B-0073) | in force |
| S-122 | v0.5 M0 baseline: a new step edits 10 files (7 in `core/`), 32 package files name the kiln's words, the five big files, `make check` 10 min 14 s | in force |
| S-123 | v0.5 M1: one domain contract (`core/domain.py`), fifteen registries (`core/registry.py`), the mechanical domain registered in place, the toy domain; a new step edits 0 core files | in force |
| S-124 | v0.5 M4: scope as data (`scope:` in `n2f.yaml`, `build: external` stubs, `model/loads/`); `later` domains leave the gates with a note, never a safety requirement | in force |
| S-125 | v0.5 M2: schema policy and migrations (`core/model/migrate.py`, `n2f init .`), calc reference cases (`calc-case` rows, L16) | in force |
| S-126 | v0.5 M2b: the checks rule hashes the calc kit (closes B-0078) | in force |
| S-127 | v0.5 M4b: scope is a recorded value (`manifest://scope`, read by the report of a product that declares one); external stubs in the build plan | in force |

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
## S-105 — v0.4 M0 baseline: the kiln's frames, hardware and placement code (2026-11-01)
Measured for S-103 (the v0.4 plan) by `scripts/v04_frame_survey.py`; see `docs/v04-baseline.md`.
Frames: every kiln pair meets in the world (origin and hole miss 0.00 mm), all 18 name `x_axis`;
offsets 0, 26 (standoff walls), 3 (post, keeper), −26.5 (door). Only `controller-mount` breaks P1
(normals and x axes opposed, 40): M1 rewrites the box frame (holes unchanged), the post and keeper's
literal origins, and the 18 helpers, read only by interface frames. Hardware: 50 bolts = 32 + 4 + 4
+ 2 + 8, but a bottom corner cannot take three bolts in one shared hole; M3 adds a through bolt (38
M6 × 16, 4 M6 × 50), moves the door's stud, anchors and gasket into the door, checks bolt length
[verify]. Amends P9: a shared hole lists each item once, on the joint it closes; non-hardware lines
need no field. 180 + 47 placement lines, 159 parameters; `make check-full` 19 min 28 s, red (B-0063).
## S-106 — v0.4 M1: interfaces place parts; alignment checked in the assembly (2026-11-01)
P1–P3 as planned. `controller-mount` lists the guard first (offset +controller-standoff; box frame
[1,0,0]/x [0,−1,0], holes unchanged). `frame_basis` moved to `core/frames.py` (holes, `place_by`,
check). `instances.json` gains `via`, `label`, no order (S-030): the P1 warning is per joint, two
joined parts both on coordinates. P14: asm evidence keys hash only v0.3 fields, a zero `offset` is
not dumped. Alignment needs a frame per party; 0.5 mm / 0.5° is a design choice, not measured.
Enclosure base frame z is `param://box-height`. Kiln: 5 joints and the door guard by `place_by`
(stand the anchor); 18 helpers gone (159 → 141 parameters). Lines 180 → 175 (kiln), 47 → 43 (door);
`place()` calls 22 → 17, 6 → 5. Goldens unchanged, misses 0.00 mm; example sign-offs REQ-007/008/019
re-keyed (box frame). 21 new tests; `make check` 8 min 51 s green, `make kiln` 2 min 42 s green.
## S-107 — v0.4 M2: sub-assemblies have ports; `place_by` places sub-assemblies (2026-11-01)
P4 as planned, with P5's home, in `core/tree.py`. Two "lowest" assemblies, kept apart: alignment
(P3) runs where both parts occur; ports start from homes, so a joint naming a part used at two
levels (a bolt) is a port of the lower module. `n2f validate` (rule `port`) refuses a missing
port and a listed one that crosses nothing, naming the assembly file, and an `asm://` party in
the loader, where the message can say the fix (closes B-0005). `place_by(…, "asm://x", …,
inner=…)` moves the sub-assembly by its party's leaf; `onto` also finds leaves of placed
sub-assemblies (two modules, a port each side). Labels survive reload since M1 (S-106). Kiln: all
nine joints inside one assembly, no ports, unchanged. Port joints escape P1's warning (B-0064).
17 new tests; `make check` 9 min 32 s green (784 tests), goldens unchanged; `make kiln` 3 min 1 s green.

## S-108 — A styled screenshot whose shader fails under load is rendered once more (2026-11-01)
Follows S-093 (blank captures are retried). `make check` failed twice in five runs on `main` today
with `THREE.WebGLProgram: Shader Error 0 - VALIDATE_STATUS false` in
`test_grey_palette_reads_as_grey`, while other test workers loaded the machine; the test passed three
times out of three alone. Headless GL (SwiftShader) raises it under load as it hands back blank
frames, and a reload clears it, so `styled_screenshots` now treats that page error like a blank:
one more render, then the correctness renders with a note. Any other viewer error still falls back
at once. How often the shader fails under load: two in five `make check` runs, not otherwise measured.

## S-109 — A landing that stops after giving out ids puts the task's own commits back (2026-11-01)
Follows S-099 and S-102 (ids at landing; a lost race starts again). When the gate failed, `make land`
stopped with the branch rebased and its placeholders already numbered. The v0.4 M3a task failed its
gate once on a flaky test (S-108), kept S-108, and collided with the next task to land, which took
S-108 too; `test_journals` caught the duplicate. Every stop after ids are given out (failed gate,
unsaved main folder, failed fast-forward, main moving three times) now resets the folder to the
task's own commits first and says so. A conflict during the rebase still stops mid-rebase as before.
## S-110 — v0.4 M3a: build units, the derived build plan, joint hardware counted (2026-11-01)
P7–P9 as amended by S-105, kiln untouched (M3b). `core/build_units.py` (strict) reads the tree once:
units (top, or `build: unit`), phantoms folded (quantities multiply), a joint closes where its
parties' homes meet (`AssemblyTree`) and occurs the larger of its parties' counts there. Beyond the
plan: `per_joint` hardware (a mating face's only form); `hardware: []` overrides `fastener:`; `loose`
counts as declared; `asm:` now writes `exploded.png` (none existed; the viewer's full explode); sheets
in `build/drawings/assemblies/`; `bom`'s output hash stays the rollups' (P14), pages read
`bom://build-plan#units.<id>`; lint `L13-assembly-driver`. Kiln (alias only): `hardware://door`,
`://kiln` warn (8 vs 4, 50 vs 30 bolts), no fail; report 3,614,355 → 3,714,969 bytes. 18 new tests;
`make check` 9 min 24 s green (803 passed), goldens unchanged; `make kiln` 2 min 55 s green.
## S-111 — v0.5 is the foundation, v0.6 the first domain as its proof (2026-11-01)
A review after v0.4 M2, at the maintainer's request: a foundation that agents of any model can
develop continuously; steps (electrical, analysis) added only when a product needs them; real
testing later. Measured: a new rule family, verify kind, check stage, report section and doc
helper edits eight core files (`FOUNDATION.md` §0.2); 23 package files carry the kiln's words;
`schema: 1` is never read; five files over 700 lines are where parallel agents collide. v0.5
(`FOUNDATION.md`, F1–F16) adds registries behind one domain contract, a toy domain, the kiln out
of the package, a schema policy, scope as data, and choices; v0.6 (`ELECTRICAL_STAGE.md`, E1–E12)
builds the electrical domain through that contract with a count of core edits as its headline.
`docs/reviews/v0.6-independent-trial.md` briefs an outside model to use and review both.
## S-112 — v0.4 M5: promotion keeps the napkin's modules; start flat, split for a reason (2026-11-01)
P10, P11. Card `driver`/`build` words are free text: lint C9 warns, never errors (the plan said
"rejects"; a typo must not block a card, N1). A line's `module:` without an entry is allowed (a stub
with no driver; L13 warns); lines without one seed nothing. Budgets: box of the module's lines, composed
again in memory, rounded up to 0.1 mm, `must`. Refused: a module named like the product, a file already
there. Empty stubs: `assembly_props` gets a centroid, no layout row, `geometry_prop` on no parts `skip`
(not a 0 mm pass); rules may say `subject: assembly`. Kiln cards: door and controls only (assembly.md
§5; an electrician wires the box); body, guard, lining, the one-part stand fit in sequence, no module.
`cli/concept.py` prints seeded files and the suggestion. Measured: blank promote 8.5 s, kiln 2.5 s; 10
new tests 32 s; kiln cards rebuild unchanged; only `kiln-board.json` moved; `make check` 12 min 38 s.
## S-113 — v0.4 M3b: the kiln built from units; door and controls hung by their ports (2026-11-01)
Door (built-as-unit, serviced-as-unit) hangs by new welded mating face `hinge-lower`; `hinge-upper`,
`latch-catch` checked; controls (tested-as-unit, separate-process-or-supplier) by `controller-mount`,
lid by `controller-lid-seat`; lining a phantom on coordinates. Product DEC-019–023: S-105 option A
(38 M6×16, 4 M6×50), all `hardware://` rows pass; bolt lengths, lid screw [verify]; rivets B-0065.
Beyond the plan: interfaces joining the same two parts (two hinges, one post) excuse each other's
occurrences in alignment (each still needs a pair that meets) and share occurrences in the plan.
`door.py` reads door sizes only; still crossing (M4): `hinge-post-y`, `-reach`, `stand-inset`. place()
kiln.py 17 → 2 (door 5, controls 5, lining 10), literal offsets 13 → 0; props identical, goldens kept.
ECR-002 patch re-made (B-0063); REQ-007/008/009/018/019 re-signed. Report 3,783,308 B. `check-full`
23 min 24 s green; rebased on S-112: `make check` 8 min 42 s, `kiln` 2 min 45 s, `demos` 9 min 7 s green.
## S-114 — v0.4 M4: parameters have a scope; `n2f context`; checks per module (2026-11-01)
P5, P6, P12 (`core/reach.py`, `core/context.py`, `core/checks/modules.py`). Beyond the plan: a
phantom owns no parameters (validate refuses); an unscoped `expr` sits at the product level, so
it reads a scoped size only if exported; interface expressions may name either party's sizes;
interface reads are tagged (`iface_reads` in the manifest), keys unchanged. `--scope` adds a
requirement allocated inside unless its target is another module's build. Kiln: 38 sizes scoped
(door 32, controls 6); unexported, 5 reads warn (S-113's three, door-leaf-width); no joint can
carry a part's size, so door-guard-width, -depth, -offset and hinge-pin-depth export: 0 warns.
Context text/json bytes: door 16,653/30,192, controls 10,632/17,343, kiln 31,156/51,881, flat
kiln 49,570/77,527: P11 splits above 32 kB (a line on one product, not an agent limit). B-0064
open. 21 new tests; `make check` 8 min 45 s, `make kiln` 2 min 53 s green; scoped door check 8 s.
## S-115 — v0.4 M6: joints between units reviewed; the one-module simulation prepared (2026-11-01)
P12, P13. `build-plan.json` gains `between_units` (each joint's sides with their unit, how it is
joined, hardware, step); the report's new "Joints between units" section adds the `iface://`
verdict and the decisions linking the joint. Beyond the plan: `ports` in the impact JSON. The
verifier reviews unit by unit (context, scoped check, inside a module or at a port), then the
joints with Boothroyd's three questions; a part to combine is a proposed `DEC-` linking the
joint, never a verdict. Scripted change (`tests/e2e/module-transcripts/`): the door's standoff
rectangle 10 mm wider and taller (inset 120 to 115 mm, pitch 452.4 to 462.4 mm), door-only;
tried by hand: no fail, scoped check 8.7 s. Bundle 34,259 B; report 3,792,417 B. 11 new tests;
`make kiln` 3 min 21 s, `make check` 11 min 8 s green (853 + 141 passed). Simulation not run.

## S-116 — v0.4 DoD 5: a fresh agent changed the door from its context alone (2026-11-01)
Run per S-115's protocol (`tests/e2e/module-transcripts/README.md`) on a built kiln copy at 016689b:
a fresh-context subagent got the 34,259-byte door bundle (design role, `n2f context asm://door`,
the door's geometry code), the folder and the owner's request (spacers 10 mm further apart). It
read the bundle, the spacer interface and the `door-standoff` lines of `parameters.yaml`, set
`door-standoff-inset` 120 → 115 mm (pitch 452.4 → 462.4 mm), ran validate, `build --asm door`,
`check --scope`, `build`, `check`: no failure, nothing signed; `--verify`: only `parameters.yaml`
changed, in the context. Seven tool calls, about 1 min 43 s. The bundle went by file, not pasted;
the client exported only its final message (`door-2026-11-01.md`). One run, one easy change.

## S-117 — The build plan is a valued read; the checks record what the hardware stage reads (2026-11-01)
Gate C found S-110's plan reads were constants: `bom://build-plan#…` did not parse, so `value_of`
gave `unknown:<key>` and a plan-only change (a `driver:`, a part's name) left the assembly sheet,
the manual and the report stale. `build-plan` is now a `bom` id (`core/uris.py`; a later selector
segment may start with a digit, for a unit named `2-stage`); its value is the plan file's field,
bare `bom://build-plan` the whole plan, while `bom://rollups` keeps the bom rule's hash (P14). The
bom rule declares `also_produces: bom://build-plan`, so `--explain`, impact and `n2f graph` see
it. The checks rule records `#name #children #build #driver #ports` per assembly and `#name` per
part (`spare:`, `loose:` live in `children`). `drawing://` reads are valued too (the report's
were constants). `values.unvalued_reads` lists any constant read; tests assert `{}` on the kiln.

## Review gate C (architecture and honesty) — outcome (2026-11-01)
Reviewed at 016689b (report: `docs/reviews/v0.4-gate-c.md`): NOT READY on two D5 blockers; placement,
ports, hardware counts, scope, context and v0.3 compatibility held. **Blockers fixed (S-117):**
(B1) plan reads valued — `test_a_plan_only_change_rebuilds_the_sheet_the_page_and_the_report`
(the driver change rebuilds `asmsheet:pod`, `doc:assembly`, `report`, nothing geometric;
`doc_staleness` flags the page first), `test_a_renamed_part_reaches_its_units_sheet`. (B2) the
checks record each assembly's fields — `test_the_hardware_verdict_follows_spare_without_a_forced_rerun`
(warn, pass, warn). **Concerns:** C7 fixed (`test_every_recorded_read_has_a_value`, units fixture
and kiln; it found the report's `drawing://` reads); C1 fixed (a refused `asm://` party skips the
"remove from ports" rule, `test_loader.py`); C3–C6 fixed by the gate D task; C2 → B-0067; the
sheet's unrecorded step total → B-0068.

## S-118 — Joints in owner words: `name:`, `closed_in:`, build order, no sheet text below 2.2 mm (2026-11-01)
Gate D found joints unreadable to the owner. An interface gets two optional fields: `name:` (the
joint in owner words; plan, sheets and check messages fall back to "<part> to <part>"; a label,
left out of sign-off evidence like a part's `role`) and `closed_in: asm://<unit>` (closed in a later
step: listed where its parts meet, "closed later, in step N", and again in that step; hardware
counted once; `L14-closed-in` warns on a unit not built after). Both dump only when set, so v0.3
files hash as before. A step's joints follow its child lines (a joint comes with the later part).
Joint messages name parts and the joint; ids, offsets and frames move to `failures`/`fix` in
`--json`. A sheet cell wraps (up to three lines) instead of shrinking below 2.2 mm. Closes B-0066, B-0068.

## Review gate D (UX, owner persona) — outcome (2026-11-01)
Reviewed at 016689b (`docs/reviews/v0.4-gate-d.md`): NOT READY on two blockers, both joint messages.
**Fixed (S-118):** (1) a misaligned joint reads "Inner sheet-metal shell and Ventilated touch guard
do not line up at their joint "Shell to guard, top wall": their holes are 5.0 mm apart (0.5 mm
allowed). Move the holes or the parts so they meet."; (2) a passing one "the 4 holes line up on both
parts, and in the assembled mini electric test kiln (within 0.01 mm)", welded "the faces touch by
design (no loose fixings); they meet in …"; gate C's C3–C6 too. **Concerns fixed:** 3–7, 9, 10, 13
(the kiln's lid joint `closed_in: asm://kiln`, the manual's prose to match), 14–17; 8 by dropping the
footer's claim; 12 by labelling each count. **To BACKLOG:** 11 → B-0069, balloons (8) → B-0070, one
count per unit (12) → B-0071. Screenshots judged by the agent only; not yet by the maintainer.

## S-119 — v0.4 closed: version 0.4.0, pins, handoff report (2026-11-01)
The three version files read 0.4.0 (S-054) and the product pin moves to `>=0.4,<0.5` wherever S-083
put it: manifest default, template and example `n2f.yaml`, product CI workflows, test fixtures;
`uv.lock` follows. No schema change, so a 0.3 product loads with the pin notice (S-056, P14).
`HANDOFF-REPORT-v0.4.md` takes the definition of done item by item: 1–6 and 8 met, 7's gates closed
(S-117, S-118); `check-full` from a clean clone and the tag are the maintainer's. Measured on a fresh
kiln copy: build 62.4 s, check no fail (251 OK), report 3,792,169 B, door context 16,524 B, mass and
box as the golden. `make check` here: 10 min 8 s green (870 passed, 5 skipped; goldens 141). Open:
B-0064, B-0065, B-0067, B-0069–B-0071, and the Linux nightly's evidence-key failure (a separate
task). Judged by the maintainer: "looking right" (the build plan section and the door sheet), 2026-11-01.
## S-120 — The v0.5 and v0.6 plans reconciled with v0.4; the Linux evidence-key defect opened (2026-11-01)
Read `HANDOFF-REPORT-v0.4.md` and S-112–S-119 against `FOUNDATION.md` and `ELECTRICAL_STAGE.md`.
Changed in the plans: the registries carry what v0.4 added (a tenth rule kind, `also_produces`,
15 report sections, the build-unit drivers as an open set, and a context contribution per domain so
`n2f context` shows a unit's circuits); `build: external` is a third value beside `unit` and
`phantom` and the build plan lists it as supplied; the kiln's choice example moves off DEC-021
(decided in M3b) to DEC-022's bolt length or B-0065's rivets; the `make check` budget is v0.4's
10 min 8 s, not 10 min; M6's budget grows with `promote.py` (1,299 → 1,647 lines). Opened B-0073:
the first Linux nightly failed on four kiln example sign-offs because a part's evidence key hashes
the mesh; fixing it (invariants, D14) is a prerequisite of v0.5 M0, outside the waves.
## S-121 — Sign-off evidence keys are tolerance-compared invariants, not the mesh (2026-11-01)
Amends S-040; closes B-0073. The first Linux nightly `check-full` (run on S-105) failed four kiln
example sign-offs: a part's key hashed its tessellation, and the kernel meshes bent sheet
differently on Linux and macOS, so a sign-off recorded on one machine was void on the other.
A part now keys as `inv:` plus volume, area, bounding box, centroid, face/edge/solid counts and
its features rounded to 1 µm; an assembly as `inv:` plus placements rounded to 0.1 µm and its
counts. `keys_match` compares `inv:` numbers within 1e-6 relative (D14's tolerance; platform
noise is near 1e-10, a real change never that small); text keys compare as before. The v0.3/v0.4
hashes are still accepted (`legacy_keys`) until the next schema bump (F7), so no existing sign-off
is voided. Measured on a fresh kiln copy: 0 needs-human before and after re-keying its six
sign-offs (`scripts/rekey_signoffs.py`); a test changes the mesh hash and keeps the sign-off, and
changes the volume by 1 % to void it. Docs and drawings still key on output hashes: whether those
differ on Linux is what the next nightly says; B-0073 reopens if they do.
## S-122 — v0.5 M0 baseline: the before numbers (2026-11-01)
Measured on `main` at 4c8d66c. Dry run (scratch branch, discarded): a no-op rule family, verify kind,
check stage, report section and doc helper, each shown reached by `n2f build` on a bracket copy, edited
10 files, 7 under `core/`: `graph/{rules,runs,impact}.py`, `checks/{evaluators,engine}.py`, `lint.py`
(L1's binary kinds), `model/requirements.py` (target schemes), plus `docs/engine.py`, `report/builder.py`,
`report.html.j2`; lint and requirements were missing from §0.2 and M1, now added. `grep -rlw` files
over `src/napkin2factory/` (all / without `templates/`, `report/vendor/`): kiln 19/13, door 34/25,
chamber 11/5, alcove 10/4, union 41/32. Lines: promote 1,647, loader 1,060, screening 866,
concept_checks 710, geometry/build 728. `make check` in a task folder: 10 min 14 s (613.6 s), green,
876 passed and 5 skipped, then 141 goldens.

## S-123 — v0.5 M1: the domain contract and the registries (2026-11-01)
`core/domain.py` holds F1's types, `core/registry.py` 15 registries (rule families, verify kinds,
check stages, gate rows, report sections, doc helpers, vocabulary, model families, context, screens;
processes, finishes, interface kinds, categories, drivers as `core/data/*.yaml` plus domains');
`domains/mechanical` is v0.4 in place (F2). Bracket, enclosure, kiln: keys, reports, pages, checks,
stages byte-identical to `main`. [revisit] `reads_all` families (checks, report, site) run after
every producer; a non-mechanical domain's hash is a `domain:<name>` input of its rules and of
validate/doc/checks/report. Hooks: `core/loader.py`, `core/uris.py`, `cli/check.py`,
`bom/build_plan.py`, `rulepacks/checks.py`, `concepts/screening.py`, `geometry/build.py`.
`tests/unit/test_domain_contract.py` (29): the toy domain edits 0 core files (S-122: 7). `make
check`: 11 min 7 s (S-122: 10 min 14 s), green, 907 passed, 141 goldens.

## S-124 — v0.5 M4: scope as data (2026-11-01)
`n2f.yaml` `scope: {<domain>: {state, decision, note, stub}}` (`stub:` beyond F11 [revisit]); a
requirement is a domain's by tag, category, or its verify kind or schemes [revisit]. `later` drops
non-safety requirements and gate rows from Design and Verify with a row; safety still blocks. L15
lints both. `build: external` stubs (`assemblies.validate_refs`; loader: the call plus two guards
[revisit]); `model/loads/` (`acts_on`). Kiln DEC-024. Status: "Electrical: later — the electrician
wires it; the box keeps its cable entries (DEC-024)"; Verify row "Electrical: later (DEC-024) — not
checked at this stage; no requirement waits for it"; report "Scope. <line>."; cover "Scope: <line>"
plus `release.json`. B-0076, B-0077. `test_scope.py` 20 passed, 15.2 s; `make check` green, 927
passed, 141 goldens, 14 min 42 s (other tasks alongside).
## S-125 — v0.5 M2: schema policy, the migration hook, calc reference cases (2026-11-01)
Closes B-0042; DoD 4, 12. `core/model/migrate.py` (by (from, to); `pending`, `apply`; `CURRENT` 1, none yet):
`n2f init .` snapshots, migrates, says what changed; a newer schema stops it and every load (the loader's
one call). `tests/fixtures/schema/v1` = the bracket at v0.4; a throwaway 1→2→3 round-trips byte for byte.
F17: kit `CASES` per pack; product `model/calcs/<m>.cases.yaml` on its own inputs; a `calc-case` stage after
sourcing (a row per calc, one per kit pack used); lint `L16-calc-case` (M4 took L15) [revisit]. Cases:
thermal_enclosure 11 (1 external), power 10 (2), mass_cost 5 (1): all 23 kit functions; kiln 21 calcs, 21
cases from `test_calcs.py`; kiln `n2f check`: 23 `calc-case` rows, all pass. External: Kanthal "Design of wire
elements" p. 51 (90.9 A, 3.95 W/cm², read in the PDF); Incropera 6th ed. Ex. 3.1, oven window, 50 °C [verify];
EN 1993-1-1 §3.2.6, steel 7850 kg/m³ [verify]. Hypothesis found the critical-thickness effect (k 1, h 2).
Times: test_migrate 6.5 s, test_calckit_cases 5.3 s, properties 3.8 s; `make check` 13 min 4 s, 948 passed.

## S-126 — v0.5 M2b: the checks rule hashes the calc kit (2026-11-01)
Closes B-0078. The mechanical `checks` family's `code` is now `core/checks`, `rulepacks`, `bom`,
`catalog`, `calckit` (`domains/mechanical/__init__.py`), so a kit formula or data-table edit reruns
the checks: calc requirements and the `calc-case` rows run kit code there. Looked for other runners:
the report and site read `checks.json` and rerun through it; impact's `hyp_calc` runs no calc; the
concept screens and rule packs import the kit outside the build graph (no rule key). Found: part
masses read `calckit/data/materials.yaml` while part keys hash only `geometry/` (B-0080, left open:
the fix moves every part key). `test_domain_contract.py`: the checks pin moved deliberately; new test
(a kit `.py` edit in a package copy moves only `checks`' inputs) failed before the change. No golden
pins a rule key: none moved. `test_domain_contract.py` 30 passed, 24.1 s; `make check` green, 969 passed,
141 goldens, 19 min 6 s (other tasks alongside).
## S-127 — v0.5 M4b: scope is a recorded value; external stubs in the build plan (2026-11-01)
Closes B-0076, B-0077. `core/graph/values.py` values `manifest://scope` (the block, `n2f.yaml` order) and
`manifest://scope#<domain>[.<field>]`; the report reads them only when `scope:` is declared, so no other
product's key moves: bracket and enclosure built on `main` (34f2c4a) and here have the same reads, values,
report and plan in all 11 / 15 rules, only code hashes differ. Cost: a first `scope:` reruns the report only
through its new `DEC-` (B-0081) [revisit]. No check row reads scope. A rig scope edit reruns validate, report,
site; impact names those three. Stubs: a step's `supplied` (only when non-empty) in the plan, the manual step
and the report ("Supplied, not built here" with the joints that fit it); joint words name the stub;
`module-has-parts` passes it (B-0082). B-0083. `test_scope.py` 27 passed, 54.7 s; touched tests 285 passed,
3 min 37 s; `make check` green, 975 passed, 141 goldens, 11 min 38 s.
