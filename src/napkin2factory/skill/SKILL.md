---
name: napkin2factory
description: Use when a person wants to design, change, undo a change to, price, or get ready to have made a physical product (a workbench, bracket, enclosure, shelf, test rig, kiln, appliance housing), described in plain words and with no CAD skill. napkin2factory turns the idea into a checked design with rough directions to choose from, a 3D model, drawings and a priced parts list. Not for software, for printing or machining a file the person already has, or for learning a CAD program.
---

# napkin2factory

napkin2factory is a command line tool (`n2f`) that turns an idea for a physical product into
a design the person can have made: rough directions to choose from, a 3D model, shop
drawings, a priced parts list, and checks against what they asked for. The person decides;
you run it and explain it in plain words.

## When to use it

The person describes something they want to exist, or an existing design they want to change,
undo, price or release, and they are not asking for code or for help with a tool of their own.

## The loop

1. Check the tool: `n2f version`. If it is missing, ask before installing it
   (`uv tool install napkin2factory`, or `pip install napkin2factory`).
2. Read the guide before anything else: `n2f docs agent-guide`. It has the rules for talking
   to the person (what to say first, plain words, one question at a time).
3. A new product: ask where it should live, where it will be built, and which units they use;
   then `n2f init <folder> --name "<their name>"`. An existing folder (it has `n2f.yaml`):
   work in it.
4. Read the folder's `AGENTS.md` and `roles/pm.md`. From here they are your instructions.
5. Sketch directions with `n2f concept new` and `n2f concept board`; the person picks one
   (`n2f concept promote`).
6. `n2f build`, then `n2f check`; show them `build/report/index.html` and say what they are
   looking at.
7. A change: a change request (`n2f ecr start`, edit the model, `n2f ecr impact`; see the guide).
   A step back: `n2f checkpoints`, then `n2f undo`, `n2f redo` or `n2f rollback`.
8. A release is the owner's call (`n2f release`).

## Without the command line

If your client lists tools named `n2f_*`, they run the same commands on one product folder
(`n2f mcp` serves them; see below). If it has neither a shell nor those tools, tell the person
that this needs an agent that can run commands on their computer.

## With the MCP server

Start the server for a product folder: `n2f mcp --dir <folder>`, or with nothing installed:
`uvx --from "napkin2factory[mcp]" n2f mcp --dir <folder>`. Set the client's per-call tool
timeout to 10 minutes (a cold first build can take a minute or more).

The seven tools run the workflow in loop order, one line each (results are JSON with `ok` and `next`;
you edit model files with your own file tools):

1. `n2f_init_product`: ask the owner for the product name, region and units, then initialize the folder; read `AGENTS.md` and `roles/pm.md`.
2. `n2f_context`: rules on talking to the owner (`topic="agent-guide"`, one section at a time), docs, or model elements.
3. `n2f_promote_or_switch`: draft ideas (`action="new"`), switch directions, or promote the card the owner chooses (`action="promote"`).
4. `n2f_napkin_sync`: lint cards, build concept models, and render the board (`build/concepts/board.html`) to show the owner.
5. `n2f_sync`: validate, lint, build, check gates, and inspect status after editing files under `model/`.
6. `n2f_decide`: record the owner's choice when a check waits on them; never pick for them.
7. `n2f_ecr`: change a finished design (`action="quick"` or `action="start"`), or undo the last change (`action="undo"`).

The full guide, if the tool is not installed yet:
https://raw.githubusercontent.com/osaxma/napkin2factory/main/docs/agent-guide.md
