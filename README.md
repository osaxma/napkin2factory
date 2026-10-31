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

```bash
n2f init demo --template bracket
cd demo
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
six manuals, example sign-offs, and two change requests. `examples/kiln/demo.sh` runs the
parametric engineering-change loop unattended (release → change → impact → approve → apply →
rebuild → check → re-sign → release → diff page); `demo-design.sh` adds a design change
applied from a pre-authored patch.

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
