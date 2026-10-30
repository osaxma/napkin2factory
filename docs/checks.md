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

Safety ladder (S-026): computed `fail` → fail; `safety: true` → `needs-human` until a valid
sign-off → `signed`; non-safety `manual` → `needs-human` → `pass` with a sign-off; a
sign-off is valid while every evidence key it recorded is unchanged (D25).

## Rule packs (`rulepacks/*.yaml`)

`sheet-metal-v0`: bend radius ≥ 1 t, hole ⌀ ≥ 1 t, hole-to-bend ≥ 2 t + r, flange ≥ 4 t,
reliefs where bends meet, flat pattern present (warn). `general-v0`: custom parts complete
(process, material, finish, tolerance class), every part in an assembly (warn), COTS parts
have a source, COTS links verified (warn). Thresholds are nominal shop rules of thumb
`[verify]`. A product may add `model/rulepacks/*.yaml` using the same named checks.

## Other rows

`iface://x` conformance, `interference://asm`, `count://asm` (instance counts equal YAML
quantities), `doc://x` staleness (recorded reads vs current values), `bom://validation@part`
(sourcing tiers: structural → link → curated catalog; unverified stays visible).

## Stage and gates (`n2f status`)

Intake: requirements and operator pass lint. Design: every custom part has geometry and is
built. Verify: no `fail`, no `needs-human`. Released: a Revision tag exists for a clean
tree. `warn` never changes the stage.
