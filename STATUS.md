# STATUS — napkin2factory

**Version:** 0.4.0, ready to tag; not tagged (last release 0.3.0, tag `v0.3.0`) · **Trunk:** `main`;
work happens in task worktrees (`make task`, `make land`; S-097) · **Open work:** `BACKLOG.md` ·
**Why things are the way they are:** `DECISIONS.md` (index at the top) · **What shipped:**
`HANDOFF-REPORT-v0.4.md` (v0.4), `HANDOFF-REPORT-v0.2.md` (v0.2), `HANDOFF-REPORT.md` (v0.1)

## Where we are
v0.4 (the tree, `PRODUCT_STRUCTURE.md`) is closed: M0–M7 done, gates C and D closed with their
blockers fixed, version files and product pins at 0.4.0 / `>=0.4,<0.5` (S-119). Left to the
maintainer: the visual judgment of the build-plan section and one assembly sheet (DoD 7),
`make check-full` from a clean clone, push and the `v0.4.0` tag. Known open: the Linux nightly
fails on a sign-off evidence key (owned by a separate task). Next: v0.5 (`FOUNDATION.md`).
Releasing a version: bump the three version files and the pins (S-054, S-083), `make check` on
`main`, push, wait for CI, tag `v<version>` on that green commit (S-072).

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
- `make check` ≈ 7 min (tests in parallel, S-070; long files split, S-080, S-084);
  `make check-full` ≈ 21 min (2026-11-01: `check` 7 min 27 s, then kiln, demos side by side
  and timing 13 min 27 s; was ≈ 28 min, S-079); the first `import build123d` on a machine takes
  one to two minutes (S-057).
- Never run `n2f build` inside `examples/`; copy a product to a temp folder first
  (`tests.conftest.copy_product`). Templates are synced with `make templates`, never hand-edited.

## Milestones (one line each; detail in the entries named)
v0.6 — `ELECTRICAL_STAGE.md` (the electrical domain through the v0.5 contract; the count of core edits is
the headline), S-111: planned, starts after v0.5. `docs/reviews/v0.6-independent-trial.md` is the
outside model's brief for after it lands.

v0.5 — `FOUNDATION.md` (the seams: domain contract and registries, toy domain, the kiln out of the
package, schema policy, scope as data, choices), S-111; reconciled with v0.4 in S-120: planned;
its prerequisite B-0073 (platform-stable sign-off evidence keys) is fixed in S-121: the push run of
`make check` on 4c8d66c is green on ubuntu and macOS; no nightly has run on a commit after S-121
yet (the latest, 10:28 on 2026-11-01, predates it), and `main` is not pushed during v0.5.
Wave times on the host (measured): M0 14 min; M1 65 min; wave 2 (M2, M3, M4 at once, then the
M2b and M4b follow-ups) 21:06–22:25, 79 min. `make check` on `main`: 9 min 7 s at 29e7d4b
(after M1, 908 passed), 9 min 14 s at 895df01 (after wave 2, 998 passed).
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

v0.4 — `PRODUCT_STRUCTURE.md` (sub-assemblies, ports, parts placed by interfaces), S-103; closed,
`HANDOFF-REPORT-v0.4.md`:
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

v0.2 — `NAPKIN_STAGE.md`:
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

v0.1 — `GRAND_PLAN.md`, closed 2026-10-31: M0–M9 and gates 1–4 — S-001–S-054 and the four gate
entries; `HANDOFF-REPORT.md`. The former milestone paragraphs are kept verbatim in
`docs/history/STATUS-through-v0.2.md`.
