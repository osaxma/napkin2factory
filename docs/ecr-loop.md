# The change loop (ECR)

```
n2f ecr new --title "Taller box" --set param://box-height=100mm      # draft
n2f ecr impact ECR-001         # what it touches, before anything changes
n2f ecr approve ECR-001 --by "Owner"
n2f ecr apply ECR-001          # edits the model in place, snapshot
n2f build && n2f check
n2f signoff REQ-004 --by "…" --statement "…"   # if a safety sign-off was invalidated
n2f ecr close ECR-001          # checks must be green; revisions bump; CHANGELOG grows
n2f release v1.1.0             # tag, ZIP, frozen site version
n2f diff v1.0.0 v1.1.0         # overlays, BOM delta, side-by-side 3D
```

## Kinds (D7)

**parametric** — `edits: [{set: <uri[#path]>, to: <value>}]`, applied mechanically.
Parameter edits change one line; selector edits (`req://REQ-001#verify.value`,
`part://x#cost.unit`) round-trip the YAML keeping comments.

**design** — `tasks: [...]` for the designer agent and optionally `patch:
changes/ECR-00x.patch`, a unified diff over `model/` produced by making the change,
capturing the diff and reverting. `apply` applies the patch and prints the tasks; the
impact report marks geometry-dependent verdicts as estimates until rebuilt.

## Impact report

Rules that would rerun (from recorded reads), parts touched with implied revision bumps,
drawings, manual pages, interfaces to re-verify, requirements with hypothetical verdicts
(`param_bound` and declared-cost `bom_rollup` are evaluated now; geometry-dependent ones
are estimates), sign-offs that would be invalidated, cost delta from declared costs.
Stored in the ECR (`impact:`) and as `build/changes/ECR-xxx-impact.md`.

## Close

Requires zero `fail`. Bumps the rev of every part whose geometry output or YAML changed,
then every assembly containing a bumped child, rebuilds the checks so title blocks and the
report carry the new revs, appends to `CHANGELOG.md`, snapshots.

## Release

Refuses unless: the folder is its own tracked project root, there are no unsaved changes,
checks have no `fail`, every safety requirement is `signed`, the Revision name is new.
Writes `released_in` on closed change requests, the changelog release header, snapshots,
tags, builds `build/release/<product>-vX.Y.Z.zip` (STEP, drawings SVG + PDF bundle, DXF flat
patterns, BOM, manuals, report, checks, changelog) and freezes `build/site/vX.Y.Z/`
(report, ZIP, `data/` for diffs). `--dry-run` builds everything without tagging or editing.

## Diff

`n2f diff A B` reuses frozen data when a ref is a released Revision, otherwise builds the
ref in a scratch copy. `B` may be `working`. The page is self-contained like the report.
