# Checks

`n2f check` builds what it needs, evaluates everything, writes `build/checks/checks.json`
and prints the matrix. Exit code 2 when any row is `fail`.

## Requirement evaluators (`core/checks/evaluators.py`)

| verify.kind | compares | evidence |
|---|---|---|
| `param_bound` | the parameter's value with `op value` | the parameter |
| `geometry_prop` | `part://x#props.bbox.x|y|z`, `volume`, `area`, `mass`, `centroid.*` from props.json | the part/assembly |
| `bom_rollup` | `bom://rollups#total_cost|total_mass|part_count|custom_ratio|max_lead_time` | the BOM |
| `calc` | the result of `model/calcs/<m>.py:<f>(P)` (pint) | source + inputs + result hash |
| `interference` | pairwise boolean common volume > 1 mm³ on an assembly | the assembly |
| `count` | occurrences of a part across top assemblies | the assemblies |
| `interface` | both parties' recorded patterns agree within 0.5 mm | both parties |
| `manual` | always needs a human | — |
| `rule` | the rule-pack rows of the same run for `rule://<pack>/<rule>`: any `fail` row fails it, a `warn` row makes it `warn` (never a failure), a `pass` row passes it; no applicable part → `skip` "no part this rule applies to yet" | the parts the rows cover |

Safety ladder (S-026): computed `fail` → fail; `safety: true` → `needs-human` until a valid
sign-off → `signed`; non-safety `manual` → `needs-human` → `pass` with a sign-off; a
sign-off is valid while every evidence key it recorded is unchanged (D25).

A sign-off flagged `example: true` (the example products ship with them; `n2f signoff
--example`) keeps its row `signed` and labelled "EXAMPLE SIGN-OFF, NOT A REVIEW", but it
verifies nothing: `summary.example` counts it instead of `summary.signed`, `n2f check` and
`n2f status` print "N example sign-offs (not reviews)", the report header shows "N example
sign-offs — not reviews" in amber, and the Verify gate stays open until a real person
replaces them. `n2f release` refuses them unless `--allow-example-signoffs` is given for a
demonstration, in which case the release goes ahead and the report keeps the labels.

## Rule packs (`rulepacks/*.yaml`)

`sheet-metal-v0`: bend radius ≥ 1 t, hole ⌀ ≥ 1 t, hole-to-bend ≥ 2 t + r, flange ≥ 4 t,
reliefs where bends meet, flat pattern present (warn). `general-v0`: custom parts complete
(process, material, finish, tolerance class), every part in an assembly (warn), COTS parts
have a source, COTS links verified (warn). Thresholds are nominal shop rules of thumb
`[verify]`. A product may add `model/rulepacks/*.yaml` using the same named checks. A check
may decide a rule does not concern a part (no row) or concern it without being able to
decide (a `skip` row saying why).

`form-v0` (v0.2, NAPKIN_STAGE N8) checks taste once it is chosen. Its thresholds live in the
product's `style.yaml`, not in the pack, and `n2f concept promote` writes the requirements
that point at it (`verify: {kind: rule, target: rule://form-v0/<rule>}`):

| rule | applies to | fails (or warns) when |
|---|---|---|
| `form-corner-radius` | custom parts with role body, door, stand, controls or trim | a bend radius (`features.json`) or the declared `corner_radius`/`fillet` (or the style default the build gave it) is below `style.corner_radius`; skipped while that is 0 |
| `form-fasteners-hidden-front` | parts with role body or door | `style.fastener_visibility` is `hidden-front` and a hole, placed in a top assembly, has its axis along Y and its centre in the front (−Y) half of the assembly's bounding box |
| `form-controls-placement` (warn) | the part with role controls | its centroid, placed in a top assembly, is not on the side `style.layout.controls` names (left/right, front/back, top/below of the assembly's centre) |

What the form checks cannot see: edges a generator rounds without recording them (custom
geometry modules, frame tubes) — such a part is skipped with a message, never passed;
whether something in front hides a hole; the screws themselves (only holes in the body and
the door). A part not placed in any built assembly is skipped for the two placement rules.
The checks re-run when `style.yaml`'s form cues or a part's `role` change (`style:form`,
`part://x#role` reads).

## Other rows

`iface://x` conformance, `interference://asm`, `count://asm` (instance counts equal YAML
quantities), `doc://x` staleness (recorded reads vs current values), `bom://validation@part`
(sourcing tiers: structural → link → curated catalog; unverified stays visible).

## Stage and gates (`n2f status`)

Intake: requirements and operator pass lint. Design: every custom part has geometry and is
built. Verify: no `fail`, no `needs-human`, no example sign-offs. Released: a Revision tag
exists for a clean tree. `warn` never changes the stage. Example sign-offs are caveats, not
blockers: the stage reads `verify` (in verification, not verified), `next` says to replace
them or release with `--allow-example-signoffs`, and a demonstration Revision made that way
still counts as released.
