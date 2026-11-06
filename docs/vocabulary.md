# Vocabulary

napkin2factory hides version control behind its own verbs (decision D22). Every
user-facing string, schema field and report label uses the left column; the right column
is for engineers who want to know what happens underneath. This file is the one place the
mapping is written down; `tests/unit/test_vocabulary.py` greps the CLI, schemas and
templates for the right-hand words.

| napkin2factory says | underneath (git) | where you meet it |
|---|---|---|
| **draft** | a branch / uncommitted work | `n2f status` ("draft · snapshot …") |
| **snapshot** | a commit (the older word; a snapshot is a checkpoint) | `n2f init`, `n2f ecr new`, `n2f ecr approve`, `n2f ecr apply`, `n2f ecr close`, `n2f concept promote`, `n2f release` make them |
| **checkpoint** (`#12`) | a commit, listed with its label and the product's mass and cost at that point | `n2f checkpoints`; every command that changes the design makes one; `n2f undo`, `redo` and `rollback` move between them and never lose one |
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

## Napkin words (the concept stage, docs/stages/v0.2-napkin-stage.md)

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
| **other ideas considered** / not chosen | directions not chosen at promotion; kept as a record in the decision | the promotion decision (`DEC-xxx`) |
| **interpretation card** | the PM's playback, in words, of what it read in a sketch or photo, corrected by the owner before any card is written | the project manager role, `roles/pm.md` (N9) |

## Structure words (the build plan, docs/stages/v0.4-product-structure.md P7–P9)

No version-control counterpart either; the owner reads the left column in the report, the
manuals and the assembly sheets, the field names stay in the files and in `--json` (N5).

| say | meaning | field, where you meet it |
|---|---|---|
| **unit** ("the door, built as one unit") | a sub-assembly put together on its own, then fitted as a whole; one step of the build plan and one assembly sheet | `build: unit` (the default) in `assemblies/<id>.yaml`; the report's Build plan, `build/drawings/assemblies/` |
| **the final assembly** | the top assembly, always the last step | the report's Build plan |
| **not put together on its own** (a phantom, "the lining (items 18–26) … lay it in place during this step") | lines grouped for the model's sake; its parts are laid in place in the step of the unit that contains it, and marked with its name in the note column | `build: phantom` |
| **why it is built on its own** (driver) | put together and fitted as one piece, tested as one unit, serviced or replaced as one unit, made by another process or supplier, comes in variants, worked on as one module | `driver: [built-as-unit, tested-as-unit, serviced-as-unit, separate-process-or-supplier, varies, agent-context]`; `n2f lint` asks for one (`L13-assembly-driver`) |
| **module** ("door (put together and fitted as one piece)" on the concept board) | a unit a concept sketches, with its reason; promotion makes it an empty sub-assembly with three size limits (P10) | `modules:` on a concept card, `module:` on a massing line; the `general-v0/module-has-parts` row while it is empty |
| **the size the concept gave it** (a size budget) | the most a module may measure along each axis, computed from its rough shapes; changing one is a decision | a `geometry_prop` requirement on `asm://<module>#props.bbox.x`, `.y`, `.z` |
| **a joint between units** (a port) | where two units built separately meet; closed in the step that joins them | `ports:` (P4); the report's Build plan |
| **joint hardware** | the bolts, nuts, standoffs a joint takes, counted from the joint; "no loose fixings" when it takes none (welded, riveted, clamped) | `spec.hardware` on an interface; the `hardware://<unit>` check row |
| **the joint's name** ("Shell to guard, top wall") | what the owner reads for a joint wherever two joints join the same two parts; otherwise "<part> to <part>" | `name:` on an interface |
| **closed later, in step N** | a joint whose parts meet in one step and that is closed in a later one (a lid after the wiring) | `closed_in: asm://<unit>` on an interface |
| **line up** ("the 4 holes line up on both parts, and in the assembled kiln") | both parts cut the joint's holes alike, and placed, their frames meet within 0.5 mm and 0.5° | the interface's check row; frames, offsets and ids in `--json` |
| **spare** | more hardware than the joints need, on purpose, with the reason | `spare: "<reason>"` on a child line |
| **packed loose for the installer** | shipped with the product, fitted on site, not in the build step | `loose: true` on a child line |
| **a size of the door** (a scoped parameter) | a size that belongs to one unit; the unit and what it sits in may read it | `scope: asm://door` in `parameters.yaml` (P5) |
| **shared** (an exported size) | a unit's size its parent may read, e.g. the door's outside width the hinge post must reach | `export: true` |
| **read from outside its module** | a part or size reading another unit's size it may not; "worth a look" | the `reach://` check rows |
| **the checks of one unit** | a unit checked alone: its parts, its inside joints, its requirements | `n2f check --scope asm://<id>`; the report's "By module" table |

## Scope and choices (FOUNDATION F11–F14, v0.5)

The owner's flexibility and the trade-offs the system hands them. No version-control
counterpart; the owner reads the left column in `n2f status`, the report and the release
package, the fields stay in the files and in `--json`.

| say | meaning | field, where you meet it |
|---|---|---|
| **domain** ("the electrical side", "the wiring") | one step of making a product, such as mechanical or electrical; with the owner, name the step itself rather than the word "domain" | `scope:` keys in `n2f.yaml`; `n2f doctor` lists the installed ones |
| **scope** ("what this product covers") | which steps this product does here, which are done elsewhere, which come later; changing it is a decision | `scope: {<domain>: {state, decision, note}}` in `n2f.yaml`; a row under its gate in `n2f status`, a line in the report overview and on the package cover |
| **done here** | the step is designed and checked here, in this product ("Wiring: done here") | `state: in` (the default for a step with content) |
| **done elsewhere** (supplied, not built here) | another person or company does it; a stand-in unit with its joints shows where it fits, and everything that names it says "supplied, not built here" (the build plan, the joints, the gates) | `state: external`; a sub-assembly with `build: external` and `ports:` |
| **left for later** (not designed here yet) | this product does not design it yet; its requirements read "left for later", counted apart, except safety ones, which still need their sign-off; each gate and the package cover say so ("Electrical: left for later (DEC-024) — not checked at this stage"; "Not included in this package: …") | `state: later`; tag the step's requirements (`tags: [electrical]`) |
| **a choice** | a trade-off a check found once the facts existed, with two or more valid designs, each with what it takes and what it costs; never a failure by itself | a `choice` row in `n2f check`; `build/checks/choices.json` |
| **waiting on you** | the open choices, listed after the gates, each with the gate it holds ("it holds the release") | `n2f status`; `waiting_on_you` in `--json` |
| **decided** ("decided in DEC-0xx: shorter bolts at both ends (chosen by <name>)") | the owner picked an option; the row reads OK with the decision until what it was decided on changes, then the choice opens again | `n2f decide <check> --pick <option> --by "<name>"`, a `DEC-` entry |
| **how it is checked** (a verify method) | the way a requirement is checked, chosen once and logged; the stronger one is offered when a mistake would cost much or the owner knows the area well | `verify.kind` on a requirement; `n2f doctor` lists the installed kinds |

## Wiring words (the electrical domain, v0.6, docs/stages/v0.6-electrical-stage.md)

No version-control counterpart. The owner reads the left column in `n2f status`, the report's
Wiring section, the manuals and the check messages; the fields and URIs stay in the files and
in `--json` (`docs/electrical.md` has every field).

| say | meaning | field, where you meet it |
|---|---|---|
| **wiring** ("Wiring: done here") | the product's electrical side at wiring level: what it plugs into, its electrical devices, what connects to what and the cables; never circuit boards. The owner's word for the `electrical` domain | `scope.electrical` in `n2f.yaml`; `model/electrical/`; the Wiring rows of `n2f status`, the report's Wiring section |
| **supply** ("the supply", "what it plugs into") | the one socket or circuit the product plugs into: its voltage, its rating and the breaker that protects it, as the owner or the electrician gives them | `model/electrical/supply.yaml` (`supply://supply`; no owner word before its id, it would read "supply supply") |
| **circuit** ("the Heater circuit") | one path the current takes: a list of connections between terminals, with what protects it; said by its `name` | `model/electrical/circuits/<id>.yaml`, `circuit://<id>`; one diagram each, `build/electrical/<id>/diagram.svg` |
| **electrical device** | a wired thing (a heater, a switch, a controller, a sensor), the part it is plus its rating and terminals | `model/electrical/devices/<id>.yaml`, `device://<id>` |
| **terminal** ("Switch terminal 1") | a named connection point on a device, as its maker marks it | `terminals:` on a device; the `#<terminal>` of a connection end |
| **cable entry** | the hole where wires cross a box, with the gland or bushing in it, and the circuits that pass it | an interface `kind: cable-entry` (`spec: {diameter, passes}`); a box supplied, not built here has its cable entries as `ports:` |
| **earth** ("a path to earth") | the protective connection that keeps a metal part safe to touch if a live wire touches it: an earth conductor to the supply's earth, or a joint a person tests | `PE` terminals; a circuit's `earth:` entries (`bonded_via`); the `earth-path` and `earth-bonded` check rows |
| **interlock** | a switch (on a door, a lid) that must stop the load while it is open | `safety: interlock` on a device; the `interlock-series` check row |
| **for an electrician to confirm** | a wiring check's finding that a wiring code judges, not arithmetic: worth a look, and a licensed electrician decides | a `warn` row of kind `electrical`; the Verify row "Wiring checks" |
| **room to spare on the supply's circuit** | the choice the wiring raises once built, when the load uses more than half the circuit: keep the circuit for the product alone, or a larger circuit | the `supply-headroom` choice; `dedicated: true` on the supply, or its rating |

## Sheet and report labels (gate D)

| say | not | where |
|---|---|---|
| **parts for this step**, **part no.** | BOM lines, BOM line | assembly sheets |
| **pulled apart** | explode axis | assembly sheets, the report |
| **not yet saved** | unsnapshotted | title blocks' date |

## Check statuses

| engineer words | owner words | meaning |
|---|---|---|
| pass | OK | the computed check holds |
| fail | needs attention | the computed check does not hold; blocks closing and releasing |
| warn | worth a look | advisory; never blocks anything (D10) |
| skip | not checked | the artifact it needs was not built |
| needs-human | needs your sign-off | a human must review and `n2f signoff` |
| signed | signed off | a valid sign-off exists for a safety requirement (D25) |
| choice | a choice waiting on you | a trade-off with two or more valid designs; never blocks by itself, holds the gate its `blocks` names until `n2f decide` records the pick, then reads OK with the decision |
| later | left for later | a requirement of a step the scope leaves for later (F11); never blocks, counted apart; what its check found is kept in `detail.later`; a safety requirement never reads this |
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

## Ceremony words (W6, S-205)

No version-control counterpart. The owner reads these in `n2f check`; the tags stay in the
files and in `--json`.

| say | meaning | field, where you meet it |
|---|---|---|
| **lite** / **standard** (the ceremony) | how much paperwork the product carries: an everyday product is lite; one with mains power, heat, moving or stored energy, or work in more than one field is standard. n2f works it out from the model; the owner can only raise it | `n2f check` ("Ceremony: standard — it runs on mains…"); `ceremony: standard` in `n2f.yaml` |
| **a hazard it names** | the kind of harm a safety requirement guards against; a sign-off is needed either way, some kinds also make the product standard | `tags: [hazard:<kind>]` on a requirement; `core/data/hazards.yaml` |
| **(default)** after a tolerance class | the class came from the part's process, not from the part's file; only on a lite product | the parts list, the drawing's title block |
