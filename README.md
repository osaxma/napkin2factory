# napkin2factory

**From napkin to factory.** Describe a physical product as text; get a manufacturable
technical data package — 3D models, drawings, flat patterns, bill of materials, manuals and
a self-contained report — and change it safely: every engineering change rebuilds exactly
what it invalidates, shows its impact before anything moves, and ships as a diff page.

> **Disclaimer.** napkin2factory designs are produced with an AI system and have not been
> reviewed by a licensed engineer. Every report, manual, drawing and package it generates
> says so. Have a qualified person review a design before you build, power or use it.
> Safety requirements can never pass by computation alone; they need a human sign-off.

Version 0.1 covers mechanical parts and the bill of materials. Electrical design, FEA and
hosted services are not included (see `BACKLOG.md`).

## Install (from source)

Requires [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`);
`uv sync` fetches Python 3.13 itself if the machine has none. The repository is private
until launch, so the clone line is for people with access; everyone else unpacks the source
archive they were given and starts at `cd`.

```bash
git clone https://github.com/osaxma/napkin2factory.git   # or unpack the source archive
cd napkin2factory
uv sync                 # add --no-dev if you only want to run it, not develop it
uv run n2f version      # napkin2factory 0.1.0
uv run n2f doctor       # is this machine ready?
```

`uv run n2f …` only works from inside this checkout. To have `n2f` on your PATH and usable
from any folder:

```bash
uv tool install .
```

or `pip install -e .` into a virtual environment. Once the package is published,
`uvx napkin2factory` will work without a checkout.

## Ten-minute first run

```bash
uv run n2f init demo --template bracket
cd demo
uv run n2f build        # the first build loads the CAD kernel: about two minutes, then seconds
uv run n2f check
open build/report/index.html        # macOS; Linux: xdg-open …; or: uv run n2f serve
```

The first `n2f build` on a machine prints "loading the CAD kernel…" and then sits silent for
a minute or two while the kernel loads; later builds take seconds. Builds also check that
each bought part's vendor link still resolves; set `N2F_OFFLINE=1` (or pass `--offline`) to
skip that.

The report opens straight from disk: a 3D view you can orbit, drawings, the bill of
materials with a "what to tell the manufacturer" column, and the check matrix. Try a change:

```bash
uv run n2f ecr new --title "Longer bracket" --set param://bracket-length=140mm
uv run n2f ecr impact ECR-001          # what it touches, before anything changes
uv run n2f ecr approve ECR-001 --by "me"
uv run n2f ecr apply ECR-001
uv run n2f build && uv run n2f check
uv run n2f ecr close ECR-001
uv run n2f release v1.0.0
```

Make a second change the same way, release it as `v1.1.0`, and the headline diff page is
one command away:

```bash
uv run n2f diff v1.0.0 v1.1.0          # → build/site/diff/v1.0.0..v1.1.0/index.html
```

`n2f status` always tells you where the product stands and what to do next.

**Sign-offs.** Some requirements cannot be checked by computation (the enclosure template
has one: inspect every edge by hand). `n2f check` lists them as `needs your sign-off` and
still exits 0, but `n2f release` refuses until a person has recorded the review:

```bash
uv run n2f signoff REQ-004 --by "your name" --statement "what you inspected"
```

`n2f status` prints the exact command to run. A sign-off stays valid until the evidence it
was bound to changes.

## The three doors

1. **Chat app only** — planned: a connector or skill that lets a chat assistant run the
   intake and build in its own sandbox.
2. **GitHub template** — planned: "Use this template", GitHub Actions as the build machine,
   Pages as the product site. Every product folder already carries the workflow files.
3. **Local CLI** — this: `uv run n2f …` (or `n2f …` after `uv tool install .`), works
   offline (`N2F_OFFLINE=1`), no accounts. Open the product folder in Claude Code, Codex or
   any coding agent: the folder's `CLAUDE.md` and skills turn it into the project team.

## The showcase: a 1200 °C test kiln

`examples/kiln` is a complete product: 21 parts, interfaces, thermal and element calcs,
six manuals, example sign-offs, and two change requests. `examples/kiln/demo.sh` runs the
parametric engineering-change loop unattended (release → change → impact → approve → apply →
rebuild → check → re-sign → release → diff page); `demo-design.sh` adds a design change
applied from a pre-authored patch.

## Learn more

- `docs/concepts.md` — the ideas (one canonical model, recorded dependencies, checks as the gate)
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
