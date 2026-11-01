# Vocabulary

napkin2factory hides version control behind its own verbs (decision D22). Every
user-facing string, schema field and report label uses the left column; the right column
is for engineers who want to know what happens underneath. This file is the one place the
mapping is written down; `tests/unit/test_vocabulary.py` greps the CLI, schemas and
templates for the right-hand words.

| napkin2factory says | underneath (git) | where you meet it |
|---|---|---|
| **draft** | a branch / uncommitted work | `n2f status` ("draft · snapshot …") |
| **snapshot** | a commit | `n2f init`, `n2f ecr apply`, `n2f ecr close`, `n2f concept promote`, `n2f release` make them |
| **change request (ECR)** | a pull request | `changes/ECR-xxx.yaml`, `n2f ecr …` |
| **impact report** | the PR description, computed | `n2f ecr impact`, `n2f impact --set` |
| **approved** | review approval | `n2f ecr approve` |
| **applied** | merged into the draft | `n2f ecr apply` |
| **closed** | merged and verified | `n2f ecr close` |
| **released / Revision vX.Y.Z** | a tag | `n2f release`, `build/site/vX.Y.Z/` |
| **unsaved changes** | dirty working tree | release refusal wording |
| **change tracking** | the repository | `n2f init` sets it up |
| **scratch copy of a Revision** | a worktree | `n2f diff` builds older Revisions in one |
| **online copy** (send to it) | the GitHub remote (push), plus its `gh-pages` branch that GitHub Pages serves | `n2f publish --online` |

## Napkin words (the concept stage, NAPKIN_STAGE.md)

These have no version-control counterpart; they are listed so every role uses the same
words with the owner.

| say | meaning | where you meet it |
|---|---|---|
| **concept** (card, `C-001`) | one rough, disposable direction for the product | `concepts/C-xxx.yaml`, `n2f concept new` |
| **direction** | what a concept proposes; the promoted one is "the design direction" | the board, `n2f concept promote` |
| **screening** | the quick feasibility pass on a concept (rough shapes, estimates, rules) — not verification | `n2f concept build` |
| **computed** / **estimate** | measured from the rough shapes / from rough calculations; every screening number carries one | the board, `n2f concept show` |
| **green** / **red** | holds up / "this direction has problems:" — red is information, never hidden | the board, `n2f concept build` |
| **board** | every direction side by side, read-only | `build/concepts/board.html`, `n2f concept board` |
| **promote** | lock a concept in as the design direction (parameters, requirements, style, a decision) | `n2f concept promote` |
| **set aside** / rejected | a direction not taken; the card is kept as a record | `n2f concept reject` |
| **interpretation card** | the PM's playback, in words, of what it read in a sketch or photo, corrected by the owner before any card is written | the project manager role, `roles/pm.md` (N9) |

## Structure words (the build plan, PRODUCT_STRUCTURE.md P7–P9)

No version-control counterpart either; the owner reads the left column in the report, the
manuals and the assembly sheets, the field names stay in the files and in `--json` (N5).

| say | meaning | field, where you meet it |
|---|---|---|
| **unit** ("the door, built as one unit") | a sub-assembly put together on its own, then fitted as a whole; one step of the build plan and one assembly sheet | `build: unit` (the default) in `assemblies/<id>.yaml`; the report's Build plan, `build/drawings/assemblies/` |
| **the final assembly** | the top assembly, always the last step | the report's Build plan |
| **a grouping, not built separately** (a phantom) | lines grouped for the model's sake; its parts are fitted in the step of the unit that contains it | `build: phantom` |
| **why it is built on its own** (driver) | built as one unit, tested as one unit, serviced or replaced as one unit, made by another process or supplier, comes in variants, worked on as one module | `driver: [built-as-unit, tested-as-unit, serviced-as-unit, separate-process-or-supplier, varies, agent-context]`; `n2f lint` asks for one (`L13-assembly-driver`) |
| **module** ("door (built as one unit)" on the concept board) | a unit a concept sketches, with its reason; promotion makes it an empty sub-assembly with three size limits (P10) | `modules:` on a concept card, `module:` on a massing line; the `general-v0/module-has-parts` row while it is empty |
| **the size the concept gave it** (a size budget) | the most a module may measure along each axis, computed from its rough shapes; changing one is a decision | a `geometry_prop` requirement on `asm://<module>#props.bbox.x`, `.y`, `.z` |
| **a joint between units** (a port) | where two units built separately meet; closed in the step that joins them | `ports:` (P4); the report's Build plan |
| **joint hardware** | the bolts, nuts, standoffs a joint takes, counted from the joint | `spec.hardware` on an interface; the `hardware://<unit>` check row |
| **spare** | more hardware than the joints need, on purpose, with the reason | `spare: "<reason>"` on a child line |
| **packed loose for the installer** | shipped with the product, fitted on site, not in the build step | `loose: true` on a child line |
| **a size of the door** (a scoped parameter) | a size that belongs to one unit; the unit and what it sits in may read it | `scope: asm://door` in `parameters.yaml` (P5) |
| **shared** (an exported size) | a unit's size its parent may read, e.g. the door's outside width the hinge post must reach | `export: true` |
| **read from outside its module** | a part or size reading another unit's size it may not; "worth a look" | the `reach://` check rows |
| **the checks of one unit** | a unit checked alone: its parts, its inside joints, its requirements | `n2f check --scope asm://<id>`; the report's "By module" table |

## Check statuses

| engineer words | owner words | meaning |
|---|---|---|
| pass | OK | the computed check holds |
| fail | needs attention | the computed check does not hold; blocks closing and releasing |
| warn | worth a look | advisory; never blocks anything (D10) |
| skip | not checked | the artifact it needs was not built |
| needs-human | needs your sign-off | a human must review and `n2f signoff` |
| signed | signed off | a valid sign-off exists for a safety requirement (D25) |
| example (summary counter, not a row status) | example sign-offs — not reviews | the sign-off is flagged `example: true`; the row stays `signed` and labelled, but it is counted apart, the Verify gate stays open, and `n2f release` refuses it without `--allow-example-signoffs` |

## Stages (computed by `n2f status`, never stored — D10)

Intake → Design → Verify → Released. A stage is complete when its gate passes; nothing
can mark a stage complete by hand. While `concepts/` holds concept cards an optional
**Napkin** stage comes first; it is complete once a card is promoted.

The stage a product **is in** is the first one not complete: a product whose intake is
done is "in Design". When only the release is left it is **ready to release**. `n2f status`,
the report badge and `n2f ecr close` all say it this way; `--json` carries it as
`current_stage`, next to the older `stage` (the last stage passed).

## Persona

`operator.yaml` `persona: owner | engineer` picks the words in the CLI and the report (the
status table above). There is no toggle: the report has one layout for everyone, and its
safety content is identical for both personas.
