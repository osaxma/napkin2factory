# Agent layer

napkin2factory does not run agents. It installs roles into every product folder so that
whatever AI client opens the folder (Claude Code, Codex, Antigravity, or a person) becomes
the project team, and it enforces the rules with deterministic tools (`n2f validate`,
`n2f lint`, `n2f check`, the release gates). Decision D6: checks are the gate; roles are
conventions.

## What `n2f init` installs

| file | role |
|---|---|
| `CLAUDE.md` = `AGENTS.md` | what the folder is, the vocabulary, the rules every agent follows, where things are, the kit list |
| `.claude/skills/n2f-pm/SKILL.md` | project manager: the only role that talks to the owner; intake protocol, question triage by consequence, register adaptation from `operator.yaml`, safety floor, turning asks into change requests, explaining reports |
| `.claude/skills/n2f-design/SKILL.md` | designer: compose the kit, inner loop with renders, interfaces, decisions, calcs, "done means" |
| `.claude/agents/n2f-verifier.md` | adversarial reviewer with a fresh context; reads `build/` and calcs, writes `reports/review-*.md`, never edits `model/` |
| `.claude/agents/n2f-impact-analyst.md` | translates an impact report into the owner's words, cost and safety first |
| `.github/workflows/build.yml`, `release.yml` | CI for share mode later: build + check on push; tag → ZIP and Pages (written and validated, not run in v0.1) |

The source of these files is `src/napkin2factory/templates/_common/`; `make templates`
copies them into every example and `tests/unit/test_templates.py` asserts they are identical.

## Intake, in practice

1. The owner opens the folder in their AI client and says what they want.
2. The PM role asks one question at a time (what/why, who, envelope, targets, environment
   and safety, budget and quantity, manufacturing, what exists), then writes
   `operator.yaml`, `parameters.yaml`, `requirements.yaml`, `decisions.yaml`, `intake.md`,
   runs `n2f validate && n2f lint` and fixes every finding.
3. The designer role composes kit parts, builds `--target geometry`, looks at the renders,
   and iterates until the silhouette matches the envelope.
4. `n2f check` is the gate; the verifier reviews calcs before a release; safety
   requirements wait for a human `n2f signoff`.

`tests/e2e/intake-transcripts/` holds the scripted intake simulation used as the DoD check:
a fresh-context subagent given only the product `CLAUDE.md`, the PM skill text and a
role-played owner transcript produced a model that passed validate and lint and built a
first silhouette.

## Why roles are text, not code

Any client can read Markdown; none can be forced to spawn fresh contexts or respect
permissions. So the separations that matter are structural: the verifier's instructions
confine it to `reports/`, but the real guarantee is that `n2f check` and the release gates
run the same way whoever (or whatever) drove the edits.
