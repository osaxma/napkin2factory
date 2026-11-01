# Using napkin2factory: the guide for agents

You are reading this because a person asked you to **use** napkin2factory: to turn their idea
for a physical product into a design they can have made, or to show them what it does. The
prompt in the README sends you here. This guide covers what happens before a product folder
exists, plus a reference for running the `n2f` command line. Once a folder exists, its own
instructions take over (step 4).

If you were asked to **develop** napkin2factory itself (change its code, tests or docs), this
is the wrong file: read `AGENTS.md` at the root of the napkin2factory repository.

The person is the **owner**: the product is theirs, and the decisions are theirs. They read
the README, pasted a prompt, and expect you to guide them. They may never type a command or
open a file. Talk to them in plain words.

## Rules from the first message

1. **Disclaimer first.** Before any design work, tell the owner once, in your own words, that
   napkin2factory designs are made with an AI system and have not been reviewed by a licensed
   engineer, and that a qualified person should review the design before it is built, powered
   or used. Every page and package the tool makes says the same.
2. **Ask before you install anything** or create folders outside the one the owner chose. Say
   what you will install and why, then wait for a yes.
3. **Plain words.** Use the owner's vocabulary: *draft*, *snapshot*, *change request*,
   *released*, *Revision*, *concept*, *board*. Never use git words (commit, branch, merge,
   repository) with the owner, even though git does the work underneath.
4. **One question at a time**, and only the questions whose answers change the design.
5. **No invented numbers.** Every number you tell the owner says where it comes from:
   *given* (theirs), *computed* (measured from the model) or *estimate* (the calc kit).
6. **Safety needs a person.** Mains power, hot surfaces, sharp edges, pinch points, lifting
   and stored energy are always stated plainly. Safety requirements never pass by computation;
   the owner (or someone they name) records a sign-off.
7. **Nothing leaves the machine** unless the owner asks: no publishing, no uploading, no
   sending files anywhere.

## 1. Check you can run it

You need a shell on the owner's computer. napkin2factory is tested on macOS and Linux;
Windows is not tested. If you have no shell (a chat app with no terminal), tell the owner
plainly that this needs an agent that can run commands on their computer. A chat-only way in
is planned but does not exist yet.

```bash
n2f version        # already installed?
```

If it is missing, install it (after the owner says yes):

```bash
uv tool install napkin2factory     # puts `n2f` on PATH; uv fetches Python 3.13 itself
```

No `uv`? Install it with `curl -LsSf https://astral.sh/uv/install.sh | sh` (see
https://docs.astral.sh/uv/), or use `pip install napkin2factory` in a Python 3.13
environment. The PyPI name `n2f` is an alias for the same package. Then:

```bash
n2f doctor         # is this machine ready? It says what to fix if not.
```

Everything runs offline after installation and needs no account. Set `N2F_OFFLINE=1` (or
pass `--offline` to `n2f build`) when there is no network. Builds otherwise check that each
bought part's vendor link still resolves.

## 2. Find or make the product folder

- **The owner already has one** (a folder with `n2f.yaml` in it, made earlier or sent by
  someone): work in it and go to step 4. If `n2f status` says change tracking is missing,
  run `n2f init .` there. That adds tracking and any missing agent files and changes nothing
  else.
- **A new product:** ask where it should live. Suggest a new folder named after the product,
  in a place the owner keeps projects. Never create it inside a napkin2factory source
  checkout.

## 3. Create it

```bash
n2f init <folder> --name "<the owner's name for it>"
```

`--template blank` is the default and right for nearly everything. `bracket` and
`enclosure` are small worked examples, useful only if the owner's product is one of those.
`--style industrial|appliance|lab` sets the starting look. `n2f init` also starts loading the
CAD kernel in the background (see "Timing" below).

## 4. Hand over to the folder's own instructions

Read these before you say anything about the design:

1. `<folder>/AGENTS.md`: the vocabulary, the rules, where things are, the part kit. It is the
   folder's only instructions file, written for any agent. If your client does not load
   `AGENTS.md` on its own, read it yourself before anything else.
2. `<folder>/roles/pm.md`: the project manager, the only role that talks to the owner. It
   covers the napkin stage, intake, change requests and explaining reports.
3. `<folder>/roles/design.md` before you edit geometry; `roles/verifier.md` before a release;
   `roles/impact-analyst.md` when the owner asks what a change means.

From here on those files are your instructions. Where they and this guide differ, they win.
The roles are plain Markdown: nothing loads them for you, so read a role's file whenever you
act in that role.

## Adapting to your client

napkin2factory assumes no particular model or client. What it needs, and what to do when your
client lacks it:

| it needs | if your client can't |
|---|---|
| a shell on the owner's computer | stop and tell the owner (step 1); nothing else works without it |
| reading `AGENTS.md` at the start | read it yourself, first |
| a fresh context for the verifier | a separate agent if you can start one; otherwise ask the owner to start a new session for the review, and judge from the files, not from memory |
| looking at renders (`build/parts/<id>/renders/*.png`) | say you cannot see images, check the numbers in `build/parts/<id>/props.json`, and ask the owner to look at the report's 3D view |
| opening a page for the owner | give them the file path and say how to open it (double-click, or drag it into a browser) |
| reaching the network | set `N2F_OFFLINE=1`; everything but the vendor-link check works offline |

Commands that work on a product take `--json` (`graph` uses `--format json`, `serve` has none).
Prefer it whenever you parse output.

## 5. Show the owner what you made

The tool writes self-contained pages. They open straight from disk and need no server and no
network:

| page | made by | shows |
|---|---|---|
| `build/concepts/board.html` | `n2f concept board` | the rough directions side by side, each number labelled given / computed / estimate; red cards stay, with their reasons |
| `build/report/index.html` | `n2f build` | a 3D view, drawings, the parts list with "what to tell the manufacturer", the check matrix |
| `build/site/diff/<a>..<b>/index.html` | `n2f diff <a> <b>` | what changed between two Revisions |

Open them for the owner with `open <file>` (macOS) or `xdg-open <file>` (Linux), or run
`n2f serve` for a local address. Then say in a sentence or two what they are looking at and
what you need from them. The owner chooses in conversation; the pages are read-only.

## 6. Show the example (the kiln)

When the owner wants to see what the tool does before starting their own product, use the
showcase: a 1200 °C test kiln with 21 parts, thermal and element calcs, six manuals, example
sign-offs, two change requests and four concept cards. It is in the source repository, not in
the installed package:

```bash
git clone --depth 1 https://github.com/osaxma/napkin2factory.git <scratch>/napkin2factory
cp -R <scratch>/napkin2factory/examples/kiln <a folder the owner chose>/kiln
cd <a folder the owner chose>/kiln
n2f concept board          # the four directions; C-001, the kiln as built, is red
n2f build && n2f check     # the full package and the report
```

Never build inside the clone's `examples/` folder; always copy first. The story to tell: C-001
needs 1236 mm of width with its door open, and the owner's alcove is about 800 mm. Without the
napkin stage that came up at hour forty; the board shows it in minute five. C-003 is the
promoted direction. The kiln is the largest example, so its first build takes noticeably longer
than a small product's.

## Command reference

This is the order a product usually goes through, so an agent (or a curious person) can see
the whole path. `n2f <command> --help` is the authority, `docs/cli.md` is the full map, and
commands that work on a product take `--json`. `n2f status` always says where the
product stands and what to do next. Run it whenever you are unsure. Its "stage" is the stage
being worked in, the first one not complete (`ready` when only the release is left); in
`--json` that is `current_stage`, and the report and `n2f ecr close` name the same one.
`--json` `stage` is the last stage passed, kept for older scripts.

**Napkin stage: rough directions before any design.** The project manager role (`roles/pm.md`) decides when.

```bash
n2f concept new "Flat bracket"                      # writes concepts/C-001.yaml
n2f concept new "Gusseted bracket" --from C-001     # a variant of C-001
n2f concept build --all     # a styled picture of each, size, weight, a cost band, screening
n2f concept board           # → build/concepts/board.html
n2f concept promote C-002   # the owner's choice becomes the design direction
```

Each card needs a rough shape (`massing`): one line per piece from the part kit, in
millimetres. For example, replacing `massing: []`:

```yaml
massing:
  - {kit: bracket_l, as: body, material: mild steel, args: {length: 120 mm, height: 80 mm, width: 60 mm, thickness: 4 mm}}
  - {kit: block, as: gusset, material: mild steel, args: {length: 40 mm, width: 4 mm, height: 40 mm}, at: {x: 24 mm, z: 4 mm}}
```

When the owner has said them, three optional card fields sharpen screening: under `envelope`,
`door_swing: 110 degree` (how far a hinged door opens; without it the door counts swung fully
back, the widest case) and `target_volume: 8 L` (the useful volume asked for); under `site`,
`touch_limit: 60 degC` (the hottest outside surface allowed; without it, a burn threshold on
file). The door angle narrows the alcove check to what the door really needs; the volume and
the touch limit add rows "worth a look", never a red verdict.

The kit list is in the product's `AGENTS.md`; `docs/napkin.md` explains the stage.

**Design and check: the factory.**

```bash
n2f validate && n2f lint            # after every model edit
n2f build --target geometry --part <id>   # after a geometry edit; look at build/parts/<id>/renders/
n2f build                           # everything: 3D, drawings, BOM, manuals, checks, report
n2f check                           # the gate: every requirement and rule
```

`n2f build` also writes the build plan, derived from the assemblies: one step per unit
(`build/bom/build-plan.json`, a "Build plan" sheet in `bom.xlsx`, the report's Build plan, and
an A3 assembly sheet per unit in `build/drawings/assemblies/`). A sub-assembly is a unit
(`build: unit`, the default, with `driver: [...]` saying why) or a grouping (`build: phantom`);
joint hardware is counted from each interface's `spec.hardware` (or its `fastener:`) by the
`hardware://<unit>` check. The fields are in `docs/product-model.md`; the design role says
how to use them.

**Changes after a release** go through a change request, and the owner approves after
reading the impact:

```bash
n2f ecr new --title "Longer bracket" --set param://bracket-length=140mm
n2f ecr impact ECR-001              # what it touches, before anything changes
n2f ecr approve ECR-001 --by "<owner's name>"
n2f ecr apply ECR-001
n2f build && n2f check
n2f ecr close ECR-001
```

**Sign-offs and releases.** A requirement that cannot be checked by computation shows as
`needs your sign-off`. `n2f check` still exits 0, but `n2f release` refuses until a person has
recorded the review. Record it only with the owner's own words about what they inspected:

```bash
n2f signoff REQ-004 --by "<owner's name>" --statement "<what they inspected>"
n2f release v1.0.0                  # freeze a Revision: checks green, safety signed
n2f diff v1.0.0 v1.1.0              # → build/site/diff/v1.0.0..v1.1.0/index.html
```

A sign-off stays valid until the evidence it was bound to changes.

**Sharing** (only when the owner asks; rule 7):

```bash
n2f publish                         # → build/publish/: one folder with every page to share
n2f publish --online                # also send it to the product's online copy on GitHub
n2f publish --since v1.2.0          # leave out older Revisions (the folder holds ≤ 20 MB)
```

## Sharing the pages

`n2f publish` puts what already exists into `build/publish/`: an index page, the latest
report, every released Revision with its package to download, the change pages between
Revisions and the concept board. It builds nothing; anything missing is listed with the
command that makes it (`n2f build`, `n2f diff <a> <b>`, `n2f concept board`). The folder opens
from disk and can be zipped and sent, or put on any web host as it is.

`--online` sends the snapshots, the Revisions and that folder to the product's **online
copy**, a GitHub project the owner already has; GitHub then shows the pages at
`https://<account>.github.io/<project>/`. Before you run it, tell the owner that anyone with
that address can open the pages, and that the online copy must exist first. napkin2factory
never creates accounts or online projects and never changes their settings, so the owner
does these once, on the GitHub website:

1. Create an empty project (no README) for the product. A private project can show pages only
   on a paid GitHub plan.
2. Link the product folder to it: `git remote add origin <the project's address>`. Sending
   uses the computer's existing GitHub sign-in (for example `gh auth login`).
3. After the first `n2f publish --online`: in the project's Settings, under Pages, choose
   `gh-pages` as the source.

If the online copy holds snapshots this folder lacks (saved on another computer), sending
refuses and changes nothing: bring them in (`git pull`) and publish again.

## Timing and trouble

- **Timing.** The first build on a machine loads the CAD kernel, which takes one to two
  minutes. `n2f init` starts that load in the background; a build that has to wait prints
  "loading the CAD kernel…". Later builds rebuild only what changed and take seconds for a
  small product. Tell the owner about the first wait before it happens.
- **Something fails.** Run `n2f doctor`, then `n2f status`. Error messages say what to do
  next. Never edit anything under `build/`; edit the model and rebuild.
- **Unsure what a page or number means.** `docs/how-it-works.md` (the ideas),
  `docs/checks.md` (verification), `docs/ecr-loop.md` (changes), `docs/product-model.md`
  (the files in a product folder), `docs/vocabulary.md` (the owner's words and what each
  means underneath).

## What napkin2factory does not do (yet)

Mechanical parts and the bill of materials are covered. Electrical design, FEA and hosted
services are not. Say so when the owner's product needs them, and say what the tool can still
do for the mechanical side.
