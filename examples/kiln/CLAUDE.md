# This folder is a napkin2factory product

It is the complete, text-only description of one physical product. Everything else
(3D models, drawings, flat patterns, bill of materials, manuals, the report page) is
**generated** from the files in `model/` by `n2f build`. Never edit anything under
`build/`; edit the model and rebuild.

## Vocabulary (use these words with the owner; never git words)
- **draft** — work in progress on the model
- **snapshot** — a saved state of the model (`n2f ecr apply`, `n2f ecr close` and `n2f release` make them)
- **change request (ECR)** — a proposed change, filed in `changes/ECR-xxx.yaml`
- **impact report** — what a change request would touch, computed before anything changes
- **approved** — the owner said yes to a change request after reading its impact report
- **released / Revision** — a frozen, named version (`v1.2.0`) sent to a manufacturer

## Rules for any agent working here
1. Run `n2f validate` after every model edit. Run `n2f build --target geometry --part <id>`
   after every geometry edit and **look at the renders** in `build/parts/<id>/renders/`.
   Run `n2f check` before claiming anything is done. `n2f status` tells you what blocks the
   next gate.
2. Never write numbers you invented. Cite the source in the calc file or the decision,
   and mark numbers that need human confirmation with `verify: true` on the decision.
3. Log every choice made on the owner's behalf as a `DEC-xxx` in `model/decisions.yaml`
   with rationale and links. Decisions are delegated, never deleted.
4. Changes to a released product go through a change request: `n2f ecr new`, then
   `n2f ecr impact`, then the owner approves, then `n2f ecr apply`, `n2f build`,
   `n2f check`, `n2f ecr close`.
5. Safety floor: anything safety-relevant (mains power, hot surfaces, sharp edges,
   pinch points, lifting, stored energy) is stated to the owner in plain words regardless
   of how expert they are. Safety requirements can never be ticked off by a calculation
   alone; they need a human sign-off (`n2f signoff`). Example sign-offs carry
   `example: true` and are labelled as examples everywhere.
6. Only the verifier role writes under `reports/`; the verifier never edits `model/`.
7. All generated output carries the disclaimer: this design was produced with an AI
   system and has not been reviewed by a licensed engineer.
8. Every requirement is atomic and testable: a measurable statement with a unit, a
   `verify` method, a category and an allocation. `n2f lint` enforces this.

## Where things are
- `n2f.yaml` manifest · `operator.yaml` who the owner is and how to talk to them
- `model/requirements.yaml`, `model/parameters.yaml`, `model/decisions.yaml`, `model/intake.md`
- `model/parts/*.yaml`, `model/assemblies/*.yaml`, `model/interfaces/*.yaml`
- `model/geometry/*.py` custom geometry (`build(P, I, kit)` / `build(P, I, parts)`), `model/calcs/*.py`
- `model/docs/*.md` manuals (templated Markdown; `safety.md` is mandatory), `model/signoffs/*.yaml`
- `changes/` change requests · `reports/` verifier reviews · `build/` generated (ignored)

## Skills and roles
- `.claude/skills/n2f-pm` — the project-manager role: intake, explaining, filing change requests
- `.claude/skills/n2f-design` — the designer role: compose the kit, look at renders, log decisions
- `.claude/agents/n2f-verifier` — adversarial review; reads `build/`, writes `reports/`
- `.claude/agents/n2f-impact-analyst` — explains an impact report in the owner's words

## Kit generators (geometry: {kit: <name>, args: {...}})
plate, panel, block, tube, hole_pattern, bracket_l, enclosure, frame. Lengths accept
`"15 mm"` or `param://…`. See the system repo's `docs/kit.md` for every argument.
