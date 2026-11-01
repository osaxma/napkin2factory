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
