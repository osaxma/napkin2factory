# Seam task: a change request's patch in its impact report; a domain's disclaimer in the package (v0.5 defects; commit subjects plain imperative, NOT `M<n>:`)

Opened by the third overseer (2026-11-03) under E10: gate H found a v0.5 contract defect in the
core, which the domain cannot fix from outside. Listed apart from the domain's count. Read
`docs/reviews/v0.6-gate-h.md` (B1, C7) and `docs/reviews/v0.6-gate-g.md` (Blocker 3, the README
line), `docs/domains.md`, and the decisions on change requests with a patch (D7) and the release
files (S-142). Hand with `brief-common.md` (its count rule does not forbid you the core: you are
the seam task; everything else in it applies). Task folder: `.worktrees/seam-impact` on
`task/seam-impact`.

## What is wrong (measured at f67dc06)
1. **The impact report of a change request with a patch says it changes nothing.** For the
   kiln's ECR-003 (adds the wiring by a patch) the owner is asked to approve a page reading
   "# Impact of 0 change(s)" / "nothing is rebuilt: no artifact reads what you are changing",
   though applying it turns the wiring from later to in, adds 5 parts, changes 4 and moves the
   cost. `core/graph/impact.py:714` counts only `report.edits`.
2. **The package README says "not reviewed by a licensed engineer"** (`ecr/release.py:189`) even
   when the package holds wiring, where the honest sentence is a licensed electrician's.
3. (gate H C7) The later Revision's cover says only "Wiring: done here"; it does not say the wiring
   is now included where the earlier Revision left it out (`ecr/release.py:185`, the scope lines).
4. (B-0160) `n2f status` says of a choice that holds no gate "it holds nothing; an agent may decide
   it and say so" even to an owner who asked to be asked about that area
   (`core/checks/choices.py:60`).

## Build (generic: no domain or example names in core, F9)
1. Impact with a patch: compute the impact of the patch too (dry-run it on a temporary copy, or
   read the files it touches): the heading counts the patch's changes, the page lists the files
   and model entities it adds/changes/removes, a scope change in owner words ("Wiring: left for
   later → done here"), and the artifacts that rebuild. A patch that does not apply says so plainly.
   Keep `to_dict`'s stored form backward-compatible or follow `docs/schema-policy.md`.
2. A domain may declare a disclaimer sentence through the contract (e.g. a `disclaimer` field on
   its registration, documented in `docs/domains.md`); the package README and the report's
   disclaimer carry each in-scope domain's sentence after the general one. The electrical domain
   sets its sentence ("Its wiring has not been reviewed by a licensed electrician: a licensed
   electrician wires the product to local code.") — the one line you may add in
   `domains/electrical/__init__.py`.
3. The cover/scope line of a Revision whose step was "later" in the previous Revision and is "in"
   now says so ("Wiring: included in this Revision; left for later in v1.0.0"), from the release
   records, in owner words.
4. B-0160: "an agent may decide it" only when the owner delegated that area (`operator.yaml`'s
   delegation/domains, as the PM role reads them); otherwise "it holds nothing" alone.
5. Tests for each; DECISIONS.md one entry (placeholder id) naming the seams and their gates;
   BACKLOG.md: a placeholder row for the impact seam closed by it, close B-0160; `docs/domains.md`
   for the new field; `docs/agent-guide.md` only if a command's output the agent reads changes.

## Owns
`src/napkin2factory/core/graph/impact.py`, `src/napkin2factory/core/checks/choices.py`,
`src/napkin2factory/core/domain.py` (the field), `src/napkin2factory/ecr/` (release README, cover
lines), `report/` only for the disclaimer line, the one line in `domains/electrical/__init__.py`,
their tests, goldens that move because of these (log them), `docs/domains.md`, `DECISIONS.md`,
`BACKLOG.md`.
## Must not touch
`domains/electrical/` other than that one line (two other tasks are there), `examples/`,
`STATUS.md`, `docs/v06-handoff/`, the untracked `FIX_CI_NIGHTLY.md`.
## DoD
Run `make lint`, `make types`, the touched tests, `uv run pytest tests/golden -q`,
`tests/e2e/test_ecr*.py` and the kiln's demo test if feasible (`tests/e2e/test_demos.py -k electrical`,
long); then `make land` (or `LAND_GATE=check make land`, since this is core). Report: landed
commit, decision id, the kiln ECR-003 impact page's first lines as printed now, the README's
disclaimer lines, files changed, test numbers, gate time.
