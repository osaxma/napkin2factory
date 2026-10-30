# CLI

Run `uv run n2f …` from inside the system checkout, or `n2f …` from anywhere after
`uv tool install .`. `n2f <command> --help` is the authority; this page is a map of it.

Every command that works on a product takes `--dir/-C <folder>` (default: the current
folder or the nearest product folder above it) and `--json` for machine-readable output
(`graph` uses `--format json`, `serve` has no JSON mode).

| command | does |
|---|---|
| `n2f init [dir] [--template blank\|bracket\|enclosure] [--name TEXT]` | new product folder with change tracking and a first snapshot; `n2f init .` in an existing product folder only sets up tracking (and adds missing agent files). `--no-tracking` is for tests |
| `n2f validate` | the model loads and every reference resolves |
| `n2f lint` | requirement quality and model hygiene, stricter than validate (the Intake gate) |
| `n2f build [--target geometry\|drawings\|bom\|docs\|checks\|report\|site\|all] [--part ID] [--clean] [--jobs N] [--no-render] [--explain] [--offline]` | rebuild exactly what changed. `--explain` is a dry run (what would rebuild, and why); `--offline` skips the vendor-link check of the BOM, same as `N2F_OFFLINE=1`. The first build on a machine loads the CAD kernel, which can take a couple of minutes; a note on stderr says so |
| `n2f check [--format table\|json\|md] [--all]` | the check matrix; `--all` shows passing rule-pack rows too; exit 2 on `fail` |
| `n2f status` | stage (intake → design → verify → released), gates, what blocks the next gate and the command that unblocks it |
| `n2f graph [--format dot\|json] [--around URI]` | the build graph (for engineers) |
| `n2f impact (--ecr ECR-001 \| --set uri=value …)` | what a change would touch, before anything changes |
| `n2f ecr new --title TEXT [--kind parametric\|design] [--reason TEXT] [--set uri=value …] [--task TEXT …] [--patch FILE] [--by NAME]` | file a change request (draft) |
| `n2f ecr impact ECR-xxx` | assess what it would touch; nothing changes |
| `n2f ecr approve ECR-xxx --by NAME [--note TEXT]` | approve after reading the impact report |
| `n2f ecr apply ECR-xxx` | apply it to the model and save a snapshot |
| `n2f ecr close ECR-xxx` | close an applied change request: checks must be green; revisions bump; changelog grows |
| `n2f ecr reject ECR-xxx --reason TEXT` · `n2f ecr list` · `n2f ecr show ECR-xxx` | the rest of the change loop |
| `n2f signoff REQ-xxx --by NAME --statement TEXT [--evidence URI …] [--example]` | a human sign-off bound to evidence; stays valid until the evidence changes; refreshes the checks and saves a snapshot. `--example` marks it as a shipped example, never a real review |
| `n2f snapshot [-m MESSAGE]` | save the current state of the model (the owner-level "save") |
| `n2f discard [--yes]` | throw away every change since the last snapshot (cannot be undone) |
| `n2f release vX.Y.Z [--dry-run] [--no-render] [--allow-example-signoffs]` | freeze a Revision: manufacturer ZIP and frozen site version; checks must be green and every safety requirement signed. Refuses EXAMPLE sign-offs unless the demonstration flag is given |
| `n2f diff A B [--out DIR] [--render]` | change page between two Revisions (`B` may be `working` for the current model): drawing overlays, BOM delta with cost impact, 3D side by side |
| `n2f serve [--port N] [--site]` | serve the report on localhost (it also opens from disk); `--site` serves `build/site` (versions and diffs) |
| `n2f doctor` | can this machine run napkin2factory, and what to fix if not |
| `n2f version` | the installed version |

Exit codes: 0 ok, 1 validation/lint/build failure, 2 check failure, 3 gate blocked
(release or close refused; the message says what to do), 4 environment problem (including
change-tracking refusals, worded for the operator).

Environment: `N2F_OFFLINE=1` skips the vendor-link check during builds (`make check` sets
it); `N2F_TIMING=1` turns on the timing assertions in the test-suite.
