# This folder is a napkin2factory product

It is the complete, text-only description of one physical product. Everything else
(3D models, drawings, flat patterns, bill of materials, manuals, the report page) is
**generated** from the files in `model/` by `n2f build`. Never edit anything under
`build/`; edit the model and rebuild.

## Vocabulary (use these words with the owner; never git words)
- **draft** — work in progress on the model
- **snapshot** — a saved state of the model (`n2f ecr apply` and `n2f release` make them)
- **change request (ECR)** — a proposed change, filed in `changes/ECR-xxx.yaml`
- **approved** — the owner said yes to a change request after reading its impact report
- **released / Revision** — a frozen, named version (`v1.2.0`) sent to a manufacturer

## Rules for any agent working here
1. Run `n2f validate` after every model edit. Run `n2f build --part <id>` after every
   geometry edit and **look at the renders** in `build/parts/<id>/renders/`. Run
   `n2f check` before claiming anything is done.
2. Never write numbers you invented. Cite the source in the calc file or the decision,
   and tag numbers that need human confirmation with `[verify]`.
3. Log every choice made on the owner's behalf as a `DEC-xxx` in `model/decisions.yaml`
   with rationale and links. Decisions are delegated, never deleted.
4. Changes to a released product go through a change request: `n2f ecr new`, then
   `n2f impact`, then the owner approves, then `n2f ecr apply`.
5. Safety floor: anything safety-relevant (mains power, hot surfaces, sharp edges,
   pinch points, lifting) is stated to the owner in plain words regardless of how
   expert they are. Safety requirements can never be ticked off by a calculation
   alone; they need a human sign-off (`n2f signoff`).
6. Only the verifier role writes under `reports/`; the verifier never edits `model/`.
7. All generated output carries the disclaimer: this design was produced with an AI
   system and has not been reviewed by a licensed engineer.

## Where things are
- `n2f.yaml` manifest · `operator.yaml` who the owner is and how to talk to them
- `model/requirements.yaml`, `model/parameters.yaml`, `model/decisions.yaml`
- `model/parts/*.yaml`, `model/assemblies/*.yaml`, `model/interfaces/*.yaml`
- `model/geometry/*.py` custom geometry (`build(P, I, kit)`), `model/calcs/*.py` calculations
- `model/docs/*.md` manuals (templated Markdown), `model/signoffs/*.yaml`
- `changes/` change requests · `reports/` verifier reviews · `build/` generated (ignored)

## Skills and roles
- `.claude/skills/n2f-pm` — the project-manager role: intake, explaining, filing change requests
- `.claude/skills/n2f-design` — the designer role: compose the kit, look at renders, log decisions
- `.claude/agents/n2f-verifier` — adversarial review; reads `build/`, writes `reports/`
- `.claude/agents/n2f-impact-analyst` — explains an impact report in the owner's words
