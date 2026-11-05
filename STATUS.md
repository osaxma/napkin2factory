# STATUS — napkin2factory

**Version:** 0.7.0, released 2026-11-05 (tag `v0.7.0`, both packages on PyPI, S-244; 0.4.0 and 0.5.0 closed, untagged) · **Trunk:** `main`;
work happens in task worktrees (`make task`, `make land`; S-097) · **Open work:** `BACKLOG.md` ·
**Why things are the way they are:** `DECISIONS.md` (index at the top) · **What shipped:**
`docs/handoffs/HANDOFF-REPORT-v0.6.md` (v0.6), `docs/handoffs/HANDOFF-REPORT-v0.5.md` (v0.5), `docs/handoffs/HANDOFF-REPORT-v0.4.md` (v0.4), `docs/handoffs/HANDOFF-REPORT-v0.2.md` (v0.2), `docs/handoffs/HANDOFF-REPORT-v0.1.md` (v0.1)

## Where we are
v0.7 (everyday breadth, `docs/stages/v0.7-everyday-breadth.md`) is closed at 0.7.0 (S-242): Track A, S-197 to S-241
(structural physics, everyday materials, derived ceremony, region and display units, the table and test-stand products,
the three-tier benchmarks and their two-vendor spec trials, the v0.7 health review); handoff `docs/reviews/v0.7-handoff.md`
(S-239). The commit history carries no personal email (S-243). Released as `v0.7.0` (S-244). Next: Track B, v0.8 (`docs/roadmap/road-to-v1.0.md`).

## Environment (host facts a cold reader needs)
- Reference platform: the macOS host (S-001); Linux is covered by the CI matrix. Python 3.13 via
  `uv`; OCP novtk wheel, renders through the built-in rasterizer; Playwright Chromium installed.
- `export PATH=$HOME/.local/bin:$PATH` before `uv`. No GNU `timeout`; `sed -i ''`.
- Pushing (only when the maintainer asks): `GH_TOKEN` in `.env` (gitignored; a deploy token for
  this repository only) authorizes `git push` and `gh`. Load it unprinted, in the same command:
  `set -a && . ./.env && set +a && git push origin main`.
- Tasks (S-097), measured 2026-11-01: `make task` takes ≈ 2 s (worktree + `uv sync` from the shared
  cache). macOS scans each newly written native library on first load (`syspolicyd`): 117–190 s
  for the first `import build123d` in a cloned environment. `make task` installs with hardlinks,
  so later task folders reuse the scanned files: 10 s (S-098); the import is also warmed detached.
- One test run uses the machine at a time (S-196): a second waits and names the folder
  running. Measured 2026-11-04 under load from other agents: `make check-fast` 124 s,
  `make check` 386 s (1,515 passed); idle host: not measured.
- `make check` ≈ 7 min before S-196 (tests in parallel, S-070; long files split, S-080, S-084);
  `make check-full` ≈ 21 min (2026-11-01: `check` 7 min 27 s, then kiln, demos side by side
  and timing 13 min 27 s; was ≈ 28 min, S-079); the first `import build123d` on a machine takes
  one to two minutes (S-057).
- Never run `n2f build` inside `examples/`; copy a product to a temp folder first
  (`tests.conftest.copy_product`). Templates are synced with `make templates`, never hand-edited.

## Milestones (one line each; detail in the entries named)
v0.7 — `docs/stages/v0.7-everyday-breadth.md` (Track A: structural physics, everyday materials, derived ceremony, region, the three-tier benchmarks), S-197; Track A delivered (S-197 to S-241), closed at 0.7.0 (S-242). Done: v0.6 trials triaged (S-208, blocker fixed in S-215; also S-212, S-214, the docs task); M1 calc pack, materials, dated regional costs (S-198, S-199, S-201, S-207); M2 frame kit, four interface kinds, structural screen (S-202, S-203, S-206, S-211); M3 region, derived ceremony, display units (S-200, S-205, S-219); M4 table and test-stand specs worked and re-derived by a second model (S-204, S-210), the oracle (S-209), the kiln spec (S-218); health review (S-217). Also: the table and test-stand products, the two-vendor spec trials (S-234), the structural screen for bare legs, trestles and a cross member (S-235), init asks region and units (S-236), health review (S-237), quick fixes (S-238), the fourth spec trial, the §2.1 measures and the handoff (S-239), trial 4 fixes (S-240, S-241), version 0.7.0 (S-242). The commit-email rewrite (B-0242) is done (S-243).

v0.6 — `docs/stages/v0.6-electrical-stage.md` (the electrical domain through the v0.5 contract; the count of core edits is
the headline), S-111; reconciled with the contract as built in S-141; closed, `docs/handoffs/HANDOFF-REPORT-v0.6.md`,
version 0.6.0 (S-181). `docs/reviews/v0.6-independent-trial.md` is the outside model's brief for after it lands.
Wave times on the host (measured, 2026-11-02 – 2026-11-03): M0 (the baseline and five seam tasks at once) 07:00–07:55, 55 min;
M1 07:56–08:26. `make check` on `main`: 9 min 34 s at 2f42a51 (after M0, 1,135 passed), 9 min 40 s at f82f838
(after M1, 1,173 passed); wave 2 (M2, M3, M4 at once, two seam tasks, M4b) 08:40–09:56; `make check` 10 min 53 s at 8d74564
(after wave 2, 1,290 passed, on a busy host); re-measured on an idle host at 81cecae: 7 min 39 s, green (1,290 passed, 141 goldens), under the 10 min 4 s budget, so nothing moved behind `-m full`. Wave 3 (M6, headroom follow-up S-171, M5) 76 min. After wave 3, M7a, the diagram follow-up (S-174) and the nightly fix (S-175): 8 min 19 s at 6135323, green (1,323 passed, 141 goldens), idle host (2026-11-03). Linux: the push run of `make check` on 7d90121 is green on ubuntu and macOS; the two nightlies since S-121 (2026-11-02, 2026-11-03, on the pushed 7d90121) passed S-121's sign-off evidence keys and failed only on BSD `mktemp` in `demo-napkin.sh` (fixed in S-175, verified in a Debian container; main is not pushed).
- M0 seam tasks (v0.5 defects, counted apart from the domain): a domain's files in the release package (S-142,
  B-0099); a rule family runs `before=` a named one (S-143, B-0125); interfaces treated by their spec's type
  (S-144, B-0126); the scope words, a "left for later" status, the domain's own word, stand-ins (S-148–S-152,
  B-0115–B-0119).
- M0 baseline and tables (the kiln's electrical survey `docs/v06-baseline.md`, report 3.8 MB, cold build 69 s; the
  conductor, earthing and wire-colour tables and `calckit.wiring`; E5: no parts-list seam, B-0128) — S-147, S-146, S-145.
- Wave-2 seam tasks (v0.5 defects the domain tasks found, E10): a family's membership key, interface field reads,
  `rule:` keys and `#props.` figures in the contract, a helper's build folder (S-165–S-167); a card field's `param`
  from any declaration, the screens import order, every status worded in a gate row, a public scope line (S-160–S-164).
- M1 the family and the joint (`domains/electrical/` installed: supply, devices, circuits, product conductors, the
  `cable-entry` kind, the Design row "Wiring", every other registration stubbed for wave 2; 0 core files) — S-153, S-154, S-155.
- M2 the `elec` rules: per-circuit diagram, record and text schematic; schedule, labels, cables to buy — S-156, S-157.
- M3 the wiring checks, the `circuit` verify kind, the supply-headroom choice, six fault fixtures — S-158.
- M4 the Wiring report section, manual helpers, Verify row, owner words, module context (S-159); the supply screen
  moved from the kiln's pack into the domain (M4b, E8) — S-168.
- M5 the kiln wired (EU 20 A/32 A circuit classes and `Supply.dedicated`, S-171; four circuits, three cable entries, the manual's wiring generated, the headroom choice decided, `demo-electrical.sh`, S-172; diagram readability follow-up, S-174).
- M6 the external-box fixture (a box supplied from elsewhere, two cable-entry ports), the diff page's "<label>: added", the owner-session script — S-169, S-170.
- M7a the docs for the wiring (`docs/electrical.md`, the guide, the three roles, vocabulary, `docs/domains.md`) — S-173; portable `mktemp` in demo scripts and bare-repo `--git-dir` in publish tests — S-175, S-177.
- DoD 7 owner simulation passed (supply-headroom choice raised after first build with wiring, decided by the owner) — S-176.
- Gate G (electrician read-through + engineering) — "Review gate G — outcome", blockers fixed in S-178, S-179, S-180; Gate H (UX, owner persona) — "Review gate H — outcome", blockers fixed in S-179, S-180; close-out, 0.6.0 — S-181. The maintainer's visual judgment is pending.

v0.5 — `docs/stages/v0.5-foundation.md` (the seams: domain contract and registries, toy domain, the kiln out of the
package, schema policy, scope as data, choices), S-111; reconciled with v0.4 in S-120; closed,
`docs/handoffs/HANDOFF-REPORT-v0.5.md`, version 0.5.0 (S-140);
its prerequisite B-0073 (platform-stable sign-off evidence keys) is fixed in S-121: the push run of
`make check` on 8bd1d47 is green on ubuntu and macOS; no nightly has run on a commit after S-121
yet (the latest, 10:28 on 2026-11-01, predates it), and `main` is not pushed during v0.5.
Wave times on the host (measured): M0 14 min; M1 65 min; wave 2 (M2, M3, M4 at once, then the
M2b and M4b follow-ups) 21:06–22:25, 79 min. `make check` on `main`: 9 min 7 s at b1916cc
(after M1, 908 passed), 9 min 14 s at a45d364 (after wave 2, 998 passed). Wave 3 (M5, M6 and the gaps task
at once) 22:37–23:50, 73 min; `make check` at d6ad20f 9 min 10 s on an idle host, 1029 passed. M7: docs and
M5b at once 23:52–00:40; the two simulations 00:45–01:30; gates E and F at once on c686da3, 28 min; their
fixes, three tasks at once, 01:40–02:50.
- M0 baseline (the before numbers: files a new step edits, product words, file sizes, check time) — S-122.
- M1 the domain contract and its registries (`core/domain.py`, `core/registry.py`, `domains/`), the toy domain, `docs/domains.md` — S-123.
- M2 schema policy (`docs/schema-policy.md`, migrations, `n2f init .` upgrades) and calc reference cases (`calc-case` rows) — S-125; the checks rule hashes the calc kit (M2b) — S-126.
- M4 scope as data (`scope:` in `n2f.yaml`: in / done elsewhere / later; external stubs; load cases) — S-124.
- M4b scope follow-ups (the scope a recorded read of the report; stubs said in the build plan) — S-127.
- M3 the kiln out of the package (screens declare their fields; the heated-box screens are the kiln's own `model/screens/`; product rule packs; `site.width`; neutral style roles; the F9 guard) — S-128.
- Gaps after waves 1–2 (`--target` and prose URIs from the registries, `manifest://` URIs, density in part keys, stub rows, no example ids, screen fields and phase, domain style roles; B-0081, B-0087 open) — S-129.
- M5 choices (`choice` rows, `build/checks/choices.json`, "waiting on you" in `n2f status`, `n2f decide`; the kiln's bolts-into-a-spacer choice) — S-130.
- M6 splits (`validate_refs` beside each schema; `concepts/promote/`; `build_part`/`build_asm`) and `make check-fast`, the land gate — S-131.
- M7a docs (`docs/domains.md` final, the guide, the roles), `n2f doctor` listing the domains, the two simulation protocols (gadget domain, kiln choice) — S-132.
- M5b gaps after wave 3 (a release held by an open choice, the report's "waiting on you", decided-not-applied, scope always read, `manifest://` links, neutral walls words; B-0097 closed in S-135 with the contract's seven gaps from the gadget run) — S-133, S-135.
- DoD 2, the count: a fresh agent added the gadget domain from `docs/domains.md` alone, 0 core files — S-134.
- DoD 6: the kiln choice simulation, raised after the first build and decided by the owner — S-136.
- Gate E (architecture and honesty) — "Review gate E — outcome"; blockers fixed in S-138 (impact, a recording accessor for
  domains, the tables hashed) and S-139. Gate F (UX, owner persona) — "Review gate F — outcome"; blockers fixed in S-137
  (the napkin stage for any product) and S-139 (the release and choices). The maintainer's visual judgment is pending.

v0.4 — `docs/stages/v0.4-product-structure.md` (sub-assemblies, ports, parts placed by interfaces), S-103; closed,
`docs/handoffs/HANDOFF-REPORT-v0.4.md`:
- M0 baseline and reconciliation (`docs/v04-baseline.md`) — S-105.
- M1 interfaces place parts (`place_by`), frame expressions, alignment checked in the assembly — S-106.
- M2 sub-assemblies have ports (`ports:`, a part's home, `place_by` for sub-assemblies) — S-107.
- M3a build plan and hardware — S-110. M3b kiln restructure — S-113.
- M5 napkin modules and promotion — S-112. M4 scope and module context — S-114.
- M6 joints review and simulation protocol — S-115; door simulation passed — S-116.
- M7 gate C (architecture and honesty) — "Review gate C — outcome", blockers fixed in S-117; gate D
  (UX, owner persona) — "Review gate D — outcome", blockers fixed in S-118; close-out, 0.4.0 — S-119.

v0.3 — released 0.3.0 on 2026-11-01: journals, README for people and the agent guide, brand,
`AGENTS.md` only, roles in `roles/`, gate reports kept, faster checks, pin `>=0.3,<0.4` —
S-073–S-084. Landed after the tag and shipped with 0.4.0: the v0.2 leftovers and share mode
`n2f publish` (S-085–S-096), one trunk and a worktree per task (S-097–S-102).

v0.2 — `docs/stages/v0.2-napkin-stage.md`:
- M0 folds and ratifications — S-055–S-061.
- M1 concept cards, loader, lint, optional Napkin gate — S-062.
- M2 massing fidelity, calc kit, screening — S-063, S-064, S-065.
- M3 styled screenshots, `style.yaml`, kit aesthetics — S-066.
- M4 board, promotion, form requirements, `rule` verify kind — S-067.
- Gate A (honesty + architecture) — "Review gate A — outcome".
- M5 PM-skill napkin protocol, DoD 7 simulation — S-068.
- M6 kiln retrofit, `demo-napkin.sh` — S-069.
- Parallel `make check` — S-070. Gate B (UX, owner persona) — "Review gate B — outcome".
- M7 close-out, release, CI gate — S-071, S-072.

v0.1 — `docs/stages/v0.1-grand-plan.md`, closed 2026-10-31: M0–M9 and gates 1–4 — S-001–S-054 and the four gate
entries; `docs/handoffs/HANDOFF-REPORT-v0.1.md`. The former milestone paragraphs are kept verbatim in
`docs/history/STATUS-through-v0.2.md`.
