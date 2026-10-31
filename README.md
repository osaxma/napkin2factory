# napkin2factory

**From napkin to factory.** Describe a physical product as text; get a manufacturable
technical data package — 3D models, drawings, flat patterns, bill of materials, manuals and
a self-contained report — and change it safely: every engineering change rebuilds exactly
what it invalidates, shows its impact before anything moves, and ships as a diff page.

> **Disclaimer.** napkin2factory designs are produced with an AI system and have not been
> reviewed by a licensed engineer. Every report, manual, drawing and package it generates
> says so. Have a qualified person review a design before you build, power or use it.
> Safety requirements can never pass by computation alone; they need a human sign-off.

Version 0.1 covers mechanical parts and the bill of materials. Version 0.2 (in development
on this branch) adds the napkin stage: cheap concept variants, screened for feasibility and
shown side by side before any detailed design (`NAPKIN_STAGE.md`). Electrical design, FEA
and hosted services are not included (see `BACKLOG.md`).

## Install

```bash
uv tool install napkin2factory     # or: pip install napkin2factory
n2f version
n2f doctor                         # is this machine ready?
```

[uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`) fetches
Python 3.13 itself if the machine has none; `pip install` needs a Python 3.13 environment of
your own. The PyPI name `n2f` is an alias that installs the same package. Everything works
offline and needs no account.

**From source (contributors):**

```bash
git clone https://github.com/osaxma/napkin2factory.git
cd napkin2factory
uv sync                 # add --no-dev if you only want to run it, not develop it
uv run n2f doctor
```

Inside the checkout, prefix every command below with `uv run` (it only works from inside
the checkout); `uv tool install .` puts that checkout's `n2f` on your PATH instead.

## Ten-minute first run

**First act: the napkin.** Before any design, sketch two directions and look at them side by
side:

```bash
n2f init demo --template bracket
cd demo
n2f concept new "Flat bracket"
n2f concept new "Gusseted bracket" --from C-001
```

Each card (`concepts/C-001.yaml`, `concepts/C-002.yaml`) needs a rough shape: one line per
piece from the kit, in millimetres. Your coding agent usually writes these; by hand, replace
`massing: []` in C-001 with

```yaml
massing:
  - {kit: bracket_l, as: body, material: mild steel, args: {length: 120 mm, height: 80 mm, width: 60 mm, thickness: 4 mm}}
```

and give C-002 the same line plus a gusset in the inside corner:

```yaml
  - {kit: block, as: gusset, material: mild steel, args: {length: 40 mm, width: 4 mm, height: 40 mm}, at: {x: 24 mm, z: 4 mm}}
```

Then build, screen and compare them:

```bash
n2f concept build --all     # a styled picture of each, its size, weight and a cost band
n2f concept board           # → build/concepts/board.html
open build/concepts/board.html      # macOS; Linux: xdg-open …
n2f concept promote C-002   # pick one: it becomes the design direction
```

The board shows the two directions side by side, and every number on it says where it comes
from: **given** (your own inputs on the card), **computed** (measured from the rough
shapes) or **estimate** (from the calc kit). A bracket's board is short: its size, its mass
and a cost band. Directions for a product with heat or power in it also show heat-up time,
heat loss and the supply circuit (see the kiln below). A direction that does not fit its site
is shown in red with its reasons. It stays on the board, because red is information.
`docs/napkin.md` explains the napkin stage.

**Second act: the factory.**

```bash
n2f build        # seconds, once the CAD kernel has loaded (see below)
n2f check
open build/report/index.html        # macOS; Linux: xdg-open …; or: n2f serve
```

The CAD kernel takes one to two minutes to load the first time on a machine. `n2f init`
starts loading it in the background, so by the time you have read this the first build is
usually quick; if you run it sooner it prints "loading the CAD kernel…" and waits. Later
builds take seconds. Builds also check that
each bought part's vendor link still resolves; set `N2F_OFFLINE=1` (or pass `--offline`) to
skip that.

The report opens straight from disk: a 3D view you can orbit, drawings, the bill of
materials with a "what to tell the manufacturer" column, and the check matrix. Try a change:

```bash
n2f ecr new --title "Longer bracket" --set param://bracket-length=140mm
n2f ecr impact ECR-001          # what it touches, before anything changes
n2f ecr approve ECR-001 --by "me"
n2f ecr apply ECR-001
n2f build && n2f check
n2f ecr close ECR-001
n2f release v1.0.0
```

Make a second change the same way, release it as `v1.1.0`, and the headline diff page is
one command away:

```bash
n2f diff v1.0.0 v1.1.0          # → build/site/diff/v1.0.0..v1.1.0/index.html
```

`n2f status` always tells you where the product stands and what to do next.

**Sign-offs.** Some requirements cannot be checked by computation (the enclosure template
has one: inspect every edge by hand). `n2f check` lists them as `needs your sign-off` and
still exits 0, but `n2f release` refuses until a person has recorded the review:

```bash
n2f signoff REQ-004 --by "your name" --statement "what you inspected"
```

`n2f status` prints the exact command to run. A sign-off stays valid until the evidence it
was bound to changes.

## The three doors

1. **Chat app only** — planned: a connector or skill that lets a chat assistant run the
   intake and build in its own sandbox.
2. **GitHub template** — planned: "Use this template", GitHub Actions as the build machine,
   Pages as the product site. Every product folder already carries the workflow files.
3. **Local CLI** — this: `n2f …`, works
   offline (`N2F_OFFLINE=1`), no accounts. Open the product folder in Claude Code, Codex or
   any coding agent: the folder's `CLAUDE.md` and skills turn it into the project team.

## The showcase: a 1200 °C test kiln

`examples/kiln` is a complete product: 21 parts, interfaces, thermal and element calcs,
six manuals, example sign-offs, and two change requests. It also has the napkin stage it
should have started with: four concept cards in `concepts/`, written after the fact from the
kiln's own numbers. C-001, the kiln as built, is **red**. It needs 1698 mm of width with
the door open, and the owner's alcove is about 800 mm. In v0.1 that problem was found at
hour forty, and the napkin stage shows it in minute five. C-002 fits the alcove, but its
chamber is smaller and its skin is hotter. C-003, the same kiln in the look the owner
preferred, is the promoted direction. C-004 keeps the v0.1 look and was rejected.

`examples/kiln/demo-napkin.sh` replays that stage unattended: it builds the four directions
and the board, shows the red one with its reasons, sets the v0.1 look aside and promotes
C-003. The factory loop then validates, builds and checks the kiln green.
`examples/kiln/demo.sh` runs the parametric engineering-change loop unattended (release →
change → impact → approve → apply → rebuild → check → re-sign → release → diff page), and
`demo-design.sh` adds a design change applied from a pre-authored patch.

## Learn more

- `docs/how-it-works.md` — the ideas (one canonical model, recorded dependencies, checks as the gate)
- `docs/cli.md` — every command · `docs/vocabulary.md` — the glossary (draft, snapshot,
  change request, Revision … and what each means underneath)
- `docs/product-model.md` — the files in a product folder · `docs/kit.md` — the part generators
- `docs/checks.md` — how verification works · `docs/ecr-loop.md` — the change loop
- `docs/agent-layer.md` — the roles a product folder installs for AI clients

## Developing

```bash
make check        # lint, types, tests, both small examples (6–10 min; sets N2F_OFFLINE=1)
make check-full   # + the kiln, both demos, timing assertions (N2F_TIMING=1)
```

See `CLAUDE.md` for the rules, `GRAND_PLAN.md` for the plan this version was built to, and
`DECISIONS.md` / `STATUS.md` / `BACKLOG.md` for the build journal.

## License

MIT — see `LICENSE`.
