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
| S-128 | v0.5 M3: the kiln out of the package: screens declare their fields, the heated-box screens are the kiln's own pack (`model/screens/`), product rule packs, `site.width`, neutral style roles, the F9 guard | in force; its guard amended by S-185 |
| S-129 | v0.5 gaps: `--target` and prose URIs from the registries, `manifest://` URIs, part keys read their density row, stubs get no module row, no example ids, screens declare fields and phase, domain style roles; B-0081, B-0087 kept open | in force |
| S-130 | v0.5 M5: choices (`choice` status, `build/checks/choices.json`, `n2f decide` writes a `DEC-`, reopened on evidence); the kiln's bolts-into-a-spacer choice (DEC-022) | in force |
| S-131 | v0.5 M6: splits and the fast gate (`validate_refs` beside each schema, `concepts/promote/`, `build_part`/`build_asm`, `make check-fast` as the land gate) | in force |
| S-132 | v0.5 M7a: docs, doctor, simulation protocols (`docs/domains.md` final, `n2f doctor` lists the domains, the gadget and kiln-choice protocols) | in force |
| S-133 | v0.5 M5b: the gaps wave 3 left: a release held by an open choice, the report's "waiting on you", decided-not-applied as a Design caveat, the scope always read, `manifest://` links resolve, neutral walls words; B-0097 waits in a separate task | in force |
| S-134 | v0.5 DoD 2: a fresh agent added the gadget domain from `docs/domains.md` alone; 0 core files changed or opened | in force |
| S-135 | v0.5 M5b follow-up: the concept summary line says only generic values; a product's screens add their own phrases (`SUMMARY_PHRASES`; closes B-0097); `docs/domains.md` fixed where the gadget run found it short (S-134) | in force |
| S-136 | v0.5 DoD 6: the kiln choice simulation; the choice raised after the first build, decided by the owner | in force |
| S-137 | v0.5 gate fixes 3: the napkin stage for any product ("the space", no door unless the card names one; the kiln's "alcove" from its pack's `WORDS`); a failing product screen or rule check is one plain line; lint L17 names the `door`/`stand` role aliases | in force |
| S-138 | v0.5 gate E fixes, the build graph: impact sees whole-object reads (B1), domains read through a recording accessor (B2), the core tables are rule inputs (B4), a bad `--set` is a plain error (C7), the impact test covers every toy field (C14) | in force |
| S-139 | v0.5 gate fixes 2: a decided pick not yet in the model holds the release; the package holds the released report; choice words, runnable pick commands, one release refusal, the demonstration cover | in force |
| Gate E | Review gate E (architecture and honesty, v0.5) — outcome | outcome recorded; blockers fixed, the rest in BACKLOG |
| Gate F | Review gate F (UX, owner persona, v0.5) — outcome | outcome recorded; blockers fixed, the rest in BACKLOG; the maintainer's visual judgment pending |
| S-140 | v0.5 close-out: version 0.5.0, product pins `>=0.5,<0.6` | in force |
| S-141 | The v0.6 plan reconciled with the contract v0.5 built: devices as a family, cable entries as a bolt-pattern spec, the seam tasks named | in force |
| S-142 | A domain's files in the release package (closes B-0099) | in force |
| S-143 | A rule family can run before a named family (`before=`), so a manual reads a domain's outputs from the same build | in force |
| S-144 | Interfaces are treated by their spec's type: a domain kind with a bolt-pattern spec gets the hole match and alignment (the seam E4 needs; a v0.5 defect) | in force |
| S-145 | E5: the conductors stay in the electrical domain's own schedule; no parts-list seam in v0.6 (B-0128) | amended by S-188 |
| S-146 | The wiring tables in the calc kit: conductors (ampacity by cited table and column; silicone rows at the PVC floor), earthing arrangements, wire colours; `calckit.wiring` | in force |
| S-147 | v0.6 M0 baseline: the kiln's electrical survey (`docs/v06-baseline.md`), its report size and build time; `make check-full` cited from S-140 | in force |
| S-148 | Seam (gate F 6): one table of scope words, "done here" / "left for later (not designed here yet)" / "done elsewhere (supplied, not built here)"; the cover's "Not included"; the kiln's electrical requirements tagged (closes B-0115) | in force |
| S-149 | Seam (gate F 7): `later` is a check status, "left for later", counted apart; the checks read each domain's scope state (closes B-0116; amends S-127's "no check row reads scope") | in force |
| S-150 | Seam (gate F 8): a domain is said by its own owner word, else its title, else its key (closes B-0117) | in force |
| S-151 | Seam (gate F 10): `n2f status` with work done elsewhere and no stand-in shows the product, the missing stand-in its first bullet (closes B-0119) | in force |
| S-152 | Seam (gate F 9): a stand-in is "supplied, not built here" everywhere; its joint said by its interface's description (closes B-0118) | in force |
| S-153 | v0.6 M1: the electrical domain's package and wiring model (four families, connection ends parsed by the domain, the fields wave 2 needs, `model/` and `interfaces/` as folders so the `elec` code hash leaves out the owner's view) | in force |
| S-154 | v0.6 M1: how the wiring model addresses instances, upstream protection, entries by voltage band (the overseer's decisions on the kiln survey; amends E2, E3, E6) | in force |
| S-155 | v0.6 M1: a cable entry is one hole; the Design row "Wiring" blocks on unwired devices; tests that assumed one installed domain take the membership form | in force |
| S-156 | v0.6 M2: the schedule rule's id is `elec-schedule`, so the key `rule:elec-schedule` the checks and manuals record is valued (the core reads `rule:<x>` as rule `<x>`'s output) | in force |
| S-157 | v0.6 M2: the `elec` outputs (the record drawn and tabulated, a left-to-right diagram from the supply, colours never guessed, labels, the cable to buy, the text schematic kept) | in force (layout amended by S-174) |
| S-158 | v0.6 M3: the wiring checks (rows per rule, the nets walked with contacts and coils, the controller's side for a limit, which materials conduct, the headroom choice, the circuit kind's figures under `#props.`) | in force (amended by S-178: a conductor against its protective device, the Class II shortcut) |
| S-159 | v0.6 M4: the owner's view of the wiring (the Wiring section with its diagrams made page-safe, the manual helpers, the Verify row, the words, the module context) | in force |
| S-160 | v0.5 defect (v0.6 wave 2): a card field's `param` comes from any declaration naming one, not only the first; two different ones are an error naming both files | in force |
| S-161 | v0.5 defect (v0.6 wave 2): the screen contract imports no schema at load, so a domain declaring `CardField`s at import loads whatever is imported first; `docs/domains.md` §1 says which public names are safe at a module's top (measured) | in force |
| S-162 | v0.5 defect (v0.6 wave 2): `check_rows_state` says every status it counts ("1 choice waiting on you"), the core's owner word where the domain gives none | in force |
| S-163 | v0.5 defect (v0.6 wave 2): `scope_entry(product, domain)` is the public way for a domain to say its scope line | in force |
| S-164 | v0.5 defect (v0.6 wave 2): `HelperContext.build_dir`, the build folder a manual page renders in | in force |
| S-165 | Seam (v0.6 wave 2, a v0.5 defect): a model family's membership key `set://<family>`, recorded wherever the family is listed during a run; impact touches it for a new object (closes B-0140) | in force |
| S-166 | Seam (v0.6 wave 2, a v0.5 defect): an interface field read is valued by its field as written, as impact matches it (closes B-0136) | in force |
| S-167 | Seam (v0.6 wave 2, v0.5 defects): a `rule:<x>` key is rule `<x>`'s output, refused when no rule answers; a verify kind's figure is `#props.<figure>`; the docs rule hands helpers its build folder (closes B-0135, B-0139, B-0147) | in force |
| S-168 | v0.6 M4 (E8): the supply screen is the wiring's (`circuit-available`, phase `check`); the kiln's pack reads its fields | in force |
| S-169 | v0.6 M6: the diff page says a report section the later Revision's package adds or drops ("Wiring: added"); a domain left for later or done elsewhere counts as not there | in force |
| S-170 | v0.6 M6: the external-box fixture (a control box supplied from elsewhere, two cable-entry ports), the scope words tested with the wiring's owner word, the owner-session script for DoD 7 on that fixture | in force (boundary words amended by S-174) |
| S-171 | v0.6 M5 follow-up: cited EU 20 A and 32 A circuit classes, so a European 16 A supply raises the supply-headroom choice; `dedicated: true` on the supply is the `dedicated` pick made in the model (closes B-0149, B-0151) | in force |
| S-172 | v0.6 M5: the kiln wired (four circuits, earth points named by the metal they earth, three cable entries in the gland holes' places, five bought parts, two studs), its manual's wiring generated, the headroom choice decided, `demo-electrical.sh` | in force |
| S-173 | v0.6 M7a: the docs for the wiring (`docs/electrical.md`, the guide, the three roles, the vocabulary, `docs/domains.md` read against the domain); an owner who asked to be asked decides every choice in that area, whatever it holds | in force |
| S-174 | v0.6 follow-up: the wiring diagrams readable at the kiln's size (the box's side of each entry, labels never overprinted, titles by purpose, the core's boundary words; closes B-0152, B-0154) | in force |
| S-175 | The kiln demos' `mktemp` calls take a template ending in X's (GNU and BSD alike), and a unit test keeps every script that way: the Linux nightly was red on BSD-only `mktemp -d -t name`; the napkin demo's test matches a promoted requirement by its line, not its id (closes B-0159) | in force |
| S-176 | The wiring session simulation (DoD 7) passed on 2026-11-03: the supply-headroom choice raised after the first build with wiring, not in the interview, decided only with the owner's answer; no fix to `roles/pm.md`; B-0160 opened | in force |
| S-177 | The two publish tests read their temporary bare repository with `git --git-dir=<remote>`, not `cwd=<remote>`: robust under `safe.bareRepository=explicit` (tests only) | in force |
| S-178 | v0.6 gate G blockers 1–2: each conductor against the device that protects it (a new `conductor-protection` row), and the Class II shortcut only where no part that conducts meets mains wiring (else a warn) | in force |
| S-179 | v0.6 M7: every wiring output carries the licensed-electrician note (diagram footer band with product, circuit and Revision or draft; `electrical/README.txt` shipped in the release package; manual helper's opening line; report headings by purpose; closes B-0157) | amended by S-193 (the note removed; footer and README.txt kept) |
| S-180 | Seam (gate H B1, C7; gate G blocker 3; B-0160): a design change request's patch dry-run in its impact report; `Domain.disclaimer` in the package `README.txt` and the report; the `later` → `in` cover line; `"an agent may decide it"` only when the area is delegated (closes B-0184, B-0160) | amended by S-194 (`Domain.disclaimer` removed) |
| Gate G | Review gate G (electrician read-through, then engineering, v0.6) — outcome | outcome recorded; blockers fixed (S-178, S-179, S-180), the rest in BACKLOG |
| Gate H | Review gate H (UX, owner persona, v0.6) — outcome | outcome recorded; blockers fixed (S-179, S-180), the rest in BACKLOG; the maintainer's visual judgment pending |
| S-181 | v0.6 close-out: version 0.6.0, product pins `>=0.6,<0.7`, `HANDOFF-REPORT-v0.6.md` | in force |
| S-182 | Loud failures for wrong param units, circular domain import, output dir escape; runtime Pillow (closes B-0163, B-0156, B-0105) | in force |
| S-183 | v0.6.0 released: CI green on both platforms, tagged, published; wiring visuals judged by the maintainer | in force |
| S-184 | Six modules over 750 lines split, code moved verbatim, each file under 550 lines | in force |
| S-185 | Structural F9 guard: AST string constants and qualified URIs replace blind text match (amends S-128) | in force |
| S-186 | Fail n2f check when a made part's material density is assumed mild steel | in force |
| S-187 | Cost delta names added or edited unpriced parts | in force |
| S-188 | A Domain bom_lines hook brings consumables to the parts list (amends S-145 E5, closes B-0128) | in force |
| S-189 | Reorganize root docs into docs/stages/, docs/handoffs/, docs/roadmap/ | in force |
| S-190 | The periodic health review: trailers and due notice, make health, review brief | in force |
| S-191 | The roadmap review: reproducible benchmark numbers, one change store, discovery, region, v1.0 contract | amended by S-192 |
| S-192 | The vision in the maintainer's words; "wherever" means any agent client; the tool's voice and one disclaimer | in force |
| S-193 | The electrical domain's own disclaimer removed from every wiring output | in force |
| S-194 | Generated output carries no AI mark; how a design was made is the sharer's to say | in force |
| S-195 | `make land` refuses a placeholder the task cites but does not define | in force |
| S-196 | Faster test runs: one run at a time, 16 workers spread per test, prebuilt products, in-process CLI | in force |
| S-197 | v0.7 opens: Track A as `docs/stages/v0.7-everyday-breadth.md`, W-series decisions, waves | in force |
| S-198 | Structural calc pack: members | in force |
| S-199 | One materials table, everyday materials, dated regional cost bands | in force |
| S-200 | Product region and display units field | in force |
| S-201 | Structural calc pack: joints, wood, fatigue, load cases | in force |
| S-202 | Frame kit: rectangular, round and T-slot profiles, rail section, slotted tabs | in force |
| S-203 | Four mechanical interface kinds through the mechanical domain (amends W5) | in force |
| S-204 | The table benchmark spec: worked figures, Track A's mass limit and budget moved by the physics | in force |
| S-205 | Ceremony derived from the model (W6) | in force |
| S-206 | The generic structural screen reads loads from the site and members from the massing (amends W4) | in force |
| S-207 | Calc pack fixes from the table benchmark: Johnson columns, room-temperature EMC, composite creep, budget screen | in force |
| S-208 | The v0.6 independent trials, triaged: one blocker (a change request that removes a part), fixes before the benchmarks | in force |
| S-209 | The benchmark oracle judges outcomes, not ids | in force |
| S-210 | The test-stand benchmark spec: an aluminium portal with a base beam closing the load loop; Track A's budget and column heights moved by the physics | in force |
| S-211 | The structural screen counts self weight and short columns | in force |
| S-212 | Discard keeps filed change requests; plain words on promotion | in force |
| S-213 | The trial's documentation gaps closed | in force |
| S-214 | Each conductor carries what it feeds; an empty cable entry is not a failure | in force |
| S-215 | A change request may remove parts, parameters and joints | in force |
| S-216 | Landing resolves a backlog row both open and closed after a merge | in force |
| S-217 | Health review 2026-11-04 — outcome | in force |
| S-218 | The kiln's benchmark spec, retrofitted from its model | in force |
| S-219 | Display units: the owner's unit first | in force |
| S-220 | Automated tests do not require example sign-offs to stay current | in force |
| S-221 | The table benchmark product | in force |
| S-222 | The test-stand benchmark product | in force |
| S-223 | Benchmark follow-ups: the oracle reads unsigned safety requirements | in force |
| S-224 | Review gate I (v0.7) — outcome: NOT READY; two blockers (fixed-base racking, region not reaching costs), twelve concerns | in force |
| S-225 | Review gate J (v0.7) — outcome: NOT READY; four blockers (an unrun structural check reads as an all-clear, costs without region and date, metric manuals in an imperial product, dimension groups half converted) | in force |
| S-226 | Gate J blockers fixed: unrun checks shown, manuals and dimension groups in the owner's units | in force |
| S-227 | Gate I blockers fixed: fixed-base racking, the product region in costs | in force |
| S-228 | Spec reproduction trial 1 (test stand): a cold agent reaches a green product; the oracle passes 30, fails 14, mostly where it encodes the example's modelling | in force |
| S-229 | The table top's cross-grain path, worked | in force |
| S-230 | The oracle judges outcomes, not one agent's modelling; the generic cost screen prices by the metre and the square metre | in force |
| S-231 | The using docs ship with the tool: `n2f docs` | in force |
| S-232 | The diff page survives a failed shader; its test no longer flakes | in force |
| S-233 | Package fixes from spec trial 1 | in force |
| S-234 | Spec reproduction trials 2 and 3 (table, two vendors): both reach a green product; the structural screen cannot judge bare legs, trestles or a cross member | in force |
| S-235 | The structural screen judges bare legs, trestles and a cross member | in force |
| S-236 | Init asks for region and units; the oracle allows an agent's extra inspection and its own massing | in force |
| S-237 | Health review 2026-11-05 (v0.7 close) — outcome | in force |
| S-238 | Health-review quick fixes before 0.7.0 | in force |
| S-239 | v0.7 close: spec trial 4, the §2.1 measures, the handoff | in force |
| S-240 | Trial 4 message and doc fixes: card and assembly hints, quantity abs, calc kit docs | in force |
| S-241 | Trial 4 package fixes: auto-layout spacing, mains without a supply, finish in lint | in force |
| S-242 | Close v0.7: version 0.7.0, pins >=0.7,<0.8 | in force |
| S-243 | The commit history carries no personal email | in force |
| S-244 | v0.7.0 released: CI green on both platforms, tagged, published | in force |
| S-245 | Open v0.8 (Track B): the bidirectional-iteration stage plan, R-series | in force |
| S-246 | M1a: store primitives and the checkpoint format | in force |
| S-247 | M1c: the no-change build (the CAD kernel loads only when a rule runs; R12) | in force |
| S-248 | M2a: `ecr/lifecycle.py` split into state, apply and revisions, code moved verbatim | in force |
| S-249 | B-0259: CI budgets for the two nightly timing tests, measured on the runner | in force |
| S-250 | v0.8 wave 1 boundary: 4 core/ files, R12's first timings, `make check` time | in force |
| S-251 | Wave 2 seam: checkpoint vitals from a fresh build; change-request baseline and approval hash fields | in force |
| S-252 | Wave 2 seam: `working_hash(exclude=...)`; a change request's approval hashes the model without `changes/` | amended by S-254 |
| S-253 | M1b: checkpoints, `undo` / `redo` / `rollback`, an undoable `discard`, plain words for B-0121 | in force |
| S-254 | M2b: live change requests: `ecr start`, edited in place, one open at a time; `impact`, `approve`, `close`, `abort`, `quick`; `new` and `apply` bridge; amends S-252 | in force |
| S-255 | M5: the thin experimental MCP server (`n2f mcp`), the skill (`n2f skill`), the prompt set and the first trigger rates | in force |
| S-256 | v0.8 wave 2 boundary: 7 core/ files (10 in v0.8), R12's timings with the new verbs, `make check` time | in force |
| S-257 | Health review 2026-11-06 (v0.8 wave 2 boundary) — outcome | in force |
| S-258 | B-0272: local `make check-full` runs the no-change build and screenshot timing tests too | in force |
| S-259 | B-0273: `core/concepts.py` split into render and lint modules, code moved verbatim | in force |
| S-260 | Runs hand off in the repository (`docs/handoffs/v<x>-overseer.md`); the per-client file test checks tracked files | in force; amends S-076's test |
| S-262 | B-0270: `cli/checkpointing.py` moved to `ecr/checkpointing.py`, code verbatim; imports updated | in force |
| S-263 | M3a seam: a card's built figures (`built:`), `Vcs.files`, a parked card needs a reason, decision links warn | in force |
| S-264 | M3a: `n2f concept switch` parks and restores a direction by file; `model/rulepacks/` is the product's | in force |
| S-265 | M3a: `concept fork-from-model` and `compare`; the board marks built cards | in force |
| S-266 | v0.8 wave 3 boundary (M2c, M3a): the core count, R12's four timings, `make check` | in force |
| S-267 | M3b: promotion keeps the card's loads, sag limit and budget, in the owner's units; new card files keep `built` | in force |
| S-268 | M4: the guide and roles teach checkpoints, live change requests and directions; `docs/cli.md` checked against the CLI | in force |
| S-261 | M2c: schema 2 and the change-request migration: `draft → approved → closed` / `aborted`, an open request has a baseline, `parked` cards; the old patch steps are gone | in force |
| S-269 | M4.0: the oracle judges a change request, an agent's own or replayed on a copy | in force |
| S-270 | v0.8 wave 4 boundary (M3b, M4.0, M4): the core count, R12's four timings, `make check` | in force |
| S-271 | Review gate K (v0.8) — outcome: NOT READY; three blockers (a change-request id reused after a rollback, impact calls an unrepriced estimate computed and unchanged, a built card's total mass in the shapes row) | in force |
| S-272 | Gate B's scripted flow on the test stand | in force |
| S-273 | Gate K fixes: one change-request id forever, approval bound to the approved checkpoint | in force |
| S-274 | Gate K fixes: every impact figure labelled, a built card's mass in the total row | in force |
| S-275 | The test stand's load-cell requirement follows the rated load (B-0279) | in force |
| S-276 | Health review 2026-11-06 (v0.8 close) | in force |
| S-277 | Gate B fixes: seeding skips a requirement already held, the switch names the card's failures | in force |
| S-278 | The oracle judges a gate B product: every checkpoint, built and parked cards | in force |
| S-279 | Gate B (v0.8) — outcome: passed by cold agents of two vendors; the oracle passes both products as the spec states them | in force |
| S-280 | Review gate L (v0.8) — outcome: NOT READY; five blockers (the example failed lint, the report's requirement tile, stale manufacturer text after a change, status silent on an open change request, the close's sign-off wall) | in force |
| S-281 | Gate L fixes: impact names stale words, close lists what stands in the way | in force |
| S-282 | Gate L fixes: status names an open change request, the report counts requirements, plainer switch and undo words | in force |
| S-283 | v0.8 close: the §2.1 measures and R12 timings | in force |
| S-284 | Close v0.8: version 0.8.0, pins >=0.8,<0.9, the handoff | in force |
| S-285 | v0.8 visual exit: the board's built-design card, judged by the maintainer | in force |
| S-286 | v0.8.0 released: CI green on both platforms, tagged, published | in force |
| S-287 | Open v0.9 (Track C): the progressive-workbench stage plan, V-series | in force |
| S-288 | v0.9 wave 1: the lens seam, viewer picking, the bridges gone, the upgrade's applied requests | in force |
| S-289 | v0.9 wave 1 boundary: the `core/` count, §11's sizes and timings, `make check` | in force |

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
macOS host: 8 min 19 s wall, against ≈ 12 min serial (docs/improvements.md §2, 723a347). Each
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
replayed, so nothing can conflict). Commit `6167443` on `main` predates this and keeps its
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
Run per S-115's protocol (`tests/e2e/module-transcripts/README.md`) on a built kiln copy at 7e24852:
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
Reviewed at 7e24852 (report: `docs/reviews/v0.4-gate-c.md`): NOT READY on two D5 blockers; placement,
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
Reviewed at 7e24852 (`docs/reviews/v0.4-gate-d.md`): NOT READY on two blockers, both joint messages.
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
Measured on `main` at 8bd1d47. Dry run (scratch branch, discarded): a no-op rule family, verify kind,
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
product's key moves: bracket and enclosure built on `main` (fdbe2dc) and here have the same reads, values,
report and plan in all 11 / 15 rules, only code hashes differ. Cost: a first `scope:` reruns the report only
through its new `DEC-` (B-0081) [revisit]. No check row reads scope. A rig scope edit reruns validate, report,
site; impact names those three. Stubs: a step's `supplied` (only when non-empty) in the plan, the manual step
and the report ("Supplied, not built here" with the joints that fit it); joint words name the stub;
`module-has-parts` passes it (B-0082). B-0083. `test_scope.py` 27 passed, 54.7 s; touched tests 285 passed,
3 min 37 s; `make check` green, 975 passed, 141 goldens, 11 min 38 s.

## S-128 — v0.5 M3: the kiln out of the package (2026-11-01)
DoD 3; F8–F10, F15. `concepts/screens/`: a runner in phases (measure, estimate, total, check) and six generic
screens declaring their card fields (`@reads(CardField…)`), skeleton and lint from them; thermal, supply, skin,
chamber, controls moved to `examples/kiln/model/screens/heated_enclosure.py`; `core/packs.py` loads
`model/screens/` (hashed into the concept build) and `model/rulepacks/*.py` (in `checks` only when present).
`site.width/depth/height`, `alcove_*` read with lint C10; roles `opening`/`support`, `door`/`stand` read. 4 kiln +
5 fixture cards: values, notes, verdicts identical; rows now system first, compared by id [revisit]. Lines:
screening 894 → 167, concept_checks 710 → 538. F9 guard 154 hits/23 files → 0 (71 in 9 wave-2 files listed,
B-0084); S-122 union 43/34 → 45/36, kiln 19/13 → 13/7. Guard 0.4 s, packs 14.6 s; `make check` 9 min 13 s,
green, 997 passed, 141 goldens.

## S-129 — v0.5 gaps: the rows waves 1–2 left, closed or kept open with why (2026-11-01)
Closed: B-0074 (`--target` reads the rule-family registry; a family is a target by its name, v0.4 names stay aliases);
B-0075 (`find_uris` matches registered domains' schemes); B-0083 (`manifest://product|scope` is a URI, never matched in
prose; `n2f impact --set manifest://scope#wiring.state=in` names the report); B-0080 (a part rule's `material` input is
its shared density row, read from `calckit/data/materials.yaml`: a mild-steel edit reruns the kiln's 9 steel parts, not
its 4 brick or 10 declared ones; every part key moves once, props do not); B-0082 (a stub gets no `module-has-parts`
row via `RuleNotApplicable` in `rulepacks/checks.py`, outside the named files; the Build plan sheet lists it); B-0084
(`ALLOWED` empty, every number kept); B-0089 (`Screen(fields, phase)`, `Domain.style_roles`, the role constants live
registry views; two YAML-split role `words` quoted). Kept open [revisit]: B-0081 (`report/builder.py`, not this wave's;
free at the v0.5 upgrade), B-0087 (`concept_checks.py`, M6's). `make check` green, 1006 passed, 141 goldens, 13 min 58 s.
## S-130 — v0.5 M5: choices (2026-11-01)
DoD 6 (M7 runs the simulation); F12, F13. `core/checks/choices.py::offer` returns `choice` only with ≥ 2 valid options,
else `fail` naming the one fix or none (§7, tested). The engine keys a choice on `detail.evidence`, lifts a rule pack's
options from its violation, writes `choices.json` (none without a choice, F16); a decided one reads `pass` until a key moves.
An open choice blocks the gate `blocks` names; `n2f release` reads no Released blocker (B-0092) [revisit]. `n2f decide`
writes a plain `DEC-`, check, option, name, keys in its `sources` (B-0094) [revisit]; `--agent` only for `none`. The rule
(hardware stage, `fastening://`): bolts into both ends of a spacer must not meet; sizes from names, sheets from kit
`thickness`. DEC-022's blind tapping is no fix (14.8 + 15.0 > 25 mm): M6 x 12 at both ends, or M6 x 35 through, nut (ISO
4762/261/4032, 1 d engaged, 2 pitches past [verify]). Status: "Waiting on you: 1 choice", "… 25 mm, steel (it holds the
release)". B-0082: a stub by name. test_choices 18 passed, 40.5 s; `make check` green, 1016 passed, 141 goldens, 13 min 55 s.
## S-131 — v0.5 M6: splits and the fast gate (2026-11-01)
DoD 8, 9; F15. Lines before → after: loader 1,107 → 386 (`Product`, `Paths`, `Doc` → new `core/product.py`, 366,
re-exported [revisit]); promote 1,658 → `concepts/promote/` (12 modules, largest `verb.py` 362); geometry/build 728 →
57 + `build_part.py` 344 + `build_asm.py` 416; concept_checks 538 → 428 + `concept_rules.py` 140 (the runner);
screening 167 (M3). `validate_refs` in parts, interfaces, assemblies, parameters, signoff, run in their old order:
validate's problems identical on 3 examples and 40 fixtures. B-0086: a product's screens may expose
`PROMOTE_REQUIREMENTS`/`PROMOTE_RATIONALE` (`promote/packs.py`); the kiln's seeds the supply row (`POWER_KEY`
dropped) [revisit]; promote goldens unchanged. `make check-fast` (lint, types, unit, smoke) is `make land`'s gate:
2 min 1 s, host idle at start. `make check`: 9 min 52 s, green, 1000 passed, 141 goldens (another task's tests ran
for about 3 of those minutes; 14 min 7 s fully alongside one); under S-119's 10 min 8 s, so no file moved to `-m full`.

## S-132 — v0.5 M7a: docs, doctor, simulation protocols (2026-11-02)
DoD 7 (first half), 11 (docs); DoD 2 and 6's protocols (the overseer runs the agents). `n2f doctor` lists each domain's verify
kinds (targets, op/value), check stages (run order), screens, the system's and the product's screens; `--json` adds the rest; all
from the registries. `docs/domains.md` rewritten for a reader with no core file: the toy end to end, every signature and object
handed over, the pitfalls (load inside `installed`, CLI in-process, unique names), scope, choices, packs and their promotion hooks,
§9 not registrable (release files B-0099, calc packs B-0100) [revisit]. Guide, napkin, cli, product model, checks, calc kit, kit,
vocabulary; the four roles and the product `AGENTS.md` (scope, method by consequence, a case per calc), synced into all three
examples (the kiln's copies too: `test_synced_copies_are_byte_identical` needs them) [revisit]. Protocols: `domain-transcripts/
README.md`, `intake-transcripts/choice-kiln.md` (by hand: build 58 s, check 3 s, `n2f decide` 16 s, DEC-025, nothing waiting);
their tests skip until a transcript exists. Closes B-0079, B-0085, B-0090, B-0096, B-0098. `make check`: 12 min 7 s, green, 1038 passed, 7 skipped, 141 goldens.
## S-133 — v0.5 M5b: the gaps wave 3 left, closed or kept open with why (2026-11-02)
Closed: B-0092 (`gate_blockers` adds open choices holding the release: "cannot release v1.0.0 yet: • a choice is waiting on
you: … — `n2f decide …`"; `demo.sh` decides the bolts as "demo owner", shorter bolts (no nut to reach), before v1.0.0 and
again before v1.1.0: ECR-001 moves the guard-standoff joints and reopens it, B-0101); B-0093 (`VOCAB` words, the overview
lists open choices with options, gate, command); B-0095 (`pass` with its decision, F12, plus a Design caveat "decided in
DEC-x (…), not yet applied — the designer makes the change: …" until the rule passes on the model: stage Design, release
not held [revisit]); B-0081 (`manifest://scope` always read; every report key moves once, no golden pins one); B-0091
(`Product.resolve` maps `manifest://product|scope`); B-0087 ("the inner space"/"wall" unless the sharing screen gives
`inner_words`/`wall_words`; the kiln's says "chamber"/"insulation": cards, board golden unchanged). Open: B-0097, done in
task `v05-m5b-summary` (WIP): it needs `cli/concept.py`, `promote/decision.py`, `verb.py`, outside this task's files.
`demo-design.sh` (with `demo.sh`) green, 13 min 45 s beside other tests; `make check` green, 1034 passed, 141 goldens, 11 min 44 s.
## S-134 — v0.5 DoD 2: the gadget simulation, 0 core files (2026-11-02)
Run by the overseer per `tests/e2e/domain-transcripts/README.md` on a detached copy of `main` at af3b80b: a fresh subagent with no
history got the scripted request and the contract (`docs/domains.md`, 47,952 bytes, read from the copy). In 224 s and 14 tool calls
it wrote `tests/fixtures/domains/gadget/`, a product and `tests/unit/test_gadget_domain.py` (15 tests, one per registry plus impact
and the code hash). Judged by the overseer: gadget and toy together 49 passed; files changed under `src/napkin2factory/core/` 0 (both
counts), under `src/` 0; files opened there: none (every tool call read). Transcript: `gadget-2026-11-02.md`. The contract fell short
in seven places (L1 needs a value with a unit for a comparing kind; the categories unlisted; optional fields vs mandatory tests;
toy assertions that assume one extra domain; card-field key uniqueness; two test-setup facts; `cli.build.targets` not in the import
list): fixed in `docs/domains.md` by the next task. The gadget itself is not kept in the repository: the transcript is the record.

## S-135 — v0.5 M5b follow-up: the build summary's product phrases; the contract where the gadget found it short (2026-11-02)
Closes B-0097 (the rest of B-0086). `concepts/build.py::summary_line(card, screening, root)` says size, mass and cost; a product's
screens module may expose `SUMMARY_PHRASES` (`fn(card, screening) -> [phrase]`, read like `PROMOTE_REQUIREMENTS`), after the mass,
before the cost; the kiln's screens carry the supply and heat-up phrases, moved verbatim. `cli/concept.py`, `promote/decision.py`
and `verb.py` pass the product root (given to this task by the overseer after S-133). Without a root the line names nothing
heated. Promote goldens and the kiln board unchanged. `docs/domains.md`: `SUMMARY_PHRASES` beside the promotion hooks, and the
seven places S-134's gadget run found short, each checked in the code: L1 for every non-binary kind (units `parse_quantity`
reads, `%`; bare numbers for `count` only); the eight system categories; which test goes with a field left out; membership, not
exact lists; card-field keys (first declaration wins); the section order (`joints` always listed) and why the impact test
rebuilds with `render=False`; `cli.build.targets` in the import list and §8. Touched tests (promote, concept e2e, screening, F9, transcript, agent docs) 3 min 26 s, green.

## S-136 — v0.5 DoD 6: the kiln choice simulation (2026-11-02)
Run by the overseer per `tests/e2e/intake-transcripts/choice-kiln.md` on an unbuilt kiln copy at 6ff5d2f: a fresh subagent with the
product `AGENTS.md` and `roles/pm.md`, six scripted owner lines one at a time (545 s, 38 tool calls). Not in the interview (two
replies, four delegated `DEC-`s); named in one line after the first build and raised in full when the owner asked about the guards,
both options with what they take and their estimated cost, no check id; `n2f decide … --pick shorter-bolts --by "Sam Rivera"` after
line 5 only (DEC-029, `made_by: human`). The PM then applied the pick itself as the designer before any release (allowed), so the
decided row gave way to the new bolt's row passing on the model; criterion e assumed an unapplied pick and is amended to accept
both forms [revisit]. B-0102: whether a decided pick should go through a change request before release. Transcript:
`choice-kiln-2026-11-02.md`.

## S-137 — v0.5 gate fixes 3: the napkin stage for any product (2026-11-02)
Gate F B3: generic rows and promotion say `{space}`, "space" or a screens module's `WORDS = {"space": …}` (`core/packs.py`, seeded
into `values.shared` like S-133's walls words; the kiln's says "alcove"). A check may pick a wording variant (`title_door`…):
`fits-site-width` does for a hinged door only, else "it is 600 mm wide but the space is 500 mm wide"; promotion "Fits the space width".
Door fields are `hint=False`: a new card lists them only once it names a door. Gate F B4 and concern 5: a product screen or rule-pack
check that fails while running is one `N2FError` naming the file, the screen or check and the next step (`screens/runner.py`;
`core/packs.py` wraps `CHECKS`, passing `RuleSkip`/`RuleNotApplicable`, imported lazily from `rulepacks` [revisit]). Gate E C13:
`promote/door.py` → `swing.py`, `about: alcove` → `space` (`--json`). Gate E C8: lint `L17-renamed-roles` (warn) for `role:`/`palette`/
`finish` aliases; L12's fix names the table's roles. Kiln: its four cards re-screen equal, goldens unchanged, six L17 warnings (B-0103).
Regression tests (each seen failing on `main`'s code): `test_screening_any_product.py`, e2e `test_concept_any_product.py`, `test_lint_role_aliases.py`.
## S-138 — v0.5 gate E fixes, the build graph: whole-object reads in impact, a recording accessor, the core tables hashed (2026-11-02)
B1: impact matches a read and an edit of one object when one field path starts with the other (`impact.py::_edit_matcher`):
`iface://x#spec.depth` reaches rules reading `iface://x` whole, `dec://DEC-xxx#rationale` the checks. B2: `RunContext`,
`StageContext` and a new `SectionContext` (a section's `data(sctx)`, was `(product, build_dir)`; contract unreleased) carry
`proxy(obj, uri)` and `log`, merged into the rule's reads; the toy and `docs/domains.md` use it. B4: each open set a rule reads
adds `table:<file>`, the hash of `core/data/<file>.yaml` (the bom now also reads drivers and interface kinds, the report finishes
and style roles); those keys move once, code hashes and goldens do not. C7: `parse_set` raises `EditError`, an `N2FError`. C14:
the impact test runs per toy field and for the toy interface. Tests, each seen failing first: `test_impact_honest.py` (kiln
interface and decided-choice edits: impact said `['validate']`; driver words reran nothing; bad `--set`), the toy's field and
interface cases. Rule-pack edits: B-0104. Measured: kiln build without renders 40.8 s; `make check` 16 min 9 s, 3 failures (a
pinned reason text, an example word) fixed.
## S-139 — v0.5 gate fixes 2: the release and choices (2026-11-02)
Gate E B3 = gate F blocker 1: `choice_blockers` adds, under `released`, every decided choice whose `blocks` is not `none` and whose row is still in `choices.json` (the rule does not yet pass on the model): "a choice is decided but not yet in the design: … you chose X (DEC-n), but the design and its parts list do not show it yet; your agent makes the change (…), then builds and checks". S-133's "release not held [revisit]" is reversed; the Design caveat stays. Tests: `test_a_decided_pick_not_yet_made_holds_the_release`, `test_a_decided_choice_not_yet_applied_holds_the_release` (flipped), `test_the_kiln_release_waits_for_the_pick_to_be_made` (kiln-shaped, no build).
Gate F blocker 2: `release` re-renders the report after the Revision exists, writes it into the package folder and re-zips (`zip_stage`); the zip is still built before the snapshot, so a failure leaves no Revision. Tests: `test_release_package_and_site`, `test_the_pick_made_releases_with_the_released_report`.
Gate F concerns: 11 (`hardware.py`: "each spacer (<name>)" in the title, "each bolt goes … into the spacer", the sums explained, "threaded all the way through", and whether the listed spacer says so in its name or notes); 12 (one runnable `n2f decide … --pick <id>` per option in status and report; `--pick 1` accepted, `pick_option`); 13 (`n2f decide` prints "Next: your agent makes the change …"; owner text says "your agent"); 14 (one refusal with every reason; "Next:" names a choice holding a later gate while the first open gate has only caveats); 17 (the cover: DEMONSTRATION with the example requirements and titles, "Choices made"; `release.json` gains `choices` and `example_signoffs`). Each test above failed on `main` and passes now.
Demos: `demo.sh` decides, sees the dry-run release refused, makes the pick by editing the model (a first release: no change request yet), builds, re-signs, saves, releases; `demo-design.sh` brings ECR-002's patch context (the door's bolt line) up to date before applying it [revisit: a pre-authored patch that the model outgrew]. The kiln model keeps its choice open. Measured on the host: both demos side by side 16 min 56 s, green; `test_choices.py` + `test_signoffs.py` 4 min 6 s; `test_release_diff.py` 3 min 2 s.

## Review gate E (architecture and honesty) — outcome (2026-11-02)
Reviewed at c686da3 (report: `docs/reviews/v0.5-gate-e.md`): NOT READY on four blockers; the seams held (core imports no domain,
goldens unchanged since 3544ebe, scope never hides a safety requirement, an open choice stops the release, `n2f check` never
decides, splits and `check-fast` within budget). **Blockers fixed:** B1 impact missed rules reading an object whole when one of
its fields was edited (older than v0.5 for interfaces) and B2 domain rules read the model raw (a recording accessor for rules,
stages and report data; the contract's section `data(sctx)` changed) and B4 the `core/data` tables hashed into no rule — S-138,
`tests/unit/test_impact_honest.py`, the toy contract tests; B3 a decided pick not yet in the model could be released — S-139,
`test_the_kiln_release_waits_for_the_pick_to_be_made`. Concerns fixed: C7, C14 (S-138), C8, C13 (S-137). Open in BACKLOG:
C1–C6, C9–C12 (B-0105 … B-0114).

## Review gate F (UX in the owner persona) — outcome (2026-11-02)
Reviewed at c686da3 (report: `docs/reviews/v0.5-gate-f.md`): NOT READY on four blockers; the scope block, "waiting on you" with
costs, the plain `n2f decide` refusals and the newer-format message read well. **Blockers fixed:** 1 a decided pick released
unapplied (= gate E B3) and 2 the package's report was the pre-release draft — S-139 (`test_release_package_and_site`); 3 a
shelf's board and promoted requirement said "open door" and "alcove" and 4 a failing product screen printed a traceback — S-137
(`test_screening_any_product.py`, `test_concept_any_product.py`). Concerns fixed: 5 (S-137), 11–14 and 17 (S-139). Open in
BACKLOG: 6–10, 15, 16, 18, 20, 21 (19 joins gate E C10) (B-0115 … B-0124). Visual exit (S-078): the status output with the
kiln's choice and the report's scope line, `docs/reviews/v0.5-status-choice.png` and `v0.5-report-scope.png`, retaken after
S-139 — judged by the agent (readable; the spacer's catalogue name stays in brackets); the maintainer's judgment pending.

## S-140 — v0.5 close-out: version 0.5.0, product pins `>=0.5,<0.6` (2026-11-02)
As S-119 did for 0.4: `pyproject.toml`, `packaging/n2f/pyproject.toml` (and its `napkin2factory==`) and
`src/napkin2factory/__init__.py` read 0.5.0 (S-054); the pin moves to `>=0.5,<0.6` wherever S-083 put it:
the manifest default and its error example (`core/model/manifest.py`), the template sources and
`examples/{bracket,enclosure}` `n2f.yaml` and product CI workflows (synced with `make templates`), the kiln's
`n2f.yaml` (its `scope:` kept) and workflows, every `tests/fixtures/**/n2f.yaml`, `tests/unit/test_version_pin.py`
and the layout line in `docs/product-model.md`; `uv.lock` follows. Dated transcripts under `tests/e2e/` keep
the pin they ran with. No schema change (F16), so a 0.4 product loads with the pin notice. `docs/domains.md` §6
now names S-137's `WORDS = {"space": …}` hook beside the promotion hooks. `make check` in the task folder:
12 min 6 s green (1087 passed, 5 skipped; goldens 141 passed), no other pytest running.
## S-141 — The v0.6 plan reconciled with the contract v0.5 built (2026-11-02)
Read `HANDOFF-REPORT-v0.5.md`, `docs/domains.md` and `core/domain.py` against `ELECTRICAL_STAGE.md`.
The contract offers everything the plan assumed except three things, now written into it: a
domain cannot add a field to a core schema, so devices are a family (`device://<id>` naming its
`part://`), not an `electrical:` block on parts (E2, [revisit] a schema-extension seam); a domain
cannot add lines to the parts list nor make `bom` run after it, so M0 decides between a seam task
and the domain's own schedule (E5); the release package takes no domain files (B-0099). A
`cable-entry` spec extends the bolt-pattern spec so the core cuts its hole (E4). The known seam
gaps (B-0099, B-0115–B-0119, E5's) become M0's tasks, landed before M1 and listed apart from the
count (E10). The F9 guard forbids the kiln's part ids in the domain's words (E6). Budgets follow
v0.5's figures: `make check` 10 min 4 s with no slack, `make check-full` 29 min 14 s (S-140).
## S-142 — A domain's files in the release package (closes B-0099) (2026-11-02)
A seam task under E10 (v0.6's wiring diagrams must ship), counted apart from the domain's count.
`Domain.release_files=(ReleaseFiles(folder, patterns=("**/*",), title=""),)`: `folder` under
`build/` (normally the rule family's `output_dir`), globs inside it, owner words for the cover.
`make_bundle` copies each match to `<domain name>/<path inside folder>`, keeping the layout the
rules wrote, and the cover's Contents line names the folder with its title only when a file was
copied, so a product without such files gets the package it had (the bracket's Contents line is
pinned by a test). An absolute folder or pattern, a `..`, or the whole build folder is refused at
`register`: the package is the manufacturer's, and nothing else of `build/` belongs in it.
`release.json` lists no files today, so it is unchanged. `docs/domains.md` §3.14.
## S-143 — A rule family can run before a named family (`before=`), so a manual reads a domain's outputs from the same build (2026-11-02)
A v0.5 defect (E10), found by the overseer reading the code before M1 (B-0125). `RuleFamily` had only `after` and ties
go by installation order, so a domain's family `after=("part",)` ran after `doc`: a manual page showing its outputs (E5's
wiring section) rendered from the previous build's files, missing on a first build, right only on the second; a domain
cannot add an `after` to a mechanical family. `RuleFamily.before` names families that wait for this one: the registry
(`_waits`) counts it as their `after` in the order and in `target_kinds` (so `--target docs` builds it); naming a
`reads_all` family is redundant, a name nothing installs is ignored, a loop is the existing error naming the families,
and a `reads_all` family naming a producer is that error too. `rules_for_target`, `explain_build` and `n2f impact` follow
unchanged (the first two read `target_kinds`, impact the recorded reads). No `before` anywhere: today's order, rule keys
and goldens unchanged (a field is in no key). `tests/unit/test_family_before.py`, with the old order kept as a control.

## S-144 — Interfaces are treated by their spec's type: a domain kind with a bolt-pattern spec gets the hole match and alignment (2026-11-02)
A v0.5 defect (E10, B-0126) found by reading the code before v0.6 M1: the build cut a domain kind's bolt-pattern holes by the spec's type,
but `check_interface` sent every non-core kind to its own check only, and the report, the fastener check and the alignment words keyed on
the kind's name. Now a spec that is a `BoltPatternSpec` (a subclass too) gets the hole match, the alignment (P3) and then the kind's
`check`: the worse status wins, the core's message first, the kind's result under `kind_check` (left out when empty, so the kiln's 13
interface rows are byte-identical: built before and after, diffed). One party with no geometry: "the hole is cut in <part>; <other>
has no shape to check it against", alignment skipped (no example has such a joint). `BoltPatternSpec` is public (`docs/domains.md` §1,
§3.9). A domain kind with a mating-face spec stays its own check's alone: the build records a face and the interference check allows
contact only for the name `mating-face`, both outside this task (B-0127) [revisit].
## S-145 — E5: the conductors stay in the electrical domain's own schedule; no parts-list seam in v0.6 (2026-11-02)
Decided by the overseer (ELECTRICAL_STAGE E5, M0). v0.6 keeps the conductors in the electrical domain's own schedule;
the parts-list seam (a `bom_lines` hook on the contract and `bom` running after the families that feed it) is not built
in v0.6. Reasons: the conductor table can carry no honest prices, so cable lines would enter the parts list unpriced and
muddy its cost rollups; the electrician's need is met by the schedule plus a per-conductor "cable to buy" total, which
ship in the release package now that B-0099 has landed (S-142); it keeps the seam work of M0 to the defects gate F and
S-132 already named. The ordering half exists since S-143 (a domain family may name `before=("bom",)`); the hook does
not. Open as B-0128. DoD 2's "the conductor lines reach the parts list only if M0 adds the seam" takes the second branch. [revisit]
## S-146 — The wiring tables in the calc kit and their typed loader (2026-11-02)
`calckit/data/conductors.yaml` (25 rows: EU 0.75–4 mm² PVC 70 °C and silicone 180 °C; US 18–10 AWG MTW/THHN, SF-2 silicone,
SJT-class cord), `earthing.yaml` (TN-S, TN-C-S, TT, IT, IEC 60364-1 §312.2 and what a Class I product needs), `wire_colours.yaml`
(EU 9, US 6), read by `calckit/wiring.py` (`conductor`, `conductors`, `earthing`, `colour`; an unknown id raises listing the
known ones, since a wiring model naming one is a typo). Ampacity bases, each cited per row: EU IEC 60204-1 Table 6 column B2
at 40 °C (the lowest method; = IEC 60364-5-52 B.52.4 × 0.87); US the 60 °C column (NEC 110.14(C)) of NEC 310.16 / NFPA 79
Table 12.5.1, NEC 402.5 for SF-2, NEC 400.5(A)(1) column B for cords [verify]. No silicone table could be read, so the EU
silicone rows carry the PVC value as a floor, valid by B.52.14's square-root rule up to 150 °C ambient [verify] [revisit].
All values were transcribed by the agent without the standards at hand; the vendor and standards sites refused reads [verify].
## S-147 — v0.6 M0 baseline (2026-11-02)
`docs/v06-baseline.md`: 12 electrical part files surveyed (the two controllers, contactor, SSR, door switch, thermocouple ×2,
element, glands ×3, earth studs ×5, label, box, lid), their makers' ratings and terminals where readable: the contactor's
(IEC 60947-4-1 marking), the SSR's (third-party pinout), the thermocouple's polarity; the two controllers and the door
switch stay `terminals: []` (datasheets not readable here, §7 risk 3). The connections from the kiln's documents, each
gland's circuit (the door switch and the four bonding leads have none), each stud's part, 4 of 9 custom metal parts bonded
only through a joint, a proposed device list and three circuits for M5, and seven open points (one part with several
instances, an upstream protective device that is no part, missing parts). Kiln cold build 69.1 s, report 3,796,445 bytes.
`make check-full` not re-run: the code equals a2832f6's, so S-140's 29 min 14 s is the baseline.
## S-148 — Scope words: one table, the cover's "Not included", the kiln's electrical requirements (2026-11-02)
Closes B-0115 (gate F 6), a v0.5 seam (E10, counted apart). `SCOPE_WORDS`/`SCOPE_MEANS` in `core/model/manifest.py`
are the one table every surface reads (status, check, report, cover): `in` "done here", `later` "left for later (not
designed here yet)", `external` "done elsewhere (supplied, not built here)". Lines read "Electrical: left for later (not
designed here yet) — <note> (DEC-024)". The cover adds "Not included in this package:", one bullet per `later` or
`external` domain with its decision's title, what is left out with it and the safety requirements still to sign
(`ecr/release.py::not_included`, in `cover_notes`). Kiln: REQ-006, -008, -009, -018, -019, -024 tagged `electrical`
(supply, door switch, limit device, earthing); REQ-007, -016, -021 stay untagged (box placement, the element as a heater)
[revisit]. Measured on a kiln copy: no row newly fails, no sign-off voided; REQ-006 and REQ-024 read "left for later"
(their checks still pass, kept in `detail.later`). `test_scope.py` 40 passed, 49 s; `test_kiln.py` 11 passed, 1 min 31 s.
## S-149 — "Left for later" is a check status (2026-11-02)
Closes B-0116 (gate F 7). A new status, not a flag: the row is no action now, so every surface that words, styles, orders
or counts a status says it (F6's closed set: `results.py`, the CLI and report words, `docs/vocabulary.md`,
`docs/checks.md`); a flag on a `needs-human` row would have left each of them to remember it. The check still runs, its
finding kept in `detail.later`; `summary.later` exists only when a row has it (F16); a safety requirement never reads it.
The `checks` rule reads `manifest://scope#<d>.state` for every domain a requirement could belong to (declared, installed,
a tag or category; "missing" until declared) and, once one is `later`, its decision and each requirement's tags, category
and allocation: a state edit reruns the checks, a note does not. Amends S-127 ("no check row reads scope"); every
product's checks key moves once. `n2f impact` lists the checks for a note edit too (its field-to-entry widening) without
them rerunning. The kiln's `test_kiln.py` DoD 4 row reads the kept finding for REQ-024.
## S-150 — A domain says itself in its own word (2026-11-02)
Closes B-0117 (gate F 8). `core/checks/stage.py::domain_word`: an installed domain's `vocabulary["owner"][<name>]`, else its
`title`, else the scope key capitalised (true today for `electrical`, not installed). The core names no domain's word: the
v0.6 domain registers "wiring" and every scope line, gate row and cover bullet says "Wiring". The owner term named like the
domain shares the vocabulary table with URI-scheme terms; a domain whose name is also its scheme says one word for both.
## S-151 — Status with work done elsewhere and no stand-in (2026-11-02)
Closes B-0119 (gate F 10). `n2f status` loads with `validate()` and goes on when the only errors are the scope's missing
stand-in (rule `external`, subject `scope.<d>`); any other problem stops it as before, and `n2f validate` still refuses.
The missing stand-in is Design's first blocker and a bullet under its scope row naming the file to add and what it needs
(`build: external`, `ports:`, no children, `stub:`), also `missing_stub` in `--json`.
## S-152 — A stand-in is "supplied, not built here" everywhere (2026-11-02)
Closes B-0118 (gate F 9). The Design gate skips `build: external` modules ("not built yet" was false for a thing never
built here); a joint side that is a stand-in carries `supplied` in the build plan and the report says "<name>, supplied,
not built here" (never "no unit"); its "how" is the interface's `description`, else "fitted to <name>, supplied, not built
here"; the interface check's row says "fits <name>, supplied, not built here" in place of "the faces touch by design".
The keys appear only on a stand-in's side: the enclosure built on `main` and here has the same `build-plan.json` and `checks.json`.
## S-153 — v0.6 M1: the electrical domain's package and its wiring model (2026-11-02)
`domains/electrical/`: `__init__.py` composes `DOMAIN`; `model/`, `interfaces/` (M1's), `outputs/` (M2), `checks/` (M3),
`owner/` (M4) export registration tuples, wave 2 fills function bodies. Families: `supply` over `model/electrical/` (id fixed
`supply`, `supply://supply`), `device`, `circuit`, `conductor` (the product's rows, `source` required), each in its own
folder; one `validate_refs`, on `supply`. A connection end is parsed by the domain, not as a core URI (whose fragment reads
`1` as an instance and refuses `+`): `device://x#T`, `part://x#T`, `supply://supply#L`, `asm://<stub>#T`. Fields beyond §3,
so wave 2 adds none [revisit]: Device `coil`, `inductive`, `safety` (interlock | limit), `through` (terminal pairs inside a
device, for the series checks); Circuit `name`, `voltage`, `dc`, `earth`; Supply `dc`, `terminals`. `code` hashes folders
only (a file hashes as nothing, B-0130), so `model/` and `interfaces/` are packages and the `elec` family's code is
`outputs`, `model`, `interfaces`: an `owner/` edit reruns no `elec:` rule. An installed domain is imported while the core's
schemas load: it imports `core.graph` and `core.checks` lazily (B-0129). Core files changed: none.
## S-154 — v0.6 M1: how the wiring model addresses instances, upstream protection, entries by voltage band (2026-11-02)
The overseer's decisions on `docs/v06-baseline.md` §5, binding for M1 and M5. 1 (amends E2, E3): connections name devices
(`device://<id>#<terminal>`); several devices may name a part placed that many times (counted in the assemblies; uncountable:
a warn), `part://` is a shorthand only when one device names the part, `instance:` words each. 2 (amends E3, E6): the
supply's `protection` is `{upstream, rating}` (the site's) or a part; a circuit's is a part, a device or `supply`, and E6's
"no protective device" fail passes for `supply` when the supply has a rating, with a warn for the electrician. 3: the
missing parts are M5's (bought, `verified: false`); type K extension cable is a product conductor row. 4 (refines E6): the
shared-entry warn is extra-low voltage (≤ 50 V AC / 120 V DC, IEC 61140 [verify]) beside mains; PE may share any entry; the
kiln keeps DEC-024's three holes. 5: a joint as an earth path is a `bonded_via` warn; opening parts get a bonding lead (M5).
6: a contact switching a coil warns unless AC-15/DC-13. 7: unsourced terminals stay `[]`, a lint warn, never invented.
## S-155 — v0.6 M1: one-hole entries, the Design row, a second installed domain (2026-11-02)
A cable entry's spec (`CableEntrySpec(BoltPatternSpec)`) is one hole at its frame's origin: `count: 1`, the pattern left
`rect` (the core's one-hole case); §3's `pattern: circle` needs a pitch circle and is refused with the fix. Its check says
"box to cable gland: carries the Heater circuit" after the core's hole sentence, fails a listed circuit with no connection
`via` it, warns on an empty `passes`. Design "Wiring": counts devices and circuits; each load or control device no
connection reaches is a blocker; scope `in` with no content is one too. Verify "Wiring checks" counts `electrical` rows.
Installing a second domain moved tests that assumed one: `test_domain_contract.py` (membership form, `mechanical_only`
sets every other domain aside, the unknown-name lookups use `nonesuch` since `wiring` is now a section), `test_doctor.py`,
`test_graph.py`, `test_report.py` (a section whose `show` is false is off the index), `test_family_before.py`, and
`test_scope.py` ("Wiring: …" where it said "Electrical: …", as S-150 foresaw). `test_electrical_model.py`: 38 passed, 16 s.
## S-156 — v0.6 M2: the schedule rule is `elec-schedule`, so `rule:elec-schedule` is valued (2026-11-02)
The wave-2 brief named the aggregate rule `elec:_schedule` and its key `rule:elec-schedule`. The core values a `rule:<x>`
read as the output hash of the rule whose id is `<x>` (`core/graph/values.py`, as `rule:asmsheet:<id>` is rule
`asmsheet:<id>`'s), so with that id the key would read "unbuilt" forever and a manual or check recording it would never
rerun on a schedule change, silently. The key is what M3 and M4 write in code, so the rule's id follows it: `elec-schedule`
(kind `elec`; it cannot collide with `elec:<circuit>`). Its inputs hold the circuits' ids, so a circuit added or removed
reruns it (it reads only the records it knew). `docs/domains.md` does not say how a `rule:` key is valued: B-0135. [revisit]
## S-157 — v0.6 M2: the `elec` rule family's outputs (2026-11-02)
`elec:<circuit>` writes `connections.json` (the wave-2 record, plus `dc`, a wire's `insulation`, a boundary's `name`),
then draws `diagram.svg` and `<circuit>.kicad_sch` from that record alone, so diagram, record and tables cannot disagree.
Diagram (judged by the maintainer: not yet): nodes in columns by their longest distance from the supply along the wires;
an entry is a dashed box each wire passes through; a module from elsewhere a dashed box with its words above and nothing
inside; each wire on its own track, labelled at its left end "id · size · colour"; columns offset half a row. [revisit]
Colour: the connection's own, else the region's for PE, N or a line terminal, a control circuit's control colour, else
"not given", never a guess. Labels `<wire> <device>:<terminal>`. `cables.csv` totals per conductor; one unknown length
makes it "not given". Calc-kit tables are an input (the code hash skips the calc kit). An interface is recorded whole:
the core values a field read as the whole joint, which impact does not match (B-0136). The text schematic (E1) is kept: a test parses it.
Measured: minimal report 1,668,966 bytes (no Wiring section yet: M4); `test_electrical_outputs.py` 35 passed, 25 s (-n 4).
## S-158 — v0.6 M3: the wiring checks, the `circuit` verify kind, the supply-headroom choice (2026-11-02)
Rows `elec-rule://<rule>@<thing>`, kind `electrical`, from `checks/electrical-v0.yaml` (owner title and fix, numbers as cited params); the model read once through `sctx.proxy` (`calcs.py`), currents by `calckit.power.element_current` at the rated voltage, an unknown never `fail`.
Nets (`nets.py`): connections, an `earth` device's terminals and a `passthrough`'s pairs joined; other `through` pairs are contacts, a coil device's closed only while its coil is live (a fixed point). Interlock: opened, a load still live warns.
Limit: the controller (a non-safety control contact outside power circuits whose opening drops a coil) and what it drives held stuck on, then the limit opened [revisit]. Protection is required of power and control circuits only.
Earth: custom parts whose material conducts by `checks/conduction.yaml` keywords [verify] (no electrical column in the calc kit's materials table, B-0138); all devices Class II/III: one pass row. A bond to no earthed party fails.
Entries: ELV ≤ 50 V AC / 120 V DC (IEC 61140, IEC 60449 band I) [verify]. A contact wired straight to a coil needs AC-15/DC-13, to an inductive load also AC-3 (IEC 60947-4-1, -5-1) [verify] [revisit].
Headroom: above 50 % of the rating (NEC 210.23(A)(2)) [verify] a choice, `blocks: none`, the larger option the region's next class in `circuits.yaml`; none larger is a warn (one option is no choice). Evidence: supply, its rating's param, power circuits, loads.
Circuit rows' subject is the assembly their devices share, so `--scope` keeps them. The kind's figures are `circuit://<id>#props.<figure>`: the core's URI check refuses a selector that is no declared field except `props.*` (`core/loader.py`), so the plan's `#load_current` cannot load (B-0139).
A new device or circuit file alone reruns no check: a family has no membership key (B-0140). Core files changed: none.
Measured: `test_electrical_checks.py` 43 passed, 20 s (one process, on M2's rules).
## S-159 — v0.6 M4: the owner's view of the wiring (2026-11-02)
`domains/electrical/owner/` reads the `elec` files (S-157), never computes. Section "Wiring" (Product, after joints): per
circuit its diagram, then its wires (from `connections.json`, else from the model before the rule ran), the schedule in a
fold, the cable to buy, the `electrical` check rows failing first, a disclaimer (no licensed electrician reviewed it); the
scope line for `later`/`external` is the core's own (`scope_entries`); shown with wiring or a scope entry (E12). A diagram is
inlined only after `owner/svg.py`: no script, handler, foreign object or outside reference, ids prefixed per circuit, its
`<style>` scoped to it (M2's `text{fill:#000}` would restyle every drawing), at the card's width but never below 0.8 of its
own size, past which the card scrolls. Minimal report 1,722,207 bytes, renders on. Helpers `circuit()` (name, purpose, protection, devices, wires,
`table`), `cable_schedule()`, `terminal_labels()`, `cables_to_buy()` (added), each recording `circuit://<id>` and
`rule:elec-schedule`; build folder from `h.product.paths.build` (B-0142). Verify row: "not checked yet" until rows exist,
present with wiring or scope `in`. No owner word for `supply` (it would read "supply supply"), no `engineer` words (§9).

## S-160 — v0.5 defect: a card field's parameter from any declaration (2026-11-02)
Found in v0.6 wave 2 (E8, the supply screen moving into the wiring domain; E10 seam task). A card field's `param`
came from its first declaration, and a domain's screens are declared before a product's own, so a domain declaring
`envelope.power` without a `param` erased a product screen's `param=...`: promotion seeded `power` instead. Now
`concepts/screens/runner.py::declared_fields` keeps the first declaration's unit, kind, example and words and takes
`param` from any declaration that names one; two naming different parameters are a plain error naming both files
(`screen_file`: `model/screens/<x>.py` for a product's pack, else the module's file). Raised wherever the fields
are merged (skeleton, lint, screening, promotion): a field seeding two parameters is a fault in either place.
B-0145. Tests: `tests/unit/test_screen_helper_seams.py`. `docs/domains.md` §1.

## S-161 — v0.5 defect: the screen contract loads before the schemas (2026-11-02)
Found in v0.6 wave 2 (E8): a domain whose `Screen` declares `CardField`s at import failed with "partially
initialized module" when a process imported `napkin2factory.concepts.screens` first: `concepts/screens/base.py`
imported `core.model.concepts`, whose package's first registry lookup imports the installed domains, which import
`CardField` from the half-loaded screens package. `base.py` now imports the schema types under `TYPE_CHECKING` and
`LabelledValue` where it is built. Measured with a probe domain on `INSTALLED` (first imports: `concepts.screens`,
`core.model`, `core.loader`, `cli.app`): `core.domain`, `core.registry`, `core.model.base`, `.interfaces`,
`.manifest`, `core.model`'s `RuleRow`/`ConceptCard`/`Part`, `core.graph.hashing`, `core.checks.results`, `core.units`
and `concepts.screens` are safe at a domain module's top; `core.graph.rules`/`.runner`, `core.checks.stage`/`.choices`/
`.evidence`, `core.model`'s `Verify`, `core.loader`, `core.context` are not. `docs/domains.md` §1 says so (B-0129's
warning). B-0146, B-0129. Test: a fresh interpreter importing the screens first.

## S-162 — v0.5 defect: a gate row says every status it counts (2026-11-02)
Found in v0.6 wave 2 (M4, B-0143): `check_rows_state` counted a `choice` row in the total but listed no word for it
("3 checks: 2 OK"), so the wiring's headroom choice (E11) vanished from its Verify row. The order is now pass, fail,
choice, needs-human, warn, skip, signed, later (`ROW_ORDER`; the others keep their v0.5 order), then any other status
by name; a status the domain's `words` leaves out takes the core's `OWNER_WORDS`, a choice counted as "1 choice
waiting on you" / "2 choices waiting on you" (the CLI's own count). A row without such statuses reads as before (the
toy's "1 check: 1 OK" unchanged); before, an unworded status printed its raw name ("1 needs-human").

## S-163 — v0.5 defect: a domain's scope line is public (2026-11-02)
Found in v0.6 wave 2 (M4, B-0144): the Wiring section imported `core.checks.stage.scope_entries`, outside the
contract's import list. `core/checks/stage.py::scope_entry(product, domain)` returns that domain's entry (its
`line`, `state`, `decision`, `note`, `left_for_later`) or `None`; §1 lists it with `core.model.manifest.scope_line`,
`scope_words` and `SCOPE_WORDS` (already public names, now in the contract).

## S-164 — v0.5 defect: a doc helper knows its build folder (2026-11-02)
Found in v0.6 wave 2 (M4, B-0142): a helper reading its rule's files took `h.product.paths.build`, wrong for a build
run in another folder. `HelperContext.build_dir` (required; only `docs/engine.py` builds one) is
`render_doc(..., build_dir=)`, defaulting to the product's build folder. The docs rule (`core/graph/runs.py`) does not
pass its `ctx.build_dir` yet: `core/graph/` was another seam task's while this one ran (B-0147). Every caller today
builds a product into its own build folder (`ecr/diff.py` builds the other version at its own root), so the default
is the build folder in fact; the one argument closes it.
## S-165 — Seam: a model family's membership key, recorded wherever the family is listed (2026-11-02)
A v0.5 defect found in v0.6 wave 2 (S-158, B-0140): listing `product.families["device"]` recorded only the objects seen, so a
new file reran no check, report or rule that listed the family. The key is `set://<family name>` (`set` already holds the
system's sets; a family named `parts`, `asms`, `reqs`, `params`, `docs`, `decs`, `ecrs`, `signoffs` or `ifaces` is refused at
`register`), valued as the hash of the sorted ids. Not forgettable: `product.families[name]` is a `Members` mapping
(`core/graph/recording.py`); used in any way while a rule runs (the runner sets the read log around `rule.run`) it records the
key, so check stages, sections, doc helpers and other domains' rules do, the electrical domain unedited. The family's own
domain's rules record nothing (its `make_rules` lists the family each build; ids as an input, as S-156; its static reads stay
whole); impact names all that domain's rules for an added file. Rejected: a `members(ctx, family)` helper (needs a domain edit).
Impact: an edit naming an object that does not exist yet touches its kind's key; a removal has no edit form (B-0148). [revisit]
## S-166 — Seam: an interface field read is valued by its field (2026-11-02)
A v0.5 defect found in v0.6 wave 2 (S-157, B-0136): `iface://x#<path>`, as `ctx.proxy` records it, was valued as the whole
resolved joint while `n2f impact` matched it by field, so an edit of another field reran a rule impact did not name. Now the
read is valued as that field of the interface as written (a `param://` stays the reference, which is what the proxy handed
the rule); a bare `iface://x` stays the resolved joint, so no part, build plan or check key moves. Rejected: impact widening a
field read to the whole joint (reruns more than the rule needs). Manual pages read joints through `I`, which also records the
joint whole, so their staleness is unchanged. S-157's reason to record an entry whole is gone; whole stays correct.
## S-167 — Seam: `rule:<x>` keys and `#props.` figures in the contract; helpers' build folder (2026-11-02)
Two v0.5 contract gaps found in v0.6 wave 2. B-0135 (S-156): `docs/domains.md` §3.2 now says a `rule:<x>` key in `produces`
or `also_produces` is the output hash of the rule whose id is `<x>`, and `build_rules` refuses a rule producing `rule:<x>`
when its family has no rule `<x>` (an error naming the family and the rule; every shipped rule already complies). B-0139
(S-158): §3.3 says a verify kind's computed figure is selected as `#props.<figure>`, with an example; letting a kind declare
its selectors was rejected (a contract field to cover a sentence). §3.1, §3.4 and §7 say the membership and field reads.
B-0147 (S-164): the docs rule passes its `ctx.build_dir` to `render_doc`, so `h.build_dir` is the folder the rule builds in;
`tests/unit/test_graph_family_reads.py` renders a page into another build folder and reads the helper's answer.

## S-168 — v0.6 M4 (E8): the supply screen moves to the wiring domain (2026-11-02)
`owner/screens.py`: rule `circuit-available`, phase `check` (after the kiln's `estimate` screens, so a heat-up-derived
power is seen; domains before a product within a phase, so the row lands where the kiln's pack had it). No row or note
for a card saying nothing of power or supply (E12); fields `hint=False`, so no skeleton names a circuit unless the card
does [revisit]; generic words. The kiln's pack drops its supply screen and imports `CIRCUIT`, `REGION`, `SUPPLY_HEADROOM`
for its promotion and summary hooks. Landed on two seams: the kiln's `param` survives the domain's `envelope.power` (S-160);
the domain's `CardField`s load whatever is imported first (S-161). A card with a power or a region gets `circuit-available`
without the kiln's pack (two screening tests). Measured: the kiln's four cards re-screened against main give the same
rows, words and numbers (only the screens hash differs); kiln board golden unchanged.

## S-169 — v0.6 M6: the diff page's added and removed sections (2026-11-02)
DoD 4's diff half. `ecr/diff.py`: `delta["sections"]` lists each report section the later Revision's package adds or drops,
said "<label>: added" / "<label>: removed" for any domain's section. A section is in a Revision when its page's side index
shows it and the scope does not leave its domain out of the package (`later`, `external`: the cover's "Not included", S-148),
because `show_wiring` keeps the Wiring section on a `later` page to say so: presence alone would never say "Wiring: added".
A released Revision's page and scope are read from `build/site/<ref>/index.html` and its package's `release.json`; a scratch
build writes `sections.json` beside its data; either page unknown claims nothing. The block is rendered in `diff.py` and put
before the 3D section, since `diff.html.j2` was not this task's file [revisit] (B-0150). No diff page golden existed: new
golden `diff-sections.json`. A diff with no section change renders as before: `tests/e2e/test_release_diff.py` 6 passed, 1 min 47 s.

## S-170 — v0.6 M6: the external-box fixture, the scope words, the owner-session script (2026-11-02)
DoD 5 and the script for DoD 7. `tests/fixtures/scope/external-box`: a warming box (box, 1200 W heater, probe); the control
box `build: external`, `ports:` two cable entries, no children; `scope.electrical: in`; the power circuit (L, N, PE) and the
control circuit (C1, C2) reach it only through them. Each circuit's diagram draws it as a dashed boundary, nothing inside:
"to the external control box, supplied from elsewhere: L, N, PE" and "…: C1, C2", the domain's words; DoD 5's one sentence
is said across the two diagrams, one per circuit. The domain's "supplied from elsewhere" differs from S-152's "supplied, not
built here" [revisit] (B-0152). Removing a port: one error, on the stub's file, naming the port and the circuit. External and
later read the core's words with "Wiring"; the later cover lists what is not included and REQ-001 still to sign. The script
(`tests/e2e/intake-transcripts/wiring-session.md`) uses this fixture, not the kiln: the wired kiln had not landed, and on
EU 16 A no larger class is on file, so its headroom row is a warn (B-0151). 5.2 A of 10 A is a choice; the owner asks to be
asked, so delegation does not apply; she picks `larger` (`dedicated` never clears, B-0149). Step 1 run as written: 5 s; tests: 18, 15 s.

## S-171 — v0.6 M5 follow-up: the supply-headroom choice on a European 16 A supply, the dedicated pick made (2026-11-02)
B-0151: `calckit/data/circuits.yaml` gains two EU rows, "20 A dedicated circuit" (IEC 60898-1 preferred MCB ratings; HD 60364)
and "32 A dedicated circuit (IEC 60309 32 A outlet)" (IEC 60309-2; IEC 60898-1), both 230 V, `verify: true` [verify]. Ratings
only the cited standards list; no other number. Table rows over the brief's generic second option, because no screen moved:
every golden unchanged (`tests/golden` 141 passed), the board, calc-kit and screening tests green; the kiln's cards name their
circuit (no region lookup); the one fixture card screened by EU region draws 6.5 A (1.5 kW). So on EU 230 V 16 A above 8 A, `larger` offers the
20 A class (S-158's "next class on file", unchanged). B-0149: `Supply.dedicated` (optional, default false, schema stays 1):
"the supply circuit serves this product alone". The headroom row reads it through `sctx.proxy` and passes, saying nothing
else may be plugged in (the electrician confirms); the `dedicated` option's what-it-takes and the no-larger-class warn's fix
name the field. Measured: decide `dedicated`, set the field, build: `n2f status` has no "not yet in the design" line. Core files changed: none.
## S-172 — v0.6 M5: the kiln wired, its manual, the headroom choice, the wiring demo (2026-11-02)
`model/electrical/`: supply 230 V 50 Hz [verify], TT [verify] (the manual asks for an RCD), EU, the site's breaker upstream;
18 devices, terminals from the makers' drawings (`docs/v06-baseline.md` §2.1) [verify]; circuits power, control (control fuse;
door switch 31-32, then the limit relay next to the coil, so its resistive-only contact-on-coil warn shows), sensing (51 mV DC
[verify]) and earth, its own circuit (inside power the diagram was unreadable). Lengths are estimates [verify]. Earth points are
devices naming the metal a stud sits on, not `part://earth-stud`: the earth walk keys on a device's part (B-0153) [revisit]. Lid
and tray get a stud and a flexible lead; hinge post, latch keeper `bonded_via`. Five bought parts, no rating or cost invented.
Three entries at the cutouts' centres (box bbox same, centroid within 0.001 mm, volume +2.6 mm³: square-with-corners to circle):
REQ-007's box key re-keyed; REQ-008/-018 (manual), -019 (stud note) renewed as EXAMPLE. Headroom decided `dedicated` (DEC-026,
`n2f decide`) and made (`dedicated: true`). Also edited (the wired kiln moves them): `test_kiln.py`, `test_scope.py`,
`test_alignment.py`, `test_build_plan.py`. Measured: cold build 60.0 s; report 3,919,200 B; `demo-electrical.sh` alone 492 s (8 min 12 s). Core/`src/`: none.
## S-173 — v0.6 M7a: the docs for the wiring (2026-11-02)
DoD 10's docs half, written from the domain as built, not the plan. `docs/electrical.md` (its circuit-requirement example run on
a copy of the minimal fixture: pass). The pm role: the supply is a fact asked at intake; the owner is asked once how electrical
questions are handled (`model/intake.md`); the room-to-spare choice only after the first build with wiring; and a new rule
[revisit]: a choice in an area the owner asked to be asked about is theirs whatever it holds, although `n2f status` says an agent
may decide a `blocks: none` one (the core's words unchanged: E10). The pick is recorded `--by` the owner, then made in the model by
the designer. Written in the role's own words, not the M6 script's. Design gains "Wiring"; verifier a "Wiring" item (6; the joints
and verdict items renumbered 7, 8). The guide drops the kiln's stale part count (21; 46 part files now), its demo time is S-172's 492 s. `docs/domains.md`:
the electrical package as the third example; §1's sample no longer names a "wiring" domain; `CardField(hint=)`, `later`, §9's two
work-rounds. Vocabulary: ten wiring words. B-0155. Tests: agent docs, templates, vocabulary, journals, the role-reading e2e files.

## S-174 — v0.6 follow-up: the wiring diagrams readable at the kiln's size (2026-11-03)
Closes B-0154, B-0152; amends S-157's layout, S-170's words; only `outputs/diagram.py`, `outputs/rules.py` (words, one input).
Sides: cut at its entries the circuit falls into pieces, a wire through an entry puts its end pieces on opposite sides; the box
is the half with no source (supply, sensor, module from elsewhere), else the larger; a device beyond an entry is drawn past it,
the box's own before it (the kiln's limit probe now outside, the lid and enclosure studs inside). Labels: "id · size · colour"
once, at an end whose terminal holds no other conductor on that side; the id again at the other end (free, or shared by two:
one above the line, one below) for a wire through an entry or over 60 mm [revisit]; a run skipping columns crosses them in a free
band between their boxes, else below. Titles: voltage for power and control, "extra-low-voltage signal" for sensing in the checks'
ELV band, nothing for earth; "Protected by" only for the checks' `PROTECTED`, read through `title_inputs()`, an input of every
`elec:` rule (`checks/` is not the family's code). Boundary: "supplied, not built here" (S-152). Golden: minimal `.svg` only. Kiln report 3,916,749 B.
Judged by the agent, the maintainer's pending: power, sensing clean; earth-7 loops below; control busy (B-0158); report line B-0157.
## S-175 — Portable `mktemp` templates: the Linux nightly's one failure (2026-11-03)
Cause: the kiln's four demo scripts made folders with `mktemp -d -t name`, a BSD form; GNU mktemp wants a template ending in
at least three X's, so only Linux saw it. Measured: the nightlies of 2026-11-02 and 2026-11-03 (runs 41434734224, 41623136649)
each failed one test, `test_demo_napkin`: "mktemp: too few X's in template 'n2f-kiln-napkin-out'" (`demo-napkin.sh`'s second
call; the test sets `DEMO_DIR`). The rest of `check-full` passed (1,092 + 141 tests, the kiln's check): S-121's (B-0073) proof.
Fix: every call is `mktemp -d "${TMPDIR:-/tmp}/<name>.XXXXXX"` (no other shell `mktemp` needed it; the templates hold no
script); `tests/unit/test_mktemp_portable.py` fails on `-t` or an X-less template in the Makefile, `scripts/`, `examples/` and
the templates, so macOS catches it. Behind it, on both systems: the test expected "+ REQ-024 …", but S-172's wiring
requirements moved the promoted ids to REQ-030–034; it now matches the line, not the id. Measured on macOS: 1 passed, 126 s.

## S-176 — The wiring session simulation, DoD 7 (2026-11-03)
Run by the third overseer from `tests/e2e/intake-transcripts/wiring-session.md` at 4d78d36, a fresh project-manager
subagent continued line by line (the first run, 2026-11-02, was lost at owner line 2 when its session was cut off).
Transcript: `wiring-session-2026-11-03.md`. All five criteria ticked: nothing about the circuit's room in the
interview; the choice raised in full in the reply that reported the first build with wiring (5.2 A of 10 A, computed;
both options with what each takes); one `n2f decide … --pick larger --by "Dana Whitfield"`, after owner line 5; DEC-005
`made_by: human`; the PM then made the pick in the model, and the row reads `pass` at 16 A. No fix to `roles/pm.md`.
Found: `n2f status` tells this owner "an agent may decide it" though they asked to be asked (B-0160, core wording, a seam
task; not a blocker: the PM followed the owner). Step 3's role texts were named by path, not pasted (same text, 33 KB).

## S-177 (2026-11-03) The publish tests read a bare repository with `--git-dir`
Under `safe.bareRepository=explicit` (set in some sandboxes) git refuses to run with a bare repository as the working
directory (exit 128), so `test_send_online_to_a_bare_copy` and `test_online_sends_to_the_online_copy` failed there though
the product was right. Reproduce: `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.bareRepository GIT_CONFIG_VALUE_0=explicit
uv run pytest` on those two tests. Fix, tests only: `_bare_git` and the e2e `git()` pass `--git-dir=<remote>`. The setting
is never weakened.
## S-178 — Gate G blockers 1–2: a conductor against its protective device; Class II in a part that conducts (2026-11-03)
From `docs/reviews/v0.6-gate-g.md` §9 (at dbe46e0); amends S-158 and E6's fail list. A new rule and row per power or control circuit,
`conductor-protection`, not inside `conductor-current`: another pair (the device's rated current against the conductor's, I_n <= I_z,
IEC 60364-4-43 433.1 [verify]) whose unknown (a device with no rating: `warn`) must not hide the load check, and `#conductor_margin`
stays the load's. Below: `fail` naming the connections, both ratings (given / from the table), the fix. A lead on the supply side of
the circuit's device (the side reaching a source with it open) is judged against the supply's; a lead fed through another product
device, a conductor no source reaches (a controller's output to a relay's input) and earth conductors are left out [revisit] (B-0182).
Class II: the shortcut passes only with no custom part that conducts or no circuit above extra-low voltage (unknown counts as mains);
else each such part with no earth path warns, naming the mains circuits through its cable entries, or saying nothing keeps them out.
Fixtures `thin-under-breaker`, `class-two-metal`; the six DoD 3 fixtures keep their rows (thin-conductor gains a second fail). Kiln,
unedited: `conductor-protection@control` warns (its fuse has no rating), `@power` passes. `docs/electrical.md`: B-0183.
## S-179 — v0.6 M7: every wiring output carries the disclaimer (2026-11-03)
Closes gate G blocker 3 and gate H B2, C3, C4 (closes B-0157); 0 core files (E10).
1. Every `electrical/<circuit>/diagram.svg` carries a `<g id="footer">` band below `bbox_of` (`outputs/diagram.py::_footer`):
`PRODUCT`, `CIRCUIT`, `REVISION` (the tag at a clean released snapshot via `outputs/rules.py::build_revision`, else `draft`, an input
of every `elec:` rule) and `DISCLAIMER` ("Produced with an AI system; not reviewed by a licensed electrician: a licensed electrician
wires the product to local code.").
2. `build/electrical/README.txt` (`outputs/schedule.py::readme_text`, shipped via `RELEASE_FILES`, S-142) carries the disclaimer,
what each file is, and that lengths are estimates; CSVs stay comment-free for parsers.
3. `circuit(id).table` (`owner/docs_helpers.py`) prepends `**{DISCLAIMER}**` once per rendered manual page (`h.state`); the kiln's
two sign-offs citing `doc://installation` (`REQ-008`, `REQ-018`) re-keyed for that line.
4. Report (`owner/report.py`, `owner/wiring.html.j2`): circuit heading says the circuit once, `carries(record)`, and "protected by"
only for `PROTECTED` (C3, B-0157); lead says lengths are the design's estimates (C4). Golden: minimal `.svg` only; kiln PNGs re-rendered.
## S-180 — Seam: patch impact, domain disclaimer, `later` → `in` cover line, delegated choice wording (2026-11-03)
Closes B-0184, B-0160; gate H B1 and C7 (`docs/reviews/v0.6-gate-h.md`), gate G blocker 3's README half
(`docs/reviews/v0.6-gate-g.md`). (1) `compute_impact(product, edits, patch=…)` and `ecr_impact` dry-run a `kind: design`
change request's patch in a temporary copy, turn its file diff into touched keys (`set://<family>`, object and field
keys, `manifest://scope`), and report files/objects added, changed or removed, scope changes in owner words, and the
artifacts that rebuild (or say plainly when the patch does not apply); `ecr.impact` stores patch-only URIs without `://`
so `load_product` validates before and after apply. (2) `Domain.disclaimer` (`docs/domains.md` §3.14, §4.1) appends each
in-scope domain's sentence to the package `README.txt` and the report's `#disclaimer`; the electrical domain sets its
licensed-electrician line. (3) `ecr/release.py::scope_lines` reads the previous Revision's `release.json` and says
`<Word>: included in this Revision; left for later in <prev>`. (4) `core/checks/choices.py` says `"an agent may decide it
and say so"` only when `operator.yaml` delegates the choice's area and `model/intake.md` does not ask to be asked.

## Review gate G (electrician read-through, then engineering) — outcome (2026-11-03)
Reviewed at dbe46e0 (report: `docs/reviews/v0.6-gate-g.md`; Part 1 read-through kept at `examples/kiln/reports/electrician-readthrough.md`):
NOT READY on three blockers; the six fault fixtures fail or warn naming the part, circuit and fix, the kiln's load current and
margins re-compute by hand through `calckit.power`, every table row is cited and `verify: true`, the domain stays generic and
reads through the recording accessors, and an electrician could wire the kiln from the package with about a dozen calls to the
maker. **Blockers fixed:** (1) a conductor rated below its protective device passed (`I_n <= I_z` unchecked) and (2) the Class II
shortcut passed a mild-steel box carrying single-insulated mains conductors — S-178 (`conductor-protection` row, Class II shortcut
restricted, fixtures `thin-under-breaker` and `class-two-metal`); (3) "not reviewed by a licensed electrician" never reached the
package `README.txt`, the manual helpers or the diagram SVGs — S-179 (diagram footer, `electrical/README.txt`, manual helper) and
S-180 (`Domain.disclaimer` in the package `README.txt`). Open in BACKLOG: concerns 1–14 (B-0161 … B-0173; 6 is B-0137, 15 closed by S-181).

## Review gate H (UX in the owner persona) — outcome (2026-11-03)
Reviewed at dbe46e0 (report: `docs/reviews/v0.6-gate-h.md`): NOT READY on two blockers; "left for later" in status, report and
the v1.0.0 cover, "Wiring: added" on the diff page, the Wiring section's banner and "a licensed electrician decides" warnings,
plain refusals without stack traces, and zero wiring words on a product without wiring all read well. **Blockers fixed:** B1 the
impact report for a `kind: design` change request with a patch (`ECR-003`) said "Impact of 0 change(s)" and "nothing is rebuilt" —
S-180 (`compute_impact` dry-runs the patch in a scratch copy and reports files/entities, scope transitions and rebuilt artifacts,
closes B-0184); B2 the wiring diagrams in the package carried no disclaimer, product name or revision (= gate G blocker 3) — S-179
(diagram `<g id="footer">` band and `electrical/README.txt`). Concerns fixed: C3, C4 (S-179, closes B-0157), C7 and B-0160 (S-180).
Open in BACKLOG: C1, C2, C5, C6, C8–C11 (B-0174 … B-0181). Visual exits (S-078): `docs/reviews/v0.6-diagram-*.png`,
`v0.6-kiln-diagram-*.png` and `v0.6-report-wiring.png` — judged by the agent; the maintainer's visual judgment pending.

## S-181 — v0.6 close-out: version 0.6.0, product pins `>=0.6,<0.7`, `HANDOFF-REPORT-v0.6.md` (2026-11-03)
As S-140 did for 0.5: `pyproject.toml`, `packaging/n2f/pyproject.toml` (and its `napkin2factory==`) and
`src/napkin2factory/__init__.py` read 0.6.0 (S-054); the pin moves to `>=0.6,<0.7` wherever S-083 put it:
the manifest default and its error example (`core/model/manifest.py`), the template sources and
`examples/{bracket,enclosure}` `n2f.yaml` and product CI workflows (synced with `make templates`), the kiln's
`n2f.yaml` and workflows, every `tests/fixtures/**/n2f.yaml` (including `tests/fixtures/electrical/**` and
`tests/fixtures/scope/**`), `tests/unit/test_version_pin.py` and the layout line in `docs/product-model.md`;
`uv.lock` follows. Dated transcripts under `tests/e2e/` keep the pin they ran with. No schema change (E12,
schema stays 1). `HANDOFF-REPORT-v0.6.md` records the E10 count (0 core files in domain commits; seam tasks
listed apart), milestones M0–M7, DoD 1–10 and gates G and H; temporary `docs/v06-handoff/` removed.
## S-182 — Loud errors for param units, circular imports, output directories; runtime Pillow (2026-11-03)
Closes B-0163, B-0156, B-0105; addresses B-0072 (Pillow).
1. `domains/electrical/checks/calcs.py::_quantity`: a `param://` of the wrong dimension raises `ValueError` naming the parameter and field instead of swallowing `UnitError` into None (B-0163).
2. `core/registry.py::Registry.ensure`: importing an installed domain while partially imported (or on `ImportError`) raises `RuntimeError` naming the module and asking to import `napkin2factory.core` first, preventing silent registration loss (B-0156).
3. `core/graph/runner.py`: `run_build` validates `RunResult.outputs` and refuses paths resolving outside `build/<output_dir>`, raising `BuildError` naming the rule and path (B-0105).
4. `pyproject.toml`: `pillow>=11.0` moved from dev dependency-group into `[project]` dependencies for runtime screenshot capability (B-0072).

## S-183 — v0.6.0 released (2026-11-03)
`make check` passed on `main` at the S-181 close-out commit, which was pushed; CI `ci` passed on
Linux and macOS (15 min 7 s), then `v0.6.0` was tagged there and `publish.yml` published both
packages (build, pypi, pypi-alias all green). Visual exit (S-078): the maintainer was sent
`docs/reviews/v0.6-kiln-report-wiring.png` and `v0.6-kiln-diagram-power.png`; judged by the
maintainer: "fine for now". The last nightly (2026-11-03 10:54) failed before S-175 landed; the
next one is not yet run.
## S-184 — Six long modules split, code moved verbatim (2026-11-03)
Pre-v0.7 tidy-up (`docs/roadmap/pre-v0.7-todo.md` §4.3; S-080's reason: parallel agents collide in
long files). Split, each resulting file ≤ 550 lines: `core/graph/impact.py` (1248) → `impact_common`,
`impact_patch`, `impact_reads`, `impact_summary`; `report/builder.py` (811) → `builder_common`,
`builder_plan`; `drawings/sheet.py` (756) → `sheet_views`; electrical `checks/stage.py` (1111) →
`protection`, `rows`; `model/__init__.py` (978) → `refs`, `schemas`; `outputs/diagram.py` (926) →
`diagram_layout`. The old modules re-export every name. Checked: every top-level def and class is
AST-identical to before. Still over 550, under 750: `core/checks/stage.py`, `core/concepts.py`,
`calckit/thermal_enclosure.py`, `core/checks/choices.py`, `electrical/checks/calcs.py`.
## S-185 — Structural F9 guard: AST string constants and qualified URIs replace blind text match (2026-11-03)
Amends S-128's guard. Everyday examples (v0.7 `examples/table`) with parts like `base-plate` or `top-rail` would cause
the blind full-text scan to flag `<table>`, `"gate table"`, and ordinary comments across ~70 package files. F9 cares
about the package depending on an example, not English words. Check A (.py files via AST): string constants (including
inside f-strings) that are not docstrings and equal an example compound identifier exactly; product names are excluded
(literal `"table"` stays legal). Check B (all text files): qualified URIs (`<scheme>://<id>` for any scheme), example
requirement, decision, and change ids (REQ/DEC/ECR), and `examples/<product-folder>` paths. Comments, docstrings, and
HTML/CSS prose are no longer scanned for plain identifiers. Real `src/` hits remain 0.

## S-186 — Fail n2f check for made parts with assumed density (2026-11-03)
`geometry/materials.py::density_kg_m3` falls back to mild steel (7850 kg/m³) when a part's
material is unlisted and has no declared density, leaving mass and BOM cost guessed silently.
A new public helper `density_is_assumed(material) -> bool` detects when this fallback triggers.
In `core/checks/engine.py`, `material://<part>` check rows verify that each made (`kind: custom`)
part has a known material or an explicit declared density; assumed density fails with plain
owner words naming the part and material, while bought (`kind: cots`) and reference parts are exempt.
## S-187 — Cost delta names added or edited unpriced parts (2026-11-03)
A change request editing or patch-adding parts without declared unit cost previously reported a bare
delta of +$0.00, reading as complete to owners. `_cost_delta` in `core/graph/impact_reads.py` now
tracks custom (non-reference, non-bought-with-price) parts whose cost remains missing after the change.
When unpriced parts exist, the cost note appends `; N part(s) without a price: <names>, so the cost change is incomplete`,
`cost_complete` in JSON is `false`, and the summary renders an incomplete delta as `at least +$X.XX` (or `−`).

## S-188 — A Domain bom_lines hook brings consumables to the parts list (2026-11-03)
Amends S-145's E5; closes B-0128 (`docs/roadmap/pre-v0.7-todo.md` §3.3). A domain may register
`bom_lines(product, reader) -> list[BomLine]`; the `bom` rule calls each one with a reader that
records its reads. No rule ordering (B-0128's `after` half): wire lengths are read from the model
(`Connection.length`), not from the domain's build outputs. Conductors carry no price, so the
cable lands unpriced: `rollups.json` `"consumables"`, `cost_complete: false`; a priced line adds
quantity × unit cost. `bom.csv`: one `kind: consumable` row per line, new last column `qty_unit`.
Electrical builds its lines with `circuit_record` and `cable_rows`, the schedule's own code, so
the parts list and `build/wiring/cables.csv` cannot disagree on a length.

## S-189 — Reorganize root docs into docs/stages/, docs/handoffs/, docs/roadmap/ (2026-11-03)
Clean up repository root: 14 root files mixed living entry points with historical stage plans
and handoff reports, and the roadmap lived outside the repo where no other agent could read it.
Old→new path map: root stage plans (GRAND_PLAN, NAPKIN_STAGE, PRODUCT_STRUCTURE, FOUNDATION,
ELECTRICAL_STAGE) → docs/stages/v0.{1,2,4,5,6}-<slug>; root handoff reports (v0.1–v0.6) →
docs/handoffs/; roadmap docs (road-to-v1.0, pre-v0.7-todo, TRACK_*) → docs/roadmap/; architecture
review → docs/reviews/v0.6-architecture-review.md. Root keeps only 5 canonical living files:
`README.md`, `AGENTS.md`, `STATUS.md`, `DECISIONS.md`, `BACKLOG.md` (+ `LICENSE`, untracked files).
History keeps old paths: `docs/history/` and existing `DECISIONS.md` entries remain unchanged.

## S-190 — The periodic health review (2026-11-03)
Agents keep no memory between sessions, and tracking drift, file sizes, or collisions while
building gets dropped; the maintainer asked for a routine review instead. Three parts:
1. `make land` stamps commit trailers (`Task`, `Task-started`, `Task-conflicts`) and prints a
   notice when a review is due every 15 landed tasks; every version close includes one.
2. `make health` (`scripts/health.py`) computes measures; `make health ARGS=--record`
   appends a row to `docs/health/trend.csv`.
3. A review brief (`docs/reviews/TEMPLATE-health.md`) guides a fresh reviewing agent.
Initial thresholds (15 tasks, 550 lines) are to be tuned by reviews. Its first run corrected
S-184: 11 modules are over 550 lines, not the five S-184 listed from a cut-off listing (B-0185).

## S-191 — The roadmap review applied to `docs/roadmap/` (2026-11-04)
The maintainer asked for gaps against the v1.0 vision and then for the fixes. Checked against
the code: Track B planned a second snapshot store though products version through `core/vcs.py`
(now: checkpoints are snapshots); Track D reused `n2f serve` (taken) for a daemon (now: the MCP
process is the warm engine) and repeated fixed packaging claims; Track A's numbers did not follow
from its geometry (table C-002 near its 55 kg limit; rough hand checks, not run). Added: worked hand
calculations and a 30 % margin for benchmarks, joint/racking/creep/wood-movement/fatigue checks,
derived (raise-only) ceremony, region-tagged supply and costs, two-vendor trials and a prompt set,
measures, the v1.0 contract, a trust model, a thin MCP in v0.8 (B-0036), phone layout. Index: §6.

## S-192 — The vision in the maintainer's words, and how the tool speaks (2026-11-04)
Amends S-191. The maintainer's own statement of the vision is now quoted in `road-to-v1.0.md` §1,
so no plan paraphrases it again. "Wherever" means any agent client (terminal, IDE, desktop chat
app), not geography: S-191 misread it; supply region stays as an accuracy item (Track A §3.5).
Browser-only chats need a hosted service and wait until after v1.0. The voice (§1.1, judged by
the maintainer: "honest but not defensive"): one disclaimer (README, said once by the agent), no
repeated warnings or "not checked" lists, no sales voice. The electrical domain's repeated
disclaimer (S-179) is B-0186.

## S-193 — The electrical domain drops its own disclaimer (2026-11-04)
Applies S-192 (one disclaimer, the README's, said once by the agent); amends S-179. Decided by
the maintainer: a printed diagram is read by the electrician, the qualified person the note
pointed to, so it needs no warning. Removed from the Wiring section, the manual helper's first
table, the diagram footer (the band keeps product, circuit, Revision) and `electrical/README.txt`
(it keeps what each file is); `Domain.disclaimer` stays unset for electrical (the field, S-180,
stays in the contract). Kept: sign-offs and checks that name an electrician where the owner acts.

## S-194 — Generated output carries no AI mark (2026-11-04)
Decided by the maintainer, extending S-192 and S-193: whoever shares a design decides whether to
say how it was made. A mark baked into every file takes that choice away and invites "it's AI, so
it's wrong" dismissals of accurate work. The README's disclaimer, which the agent says once at the
start, is the only one. Removed from the report, the shared pages, the comparison page, manual
footers, drawing title blocks, the parts list's note row, the release cover; `Domain.disclaimer`
and `domain_disclaimers()` (S-180) are gone. Product `AGENTS.md` rule 7 now says: say it once,
never write it into files. A guard test checks no file under `build/` carries the mark.
## S-195 — Landing refuses a cited but undefined placeholder (2026-11-04)
Amends S-097's placeholder rule. Two parallel tasks (`make health`, the commit trailers) cited
the health decision as `S-195` while a third task defined it; landing gave each the next free
number, S-194, which names no decision, and 12 comments pointed at nothing (fixed to S-190).
`scripts/journal_ids.py` now stops the landing, before any rewrite, when a task cites `S-NEW<n>`
or `B-NEW<n>` without defining it (an index row or heading in `DECISIONS.md`, a row in
`BACKLOG.md`). A task citing another task's decision waits for it to land and cites its real id.
## S-196 — Faster test runs (2026-11-04)
Agents waited 10–25 min per check: two or three suites ran side by side on the host's 8 cores
(i9-9980HK, 16 threads), and most heavy tests built an example from scratch in a fresh process.
Now: `scripts/test_lock.py` lets one test run use the machine at a time, for every folder of the
clone (a second run waits and says who holds it; `N2F_TEST_LOCK=0` skips it); `-n logical --dist
loadgroup` (406 s against 456 s for `-n 8 --dist loadfile`, single runs) with `xdist_group` on
modules sharing a product, made to work under pytest 9.2 in `tests/conftest.py` and guarded by a
collection failure; one pytest call in `make check` (`make tests`); `copy_product(prebuilt=True)`
copies a product built once per session; `n2f()` runs the CLI in process (`N2F_TEST_SUBPROCESS=1`,
set by `check-full`, restores real processes); `test_impact_honest` and `test_choices` moved to
e2e. Measured back to back under load: `make check-fast` 167 → 124 s, `make tests` 493 → 354 s.
## S-197 — v0.7 opens: everyday breadth (2026-11-04)
Road §5 step 3: Track A becomes `docs/stages/v0.7-everyday-breadth.md` (W1–W12), milestones M0–M5
in four waves. Its "today" claims were checked against the code first (road §5 step 4): all hold,
except that density lives in two tables (`calckit/data/materials.yaml` and `geometry/materials.py`;
W2 makes one) and the conductor and wire-colour tables already carry a region (only earthing
lacks one, W7). Locked here: two calc modules (members, joints), derived raise-only ceremony with
a hazard tag on every safety requirement, product region and display units, benchmarks worked
then re-derived by another vendor's model, an oracle runnable on any folder. The v0.6 trial's
findings are triaged in a follow-up entry (W12). Open items: B-0188–B-0196.
## S-198 — Structural calc pack: members (2026-11-04)
Pure-function envelope-grade structural module `calckit/structural.py` (v0.7 W1, Track A §3.1).
Computes sections (`rect_section`, `rect_tube_section`, `round_tube_section`), beam deflections
(simply supported point/uniform, cantilever tip with column rotation), bending stress and yield factor,
Euler buckling with K factors and slenderness check refusing inelastic range (naming Johnson's formula),
tip-over safety factor (restoring/overturning moment), and fastener group shear.
Why: generic `structural` screen (W4) and product sizing share verified physics with pint in/out.
Sources: Roark's Formulas for Stress and Strain 7th ed. (Tables 1, 8.1, 15.1, §8.1), Shigley's Mechanical
Engineering Design 11th ed. (Tables 4-2, §1-10, §4-11, §8-5), AISC 15th ed. (Table C-A-7.1).
Covered by 27 reference cases (8 external published cases) and Hypothesis property tests.

## S-199 — One materials table, everyday materials, dated regional cost bands (2026-11-04)
W2, W3 (milestone M1c). `calckit/data/materials.yaml` becomes the sole materials table, gaining
optional `youngs_modulus`, `yield_strength`, and wood `moisture_basis`; expanded with Track A §3.2
materials (metals, woods, polymers, printed plastics) and all old `DENSITIES` entries.
`geometry/materials.py` reads it directly with keyword matching and no density dict; S-186 strict density
check preserved. `core/data/processes.yaml` gains `woodworking`, `cnc-routing`, `laser-cutting`,
`extrusion-cut`, and default tolerance classes. `calckit/data/cost_bands.yaml` replaces old columns
with dated regional fields (`low`, `high`, `currency`, `region`, `as_of`); `mass_cost.cost_band` exposes
dated regional lookups, failing loudly on unknown regions and marking rows >24 months old as stale.
The board's cost-band line names region, date, and staleness in plain words. Closes B-0189.
## S-200 — Product region and display units field (2026-11-04)
Manifest (`n2f.yaml`) gains optional `region` validated against the regions the tables know
(AU, EU, SA, UK, US) and `units: Literal["metric", "imperial"] = "metric"` per W7/W8 and schema
policy rule 1. The electrical supply's region defaults to the manifest's when omitted from
`supply.yaml`, and validation fails naming both when they disagree. `earthing.yaml` gains its
`region` column (AU, EU, SA, UK, US) with cited standards and `verify: true`. `calckit/wiring.py` lookups
(`conductors`, `colour`, `earthing`) take region and fail loudly naming the table and its known
regions when a region has no rows, never falling back silently. Products with no region anywhere
retain legacy behaviour. Backlog row B-0193 remains open for report display unit integration.
## S-201 — Structural calc pack: joints, wood, fatigue, load cases (2026-11-04)
W1 / M1b: `calckit/joints.py` adds pure-function pint structural mechanics for joint and fastening
limits before members fail. NDS-2018 Section 12.2 wood/lag screw withdrawal; threaded insert pull-out
with safety factor from RAMPA catalogue rows [verify]; welded and bolted corner moment capacity before
yield (Shigley Section 8-5); unbraced portal frame racking sway with rigid/semi-rigid corners (Roark
Table 8.2); wood creep sag (Eurocode 5 Table 3.2 / USDA Wood Handbook Ch. 5); across-grain wood movement
from `calckit/data/wood_movement.yaml` (USDA Wood Handbook Table 4-4 [verify]); fatigue safety margin via
Modified Goodman (Shigley Ch. 6, failing loudly when non-ferrous materials omit S-N strength); load-case
table `calckit/data/load_cases.yaml` [verify] with `factor_of_safety` enforcing tightening-only (W1).
Tests in `tests/unit/test_joint_calcs.py` (33 passed, mypy clean).

## S-202 — Frame kit: rectangular, round and T-slot profiles, rail section, slotted tabs (2026-11-04)
Track A §3.3 item 1 (M2a): `geometry.kit.frame` gains `"rect-tube"` (size × size2 × wall),
`"round-tube"` (outside diameter, wall) and `"t-slot"` (simplified square extrusion with 4
centered grooves of `slot_width` and `slot_depth`, supporting `process: extrusion-cut`).
`Args` gains `rail_member` (rails use it when given; legs keep `member`), `apron_offset_top`
(top rails recessed while legs keep full height), and `mounting_tabs` (`TabSpec` with through
slots across the rail for wood movement, listed in `props["mounting_tabs"]` and notes).
Profile cross-section helpers moved to `_profiles.py` to keep `frame.py` under 550 lines.
All defaults preserved; existing frame outputs, goldens, and volumes remain unchanged.
Measured: relative volume diff < 1e-15 on tabs, < 1e-5 on round tubes, 7 unit tests pass in 10 s.
## S-203 — Four mechanical interface kinds through the mechanical domain (amends W5) (2026-11-04)
W5 amendment: rather than core YAML data, the four interface kinds (`threaded-insert`,
`wood-screw-pattern`, `t-slot-joint`, `hinge-pin`) are registered by the mechanical domain via
`Domain.interface_kinds` in `domains/mechanical/interfaces.py`, mirroring `cable-entry`.
Each spec subclasses `BoltPatternSpec` (S-144). A minimal core seam was required for per-party
hole diameters and party skipping: `BoltPatternSpec.hole_for(party_uri) -> diameter | None` in
`core/model/interfaces.py`, called by `apply_interfaces` in `geometry/build_part.py`, and
checked by `_core_report` and `_diameters_match` in `core/checks/interface.py`. Receiving parties
get bore or pilot holes, passing parties clearance holes, and T-slot extrusions remain uncut.
Each kind carries its domain check (material must be wood/plastic; extrusion profile/process; 2 parties).
Measured: 11 tests in `test_mechanical_interface_kinds.py` pass; all 34 interface tests pass.
## S-204 — The table benchmark spec (2026-11-04)
`examples/table/SPEC.md` (W9, road §4.1): every figure worked by hand from stated geometry, then
re-derived independently by a second model from the spec alone (140 figures, all within 0.35 %).
Track A's draft could not be both decisive and true: at 55 kg the promoted card cleared mass by
only 30–31 %, and the repository's own cost bands price the oak top alone at 259–634 USD. So the
mass limit is 70 kg, the budget 1600 USD, the top 30 mm (ECR-1 takes it to 32 mm), all members
50×50×1.5 tube, bolts M8×25. The re-derivation's findings were fixed before landing (ECR-1's
margin, seven modelling choices now stated). The check also found four calc-pack defects
(short columns, moisture constants, composite creep, no budget check), fixed in their own task.
## S-205 — Ceremony derived from the model (W6) (2026-11-04)
`derive_ceremony(product)` (`core/ceremony.py`) gives `standard` for a hazard a domain with content reports (`Domain.hazards`; the wiring: supply above 50 V AC / 120 V DC, the cited `entry-voltage` limits), content in more than one domain (`Domain.has_content`), a requirement tag `hazard:<kind>` the table `core/data/hazards.yaml` classes as raising (mains, high-temperature, moving-machinery, stored-energy; tip-over, sharp-edge, pinch, structural-failure, chemical-exposure do not), or `ceremony: standard` in `n2f.yaml` (raise-only; `lite` there is an error). Lint `L4-hazard-tag`: a `safety: true` requirement names a known hazard. `lite` relaxes only: `tolerance_class` from the process's `default_tolerance_class` (labelled "(default)" in the parts list and title block), one `build-and-care` page as the manual (`L18-manuals`), and no empty Sign-offs, Joints between units or Change requests sections; provenance, alignment and sign-offs never relax. `n2f check` and `--json` (`ceremony`, `ceremony_reasons`, `ceremony_raised`) name the level and, once, a rise since the last check (`build/.n2f/ceremony.json`).
Existing safety requirements (kiln, enclosure, fixtures) gained tags; the kiln derives `standard`, the bracket and enclosure `lite`. Hazard rows are classifications only (no numbers) and `verify: true` against ISO 12100 Annex B, IEC 61140, ISO 14118/14120.
Core files touched (planned, W10): `core/ceremony.py` (new), `core/data/hazards.yaml` (new), `core/domain.py` (two hooks, `Process.default_tolerance_class`), `core/registry.py`, `core/model/manifest.py`, `core/lint.py`, `core/graph/values.py` (`manifest://ceremony` read), `core/checks/engine.py` (one read). Not measured: a cold build of the kiln with the new reads.
## S-206 — The generic structural screen reads loads from the site and members from the massing (amends W4) (2026-11-04)
W4 / M2c: `concepts/screens/structural.py`, generic; 0 `core/` files (W10). Loads and limits are
`site` fields (`point_load`, `distributed_load`, `edge_load`, `edge_offset`, `max_deflection`,
`cycles`, underscored), not a card section. Members come from the massing: a `frame` plus its widest
flat board gives top sag and yield, leg buckling and tip-over; a `tube`/`block` column with an arm
gives tip deflection, yield and buckling. The top and the two long top rails share one span, so E·I
adds and the top takes its share of the moment. A check missing an input is a `skip` row naming it;
so is a short column, until the calc kit has Johnson's formula (Euler refuses it, and a 50 x 50 x 2
steel leg is always short). Factors: `joints.factor_of_safety`.
Measured against hand calculations: an 800 x 22 mm pine top sags 9.63 mm over 1400 mm; 40 mm oak on
50 x 50 x 2 rails 0.754 mm; a 60 x 60 x 4 steel column's arm tip 0.215 mm.
## S-207 — Calc pack fixes from the table benchmark: Johnson columns, room-temperature EMC, composite creep, budget screen (2026-11-04)
An independent hand calculation of the table benchmark (SPEC §4) found five defects in S-198 and S-201. (1) `structural.johnson_buckling_load` (Shigley §4-12) and `column_buckling_load`, which picks Euler or Johnson by slenderness against sqrt(2 pi^2 E/S_y) and says which in `BucklingResult.method`; `euler_buckling_load` still refuses short columns. Table leg: slenderness 72.7, P_cr 60 578 N, factor 38.3. (2) `joints.equilibrium_moisture_content`: Hailwood-Horrobin (FPL-GTR-190 Eq. 4-5) with temperature an input (default 21 degC); the old constants were for another temperature (5.77 points for 30 to 70 % RH, now 6.92, Table 4-2: 6.2 / 9.2 / 13.1 at 30 / 50 / 70 %); `wood_movement` at 280 mm: 7.07 mm (SPEC 7.05). (3) `joints.composite_creep_deflection`: EN 1995-1-1 §2.3.2.2, only the timber's E drops to E/(1+k_def); long-term sag 0.754 mm for the SPEC case (the whole-sag multiplier gave 1.06 mm). (4) k_def lives only in `calckit/data/timber_creep.yaml` (Table 3.2 [verify]); the `deflection`/`sustained` row of `load_cases.yaml` is gone, a creep factor being no factor of safety; the 0.25 medium-term k_def is S-201's estimate, flagged [verify]. (5) The cost-band screen reads `site.budget`: pass when the band's high end is within it, fail when its low end is over, amber between.
Measured: `tests/unit/test_calc_fixes.py` and the pack's reference cases; the old 17.25-points-per-unit-RH slope for a single RH swing is replaced by a swing centred on 50 % RH.
## S-208 — The v0.6 independent trials, triaged (2026-11-04)
Road step 0, W12. Two outside models of different vendors ran `docs/reviews/v0.6-independent-trial.md`
at 4dc9ad1 (`docs/reviews/v0.6-trial-1.md`, `-2.md`). Trial 1: no blocker, 4 concerns. Trial 2 (owner a
separate agent): one blocker: a change request that removes a part, parameter or joint leaves the
product unloadable (the stored impact names the removed URIs; apply stops half-done). The trials
disagree on most rows; trial 2 used the system longer and is the evidence for fixes. Tasks before
the benchmark examples: B-0197 (the blocker, with C3), B-0198 (`n2f discard` deleted an approved
change request, C2), B-0199 (per-conductor current, `passes: []` for later; C9, C1), B-0200 (docs:
C5, C6, C7, C13, C15, owner words C10). Rows only: B-0201–B-0205.
## S-209 — The benchmark oracle judges outcomes, not ids (2026-11-04)
`tests/benchmarks/oracle.py` (W9, road §4.2) judges any product folder against a `SPEC.oracle.yaml`:
`uv run python -m tests.benchmarks.oracle <product> <oracle>`, PASS/FAIL per row, exit 0/1/2. A cold
agent's names differ, so a card is found by status, the category of its failing checks (structural,
mass, cost, envelope, read from the rule's words) and a property (material, kit); a number by what it
is: a screening value, the requirement whose bound it meets (`2.5 mm`; several share one bound, so
the expected value picks), a BOM roll-up, or a check result row. Facts: ceremony, region, supply,
assemblies, requirement counts, gate blockers. Gaps (listed as `pending:` in the table oracle):
no change-request replay, no product-level cost band (the BOM has one total), no card-level Johnson
buckling or rail stress, movement has no fixed requirement form. Measured: bracket and kiln cards.
## S-210 — The test-stand benchmark spec (2026-11-04)
`examples/test-stand/SPEC.md` (W9): worked by hand, checked by script, then re-derived by a second
model from the spec alone (22 expected outcomes within 0.4 %). Track A's draft left the member under
the specimen out of the load loop and used a 400 mm column; with the stated vertical stack the
columns are 760 mm (C-002) and 820 mm (C-001), C-002 gains a base beam, both frames are aluminium
6063-T5 (a steel C-002 misses the mass margin), the budget is 2400 USD (at 800 USD the shared parts
alone fall inside the band), and the part list is 19 definitions. Open: bought-in parts priced in
the kiln-derived controls band; bolt fatigue is a hand check (no preload term in the calc kit).
## S-211 — The structural screen counts self weight and short columns (2026-11-04)
Follow-up to S-206 closing three gaps against the table benchmark spec (SPEC §4).
(1) Buckling rows use structural.column_buckling_load (Euler or Johnson by slenderness, S-207)
and name the curve in formula text; unbraced table legs sway laterally (AISC Table C-A-7.1
case f, K = 2.0). (2) Self weight: the top's own weight (volume × density from the massing call
and materials.yaml) adds as a uniform load on the span; each leg carries its share of total table
weight plus applied loads; row text states both; explicit distributed loads still add on top.
(3) geometry.materials.material_row replaces the private _match_row import.
Measured: C-002 benchmark card gives top sag 1.54 mm (within 2.3 % of SPEC 1.58 mm) and
leg buckling factor 38.3 (matching SPEC 38.3).
## S-212 — Discard keeps filed change requests; plain words on promotion (2026-11-04)
Fixes trial 2 C2 (B-0198) and C10 (part of B-0200, S-208). `n2f ecr new`, `approve` and `reject` take
snapshots (`ecr/lifecycle.py`), fitting `core/vcs.py`'s snapshot design; untracked or filed change
requests and their patches now belong to the latest snapshot and survive subsequent `n2f discard`
calls, which restore only unsaved model edits and name what was undone (`cli/snapshot.py`,
`core/vcs.py unsaved_files`). Promotion's owner-facing decision context replaces "Rejected
alternatives:" with plain words "Other ideas considered:" (`concepts/promote/verb.py`), preserving
card YAML `status: rejected`.
Measured: `tests/unit/test_snapshot.py` reproduces C2 and verifies ECR and patch survival on the
bracket; 52 targeted tests and acceptance suite pass.

## S-213 — The trial's documentation gaps closed (2026-11-04)
Trial 2 docs gaps closed (B-0200; C5, C6, C7, C13, C15): (1) Massing origins stated in
`roles/pm.md`, `docs/napkin.md`, and `docs/kit.md` where generators differ (`bracket_l` corner origin
at x=0 along +x, `tube` along +axis from end centre). (2) `docs/kit.md` explains `vent.size` (slot width)
and lists the five frame member profiles (`square-tube`, `angle`, `rect-tube`, `round-tube`, `t-slot`; S-202).
(3) Kit args clarify `{expr: ...}` is refused, showing the helper-parameter pattern in `docs/kit.md` and
`docs/agent-guide.md`. (4) First CAD kernel load timing raised to up to ~4 min; Playwright browser install
step documented in `docs/agent-guide.md` and `docs/napkin.md`. Measured: doc and template tests green.
## S-214 — Each conductor carries what it feeds; an empty cable entry is not a failure (2026-11-04)
Fixes trial 2 concerns C9 and C1 (B-0199, S-208). (1) Per-conductor current: each conductor's current is derived from the downstream loads it feeds by walking the circuit net from load terminals back toward the supply; a conductor feeding one device carries that device's load, and a shared conductor carries their sum. (2) `check_cable_entry`: an empty `passes: []` returns pass ("nothing passes through yet"), so a cable-entry interface placed before circuits are routed no longer fails a requirement verifying it; an unrouted listed circuit still fails. Existing fixtures and the kiln's wiring results are unchanged (the old rule evaluated single-load circuits correctly; only multi-load branched circuits were charged the full circuit total on thin branch conductors). Measured: `tests/fixtures/electrical/branch-loads/` (10 A heater branch, 0.2 A fan branch on 0.75 mm² PVC) passes with 3.1 A least margin; unit tests in `tests/unit/test_electrical_checks.py` and `test_electrical_model.py`.
## S-215 — A change request may remove parts, parameters and joints (2026-11-04)
Trial 2 blocker 1 (S-208, B-0197): applying an ECR that removed an object broke the loader because `all_uris()` walked the ECR's stored impact, resolving deleted URIs. Stored impact is history, not live model references, so `Product.all_uris` skips `e.impact` and `_validate_uris` warns instead of erroring on dangling references in sign-offs and historical change requests. Sign-offs citing a removed requirement or evidence are reported in `n2f ecr impact` under "Sign-offs that will no longer apply" (naming the file, C3) and moved to `<file>.invalid` on `n2f ecr apply` so the product loads cleanly. Apply is atomic: failures roll back with `vcs.discard()`, keeping the ECR approved with plain-words errors.
Measured: `tests/e2e/test_ecr_remove.py` proves removal of parts and parameters, sign-off invalidation, and rollback on apply failure.
## S-216 — Landing resolves a backlog row both open and closed after a merge (2026-11-04)
When a task closes a backlog row while main touches the backlog too, git rebase with
merge=union keeps both Open and Closed copies, failing test_backlog_ids_unique.
`scripts/journal_ids.py` now resolves any id present in both tables by dropping the Open row
(closing is the newer act), leaving intra-table duplicates for the gate to catch.
The change is committed into the task commit during post-rebase journal rewriting.

## S-217 — Health review 2026-11-04 — outcome (2026-11-04)
Periodic health review across 34 commits since f6d55b3 (S-190). Trend recorded at 9d030b1 in `docs/health/trend.csv`. Long modules stable at 11; 0 new modules exceed 550 lines since v0.7 began (structural/joints modularized under 370 lines), but `core/checks/interface.py` grew to 677 lines (+39) and `mechanical/interfaces.py` reached 509 lines. 7 task collisions occurred (`docs/agent-guide.md` in 4 pairs). Unconfirmed verify rows rose from 170 to 268 (+98) from materials and cost expansion. E10 seam commits rose to 11 (+5); M1c touched `core/data/processes.yaml` (target 0 core files under W10). Zero core-to-domain or cross-domain imports. Zero TODO/FIXME lines in src/. Test suite expanded to 1195 (+166), test skips to 35 (+2, both justified). Report in `docs/reviews/health-2026-11-04.md`; opened backlog rows B-0206 (union merge backlog deduplication), B-0207 (agent guide collision hotspot), and B-0208 (v0.7 verify numbers confirmation).
## S-218 — The kiln's benchmark spec, retrofitted from its model (2026-11-04)
`examples/kiln/SPEC.md` and `SPEC.oracle.yaml` retrofit the Tier 3 benchmark (W9, road §4.2)
from the shipped kiln: customer intent (200 mm cube chamber, 1200 °C, 230 V / 16 A circuit),
all 29 requirements, and 4 concept cards (C-003 promoted; C-001 rejected by envelope; C-002
by touch temperature and volume; C-004 styling variant). Worked figures cite mean-area thermal
conduction (898 W loss, 44 °C touch), element sizing (10.9 A, 29.3 m wire), and swing clearance
(6.32 mm). The oracle asserts 47 rows (concepts, figures, ceremony standard, 6 safety sign-offs).
Measured: `tests.benchmarks.oracle` on a copy of kiln: 47 passed, 0 failed; `test_benchmarks.py` green.
## S-219 — Display units: the owner's unit first (2026-11-04)
W8 / M3b: `n2f.yaml` `units: metric | imperial` (display only; defaults to `metric`, S-200).
A helper `display(q, units)` (`report/units.py`) formats quantities in the owner's chosen unit:
for `imperial`, lengths in `in` (`ft` above 120 in), masses `lb`, forces `lbf`, stresses
`psi`/`ksi` (above 1000 psi), temperatures `°F`, with the original engineering unit in brackets
(`31.5 in (800 mm)`). The report's parameter, requirement and parts tables, and the napkin board's
computed and estimated figures and limitation messages use it. Metric products remain byte-identical
to before; drawings and exported files stay in mm. Tested against prebuilt bracket and board copies.
Closes B-0193.
## S-220 — Automated tests do not require example sign-offs to stay current (2026-11-04)
The nightly failed on Nov 1 and Nov 4 because `test_kiln.py` asserted no `needs-human` result.
The kiln's EXAMPLE sign-offs hash the rendered installation manual, so any edit to the manual's
text voids them; 11 commits did so after the hand renewal on Nov 3, and the kiln is checked only
nightly, so every landing stayed green. A sign-off is a person's call, not a test's: the kiln test
now asserts no failed check and no real sign-off (S-047), not that the example sign-offs are current.
The sign-off mechanism stays tested in `test_signoffs.py`, which signs at test time.

## S-221 — The table benchmark product (2026-11-04)
M4a / W9: `examples/table` from its `SPEC.md`: 3 cards (C-002, oak on a steel apron frame, promoted), 15
requirements (tip-over the one safety requirement, ceremony `lite`), 5 parts, 3 insert interfaces, 12 calcs
with SPEC 4.1 reference cases, one manual, one EXAMPLE sign-off. 0 package files (W10). Product screens (F10)
carry what the package lacks: the hardware set (mass, 36 USD), a mass limit, and sag, stress and tip-over rows
for C-001 and C-003 (the frame kit refuses bare legs; the structural screen reads only a frame with a top or a
column with an arm). Wanted: legs without rails; trestle ends in the structural screen.
Measured: oracle on a copy 46 pass, 0 fail, 5 pending as written. Product: sag 1.580 mm, long-term 0.754, yield
5.69, buckling 38.3, tip-over 3.92, sway 1.50 mm, corner 15.3, pull-out 84.5, 45.2 kg, 980.35 USD. Not exact:
napkin C-002 sag 1.54, yield 34.7, tip-over 3.88, buckling 29.6 (screen adds the edge load); movement 7.07 mm;
frame 15.90 kg. The oracle cannot parse an unsigned safety message (the dash after `>= 2` reads as a unit): re-sign REQ-009 after any edit to its evidence.
## S-222 — The test-stand benchmark product (2026-11-04)
`examples/test-stand` built from its `SPEC.md` with 0 package files (W9, W10): three cards, 19 parts (25 items) in three units, 12 interfaces, 23 requirements (the spec's 20, with footprint, fatigue and fuse each split in two), 7 calc modules with reference cases, wiring on 120 V / 60 Hz (13 devices, 7 circuits), five manuals, five decisions; `standard` ceremony, no sign-offs (12 wait on a person).
Oracle (`SPEC.oracle.yaml`, on a copy): 40 rows pass, 0 fail, 8 pending, run by `tests/e2e/test_benchmarks.py`. Cards: the C-frame is rejected on structure, the plate gantry on mass and cost, the portal promoted; card costs (460-1558, 434-1598, 3476-13965 USD) and masses (16.1, 16.5, 110 kg) are within 0.2 % of the spec.
Not reproduced: the screen's C-frame sag is 1.82 mm (spec 1.90: it leaves out the base arm and the column's stretch; inside the 5 % tolerance) and its yield factor 6.32 (spec 5.76); the parts list weighs 15.82 kg, the spec's 16.52 kg less the 0.60 kg of fasteners and wiring that have no part (the oracle expects 15.92 kg). Pending, with reasons: the portal's and the gantry's card-level structure (B-0210), the safety factors read through the requirements (B-0212), the two change requests (no replay step).
Gaps found: the structural screen has no portal case (B-0210); the cost screen cannot price per-metre or per-square-metre bands (B-0211), so `model/screens/stand.py` prices them and adds the bought-in parts and a mass-limit row (F10); the oracle misreads a unitless bound on a signed-off row (B-0212); the wiring diagram fails on a circuit that returns through its cable entry (B-0213). Beam sections are 60 x 40 x 5 mm in the model and a 60 x 60 x 4 mm stand-in of equal weight on the card; part costs are band mid-points (DEC-002 of the product). B-0194 stays open until both tiers land.

## S-223 — Benchmark follow-ups: the oracle reads unsigned safety requirements (2026-11-04)
An unsigned safety requirement's message ends `>= 2 — passes by computation; ...` and the oracle's bound
finder read the dash as the bound's unit, so the table's tip-over figure needed a current sign-off (S-221).
`parse_bound_message` now takes a unit only if it starts with a letter, `%` or `°` and the unit registry knows
it. Tests pin each message shape `n2f check --json` emits (plain, failing, signed, unsigned, stale sign-off).
Measured: the table oracle passes on a copy with `REQ-009.yaml` removed (46 of 46 before the new figure); the
example keeps its EXAMPLE sign-off, so S-221's "re-sign after an edit" no longer matters to the oracle.
New figure `req-slot-clearance` (13 less 7.05 mm, ±0.35 mm, found 5.93): 47 pass, 0 fail, 5 pending. Movement
and slot travel alone stay pending: no requirement bounds either one. Gaps filed: B-0214 to B-0219.
The test stand's unsigned yield, fatigue and tip-over figures are real rows now (44 pass, 7 pending on a copy); closes B-0212.
## S-224 — Review gate I (v0.7) — outcome (2026-11-05)
Engineering and honesty, fresh context, at 4024c8e (`docs/reviews/v0.7-gate-i.md`). NOT READY. Blockers,
fixed before the close: the fixed-base branch of `frame_racking` uses (k+2)/(6k+1) for (3k+2)/(6k+1)
and under-reports sway up to 3x (confirmed by a stiffness-matrix solve); the product region never
reaches the cost screen (US bands, USD, no region or date on the owner's cost line; an EUR band
would crash). Held: eleven hand-checked formulas, the three benchmarks green on their oracles, the
oracle judging outcomes not ids, ceremony relaxing paperwork only. Concerns go to the fix task (C1,
C2, C9: provenance wording, stale texts) or to rows B-0220–B-0226; C8 (the table top's cross-grain
load path, near its sag margin) is a benchmark fix before the close.
## S-225 — Review gate J (v0.7) — outcome (2026-11-05)
UX in the owner persona (a US hobby woodworker), fresh context, at 4024c8e (`docs/reviews/v0.7-gate-j.md`).
NOT READY. Blockers, fixed before the close: a card whose structural check did not run shows "holds
up"; costs never name region or date (the same defect as gate I's second blocker); manuals render N,
kg and mm in an imperial product; "50 x 50 x 1.5 mm" displays as "50 x 50 x 0.0591 in". Held: inches
first on the board and the report tables, a visibly shorter lite report, the budget row, one
disclaimer and no lecture. Concerns C1, C5, C8 go to the fix task; the rest are rows B-0227–B-0232
(phone-width overflow belongs with the workbench, Track C).
## S-226 — Gate J blockers fixed: unrun checks shown, manuals and dimension groups in the owner's units (2026-11-05)
Fixes B1, B3, B4 and concerns C1, C5, C8 of S-225 (B2, cost region and date, is another task's).
B1: a card with a skipped `structural-*` row (the screen adds rows only when the card gives a load) shows one amber
line on the board, `concept show` and `concept build` ("not checked: the structural screen does not model this
shape — sag and tip-over are unknown"; a skip that asks for a card field says so instead) and reads "no problems
found, but not fully checked", never "holds up" or "screening found no limitations".
B3: manual values (`P[...]`, `bom`, parts, requirements) go through `report/units.py` like the report tables; the table
manual carries no literal units. B4: a dimension group converts whole and stays in inches (`1.97 x 1.97 x 0.059 in
(50 x 50 x 1.5 mm)`): a US shop reads inches, and "50 x 50" beside an inch sign reads as 50 inches; inches stop at three
decimals. C1: `330 lb` on a force field hints "330 lbf or 1470 N". C5: no Manuals section when Safety is the only page.
C8: Interfaces resolves `param://` to its value and units. Measured: the touched unit tests, the board, report and docs tests, the benchmarks.

## S-227 — Gate I blockers fixed: fixed-base racking, the product region in costs (2026-11-05)
B1: fixed-base sway is P h^3 (3k+2)/(12 E I_c (6k+1)); the corner spring, derived with the base sharing the moment, is
delta = P h^3/(24 E I_c) (4 - 3 r), r = 1/(1 + 1/(6k) + E I_c/(h K)), not the old additive P h^2/(4K). Both match a 2D
frame stiffness solve in `tests/unit/test_joint_calcs.py` (k = 1: 0.02976 mm; rigid beam: 0.02083 mm; pinned too).
B2: the cost screen reads the card's `site.region`, else `n2f.yaml`'s (the runner puts it in `values.shared`); none declared
reads the US bands and says "no region declared". Amounts stay in the band's currency (a mixed card is not summed; a USD
budget is not held against EUR); processes a region has no band for are named. Every cost line, the report total and the
parts table name region and date ("stale" only over 24 months); mid-point prices carry a numbered note (gate J).
C1/C2/C7/C9: no structural or joints case is `external` unless the source prints that example (kept: datasheet, Eurocode and
moisture-table lookups); Roark simply supported cases are 2a and 2e; no "Track A" source; citations `[verify]`; joints raise
`UnitError`. The table and test-stand screens skip adding USD to EUR. C8 and C10-C12 stay with B-0220-B-0226.
## S-228 — Spec reproduction trial 1: the test stand (2026-11-05)
Road §4.3, one model of the first vendor, empty folder, only `SPEC.md` and the installed tool
(`docs/reviews/v0.7-spec-trial-stand-1.md`). First board 15 min / ~42 tool calls, first report 24 min /
~68 calls; a product with 0 failing checks. Oracle: 30 pass, 14 fail, 7 pending. Most failures are
the oracle's: it encodes the example's modelling (19 parts exactly, the mass without a wiring part,
beam fatigue as its own requirement, card figures at ±5 % where the screen simplifies). The rest are
package gaps: no generic mass-limit screen, per-metre bands unpriced (B-0211), a traceback on a plate
gantry card, the wiring IndexError (B-0213), earth wires counted as load current, repository docs an
installed tool cannot reach. Fixes before the second vendor's trials: B-0233–B-0238.

## S-229 — The table top's cross-grain path, worked (2026-11-05)
Gate I C8 (S-224): the table spec took top + long rails as one beam and assumed the 150 kg at the middle reached the rails through the oak. Worked in `examples/table/SPEC.md` 4.1: white oak E_T/E_L 0.072 (FPL-GTR-190 Table 5-1), E_T 885.6 MPa; the top as an orthotropic plate between the rails (closed form for a point load, double Fourier series for the 100 x 100 mm base the spec states) dishes 3.88 mm (point) or 3.79 mm (base), bending stress 1.75 MPa against 5.5 MPa tension across the grain (factor 3.1). It would not break; it would sag 5.39 mm with the 1.60 mm along the length, 116 % over 2.5 mm. The review's 650 mm strip (6.50 mm, 2.45 MPa) overstates both.
Design change: a 75 x 75 x 1.5 mm cross rail, a part of its own (the frame kit has no member across the middle; kit `tube`, welded between the long rails, top flush, 25 mm lower than the apron), dip 0.106 mm, bearing 0.196 MPa across the grain (factor 37.7, new REQ-016). Sag 1.580 -> 1.705 mm (36.8 % -> 31.8 %); scan: 50 x 50 gives 21.5 %, 60 x 60 27.8 %, 70 x 70 30.8 %.
Moved: fixings 8 -> 6 (the x = 0 tabs sat where the rail is welded; long-rail tabs now x = +-300), hardware 0.500 kg, table 45.3 -> 47.2 kg (32.6 %), cost 606-980 -> 639-1014 USD (36.6 %), tip-over 3.92 -> 4.09, pull-out 84.5 -> 75.6, long-term sag 0.754 -> 0.811 mm; ECR-1 is now 31 mm (32 mm would leave 29.8 % on mass). SPEC 8.1 lists every old -> new figure for the second re-derivation.
The cross rail protects the middle only; a 150 kg base elsewhere on the centre line would dish as above, and the manual says to stand heavy loads over it. Measured: the oracle on a copy, 50 passed, 0 failed, 6 pending (the new pending row is the unsupported dish); `tests/e2e/test_benchmarks.py` and `tests/unit/test_oracle.py` pass; `make lint` and `make types` clean; all 16 reference cases of the table calcs reproduce under `n2f check`. Not measured: a second vendor's re-derivation of the new figures.

## S-230 — The oracle judges outcomes, not one agent's modelling (2026-11-05)
Spec trial 1 (S-228) failed 14 oracle rows; all but two were the oracle's, not the product's. Road §4.2: outcomes, not one agent's choices. `SPEC.oracle.yaml` of the test stand now takes the assembled and required mass as 16.52 or 15.92 kg (a part for fasteners and wiring or none), distinct parts 19 to 20 and items 25 to 26 (a range, since the spec lists every part and an agent adds at most the allowance part), and the governing fatigue factor (`aggregate: min` over the requirements worded fatigue, 7.42 whether beam and bolt are one requirement or two). The width at 400 mm is found by `words: bbox.[xy]`, so a part's height at 400 mm no longer makes it ambiguous. `RequirementFind` gains `words`, `not_words`, `aggregate`. Card figures the screen simplifies carry a stated tolerance: C-frame sag ±10 % (the screen leaves out the base arm and the column's stretch), the two cards' cost bands ±5 % (hinges, feet and fasteners drawn as pieces are priced: 0.8 kg of 16.5 kg). The plate gantry's figures are found as "rejected, not by stiffness", so a missing mass screen (B-0234) hides only the concept row. Table and kiln oracles: the table's heavy card found the same way, counts stay exact (their specs list every part, no allowance part).
B-0211 closed: the generic cost screen prices a piece on a per-metre band by its longest side and on a per-square-metre band by its biggest face; the test stand's own screen lost that code and keeps its bought-in parts and mass limit. Its three cards price as before (460 to 1558, 434 to 1598, 3476 to 13965 USD).
Measured: the oracle on a copy of the trial's product with this tool: 41 passed, 2 failed (before: 30 and 14); on copies of the test stand, table and kiln: all pass. The 2 failures are both the missing generic mass-limit screen (B-0234). Not measured: a second agent's product.
## S-231 — The using docs ship with the tool: `n2f docs` (2026-11-05)
Spec trial 1 (S-228): the product's `AGENTS.md` and roles sent the agent to `docs/kit.md`, `docs/electrical.md` … "in the system repo", which an installed tool cannot reach; and `n2f init` refused a folder holding only the owner's `SPEC.md`.
Decided: the using-side pages ship in the wheel (`napkin2factory/_docs/`, hatch `force-include` from `docs/`, which stays the one source; the sdist holds them too because `uv build` builds the wheel from the sdist; the `n2f` alias package is a placeholder and needs nothing). The verb `n2f docs [topic]` (`cli/docs.py`) lists the 14 topics with the page's first heading, prints one (`--json`: topic, title, text) and lists the known ones for an unknown name; in a checkout it reads `docs/`, installed it reads the packaged copy. Beyond the brief's eleven pages it also ships `how-it-works`, `ecr-loop` and `schema-policy`, which the guide points at.
Every "system repo" pointer in `_common` (so every template and example) and the guide now says `n2f docs <topic>`; the product `AGENTS.md` names the verb. `n2f init` refuses only when a file it writes already exists, naming it; the owner's other files stay.
Measured: `uv build` wheel holds all 14 pages; tests in `test_docs_verb.py` (list, topic, json, unknown, wheel contents, both init cases), `test_agent_docs.py`, `test_templates.py`.
## S-232 — The diff page survives a failed shader; its test no longer flakes (2026-11-05)
B-0209: `test_diff_page_loads_and_highlights` failed in loaded `make check` runs. Cause, reproduced: under CPU load SwiftShader's software WebGL fails to link a shader (`THREE.WebGLProgram: Shader Error … VALIDATE_STATUS false`, empty log) on `part://base`; three.js logs that as `console.error`. Loading the built diff page 40 times beside 8 busy loops, 26 of 40 loads logged it (14 clean); The earlier answer (B-0024: reload the page once in the test) cannot cover a failure rate that high.
Fix in `report/viewer.js` (shared by the report, board and diff page): `renderer.debug.onShaderError` replaces the console error; after a frame the viewer disposes its materials and draws again, up to 3 times, and a lost context goes straight to the end; then it hides the canvas and shows a plain notice (the diff page's own sentence points to its part list, drawings and tables) with one `console.warn`. New `viewer.settled` / `glState` (`ok`, `unavailable`; `data-n2f-webgl`) say which; `n2fViewerReady` waits for it, and the first draw of a loaded model runs off screen too, so it never hangs.
Test: opens from file://, no console errors, each viewer `ok` or `unavailable`, the changed part's colour set in the scene graph (not GPU output), the changed pill in the DOM; no retry, no sleep. The other four Playwright tests keep `real_page_errors` (now redundant, harmless).
Measured: same page, same 8 loops, 40 of 40 loads clean (34 needed one recompile, 6 none); forcing every link to fail gives `unavailable` with the notice and a warning, no error. 20 of 20 passes of the test function under 8 busy loops; `make check` once at the end.
## S-233 — Package fixes from spec trial 1 (2026-11-05)
Closes B-0213, B-0234, B-0235, B-0236, B-0238 (S-228). (1) New generic `mass-limit` screen (`screens/mass_limit.py`): over `site.mass_limit` fails, within 10 % of it warns (a screening choice, the mass being read off rough shapes); a product's own row of the same id replaces it (the runner), so the table and the stand are unchanged. (2) The structural screen takes one column and one arm: a second upright at least half as tall, or an "arm" below the column's foot, is a skip in the gate I wording, and the formula's own error is a skip too; the plate gantry with block feet no longer raises. (3) A load wired by its `PE` terminal alone is not fed by that circuit (`Wiring.load_devices`), so earth bonds in a mains circuit add no current; an unlisted card material is named in the screening notes with the known ones (it was weighed as mild steel unannounced; no lint rule, that would be a `core/concepts.py` edit). (4) The wiring layout closes empty columns and `_channels` skips one. (5) The promotion decision says "no problems found, but not fully checked" where it said green; L5 (a `core/lint.py` edit) skips a bound with no unit.
Measured: each fix has a test that fails without it (`test_structural_screen.py`, `test_mass_limit_screen.py`, `test_electrical_checks.py`, `test_electrical_diagram.py`, `test_promote.py`, `test_lint_unit_agreement.py`); the test stand now lints with no L5 warning. Not changed: B-0210 (a portal or gantry is still "not run"), B-0211 (per-metre pricing, another task).
## S-234 — Spec reproduction trials 2 and 3: the table, two vendors (2026-11-05)
Road §4.3: cold agents of two vendors, empty folders, only `SPEC.md` and the installed tool (with
`n2f docs`, S-231) (`docs/reviews/v0.7-spec-trial-table-1.md`, `-2.md`). Both reach a product with 0
failing checks. First board 8 / 13 min, first report 17 / 30 min (~95 / ~159 tool calls). Oracle:
32/18/6 and 38/12/6. Common causes: the generic structural screen has no case for bare legs, trestle
ends or a cross member under the top (the example judges them in its own screens, which a cold agent
does not write), so a pine card on four legs is not rejected for sag; the oracle reads figures by the
example screen's names, expects exactly one sign-off and ±2 % on card-level costs; `n2f init` asks no
region. The test stand's trial 1 now passes 43/0/7 after S-230 and S-233. Fixes: B-0239–B-0241.

## S-235 — The structural screen judges bare legs, trestles and a cross member (2026-11-05)
Closes B-0239, B-0214, B-0215, B-0217 (S-234). The generic `structural` screen reads a top on a stand
in three shapes: a `frame` call (the kit now allows `top_rails: false` with `bottom_rails: false`: four
legs in one part, so volume, mass and the cut list stay exact), bare upright tube or block legs, and
plate or frame trestle ends; a tube or block across the frame under the top is a cross member whose dip
adds to the sag along the length. Leg buckling takes a quarter of the weight plus the centre load, not
the edge load; tip-over uses the lowest feet (glides, else bar or leg faces) with hardware mass.
Values (named in `docs/napkin.md`): `deflection`, `deflection_along`, `cross_member_dip`,
`yield_factor`, `cross_member_yield_factor`, `buckling_factor`, `tip_over_factor`. Measured
(`test_structural_stands.py`): C-001 sag 14.3 mm (spec 14.25), C-002 1.71 (1.705), C-003 0.837, within 5 %.
The table's supports and cross-rail screens are deleted; its oracle reads these names (52 passed, a copy).

## S-236 — Init asks for region and units; the oracle allows an agent's extra inspection and its own massing (2026-11-05)
Spec trials 2 and 3 (S-234): neither cold agent set the product region (the spec says US), so the oracle failed the region row and read US bands without anyone choosing them. `n2f init` gains `--region <code>` and `--units metric|imperial`, validated by the manifest model and written to `n2f.yaml` (nothing is written for a bad value; refused on an existing product). Without them init asks nothing new but prints a reminder; the product `AGENTS.md` (rule 10) and `roles/pm.md` tell the agent to ask the owner, once, where it will be built and bought and which units they think in. `n2f check` prints one sentence and `--json` carries `region_note` while no region is declared and costs read bands; the board adds the same as one note (it builds on S-227's labelled cost line).
Oracle: the table and the stand no longer count exactly one sign-off; two facts say "at least one requirement waits on a sign-off" and "the tip-over (safety) requirement is among them" (new `words` filter of `count_requirements`). Card-level cost bands carry ±20 % (table) and ±10 % (stand), from the trials: promoted table card 628-1204 USD (+18.7 %, a cross rail given the machining process) and 603-977 against 639-1014, stand portal -7.1 % / -6.8 %; the finished product's parts-list total stays a strict range.
Measured, oracle on fresh copies after S-235's value names: the table example 53 pass / 0 fail and the stand example 45 / 0; the stand trial product 45 / 0 (it was 30 / 14); the table trial products 46 pass / 7 fail (was 32 / 18) and 47 / 6 (was 38 / 12). What still fails there is the agents' own work, not the oracle: neither set a region (the init flags and the PM question address that), one trial's pine and trestle massing differs from the spec (mass, cost, tip-over), and the cards of one trial carry their own screens, which name no `deflection` or `tip_over_factor`.

## S-237 — Health review 2026-11-05 (v0.7 close) — outcome (2026-11-05)
Trend row recorded at 0f94927 (`docs/reviews/health-2026-11-05.md`; window 9d030b1..5011b22, 36 commits). Worse: modules over 550 lines 11 -> 13 (`electrical/checks/calcs.py` 838, `ecr/lifecycle.py` 608), verify rows 268 -> 279, open rows 109 -> 124, E10 seam commits 11 -> 18; better: 0 task conflicts, 0 unstamped, tests 1195 -> 1288, `docs/agent-guide.md` in 0 of 7 collision pairs (was 4).
W10: 17 distinct `core/` files in 7 commits since S-197; M2a, M2c, M3c, M4 touched 0; the three fix tasks S-212, S-215, S-233 are the only unplanned ones. Four non-core seam commits (S-219, S-226, S-227, S-236) did not name their file.
Union-merge duplicates: S-216 covers an id in Open and Closed; the same row edited by both sides keeps two copies in one table (reproduced on a scratch repo), which the gate catches and `make land` then gives up on.
Closed here: B-0190, B-0194 (delivered), B-0206 (S-216). Opened: B-0243 (same-table duplicates, ~30 min), B-0244 (split calcs.py and lifecycle.py), B-0245 (split `report/builder.py`, 549), B-0246 (land warns on unnamed seam edits), B-0247 (three dead skips), B-0248 (coverage read from the main folder), B-0249 (STATUS and CLI-reference drift). CI results on `main`: not measured (no `gh` login in the task).

## S-238 — Health-review quick fixes before 0.7.0 (2026-11-05)
Four small findings of the S-237 review. `scripts/journal_ids.py` `dedupe_backlog` keeps the last copy of a
backlog id repeated within one table (union puts the task's edit after main's), beside the S-216 Open-against-Closed
rule (B-0243). Three skips that could no longer fire for their stated reason are assertions (B-0247). `make health`
reads `coverage.xml` from the main worktree (git common dir) when its own folder has none and prints the file and
its age; it no longer refuses a file older than HEAD, the age lets the reader judge (B-0248). `STATUS.md` "Where we
are" describes v0.7, and `docs/cli.md` says `n2f discard` keeps filed change requests since S-212 (B-0249).
Measured: `tests/unit/test_journals.py` (new same-table case), `make health` run once.

## S-239 — v0.7 close: spec trial 4, the §2.1 measures, the handoff (2026-11-05)
Trial 4 (`docs/reviews/v0.7-spec-trial-stand-2.md`): the stand again, vendor 2 (Gemini Flash). First board 20 min, first report 43 min (103 / 254 tool calls); a product with 0 failing checks; oracle 39 passed, 6 failed, 7 pending. The six failures are the agent's own model (no electrical supply, a fatigue requirement for the beam only, a depth limit lost when it rewrote the promoted requirements, blocks where the spec has tubes), with gaps behind three of them. The suspected auto-layout bug is confirmed: it steps by the previous part's width from origin to origin, so a part over 40 mm wider than its predecessor overlaps it (reproduced: 3 interferences). Nine rows opened: B-0250 (no supply under a `hazard:mains` requirement says nothing), B-0251 to B-0258.
The §2.1 measures (`docs/reviews/v0.7-measures.md`), the baselines Gate A inherits: first report 16 / 30 min (table, two vendors) and 23 / 43 min (stand); warm rebuild 14.4 s (table, target 1 s), 19.4 s (stand), 50.8 s (kiln); guide plus product `AGENTS.md` about 9,100 tokens (characters / 4; no tokenizer installed); tokens 649k and 1548k for the two Gemini runs, the Claude runs not measured; oracle pass rate stand 100 % (Claude) and 87 % (Gemini), table 87 % and 89 %; skill suggestion rate not measured (Track B).
The handoff (`docs/reviews/v0.7-handoff.md`): items 4, 8 partly met, 9 not re-run, the rest met; tiers 1 and 2 ran with two vendors, tier 3 and two client kinds did not. The version bump and tag are the overseer's. Docs only; no `core/` file.

## S-240 — Trial 4 message and doc fixes: card and assembly hints, quantity abs, calc kit docs (2026-11-05)
Closes B-0253, B-0255, B-0258 (S-239, spec trial 4 and table trial 3 hit all three). A card key that is really a
screen field (`point_load`, `max_deflection`, `cycles`) or `loads:` at the top says it goes under `site:`, and
`site.loads:` says each load is its own key; the skeleton lists the structural keys on one line (`CardField.group`,
the fields stay hidden otherwise, S-137). An empty massing suggests `frame`/`tube`/`block` when the card carries a
load, else `enclosure`. An assembly line with `at:` (or other coordinates) says positions come from the geometry
module's `place_by` or the automatic layout. A reference case's `abs:` takes a quantity (`0.05 mm`, converted to
the expected unit; a temperature step reads as a difference) and names both units when the kind differs.
`docs/calckit.md` documents `structural`, `joints` (including wood movement and moisture) and the three new tables.
Measured: new tests in test_concepts, test_massing, test_loader, test_calckit_cases pass.

## S-241 — Trial 4 package fixes: auto-layout spacing, mains without a supply, finish in lint (2026-11-05)
Three package faults of spec trial 4 (S-239). `_auto_layout` (`geometry/build_asm.py`) placed each child one previous-width
past the last origin, though a part's box is not centred on its origin, so a wide part after a narrow one overlapped it
(B-0251); it now starts each child one 20 mm gap past the previous child's far x face, using each box's own min and max.
`n2f check` and its `--json` (`hazard_note`) say, in one line like the region line (S-236), when a requirement carries a
hazard tag whose model is absent: `core/data/hazards.yaml` names the domain of `mains` (`electrical`), and
`core/ceremony.py::unmodelled_hazard_note` fires when that domain has no content and `n2f.yaml` has no scope line other
than `in` for it (B-0250). A custom part with no `finish` is now an `n2f lint` error, rule `L8-custom-finish`, beside its
tolerance, process and material; the `custom-part-complete` check stays (B-0256).
Measured: `tests/unit/test_auto_layout.py`, `test_ceremony.py` (three new), one e2e `n2f check` case; examples and templates lint clean.

## S-242 — Close v0.7: version 0.7.0, pins >=0.7,<0.8 (2026-11-05)
Track A is delivered (S-197 to S-241; the handoff is `docs/reviews/v0.7-handoff.md`, S-239). `pyproject.toml`,
`packaging/n2f/pyproject.toml` (and its `napkin2factory==` pin) and `src/napkin2factory/__init__.py` say 0.7.0; every
product pin the package writes or ships (the manifest default, the templates and their workflows, the five examples, the
test fixtures, `docs/product-model.md`) says `>=0.7,<0.8` (S-083). Before the tag: the commit-email rewrite (B-0242),
`make check` on `main`, CI green. Tagging stays the maintainer's call (S-072). Open at the close: the stand's portal on the
structural screen (B-0210), no tier-3 spec trial, one client kind in the trials (§2.1), B-0252, B-0254, B-0257.

## S-243 — The commit history carries no personal email (2026-11-05)
The owner's old personal address was the author or committer of about 270 commits (metadata only: no file, message or
package carried it), and spam followed. Before the `v0.7.0` tag, `git filter-repo --mailmap` rewrote every commit's author
and committer to the GitHub noreply address, with the mapping in a private file outside the repository (B-0242): 328
commits, every tree byte-identical to its original (compared for all of them through filter-repo's commit map), names
unchanged, the six tags moved with them. The commit hashes quoted in the journals, handoffs, reviews and transcripts were
replaced by their rewritten ones (271 in 41 files). The force-push of `main` and the tags is the maintainer's step; clones
made before it keep the old history, which the owner accepted.

## S-244 — v0.7.0 released (2026-11-05)
`make check` passed on `main` at the S-243 commit (1,829 passed, 4 skipped); the email-rewritten history was force-pushed
by the maintainer (S-243; the first attempt failed on GitHub's side, "fatal error in commit_refs", the retry went through);
CI `ci` passed on Linux and macOS there (17 min), then `v0.7.0` was tagged on it and `publish.yml` published both packages
(build, pypi, pypi-alias green; `napkin2factory` and `n2f` 0.7.0 on PyPI). The nightly `check-full` failed on 2026-11-04
and 2026-11-05 on two timing budgets only (two cards through one screenshot session 23.5 s; a warm concept build 31.0 s on
the CI runner; B-0259). Visual exit (S-078): not yet judged by the maintainer for v0.7's boards (the table and test stand).

## S-245 — Open v0.8, Track B: forward and backward (2026-11-05)
`docs/stages/v0.8-bidirectional-iteration.md` schedules Track B (M0 to M6, R1–R15). Checked against the code first (road §5.4):
`.patch` files, not embedded strings, carry design edits; `core/vcs.py` cannot list or restore snapshots, read a file at one,
diff against unsaved files, or make a draft line. So R1 adds those primitives and R2 amends Track B §1 and §3.3: history only
moves forward, a parked direction and a change request's baseline are named refs (`refs/n2f/`), never a switched line. The
direction/product ownership table is §3. Schema 2 carries every format change (R8). Also scheduled: the no-change build (R12,
8–11 s measured, 2 s target), B-0218, B-0230, the lifecycle split of B-0244, B-0259, the thin MCP server and skill (B-0036,
R14). Rows B-0260 to B-0266. Two of the overseer's own subagents at a time, as the maintainer set.

## S-246 — M1a: store primitives and the checkpoint format (2026-11-05)
`Vcs` gains R1's primitives (in `core/vcs_store.py`, a mixin, to stay under 550 lines, S-184): `snapshots`, `snapshot_count`,
`read_file`, `tree_of`, `diff_working`, `working_hash` (a temporary index; real index, current snapshot and folder untouched),
`restore` (whole or by path prefix; ignored files never touched; saves nothing, the caller snapshots, R2) and markers
`set_ref`/`read_ref`/`delete_ref`/`list_refs` under `refs/n2f/` (validated names). `core/checkpoints.py` holds R3: a label,
then trailers `Checkpoint-Mass`, `-Cost`, `-Restores`, `-Undoes`, `-Redoes`. Undo and redo come from the log by two stacks:
`Undoes: X` moves X done to redo, `Redoes: X` back, any other checkpoint (rollback included) is pushed on done and empties redo;
undo restores the entry below the top (stopping at a baseline id), redo restores the top of redo. Restores are always recorded,
even when the tree is unchanged. `publish` sends no marker and a fresh copy has none (both tested). Measured: 62 new tests
(35 store, 27 checkpoints, 5 of them 200-example property runs) in 17 s; `test_vcs.py`, `test_publish.py`, `test_vocabulary.py`
pass untouched. B-0060's store half is done; M2b closes it. `core/` touched: `vcs.py`, `vcs_store.py`, `checkpoints.py`.
## S-247 — M1c: the no-change build (2026-11-05)
R12 targets under 2 s for a build with nothing changed. Measured as three fresh `n2f build` processes after one cold build, `/usr/bin/time -p`, copies of
`examples/table` (tier 1) and `examples/test-stand` (tier 2) in a temp folder. Before: tier 1 8.1–8.6 s, tier 2 9.1–11.2 s. Profiled (cProfile, `-X importtime`):
`cli/build.py` imported the CAD kernel (build123d/OCP, with scipy and sklearn) before looking at anything, about 3 s of a 5 s build even with every rule up to
date; the rest is imports (pydantic, pint units ≈ 0.65 s), reading 136 YAML files (≈ 0.3 s), `needs_run` over 14 rules (≈ 0.2 s). `run_build` now takes
`before_first_run`, called once just before the first rule that must run; the CLI passes the kernel loader there, so a no-change build never imports the kernel
(its "loading the CAD kernel" note is then not printed; the assembly and geometry-only paths still load it first). Needs-run decisions are untouched, so a
changed input rebuilds exactly what it did. After: tier 1 1.3–1.5 s, tier 2 1.9 s; outputs byte-identical (`tests/e2e/test_nochange_build.py`, with a timing
budget under `N2F_TIMING=1`). Host fact: `PYTHONDONTWRITEBYTECODE=1` and an editable `uv sync` leave no `.pyc`, which cost another 3 s per process here until
`python -m compileall` ran on the venv and `src/` (the before figures are without it; with it, tier 1 was 5.0–6.4 s; B-0267). `core/` touched: `core/graph/runner.py`. Left: the pint registry and YAML parsing, if a later loop needs it.
## S-248 — M2a: `ecr/lifecycle.py` split, code moved verbatim (2026-11-05)
v0.8 M2a, the lifecycle part of B-0244 (S-184's method; S-080's reason: parallel agents collide in long files, and M2b
rewrites this module next). `ecr/lifecycle.py` (608 lines) → `ecr/state.py` (62: `EcrError`, the file and transition
helpers, `next_ecr_id`), `ecr/apply.py` (253: the edit and patch application), `ecr/revisions.py` (164: output hashes,
revision bumps, the close gate, the changelog), `ecr/lifecycle.py` (241: new, impact, approve, reject, close, the table),
which re-exports every moved name. Checked: all 25 top-level defs and classes AST-identical to before; no test or caller
changed. B-0244 stays open for `domains/electrical/checks/calcs.py` and `outputs/diagram_layout.py`. `core/` touched: none.
## S-249 — B-0259: the nightly timing budgets, measured on the runner (2026-11-05)
The nightly `check-full` (ubuntu-latest, `N2F_TIMING=1`) failed on 2026-11-05 on two timing tests only: two cards through
one screenshot session 23.5 s (budget 15 s) and a warm `concept build --all` 31.0 s (budget 20 s). The same tests on the macOS
host: 5.1 s and 7.2 s, so the runner is about 4.5× slower, not a slowdown in the code. The host budgets stay; under `CI=true`
the budgets are 1.5× the runner's times, 35 s and 50 s. Correction to S-244: the 2026-11-04 nightly failed on
`test_kiln_checks_green_with_example_signoffs` (2 failures), not on these budgets; the 2026-11-05 nightly passed it. `core/` touched: none.

## S-250 — v0.8 wave 1 boundary: the core count and R12's first timings (2026-11-05)
Wave 1 (M1a S-246, M1c S-247, M2a S-248, B-0259 S-249): 22:28–22:57, 29 min, two subagents and two workers at once, landed one at a
time. R13 count: 4 `core/` files, all planned: `core/vcs.py`, `core/vcs_store.py` (new), `core/checkpoints.py` (new) in M1a;
`core/graph/runner.py` in M1c; M2a and B-0259 none. R12 on the macOS host, warm, fresh `n2f` processes after one cold build,
copies of `examples/table` (tier 1) and `examples/test-stand` (tier 2): a build with nothing changed 1.3–1.4 s and 1.7 s (target
2 s; was 8–11 s); a one-parameter `ecr impact` (today's static impact, before M2b's live diff) 1.1 s and 1.3 s; `undo` and
`concept switch`: not measured (not built yet). `make check` on `main` at 999f78d: 6 min 36 s, green, on a host otherwise idle.
§2.1 measures: not re-measured at this boundary (no guide or product-file change in wave 1).

## S-251 — Wave 2 seam: vitals and the change-request fields M1b and M2b share (2026-11-05)
Written by the overseer before M1b and M2b start, so neither waits on the other. `core/vitals.py` `current_vitals(product)`:
total mass and priced cost from `build/bom/rollups.json` ("47.2 kg", "1,014 USD", with "(some parts without a price)" when
incomplete) only when the parts-list rule is up to date under either render setting, else not measured (R3); it builds nothing.
Not in `bom/`: a new file there changes that package's code hash and restales every parts list. `core/model/ecr.py`:
`Approval.model_hash` (the folder hash at approval, R7) and `Ecr.baseline` (`checkpoint`, `mass`, `cost`, R6), both optional,
so v0.7 files still load; M2c's schema 2 makes them the rule. Tests: `tests/e2e/test_vitals.py`. `core/` touched: `core/vitals.py`
(new), `core/model/ecr.py`, `core/model/__init__.py`.

## S-252 — Wave 2 seam: the approval hash leaves out `changes/` (2026-11-05)
R7 binds an approval to the folder's hash, but `ecr approve` then writes its own record into `changes/ECR-x.yaml`, and `close`
and other change requests write there too, so a whole-folder hash would go stale at once. `Vcs.working_hash` takes `exclude`
(folder prefixes dropped from the temporary index before hashing); the approval hash is `working_hash(exclude=("changes/",))`,
and M1b's staleness report compares the same. Added before M1b and M2b start so both use one definition. `core/` touched:
`core/vcs_store.py`.

## S-253 — M1b: checkpoints, undo, redo and rollback (2026-11-06)
`n2f checkpoints [--all]` (newest first, 20 by default, "not measured" without vitals, marks undone ones and the current one), `undo`, `redo` and `rollback <#n | n | ECR-x | v1.0.0>`
(`cli/undo.py`; the steps are `do_undo`/`do_redo`/`do_rollback`, the verbs only print). Each saves unsaved edits first ("edits since #12 <label>"), restores,
and records "Undid: …", "Redid: …" or "Rolled back to …" with `restores=`; the vitals are copied from the state brought back. Undo stops at the open change
request's start (`draft` or `approved`; `cli/checkpointing.py` `open_change_request`), rollback refuses then and names `n2f ecr abort`. The staleness report reads the
checks after a restore (sign-offs, in `n2f check`'s words, built without renders) and compares each approved request's `model_hash` with `working_hash(exclude=("changes/",))`; it never revives. Labels: "Promoted
C-002 (title)", "Decided D-004: …", "Signed off REQ-003", "Released v1.1.0", the snapshot message. `discard` saves the edits as "edits discarded", then undoes them, so `redo` brings them
back. B-0121 and B-0260 closed ("nothing frozen", no hash, "change tracking", `docs/vocabulary.md` "checkpoint"). Measured R12, fresh `n2f undo` processes, bytecode on, best of three: tier 1
(`table`, one parameter) 9.1 s (10.0, 10.7, 9.1; one sign-off, so the checks rebuild what the parameter touches, a plain rebuild was 10.7 s), tier 2 (`test-stand`) 1.8 s (no sign-offs, no build). Tests: 13 unit
(`test_undo.py`), 1 property test of 10 random sequences (`test_undo_properties.py`, about 20 s), 1 e2e (`test_undo_signoff.py`, a stale sign-off named); old tests updated. Opened: B-0268 (the table's shipped REQ-009 sign-off reads stale), B-0269 (skip the checks build when no sign-off can be touched). `core/` touched: none.
## S-254 — M2b: live change requests (2026-11-06)
R6, R7, R9. `ecr start` saves unsaved edits as their own checkpoint, takes the newest checkpoint as the baseline (vitals in `baseline:`, marker `ecr/<id>/baseline`), records the start checkpoint right after it (undo stops there; nothing in between), then applies `--set` edits. One live request (`draft` or `approved`) is open at a time; requests without a baseline (v0.7 files, the kiln's drafts) keep the old steps behind `TODO(B-0263)`, do not count as open, and go in M2c. `impact` diffs the folder against the baseline (`core/graph/impact_live.py`), rebuilds up to the checks, and compares with `build/changes/<id>/baseline.json` (built once in a scratch copy of the baseline, started from this folder's `build/`); "rebuilt" is every rule whose key moved since the baseline. `approve` stores `working_hash(exclude=("changes/",))` and refuses when the model moved since the impact; `close` refuses when it moved since the approval (this sees unsaved edits: B-0060) and bumps revisions from the baseline, leaving parts born in the request at rev A; a new impact on an approved request puts it back to `draft`. `abort` saves the work, restores the start checkpoint, records "Aborted" with `restores`. S-252's exclusion is widened to `model/signoffs/` (`APPROVAL_HASH_EXCLUDE` in `cli/checkpointing.py`, used by impact, approve, close and the staleness report): an approval approves the design change, sign-offs are checked at close (`check` green), and the owner signs off what the change invalidated after approving.
Measured, macOS host, fresh processes, other work running: one-parameter `ecr impact` on a copy built with renders, best of three after the first: tier 1 (table) first 10.1 s, which fills the baseline cache and rebuilds the changed part, then 9.4 s with a fresh rebuild each time (the rebuild is nearly all of it) and 2.0 s with nothing to rebuild; tier 2 (test-stand) 17.4 s, 16.6 s, 3.0 s. Tests: 11 new (`test_ecr_live.py`), 7 old files moved to `_legacy_new`; 287 selected tests (the change-request, impact, release, snapshot, vocabulary and undo suites) green in 2 min 41 s plus 22 undo tests; the verbs save through `cli/checkpointing.py` (S-253). `core/` touched: `core/model/ecr.py` (`aborted`, transitions, `aborted_reason`), `core/graph/impact_live.py` (new), `core/graph/impact_patch.py` (`signoffs_removed_by` extracted), `core/lint.py` (L10 skips live requests).

## S-255 — M5: the thin experimental MCP server and the skill (2026-11-06)
`n2f mcp [-C DIR]` serves stdio from `napkin2factory/mcp/` (`tools.py` makes the tools and runs a call, `server.py` speaks the protocol); the optional extra is `napkin2factory[mcp]` (R14). Tools are
generated one to one from the Typer tree, so a verb added later appears with no edit (a test registers a dummy one): `n2f_<group>_<verb>` (`n2f_build`, `n2f_ecr_new`, `n2f_concept_build`), 39 at this commit, schema from the Click
parameters, `--json` always passed. Left out: `mcp`, `serve` (never returns), `skill` (writes outside the folder). Every call is the CLI as a process in the folder, exit code and stderr tail on failure, one at a time. The folder is fixed:
`dir` is in no schema, a path argument that leaves the folder (`..`, absolute, symlink out) is refused, `init` gets the folder as its positional (Track D 3.4). The server's instructions say once that the tools are experimental and
change before 1.0; nothing else does. The skill is `skill/SKILL.md` in the package (name, description, an eight-step loop that sends the agent to `n2f docs agent-guide`); `n2f skill` prints it, `--write DIR` makes `DIR/napkin2factory/SKILL.md`;
`n2f init` writes neither it nor a server config. The guide's "Adapting to your client" gained two rows with the fallback (the command line and the guide). `docs/reviews/prompt-set.yaml`: 40 prompts (20 should trigger, 20 should not; ids neutral, shuffled);
`scripts/trigger_rates.py` writes the judge's brief (no answers in it) and computes the rates. First measurement, one run by Gemini 3.8 Flash High through agyctl (a vendor other than the skill's author) seeing the name and description and the 40 prompts in one brief, workspace holding only the brief:
should-trigger 20/20 (100 %), should-not-trigger 0/20 (0 %). Too clean to be a target: the set is easy and one judge read the list in one pass, so Gate D (two vendors, one prompt per call, harder near-misses) sets the targets. `core/` touched: none.

## S-256 — v0.8 wave 2 boundary: the core count and R12's timings (2026-11-06)
Wave 2 (seams S-251, S-252; M1b S-253, M2b S-254, M5 S-255): about 05:45–07:02, two subagents at once, landed one at a time.
R13 count, this wave 7 `core/` files: the overseer's seams `core/vitals.py` (new), `core/model/ecr.py`, `core/model/__init__.py`,
`core/vcs_store.py`; M2b `core/graph/impact_live.py` (new), `impact_patch.py`, `core/lint.py` (unplanned: L10 skips live requests)
and `core/model/ecr.py`; M1b and M5 none. v0.8 so far: 10 distinct `core/` files. R12 on the macOS host, idle, warm, fresh `n2f`
processes, tier 1 (`examples/table`) / tier 2 (`examples/test-stand`): no-change build 1.4 / 1.7 s; `undo` of a one-parameter edit
7.8 / 2.5 s (tier 1 pays a checks build for its sign-off, B-0269); one-parameter `ecr impact` 11.1 / 8.4 s first (baseline cache and
the rebuild), 2.1 / 3.0 s again; `concept switch`: not built yet. `make check` on `main` at 11a1b35: 7 min 39 s, 1,945 passed, green.

## S-257 — Health review 2026-11-06 (v0.8 wave 2 boundary) — outcome (2026-11-06)
Trend row recorded at 75100c8 (`docs/reviews/health-2026-11-06.md`; window a55f8bb..75100c8, 19 commits). Worse: TODO lines in `src/` 0 -> 5 (all `TODO(B-0263)`, gone with M2c), open rows 124 -> 131, modules over 550 lines still 13 but a different set (`ecr/lifecycle.py` out, 608 -> 247 by S-248; `core/checks/calcs.py` 579 and `core/concepts.py` 740 up in S-240), `make check` 6 min 36 s -> 7 min 39 s (S-250 to S-256, cause not measured). Better: collisions 7 -> 1, tests 1288 -> 1386, skips 36 -> 34, coverage measured for the first time (0.9413).
All six seam edits since v0.7.0 (S-246, S-247, S-251, S-252, S-253, S-254) have an entry that names the seam file. The library now imports up into the CLI layer in three places (`ecr/live.py`, `ecr/live_impact.py`, `ecr/release.py` use `cli/checkpointing.py`), and `docs/cli.md` lacks `checkpoints`, `undo`, `redo`, `rollback` and `ecr start/abort/quick` with no test to catch it.
Fixed here: `docs/calckit.md` says 16 circuits (B-0155 closed); B-0185 text corrected. Opened: B-0270 (move the checkpoint helpers out of `cli/`, after M2c), B-0271 (docs/cli.md against `--help`, with M4), B-0272 (`check-full` skips two timing tests), B-0273 (split `core/concepts.py` before M3a), B-0274 (measure upward imports into `cli/`). CI results on `main`: not checked (no token).

## S-258 — B-0272: local `make check-full` runs every timing test but the kiln's (2026-11-06)
The health review (S-257) found `check-full` set `N2F_TIMING=1` for two files only, so R12's no-change build test (S-247) and the
two-cards screenshot test (S-249) ran nightly on CI but never on the host. Both are added (the screenshot one by node id, the rest
of that file already runs in `check`). The kiln's cold-build timing test stays CI-only: a cold kiln build is the slowest step there is.
## S-259 — B-0273: `core/concepts.py` split before M3a, code moved verbatim (2026-11-06)
`core/concepts.py` (740 lines) split into `concept_render.py` (125), `concept_lint.py` (330) and `concepts.py` (345), all ≤ 400 lines (S-184 method; S-080's reason: parallel agents collide in long files, and M3a edits concepts next).
`concept_render.py` holds YAML card text rendering (`render_card` and helpers); `concept_lint.py` holds promotion words and the concept lint (`decision_ids` through `lint_concepts`); `concepts.py` keeps card loading, numbering and status updates, re-exporting every moved name.
Checked: 42 top-level definitions AST-identical; no caller changed. `core/` touched: `core/concepts.py`, `core/concept_render.py` (new), `core/concept_lint.py` (new).

## S-260 — Runs hand off in the repository; the per-client file rule is about tracked files (2026-11-06)
The maintainer asked that ongoing work be picked up by any agent of any model, so a run's state lives in the repository, not
in one agent's private notes: the overseer keeps `docs/handoffs/v<x>-overseer.md` current at each wave boundary and when it
stops (AGENTS.md, How work flows; STATUS points at it). And S-076's rule (no per-client instructions files) is about what the
repository carries: a maintainer's own local, ignored file on their machine never reaches another contributor. The test now
checks tracked paths (`git ls-files`), falling back to the disk when there is no history. `core/` touched: none.
## S-261 — M2c: schema 2 and the change-request migration (2026-11-06)
R8, R15; closes B-0263. `migrate.CURRENT` is 2. `EcrStatus` is `draft | approved | closed | rejected | aborted` (`rejected` readable history; `impact`, `applied` gone as states); model validators: an open request needs `baseline`, an approved one `approval.model_hash`, `patch:` and `applied:` stay readable on finished requests only (plain messages, two invalid fixtures); `ConceptStatus` gains `parked` (nothing writes it before M3a); L10 retired. The migration (`ecr/upgrade.py`, registered in `migrate.py`) has a pre-check that `n2f init .` runs before touching anything: an open request whose edit or patch no longer fits refuses the whole upgrade naming the request and file, folder and history untouched. Mapping: draft/impact/approved with or without a patch: the lowest id stays open as a draft (checkpoints "Upgraded the file format to 2" = its baseline, "Started …", "… carried over from the old format"; edits through the live `--set` code, a patch by `Vcs.apply_patch`, kept only for this), an approval is cleared and the report says "approve it again"; `applied`: `approved` with `model_hash` of the tree now, baseline the state before its apply snapshot when in the history (so `close` still bumps revisions), else the checkpoint before upgrading, said in the report; `closed`, `rejected` unchanged; every other unfinished request becomes `aborted` ("set aside when upgrading: one change request is open at a time. …"), `patch:` key dropped, patch file kept. `n2f init .` now adds missing agent files before its "Before upgrading the format" snapshot, so a carried request does not count them as its change; the live impact reads a pre-upgrade baseline as the current format and ignores a schema-only `n2f.yaml` move. Going back: no open request, `n2f undo`; open one, `ecr abort` then `rollback #n` (undo stops at the request's start, R5); the report names both.
Removed: `lifecycle.new_ecr/run_impact/approve/reject/close`, `apply.apply` and the sign-off mover, `impact_patch.dry_run_patch` and its helpers, `compute_impact(patch=)`, `--patch`, `_snapshot_before`; `ecr reject` bridges to `abort` like `new` and `apply` (R9). Kiln: ECR-001 live (its edits applied: chamber 250 mm, heat-up 9 h, so mass 110.52 → 117.55 kg in `kiln.json`; its baseline checkpoint is not in a fresh copy's history, B-0276), ECR-002 and ECR-003 set aside with their patch files; `tests/golden` unchanged (142 tests), `kiln.json` regenerated. Tests that guard the kiln as designed (calckit reference numbers, napkin promotion, the oracle) read it through `copy_kiln_as_designed` (200 mm, 7 h). Opened B-0275 (abort of an upgraded `applied` request), B-0276, B-0277 (the kiln demos script the old flow; `make demos` is red until rewritten). Tests: 14 migration tests on `tests/fixtures/schema/v1` (a request in each v1 state: mapping, one-open, report words, undo, abort + rollback, refusals), throwaway-migration tests moved to 2 → 3 → 4, schema tests; 7 e2e files moved to the live flow. `core/` touched: `core/model/ecr.py`, `core/model/concepts.py`, `core/model/migrate.py`, `core/graph/impact.py`, `core/graph/impact_patch.py`, `core/lint.py`, `core/loader.py`, `core/vcs.py`.
Landed with the kiln settled (maintainer: "Set it aside"): ECR-001 ships `aborted` with its edits kept, like ECR-002 and ECR-003, and the two model parameters it had applied are back to 200 mm and 7 h; no example ships an open request. The three kiln demos and `tests/e2e/test_demos.py` run `ecr start` → `impact` → `approve` → `close` (ids ECR-004, ECR-005 and, in the electrical demo, ECR-004; the kept patches are applied by `git apply` as the edit step; the electrical demo approves again after its pick). Wave 3's half: `core/` this task 8 files (R13). R12 on the macOS host, warm, fresh processes, tier 1 (`examples/table`) / tier 2 (`examples/test-stand`): no-change build 1.5 / 2.1 s; one-parameter `ecr impact` 9.5 / 9.1 s first, 2.2 / 3.2 s again; `undo` 2.7 / 3.2 s; `concept switch`: not built yet. These ran while nothing else was testing, not repeated. `make check` on `main` at 1c1766e: 7 min 52 s, 1,964 passed, 5 skipped, green. The three demos and the golden tests pass.

## S-262 — B-0270: the checkpoint helpers move below `cli/` (2026-11-06)
`cli/checkpointing.py` (`checkpoint`, `save_edits_first`, `stale_after_restore`, `open_change_request`, `APPROVAL_HASH_EXCLUDE`) is now `ecr/checkpointing.py`: `ecr/` and `concepts/promote/` no longer import up into `cli/`; the CLI verbs import from `ecr/`. Moved with `git mv`; AST of the module identical before and after (S-184 method); only import paths and two docstring mentions changed. No `core/` file touched (R13: 0). Tests: undo, undo properties, change-request migration, `ecr_live` e2e import the new path. Not run beyond the land gate. B-0274 (measure upward imports) is still open; its baseline is now 1 (`core/graph/runner.py` console import).

## S-263 — M3a seam: the card's built figures, `Vcs.files`, decision links are history (2026-11-06)
The concept bridge (R10, R11) is designed in `docs/handoffs/v0.8-m3a-design.md`; this seam lands what both of its tasks share. A card gains an optional `built: {event: forked | parked, checkpoint, number, mass, cost, at}`: the figures measured from a direction's built design, never the napkin's; schema 2 is not released yet, so the optional field joins it without a new bump (F7, `docs/schema-policy.md`), and a card without it dumps as before. `update_card_status` sets or clears it; `Vcs.files(ref)` lists a saved state's files (the switch checks every tracked folder against §3). A parked card needs a reason, as a rejected one does (`C7-parked-has-reason`). A link in `model/decisions.yaml` that no longer resolves warns instead of stopping the load: decisions are history, as finished change requests are (S-215), and a switch leaves the parked direction's links behind. `core/` touched (R13): `core/model/concepts.py`, `core/model/__init__.py`, `core/concepts.py`, `core/concept_lint.py`, `core/vcs_store.py`, `core/loader.py`. Tests: `tests/unit/test_concept_built.py`.

## S-264 — M3a: `concept switch` parks a direction and brings another back (2026-11-06)
R10 as designed in `docs/handoffs/v0.8-m3a-design.md`: `concepts/direction.py` holds §3's two lists (plus every registered domain family's folder on the direction side); a tracked top-level folder or `model/` entry neither names stops the switch with its name, a top-level file neither names (an example's `demo.sh`) stays with the product. New row: `model/rulepacks/` belongs to the product, as `model/screens/` does (the product's own rules, F10). `concepts/switch.py` refuses first (no history, a Revision released, an open change request, nothing chosen, the same card, an unnamed folder, a parked card without its saved files and no `--fresh`, promotion's gates on the seed route), then saves edits, parks the current card (marker `parked/C-00x`, `status: parked`, its built figures), and either restores the target's parked files by file with a decision superseding the previous one, or runs the normal promotion over the model as it is (`promote(supersedes=)`; the parked direction's parts stay until changed, and the result says so). Any failure after the save puts the whole folder and the marker back. One checkpoint, `Switched to C-00x (…); C-00y parked`. `concept promote`'s lockout now names `concept switch`, or `ecr start --kind design` after a release. `core/` touched: none (R13).

## S-265 — M3a: `concept fork-from-model` and `compare`, built cards on the board (2026-11-06)
R11 as designed in `docs/handoffs/v0.8-m3a-design.md`. `concepts/fork.py` refuses when the build no longer matches the model, saves edits, writes the next card (based on the chosen one: its sections copied, its envelope re-read from the model's parameters, an entry the model lacks keeps the card's value with a note), with width, depth, height (the top assembly's bounding box), mass and cost labelled computed, "from the built design (checkpoint #n)", one fail row per requirement the last check failed, and `built: {event: forked, …}`; then checkpoints `Forked C-00x from the built design`. Stale means a non-render rule would run under both render settings: the design's `render=False` plan alone called every default build stale, because `render` is an input of the part and assembly rules (the reason `current_vitals` gives, S-251). `concepts/compare.py` prints the board's values per card (`--json` the same rows). The board marks a forked card "from the built design", shows a parked card's figures, and `cost` joins its strip; `concept build` refuses a forked card and points at a variant. Implemented by a worker of another vendor from the written design, reviewed by the overseer. `core/` touched: none (R13).

## S-266 — v0.8 wave 3 boundary: the core count and R12's four timings (2026-11-06)
Wave 3 is M2c (S-261), B-0270 (S-262) and M3a (S-263 seam, S-264 `concept switch`, S-265 `fork-from-model` and `compare`; design in `docs/handoffs/v0.8-m3a-design.md`). R13 count, de-duplicated (`git diff --name-only v0.7.0..HEAD -- src/napkin2factory/core`): v0.8 so far 17 distinct `core/` files; wave 3 12 of them (M2c 8; M3a's seam 6, two shared with M2c: `core/model/concepts.py`, `core/loader.py`; S-264 and S-265 none). R12 on the macOS host, idle, warm, fresh `n2f` processes, one run each, tier 1 (`examples/table`) / tier 2 (`examples/test-stand`): no-change build 1.6 / 1.9 s (target 2 s); `undo` of a one-parameter edit 9.8 / 2.8 s (tier 1 pays a checks build for its sign-off, B-0269); one-parameter `ecr impact` 12.3 / 9.0 s first, 2.3 / 3.3 s again; `concept switch` to a never-promoted card (seeded) 10.9 / 5.0 s, back to the parked one (restored) 10.3 / 4.1 s (tier 1 again pays the sign-off checks build). `make check` on `main` at d6cdda6: 8 min 40 s, 1,998 passed, 5 skipped, green. Not checked: CI on `main` (nothing pushed since S-244). Opened B-0278.

## S-267 — M3b: promotion keeps the card's loads, limits and units (2026-11-06)
Closes B-0230 (gate J C7) and B-0278. `concepts/promote/loads.py`: every `site` number the screens group as a load (their "when it carries a load" fields) and the budget seed parameters, owner `napkin`; the sag limit becomes a requirement verified by hand (no sag calc exists in a new model; the owner's limit must not vanish) and the budget a `bom_rollup` bound on the total cost. Both are allocated to the top assembly, never to a seeded parameter, because `concept switch` back to a parked direction removes seeded parameters (S-264). The tip-over factor is not seeded: the card carries only its inputs (edge load, offset), and the factor is computed. A value of the wrong kind is listed in the promotion notes. Statements use the product's display units, rounded (`less than 150 lb`; the stored bound stays exact). Form requirements come only from style the card or the owner stated, never a default preset. The decision names other ideas by their finding, without formula or source clauses. `render_card` prints `built`, so `fork-from-model` writes it once. Table promotion, measured on a copy: `Seeded 0 parameters, 1 requirement` before, `Seeded 3 parameters (2 already declared), 3 requirements` after. `core/` touched (R13): `core/concept_render.py` (B-0278); M3b none.
## S-268 — M4: the guide and roles teach the three loops; the command map is checked (2026-11-06)
Closes B-0265 and B-0271. `docs/agent-guide.md` gains "Stepping back, changing, switching: three loops" (checkpoints, `undo`/`redo`/`rollback`; the live change request from `ecr start` to `ecr close`, `quick`, `abort`; `concept switch`, `fork-from-model`, `compare`, and why a switch is refused after the first release). `roles/pm.md` puts a change and an undo to the owner in their words; `roles/design.md` edits model files inside an open request and never writes a patch. `docs/ecr-loop.md` (`n2f docs ecr-loop`) teaches the live flow, the old verbs only as R9's bridges. `docs/cli.md` has a row for every verb, and `tests/unit/test_cli_doc_rows.py` reads the verbs from the CLI app (top level, `ecr`, `concept`) so a new verb without a row fails. Budget (road §2.1), characters / 4, no tokenizer: the guide plus the product `AGENTS.md` was 36,703 characters (about 9,175 tokens) and is 36,260 (about 9,065): room came from moving the ceremony rules to `docs/product-model.md` and the structural screen's fields to `docs/napkin.md`, which the guide links. `core/` touched (R13): none.

## S-269 — M4.0: the oracle judges a change request (2026-11-06)
Closes B-0218. Designed by the overseer in `docs/handoffs/v0.8-m40-design.md`, implemented by a worker of another vendor from that file (about 45 min, 0.64 USD), reviewed by the overseer. An oracle's `changes:` rows are judged on a scratch copy, never the folder given: the agent's own request when exactly one in `changes/` matches the row's kind and words (a draft or approved one as it stands; a closed one at its `Closed` checkpoint; an aborted one at the checkpoint before `Aborted`), else a replay (`ecr start` with parameters found by value and words, never by id, then small file edits). The outcome (accepted: no requirement fails; refused: each `fails` regex names exactly one failing requirement, none left over), then figures and facts by the usual finders, plus `impact:` and `signoffs_lost` from `ecr impact --json`. Gate B (M6) uses the first path. Rows: table ECR-1 (accepted; sag, mass, cost band, tip-over) and test-stand CR-1 (refused by the load-cell requirement); both pass against SPEC.md section 6 as written. Table ECR-2 and test-stand CR-2 stay pending: each needs more than about 40 edited model lines (the table's frame follows the top's length, so a one-ended overhang is a redesign). CR-1 also edits the load-cell requirement's bound, which is written as 2000 N rather than read from the rated load (B-0279). Measured: the change rows add 83.5 s of test time to `make check` (31.5 + 52.1 s), the agent-request test 26 s. `core/` touched (R13): none.

## S-270 — v0.8 wave 4 boundary: the core count and R12's four timings (2026-11-06)
Wave 4 is M3b with B-0278 (S-267), M4 (S-268) and M4.0 (S-269; design in `docs/handoffs/v0.8-m40-design.md`), with a test fix that M4 made due: the pm skill's verb test read concept verbs from `cli/concept.py` alone, and `concept switch` lives elsewhere (fad565b). R13 count, de-duplicated (`git diff --name-only v0.7.0..HEAD -- src/napkin2factory/core`): v0.8 so far 17 distinct `core/` files, unchanged; wave 4 touched one, `core/concept_render.py` (B-0278), already counted in wave 3; M3b, M4 and M4.0 none. R12 on the macOS host, idle, warm, fresh `n2f` processes, one run each, tier 1 (`examples/table`) / tier 2 (`examples/test-stand`): no-change build 1.5 / 1.7 s (target 2 s); `undo` of a one-parameter edit 9.6 / 2.6 s (tier 1 pays a checks build for its sign-off, B-0269); one-parameter `ecr impact` 11.2 / 9.1 s first, 2.1 / 3.0 s again; `concept switch` to a never-promoted card (seeded, `--override` for a red card) 10.1 / 4.8 s, back to the parked one (restored) 9.2 / 4.0 s. `make check` at fad565b (the land gate of S-269, on the tree `main` now holds): 8 min 45 s of tests, 2,014 passed, 5 skipped, green. Not checked: CI on `main` (nothing pushed since S-244). Opened B-0279.
## S-271 — Review gate K (v0.8) — outcome (2026-11-06)
Engineering and honesty, fresh context, at b1a88fb (`docs/reviews/v0.8-gate-k.md`). NOT READY. Held:
history only moves forward, redo after undo is the identity, no checkpoint lost across undo, redo,
rollback, abort and switch; the approval binding and the red-check refusals; `refs/n2f/` stays out of
`publish`; schema 2 refuses rather than guesses. Blockers, fixed before the close: B1 an `ecr start`
after a rollback reuses an id a release already names; B2 `ecr impact` heads its numbers "computed"
and prints an unrepriced cost as "no change"; B3 compare and the board put a built card's total mass in
the napkin "mass of the shapes" row. Concerns C1 (approval hash copied into the YAML), C6 (`ecr show`
after a later edit), C9, C10 go to the fix tasks; C7 (R12 on an idle host) to the close-out measures;
the rest are rows B-0280 to B-0284.

## S-272 — Gate B's scripted flow on the test stand (2026-11-06)
`tests/e2e/test_gate_b.py` (`full`) runs gate B's script (plan §6) through in-process `n2f()` on a prebuilt tracked copy of `examples/test-stand` put back to "C-002 not promoted" by `prepare_gate_b_start` (C-002 back to `exploring` without its `decision:` line, DEC-001 removed from `model/decisions.yaml`, saved as the checkpoint "Gate B start"; the cold agents reuse it). Steps: promote, build, check (3 sub-assemblies); fork-from-model (card labelled computed); switch to red C-001 with `--override`, back to C-002, the direction files byte-identical; design change request with direct edits, stale approval refused, re-approved, closed; hand edit, `undo`, `redo`, `checkpoints`.
Measured: `test_gate_b_flow` 217 s on the macOS host (one run, machine busy); the xfail test 15 s. Found: B-0285 (`n2f check` shows no failure after the switch to C-001; one xfail test), B-0286 (promotion and switch seed requirements the model already holds). Walls a cold agent meets: `ecr start` needs `--title`, `approve` needs `--by`; after a stale approval `ecr approve` first needs `ecr impact` (the `close` refusal says so); `ecr close` also lists every requirement waiting for a person's sign-off (the script signs them in rounds, a dozen or more).
## S-273 — Gate K fixes: one change-request id forever, approval bound to the approved checkpoint (2026-11-06)
Gate K (S-271) blocker 1 and concerns 1 and 6. `next_ecr_id` is one past the highest `ECR-nnn` in
`changes/`, the `refs/n2f/ecr/*` markers and every checkpoint label: a rollback removes a request's
file but not its history, so an id was reused and "ECR-001" meant two requests. `ecr close` also needs
the model to equal the one in the newest "Approved <id>" checkpoint (the hash in the request file can
be pasted by anyone; the history cannot), compared by name and content with the same files left out as
the hash (`APPROVAL_HASH_EXCLUDE`). `ecr show` says "approved, but the model changed since" and names
checkpoints as `#<n> "<label>"`. Core files: none (existing `Vcs.list_refs`, `snapshots`, `diff_working`).
Not fixed, found: `DEC-` ids (`next_decision_id`, from `model/decisions`) and card ids (`next_concept_id`,
from `concepts/*.yaml`) read only the folder, so a rollback past them can reuse an id the same way.
Tests: `tests/e2e/test_ecr_live.py` (id after rollback; forged hash refused).
## S-274 — Gate K fixes: labelled impact figures, a built card's mass (2026-11-06)
Blockers 2 and 3 of S-271. `ecr impact --json`: `mass`, `cost` and each `envelope` entry carry `basis`; mass and envelope are `computed`, cost is `estimate` when any priced row of the parts list is one, else the rows' common basis (`bom.rollups.cost_basis_of`). The text drops the blanket "computed" heading and labels each line; parts rebuilt with an unchanged declared unit cost are named ("Shape changed, price not re-quoted"; `cost.shape_changed_not_requoted`), so an estimated cost never reads as a bare "no change". A forked card writes the built total under `total_mass` (computed, "from the built design"), leaves `mass` ("mass of the shapes") empty, and puts the cost under `estimates` when its basis is estimate; compare shows a parked card's built mass in the total-mass row. The fork note now says what the card holds (envelope kept or empty). Not measured: the cost of shape changes stays unestimated, as in v0.7.

## S-275 — The test stand's load-cell requirement follows the rated load (B-0279) (2026-11-06)
REQ-002's verify read a literal 2000 N, so raising `rated-load` to 2500 N (SPEC §6, CR-1) left it
passing. `param_bound` compares a parameter against a literal value, not another parameter, so the
requirement now uses the `calc` kind on a new example calc, `calc://capacity.load_cell_margin`
(`model/calcs/capacity.py`, capacity ÷ rated load, case 2000/2000 = 1), verified `>= 1`. No change
under `src/`. The oracle's CR-1 row drops its hand edit of the requirement's bound and still refuses
with the same "load cell" row. B-0279 closed.
## S-276 — Health review 2026-11-06 (v0.8 close) (2026-11-06)
Trend row `45119c8` (window 32 commits since `5898aae`; report `docs/reviews/health-2026-11-06-v08-close.md`). Worse: unstamped commits 0 -> 3
(docs-only handoff commits on `main`), E10 seam commits 6 -> 11 (all named in S-259, S-261 to S-263, S-267), skips 34 -> 35 (the strict xfail
of B-0285), coverage 0.9413 -> 0.9391, open rows 131 -> 138. Better: long modules 13 -> 12 (`core/concepts.py` 740 -> 364, S-259), TODO lines
5 -> 0 (M2c), upward imports into `cli/` 4 -> 1 (S-262). v0.8 touched 17 distinct `core/` files since v0.7.0.
Actions: B-0264 closed (S-264, S-265), B-0274's baseline corrected to 1; opened B-0287 (the unstamped measure). No source changes.
Not done: B-0266 (cold-agent gate B) stays open, S-272 ran the scripted flow only.

## S-277 — Gate B fixes: seeding skips a requirement already held, the switch names the card's failures (2026-11-06)
Closes B-0285, B-0286 and B-0280. (1) Promotion (and the switch's seeding, R10) does not append a planned requirement when the model already holds one with the same verify target, operator and value, the values compared as quantities (`0.2 m` equals `200 mm`); a manual requirement has no target and is never matched. The result and the text say "REQ-006 already asks this: …" in a note, as for "already declared" parameters. Why: each copy of a safety requirement needed its own sign-off before `ecr close`. (2) The switch's red-card refusal and its result list the card's failing screening checks as `n2f concept show` prints them, and say the model's parts are still the earlier direction's, so a check judges those until the design changes; a never-promoted card brings only its sketch by design (R10), so the failure is shown from the card's screening, not from a new model. (3) The unnamed-folder stop looks at the saved and the unsaved files together, before anything is saved.
Measured (gate B script): 14 sign-offs before `ecr close` both before and after, because the copies left are the manual sag requirement (no verify target to match) and the weight one (a geometry mass limit, not the model's bom rollup target); the cost, width and depth copies are gone (3 of 5 rows held per seeding). Matching those two by meaning is not done: not decided.

## S-278 — The oracle judges a gate B product: every checkpoint, built and parked cards (2026-11-06)
Gate B (S-277) ran the forward-and-backward script on the test stand with two cold agents; the oracle failed both identically, for reasons of its own.
(1) An aborted request is found among `n2f checkpoints --all`, not the last 20: the abort sat 30 checkpoints back.
(2) A card with a `built` block of event `forked` (written by `concept fork-from-model`) holds the built design, not a napkin idea: the concept rows and the card count leave it out (the count row names it), and its refusal to build is no problem. A `parked` card is an idea set aside, judged like a rejected one by the checks its screening fails.
(3) The test stand's REQ-002 statement names the rated test force again (2000 N), so `n2f status` no longer reports it unmeasurable.
Measured on copies of both gate B products: 47 passed 3 failed 7 pending before (gemini), 48 passed 2 failed 7 pending after, both products. The two left fail on the assembled mass (16.98 and 16.91 kg against 16.52 or 15.92): the agents' own design change moved it, expected on the final folder.
## S-279 — Gate B (v0.8) — outcome (2026-11-06)
Track B §4's script, run by two cold agents in folders outside the repository on the test stand put back
to "no direction chosen" (S-272's start, no build, no oracle file), from six owner-worded requests:
Gemini 3.8 Flash (Google) 27 min, 213 tool calls, 687k tokens; DeepSeek V4 Pro 28 min, 75 tool calls,
0.33 USD (`docs/reviews/v0.8-gate-b-trial-{gemini,deepseek}.md`). Both did all six: promoted and built
the portal (first report 5 min in, after 58 and 20 tool calls), forked the built design, switched to the
C-frame and back with nothing lost, aborted the 2500 N change on the load-cell failure, closed the platen
change after a refused stale approval (both lengthened the columns 5 mm to keep the 250 mm daylight),
undid and redid a hand edit. Oracle (S-278) at the state before each agent's own design change: 50 passed,
0 failed, 7 pending, both, CR-1 judged on the agent's own aborted request. Gate B passes. Found: B-0289,
B-0290. Both read `close`'s sign-off list (14) as a surprise; the guide's line on it is gate L's fix task.
## S-280 — Review gate L (v0.8) — outcome (2026-11-06)
UX in the owner persona (Dana, a materials-testing lab owner, no git), fresh context, at e3df06a, on the
gate B start folder (`docs/reviews/v0.8-gate-l.md`, three screenshots). NOT READY. Held: promote, switch,
undo, redo, rollback and abort each say what happened and how to take it back; refusals clean (no trace,
no git word); board and report work from `file://`. Blockers: B1 REQ-002's statement lost its number
(fixed in S-278 before this entry); B2 the report's tile counts rule rows as requirements and leaves gate
rows blank; B3 a closed change leaves the old size in the part's manufacturer text; B4 `n2f status` never
names an open change request; B5 `ecr close` lists sign-offs as one paragraph of ids. Concerns C3, C4, C6,
C7, C10, C11, C12 go to the fix tasks; C1 is B-0288; C13 is B-0269; the rest are rows B-0291 to B-0295.

## S-281 — Gate L fixes: impact names stale words, close lists what stands in the way (2026-11-06)
Gate L's blockers 3 and 5, concerns 6 and 7. A closed change left "100 x 100 x 15 mm" in a part's
`material.spec` and `manufacturer_notes` while the drawing showed 125. `ecr impact` now lists, per
changed parameter, the free-text fields of the parts and assemblies reading it whose words hold the old
value with its unit or inside an "a x b" size (`ecr/stale_text.py`; `--json`: `stale_text`); `close`
prints the same list once, as a warning. `close`'s refusal is one line per failing check and per
requirement waiting for a person (title, why), the count never signed before, and the sign command. The
impact's two sign-off lists both come from the check's own state (signed or pass before, waiting now),
and a failing change shows its figures and offers `n2f ecr abort` instead of "approve and close".


## S-282 — Gate L fixes in status, report and switch (2026-11-06)
Gate L (owner UX, `docs/reviews/v0.8-gate-l.md`): `n2f status` ignored an open change request and
spoke of "unsaved changes since the last snapshot"; the report's front tile counted rule rows
("183 / 25 requirements"); a forked card said "holds up in screening" though nothing was screened.
Now: status names the open request (title, state) and its next step (`n2f ecr impact`, or the failing
requirement with `n2f ecr abort`), unsaved edits say "save as a checkpoint or undo", the tile counts
requirements only and a gate not reached reads "not reached yet", a forked card reads "the built
design: no requirement fails" plus the sign-offs waiting, `concept build` suggests `--from`, and
the no-history error says what `n2f init .` does. Core file: `core/checks/stage.py`.

## S-283 — v0.8 close: the §2.1 measures and R12's timings (2026-11-06)
`docs/reviews/v0.8-measures.md`, at 6bd45b4 on the macOS host, quiet but not idle (load 2 to 4), three runs each, medians, tier 1 / tier 2. R12: no-change build 2.2 / 2.6 s, **target of 2 s not met** (start-up floor `n2f --help` 1.7 s; re-run at load 3.6: median 1.93 s, floor 1.1 s, so at the target, not clearly under it); `undo` 3.2 (first run 11.3) / 3.9 s; `ecr impact` first 12.7 / 20.4 s, again 2.9 / 4.0 s; `concept switch` 11.5 / 7.2 s, back 11.0 / 6.1 s. Against S-270's single runs, tier 1's first `undo`, first `impact` and `switch` hold (within 20 %); the no-change build, the second `impact` and all tier 2 figures but the no-change build and `undo` are 30 to 120 % slower, cause not isolated (load or the gate K and L fixes).
Warm one-parameter rebuild: 19.4 / 22.3 / 61.6 s for tiers 1 / 2 / 3 (v0.7: 14.4 / 19.4 / 50.8 s; tier 1 target under 1 s not met); nothing changed 2.8 / 3.1 / 5.0 s (v0.7: 8.2 / 8.7 / 11.2 s).
Guide plus product `AGENTS.md`: 36,227 characters, about 9,057 tokens (chars / 4), against 9,059 at v0.7 and 9,065 at S-268.
Gate B trials (copied, a terminal agent harness only, a product with a model so not v0.7's rows): first report 5 min 03 s / 58 calls (Gemini 3.8 Flash), 5 min 18 s / 20 calls (DeepSeek V4 Pro); oracle 50 passed, 0 failed, 7 pending for both. Skill suggestion rate as S-255 (20/20 and 0/20), not re-measured. `core/` touched: none.
## S-284 — Close v0.8: version 0.8.0, pins >=0.8,<0.9, the handoff (2026-11-06)
`pyproject.toml`, `packaging/n2f/pyproject.toml` (and its `napkin2factory==` pin), `src/napkin2factory/__init__.py`
and `uv.lock` say 0.8.0; every product pin the package writes or ships (the manifest default in
`core/model/manifest.py`, the templates and their workflows, the five examples, the test fixtures,
`docs/product-model.md`) says `>=0.8,<0.9` (S-083, as S-242). Kept at `>=0.7,<0.8`: the schema-1 fixture
`tests/fixtures/schema/v1`, which stands for a v0.7 product the upgrade opens (R15). The manifest default
is the one `core/` file this bump edits: v0.8 touched 19 distinct `core/` files since v0.7.0. The handoff is
`docs/reviews/v0.8-handoff.md` (DoD 2 and 6 partly met). Tagging and pushing stay the maintainer's calls (S-072).
## S-285 — v0.8 visual exit: the board's built-design card, judged by the maintainer (2026-11-06)
The test stand's board after gate B (DeepSeek's trial product rebuilt at 60bc71d: C-001 parked, C-002
promoted, C-003 rejected, C-004 "Twin-column portal, as built" with "the built design: no requirement
fails", total mass 15.8 kg computed, cost 1,017 USD estimate) and the portal's assembly render after the
platen change were sent to the maintainer. Judged by the maintainer: "Yes, keep it". The card's
"rejected" label after a later switch stays open as B-0289. This closes M6's visual exit (S-284).

## S-286 — v0.8.0 released (2026-11-06)
The maintainer asked to push, watch CI, then tag. `main` was pushed at fe84fcf; CI `ci` failed on Linux and macOS
on one test, `tests/e2e/test_ecr_live.py::test_bridges`: CI forces colour, so the usage error split `--patch` with
escape codes (2,031 passed). The test now strips colour codes before matching (95e6fb0, checked locally with
`GITHUB_ACTIONS=true FORCE_COLOR=1`). CI `ci` passed on both platforms at 95e6fb0; `v0.8.0` was tagged on it and
`publish.yml` published both packages (build, pypi, pypi-alias green; `napkin2factory` and `n2f` 0.8.0 on PyPI).
Visual exit: judged by the maintainer (S-285).

## S-287 — Open v0.9, Track C: the design first (2026-11-07)
`docs/stages/v0.9-progressive-workbench.md` schedules Track C (M0 to M6, V1–V13) and finishes Track B: the R9 bridges go (`ecr new`,
`ecr apply`, and `ecr reject`, which S-261 joined to them; no product file names them, so no schema bump), and the v0.8 handoff's open
DoD rows are M5a to M5d. Checked against the code first (road §5.4, plan §9): sections are registered (F5) and already hide at `lite`
(W6); the viewer already picks (on pointer-down, so every orbit picks), explodes along one ranked axis and cuts on Z at mid-height; no
insertion axis exists; the schemes are `iface://` and the domain families' (no `ifc://`, `elec://` or `product://`); no STL is exported;
only the first top GLB is embedded. So V4 keys the inspector by existing URIs and V5 adds a lens and inspector seam (M2s). Six questions
are with the maintainer (plan §3, Q1–Q6). Rows B-0296 to B-0304. Baseline: `core/` files touched in v0.9: 0. `make check` on `main` at
ae87589: green, 2,032 passed, 9 min 57 s (load 3.1 rising to 18 from other agents; not idle). The stage records §11's sizes and timings.

## S-288 — v0.9 wave 1: the lens seam, viewer picking, the bridges gone, the upgrade's applied requests (2026-11-07)
M2s (V5): `ReportSection.lens` (one of `LENSES`: workbench, drawings, build, verification, history; default verification, so a section a domain
leaves undeclared still renders) and `Domain.inspector` (entries keyed by the domain's own URIs); the registry refuses an unknown lens at register,
and `inspector_entries` refuses a non-URI key or a key two domains return. The mechanical sections and the electrical Wiring declare lenses
(Wiring in drawings). M1 (V3): a click of under 5 px picks, a drag orbits and never picks; `frame`, `ghost`, `screenPoint`, `section(axis, offset)`
on x, y or z (`section(true)` still works for the page's checkbox), a double-click isolates, an empty click clears; the explode is unchanged
(Q2 recommended one-axis, B-0304). The interaction test skips when the host loses WebGL, which software GL does under heavy load (the viewer then
hides its canvas, S-232); the first version failed the land gate for that reason, not for a picking fault. M5a (V10): `ecr new`, `ecr apply`, `ecr
reject` and their MCP tools are gone (unknown-command error, exit 2); `core/vcs.py`'s message says `ecr start`; the eight `impact-analyst.md` role
files named `ecr reject` (plan V10 said no role did) and now name `ecr abort`. M5d: an `applied` request set aside by the upgrade closes (its
`applied:` kept); a set-aside approved one says its approval was cleared; `status: applied` and `impact` in a format-2 file give one plain message
(`core/model/ecr.py`, not `migrate.py`); `ecr abort` of an upgraded applied request restores the changed model files from its baseline (never the
format, the requests or the sign-offs). Asked the maintainer: Q5 was asked on a stale premise. The kiln ships ECR-001 to ECR-003 aborted and its demos
already use `ecr start` (`test_demos.py` parametric and design pass on main), so B-0276 and B-0277 are closed as already true and the kiln is unchanged.

## S-289 — v0.9 wave 1 boundary: the `core/` count, §11's sizes and timings, `make check` (2026-11-07)
`core/` files touched in v0.9 so far: 4 (`core/domain.py`, `core/registry.py` for M2s; `core/model/ecr.py` for M5d, where the plan named
`core/model/migrate.py`; `core/vcs.py` for M5a). Measured at b34a259, macOS host, copies of the examples built cold then three no-change builds,
load 3.0 to 3.3 (my own earlier busy loops had left the host loaded; killed and the load let fall before measuring): report size 1.95 MB table,
3.00 MB test stand, 3.93 MB kiln (limit 20 MB). No-change build, median of three: 1.52 s table (tier 1; R12's target 2 s met), 1.93 s test stand,
2.58 s kiln; the report rule is up to date on a no-change build and prints no time (the table's cold report rule was 1.7 s; the others' not read).
Page open to first frame in Chromium on `file://` with software GL, median of three: 0.35 s, 0.54 s, 0.70 s. `make check` on main at b34a259:
green, 2,043 passed, 6 skipped, 9 min 12 s wall (8 min 28 s in pytest), load 8.5 at its end. The wave added no interaction test to `make check` beyond
`tests/smoke/test_viewer_interaction.py` (about 5 s alone). Wave 1 closed B-0275, B-0276, B-0277, B-0283, B-0296 and B-0301.
