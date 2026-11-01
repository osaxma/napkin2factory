# Agent layer

How napkin2factory equips the agent that **uses** it on a product: the files `n2f init` writes
and why roles are text. This page explains the design to people developing napkin2factory and
to anyone curious. An agent that has been asked to use the tool starts at
[agent-guide.md](agent-guide.md) instead.

napkin2factory does not run agents. It installs roles into every product folder so that
whatever AI client opens the folder (Claude Code, Codex, Antigravity, or a person) becomes
the project team, and it enforces the rules with deterministic tools (`n2f validate`,
`n2f lint`, `n2f check`, the release gates). Decision D6: checks are the gate; roles are
conventions.

## What `n2f init` installs

| file | role |
|---|---|
| `AGENTS.md` | what the folder is, the vocabulary, the rules every agent follows, where things are, the kit list |
| `roles/pm.md` | project manager: the only role that talks to the owner; the napkin stage (diverge into 3–5 concept cards, screen them, talk limitations from the screening data, interpretation cards for dropped sketches and photos, promotion in the owner's words), intake protocol, question triage by consequence, choices (raised after a build, never in the interview, recorded with `n2f decide`), scope (in / done elsewhere / later), verify methods chosen by consequence, register adaptation from `operator.yaml`, safety floor, turning asks into change requests, explaining reports |
| `roles/design.md` | designer: start from the promoted concept's massing and `style.yaml` (roles, the kit's aesthetic parameters, form requirements; `concepts/` is never edited after promotion), compose the kit, inner loop with renders, interfaces, choices and scope, decisions, calcs with a reference case each, verify methods by consequence, "done means" |
| `roles/verifier.md` | adversarial reviewer with a fresh context (a separate agent, or a new session); reads `build/` and calcs (and their reference cases), classes choices like failures, checks scope and methods, writes `reports/review-*.md`, never edits `model/` |
| `roles/impact-analyst.md` | translates an impact report into the owner's words, cost and safety first |
| `.github/workflows/build.yml`, `release.yml` | CI for share mode: build + check on push; a `v*` tag → build, check, a dry-run release that re-packages that Revision, and its ZIP attached to a GitHub release. The web pages are not deployed from a tag (a tag holds one Revision, the pages hold all of them): `n2f publish --online` sends them to the `gh-pages` line |

The roles are plain Markdown in a client-neutral folder, so any agent can follow them; the
product's `AGENTS.md` says which file to read for which role (S-077). The source of these files
is `src/napkin2factory/templates/_common/`; `make templates`
copies them into every example and `tests/unit/test_templates.py` asserts they are identical.

## The napkin stage, in practice (optional)

Before intake, when the owner arrives with an idea rather than a spec (NAPKIN_STAGE N11):

1. The PM role asks only the two or three facts that split directions, then writes 3–5
   concept cards (`n2f concept new`), builds and screens them (`n2f concept build --all`)
   and shows the board (`n2f concept board`). Limitations are read from each card's
   screening, labelled computed or estimate; a red card is explained, never hidden.
2. A dropped sketch or photo gets an **interpretation card** first — proportions, layout,
   style cues and `[verify]` dimensions, in words — and the owner corrects it in words
   before any card is written (N9). The file lands in `concepts/refs/`.
3. The owner picks a direction; the PM asks "Lock this in as the design direction?" and runs
   `n2f concept promote`, which seeds parameters, requirements (site and form), `style.yaml`
   and a decision. Intake then continues, skipping what the cards answered.

The mechanics are in [napkin.md](napkin.md); the protocol is the "Napkin stage (before intake)" section of
`roles/pm.md`.

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
a fresh-context subagent given only the product's agent instructions, the PM skill text and a
role-played owner transcript produced a model that passed validate and lint and built a
first silhouette (`monitor-bracket.md`, v0.1). `napkin-bench-kiln.md` (v0.2) does the same for
the napkin stage: a textual sketch of a bench kiln, an interpretation card, one correction
in words, three lint-clean cards, `n2f concept build --all` with a red card explained;
`tests/e2e/test_napkin_protocol.py` checks the skill text and the transcript's script.

## Why roles are text, not code

Any client can read Markdown; none can be forced to spawn fresh contexts or respect
permissions. So the separations that matter are structural: the verifier's instructions
confine it to `reports/`, but the real guarantee is that `n2f check` and the release gates
run the same way whoever (or whatever) drove the edits.
