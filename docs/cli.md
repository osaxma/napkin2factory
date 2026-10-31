# CLI

The map of every command, for agents using napkin2factory and for anyone curious. The
walkthrough (install, first product, handing over to the product folder) is
[agent-guide.md](agent-guide.md).

`n2f …` after `uv tool install napkin2factory` (or `pip install napkin2factory`); inside a
source checkout, `uv run n2f …`. `n2f <command> --help` is the authority; this page is a map of it.

Every command that works on a product takes `--dir/-C <folder>` (default: the current
folder or the nearest product folder above it) and `--json` for machine-readable output
(`graph` uses `--format json`, `serve` has no JSON mode).

| command | does |
|---|---|
| `n2f init [dir] [--template blank\|bracket\|enclosure] [--name TEXT]` | new product folder with change tracking and a first snapshot; `n2f init .` in an existing product folder only sets up tracking (and adds missing agent files). `--no-tracking` is for tests |
| `n2f validate` | the model loads and every reference resolves |
| `n2f lint` | requirement quality and model hygiene, stricter than validate (the Intake gate) |
| `n2f build [--target geometry\|drawings\|bom\|docs\|checks\|report\|site\|all] [--part ID] [--clean] [--jobs N] [--no-render] [--explain] [--offline]` | rebuild exactly what changed. `--explain` is a dry run (what would rebuild, and why); `--offline` skips the vendor-link check of the BOM, same as `N2F_OFFLINE=1`. The first build on a machine loads the CAD kernel (one to two minutes; `n2f init` starts loading it in the background); a note on stderr says so if the build has to wait |
| `n2f check [--format table\|json\|md] [--all]` | the check matrix; `--all` shows passing rule-pack rows too; exit 2 on `fail` |
| `n2f status` | stage (intake → design → verify → released, with an optional napkin stage first while `concepts/` holds cards), gates, what blocks the next gate and the command that unblocks it |
| `n2f graph [--format dot\|json] [--around URI]` | the build graph (for engineers) |
| `n2f impact (--ecr ECR-001 \| --set uri=value …)` | what a change would touch, before anything changes |
| `n2f ecr new --title TEXT [--kind parametric\|design] [--reason TEXT] [--set uri=value …] [--task TEXT …] [--patch FILE] [--by NAME]` | file a change request (draft) |
| `n2f ecr impact ECR-xxx` | assess what it would touch; nothing changes |
| `n2f ecr approve ECR-xxx --by NAME [--note TEXT]` | approve after reading the impact report |
| `n2f ecr apply ECR-xxx` | apply it to the model and save a snapshot |
| `n2f ecr close ECR-xxx` | close an applied change request: checks must be green; revisions bump; changelog grows |
| `n2f ecr reject ECR-xxx --reason TEXT` · `n2f ecr list` · `n2f ecr show ECR-xxx` | the rest of the change loop |
| `n2f concept new TITLE [--from C-xxx]` | start a concept card (`concepts/C-xxx.yaml`, status exploring) with every section commented; `--from` copies an earlier card's content and records `based_on` |
| `n2f concept list` · `n2f concept show C-xxx` | the cards (id, status, title, based on, verdict green/red/—) · one card and its screening: `computed` and `estimate` numbers labelled, each rule's outcome, notes |
| `n2f concept build C-xxx \| --all [--no-render] [--json]` | build each card's rough shapes (kit calls at massing fidelity) into `build/concepts/C-xxx/` (GLB, props, features, renders) and screen it against the `concept-v0` rules (site fit with the open door, supply circuit, lift class, stock sheets, walls, controls); writes `screening:` into the card. A red card prints "this direction has problems:" with reasons and still exits 0 (red is information); exit 1 only on errors such as an impossible shape. `--all` skips rejected cards. Outside the build: no manifest entry, no rule reads it ([napkin.md](napkin.md)) |
| `n2f concept board [--json]` | write `build/concepts/board.html`: every card side by side in id order (red cards in place, with "this direction has problems:" and their reasons), the styled picture, an interactive 3D view, key sizes and the estimate strip with every number badged `computed` or `estimate`, "worth a look:" warnings, reference images, notes, and the decision on chosen/set-aside cards. Self-contained like the report (one inline module script, everything embedded, ≤ 20 MB — reference images, then front pictures are left out first, with a note), opens from `file://`; read-only. `--json` prints the gathered data. Not a build output (N1) |
| `n2f concept promote C-xxx [--override --reason TEXT] [--by NAME] [--json]` | make a direction the design: seeds `model/parameters.yaml` from `envelope` (refuses to change a different existing value unless `--override`), writes site requirements (alcove with the door swing, supply circuit, mass limit) and form requirements (`rule://form-v0/…`), merges its `style` and `layout` into `style.yaml`, appends a `DEC-` with the other cards as rejected alternatives, flips the cards (promoted / rejected) and takes a snapshot. All or nothing; refusals exit 3 (not built yet, red without `--override --reason`, another card already chosen, a parameter collision). See [napkin.md](napkin.md) |
| `n2f concept reject C-xxx --reason TEXT` | set a direction aside (status rejected, `decision: {reason, at}`); the card is kept. Refuses on the promoted card (exit 3) |
| `n2f concept lint` | check the cards (schema plus rules C1–C7); exit 1 on errors, warnings never fail. Concepts are outside the build: `validate` ignores them |
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
