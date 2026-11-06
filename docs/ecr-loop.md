# The change loop (ECR)

A change to a product after its design is settled is a live change request. The model
files are edited in place; the request records a baseline when it starts, and compares
the live model with that baseline until it is closed. There is no patch and no apply step.

```
n2f ecr start --title "Taller box" --set param://box-height=100mm   # records the baseline
# edit the model/ files directly, then:
n2f build && n2f check
n2f ecr impact ECR-001              # the live model against the baseline: what it touches
n2f signoff REQ-004 --by "…" --statement "…"   # if a safety sign-off was invalidated
n2f ecr approve ECR-001 --by "Owner"           # binds to the model as it is now
n2f ecr close ECR-001               # refuses if the model changed since approval, or build/check is red
n2f release v1.1.0                  # tag, ZIP, frozen site version
n2f diff v1.0.0 v1.1.0              # overlays, BOM delta, side-by-side 3D
```

Every change command saves a checkpoint before it changes anything, so a wrong edit is
undone with `n2f undo` (inside an open request it stops at the request's start); `n2f
checkpoints` lists them, and `n2f rollback` restores one.

## Verbs

- `n2f ecr start --title TEXT [--kind parametric|design] [--reason TEXT] [--set uri=value …]
  [--task TEXT …] [--by NAME]`: opens the request and records its baseline. `--set` applies
  its edits now.
- `n2f ecr quick --set uri=value … [--title TEXT] [--reason TEXT] [--by NAME]`: start, apply the
  edits and show the impact in one step, for a small parameter change.
- `n2f ecr impact [ECR-xxx]`: what the change touches; nothing changes.
- `n2f ecr approve [ECR-xxx] --by NAME [--note TEXT]`: approval after reading the impact. It
  stores the model as it is now; any later edit makes the approval stale.
- `n2f ecr close [ECR-xxx]`: refuses if the model changed since approval, or if build or check
  is not green. Otherwise it bumps revisions, grows the changelog and saves a snapshot.
- `n2f ecr abort [ECR-xxx] [--reason TEXT]`: drops the request and returns the model to where it
  started. Undoable.
- `n2f ecr list` and `n2f ecr show ECR-xxx`: the requests and one of them.
- Bridges for one version: `n2f ecr new` does what `start` does and says so. `n2f ecr apply`
  refuses and names the next steps (`approve`, then `close`). `n2f ecr reject` says to use
  `abort`.

## Kinds (D7)

**parametric** (the default): edits to parameters and selectors (`param://…`,
`req://REQ-001#verify.value`, `part://x#cost.unit`), applied mechanically. Parameter edits change
one line; selector edits round-trip the YAML keeping comments.

**design**: for asks that change shape or add features. `--task TEXT` gives the designer a
task; the designer edits the model files as any model edit, builds and checks. Nothing is
written as a patch file.

## Impact report

What the live model changes against the baseline: parts touched with the revisions they imply,
drawings, manual pages, interfaces to re-verify, requirements whose verdict could change (values
that depend on geometry are estimates until the model is built), sign-offs that would be
invalidated, and the cost delta from declared costs. `n2f ecr impact --json` gives the same data.

## Close

Requires zero `fail`. Bumps the revision of every part whose geometry output or YAML changed,
then every assembly containing a bumped child, rebuilds the checks so title blocks and the
report carry the new revisions, appends to `CHANGELOG.md`, and saves a snapshot.

## Release

Refuses unless: the folder is its own tracked project root, there are no unsaved changes,
checks have no `fail`, every safety requirement is `signed`, the Revision name is new.
Writes `released_in` on closed change requests, the changelog release header, snapshots,
tags, builds `build/release/<product>-vX.Y.Z.zip` (STEP, drawings SVG + PDF bundle, DXF flat
patterns, BOM, manuals, report, checks, changelog) and freezes `build/site/vX.Y.Z/`
(report, ZIP, `data/` for diffs). `--dry-run` builds everything without freezing a Revision or editing.

## Diff

`n2f diff A B` reuses frozen data when a ref is a released Revision, otherwise builds the
ref in a scratch copy. `B` may be `working`. The page is self-contained like the report.
