# v0.9 wave 8: the trial's open rows, run by a coordinator, overseers and workers

Written 2026-11-09 by the v0.9 coordinator, for a run with no supervision until a review on
2026-11-12. The maintainer decided: the wave 7 persona trial's open rows (S-339, S-340) get fixed
before the third trial run and M6; this run does the fixes, not the trial.

## Roles (three layers, each reads only its own files)
| Role | Who | Reads | Does |
|---|---|---|---|
| Coordinator | one long session the maintainer starts | `coordinator.md`, the state file | runs the tasks in order, one at a time, through `bin/run-overseer.sh`; keeps the state file; never edits code |
| Overseer | one fresh session per task, started by the script | `overseer.md` + one `tasks/T<n>/card.md` | makes the task folder, runs the worker, verifies, sends at most two fix rounds, lands |
| Worker | a `workerctl` run per task | `AGENTS.md` + `tasks/T<n>/worker.md` | edits code and tests in the task folder, commits, reports JSON |

## The tasks, in order (one at a time; never two at once)
| Task | Row | What | Lands in the repository |
|---|---|---|---|
| T1 | B-0325 | `n2f_sync` gives a failed validate's problems whole | yes |
| T2 | B-0326 | `concept switch` refuses a missing `model/parameters.yaml` plainly | yes |
| T3 | B-0323 | the napkin overlap screen tests a frame kit's members | yes |
| T4 | B-0324 | promotion never seeds a requirement the card's own screening fails | yes |
| T5 | B-0327 | a quick change's impact shows the structure figures first | yes |
| T6 | B-0328 | a check finds parts that are not held up | yes |
| T7 | (S-339 §6) | the trial sandbox blocks package installs | no: files in `/Users/wakeel/n2f-trial/rerun` |
| T8 | B-0329 | a design note for re-seeding on a concept switch (no code) | yes (one doc) |
| T9 | close | handoff, wave entry, `make check` on main | yes |

## Files
- `coordinator.md`: the coordinator's loop.
- `overseer.md`: the overseer's procedure (same for every task).
- `tasks/T<n>/card.md`: the task's facts for the overseer (slug, goal, allowed files, tests, review points).
- `tasks/T<n>/worker.md`: the worker's brief, passed to `workerctl` as is.
- `bin/run-overseer.sh T<n>`: starts one overseer and logs it.
- `bin/verify.sh T<n>`: the mechanical gate (files in scope, lint, tests, no WIP).
- `state-template.md`: copied to `/Users/wakeel/n2f-wave8/state.md` at the start; the coordinator keeps that copy (outside the repository, so the main folder stays clean). The single source of truth.

Run logs live in `/Users/wakeel/n2f-wave8/logs/`.

## Why it is written this way
The models expected for this run follow short, explicit, numbered steps best, and drift on
open-ended ones. So every judgment that could be made in advance is made here (each card states
the decided design). Every step names a command and its expected result. Every layer keeps its
state in a file and re-reads it. And the hard rules are repeated at the end of each file.
