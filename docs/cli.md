# CLI

Until the package is installed as a tool, run `uv run n2f …` from the system repo (or
`n2f …` after `uv tool install .`). Every command accepts `--json` and `--dir/-C <folder>`.

| command | does |
|---|---|
| `n2f init <dir> [--template blank\|bracket\|enclosure] [--name]` | new product folder with change tracking and a first snapshot |
| `n2f validate` | schemas and cross-references |
| `n2f lint` | requirement quality and model hygiene (Intake gate) |
| `n2f build [--target geometry\|drawings\|bom\|docs\|checks\|report\|site\|all] [--part ID] [--clean] [--jobs N] [--no-render] [--explain]` | rebuild exactly what changed |
| `n2f check [--format table\|json\|md] [--all]` | the check matrix; exit 2 on `fail` |
| `n2f status` | stage, gates, what blocks the next gate |
| `n2f graph [--format dot\|json] [--around URI]` | the build graph |
| `n2f impact (--ecr ECR-001 \| --set uri=value …)` | what a change would touch |
| `n2f ecr new\|impact\|approve\|apply\|close\|reject\|list\|show` | the change loop |
| `n2f signoff REQ-xxx --by NAME --statement TEXT [--evidence URI…] [--example]` | a human sign-off bound to evidence |
| `n2f release vX.Y.Z [--dry-run]` | Revision tag, manufacturer ZIP, frozen site version |
| `n2f diff A B [--out DIR]` | change page between two Revisions (or `working`) |
| `n2f serve [--port] [--site]` | serve the report locally (it also opens from disk) |
| `n2f doctor` | environment check |
| `n2f version` | version |

Exit codes: 0 ok, 1 validation/lint/build failure, 2 check failure, 3 gate blocked,
4 environment problem (including change-tracking refusals, worded for the operator).
