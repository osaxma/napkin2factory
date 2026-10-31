# Vocabulary

napkin2factory hides version control behind its own verbs (decision D22). Every
user-facing string, schema field and report label uses the left column; the right column
is for engineers who want to know what happens underneath. This file is the one place the
mapping is written down; `tests/unit/test_vocabulary.py` greps the CLI, schemas and
templates for the right-hand words.

| napkin2factory says | underneath (git) | where you meet it |
|---|---|---|
| **draft** | a branch / uncommitted work | `n2f status` ("draft · snapshot …") |
| **snapshot** | a commit | `n2f init`, `n2f ecr apply`, `n2f ecr close`, `n2f release` make them |
| **change request (ECR)** | a pull request | `changes/ECR-xxx.yaml`, `n2f ecr …` |
| **impact report** | the PR description, computed | `n2f ecr impact`, `n2f impact --set` |
| **approved** | review approval | `n2f ecr approve` |
| **applied** | merged into the draft | `n2f ecr apply` |
| **closed** | merged and verified | `n2f ecr close` |
| **released / Revision vX.Y.Z** | a tag | `n2f release`, `build/site/vX.Y.Z/` |
| **unsaved changes** | dirty working tree | release refusal wording |
| **change tracking** | the repository | `n2f init` sets it up |
| **scratch copy of a Revision** | a worktree | `n2f diff` builds older Revisions in one |

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
can mark a stage complete by hand.

## Persona

`operator.yaml` `persona: owner | engineer` picks the words in the CLI and the report (the
status table above). There is no toggle: the report has one layout for everyone, and its
safety content is identical for both personas.
