# One module, one agent: the door simulation (v0.4 DoD 5)

`PRODUCT_STRUCTURE.md` §1.3 item 5 asks whether an agent that knows only one module can change
it alone. A fresh agent gets the design role, the output of `n2f context asm://door` and the
door's geometry code (one file, the *bundle*), then makes one scripted change to the door. It
passes when the door's own checks and the whole kiln's checks have no failure and every file it
changed is one the context lists. CI does not run it (§6): an agent runs it once and saves the
transcript here as `door-<YYYY-MM-DD>.md`; `tests/e2e/test_module_transcript.py` then checks the
transcript. This protocol is the same for any client.

## Who runs the fresh agent
- A client that can start a separate agent (a subagent, a background agent): start one with no
  history and give it only what step 3 lists.
- A client that cannot: open a new session with no history, in a new window, and paste the same
  message. The session that prepared the run (steps 1 and 2) and judges it (steps 4 and 5) is
  never the one that makes the change.

## Steps
Run from the repository root with the environment set up (`uv sync`). `<tmp>` is any new
temporary folder outside the repository.

1. **Copy and build the kiln** (never build inside `examples/`):
   ```
   cp -R examples/kiln <tmp>/kiln
   cd <tmp>/kiln && uv run --project <repo> n2f build && uv run --project <repo> n2f check
   ```
   Note the summary line of `n2f check` (the baseline: no failure).
2. **Write the bundle** (from the repository root):
   ```
   uv run python scripts/module_sim_bundle.py <tmp>/kiln asm://door
   ```
   It writes `<tmp>/kiln-door-bundle.md` and prints its size in bytes. Record the size.
3. **Hand the fresh agent exactly this**, and nothing else from the repository or this session:
   the bundle's text, the product folder's absolute path `<tmp>/kiln`, and the message below.
   ```
   You are the designer of a product, working in the folder <tmp>/kiln (run every n2f
   command there; n2f is installed: `uv run --project <repo> n2f …`). Below is your whole
   working context: your role, the context of the one module you may change (the door), and
   its geometry code. Open only the files the context lists under "Its files"; if you need
   any other file, stop and say which and why instead of opening it. Make the owner's change,
   then run `n2f build --asm door`, `n2f check --scope asm://door`, `n2f build` and
   `n2f check`, and fix anything that fails inside the door. Do not sign off any requirement.
   When you are done, list every file you opened and every file you changed.

   The owner's request:
   <the request below, verbatim>

   <the bundle's text>
   ```
4. **Judge the result** in the preparing session:
   ```
   cd <tmp>/kiln && uv run --project <repo> n2f check --scope asm://door
   cd <tmp>/kiln && uv run --project <repo> n2f build && uv run --project <repo> n2f check
   uv run python scripts/module_sim_bundle.py --verify <tmp>/kiln examples/kiln asm://door
   ```
5. **Save the transcript** as `tests/e2e/module-transcripts/door-<YYYY-MM-DD>.md` in the shape
   under "Transcript shape", and record the outcome in the milestone's decision entry.

## The scripted change
### Request
> The four spacers that hold the door's outer guard off the door sit too close to the middle.
> Move them out towards the corners so that the rectangle they make is 10 mm wider and 10 mm
> taller. Nothing else on the kiln should change.

### Why this change
It is a change an owner could ask for (fixings nearer the corners hold a sheet flatter), and it
lies wholly inside the door: the four standoffs join the door tray to the door guard
(`iface://door-guard-standoff`, a joint inside the door), and the sizes that place them are the
door's own (`door-standoff-inset`, `door-standoff-spacing-x`, `-z`, scoped to `asm://door`). No
port (the hinges, the latch) and no size the kiln reads moves, so no kiln-side edit is needed.
The agent still has to find, from the context alone, which size drives the pattern: the pitch
is derived (`door-width - 2 × door-standoff-inset`), so 10 mm wider means the inset goes from
120 mm to 115 mm (or the two spacing expressions gain 10 mm). Measured on 2026-11-01 by setting
the inset to 115 mm on a built copy: the pitch went from 452.4 mm to 462.4 mm each way;
`n2f build --asm door` rebuilt the door tray, the door guard and the door (15 s), `n2f check
--scope asm://door` had no failure (8.7 s), `n2f build && n2f check` had no failure, and
`--verify` reported `model/parameters.yaml` only, in the context.

### Expected outcome
- [ ] a. `n2f check --scope asm://door`: no failure.
- [ ] b. `n2f build && n2f check` on the copy: no failure. Two safety requirements carry
  example sign-offs whose evidence includes the door guard (REQ-003, touch temperature; REQ-019,
  earth continuity); they lapse to "needs your sign-off". That is correct, not a failure, and
  the agent must not sign them.
- [ ] c. `scripts/module_sim_bundle.py --verify`: every changed file is in the context
  (expected: `model/parameters.yaml` only).
- [ ] d. The agent's list of opened files holds only files the context lists.

## Transcript shape
`test_module_transcript.py` reads these headings and lines; keep them as written.
```
# Door simulation, <YYYY-MM-DD>

## Setup
- client and how the fresh agent was started (subagent, or new session)
- bundle: <bytes> bytes (`scripts/module_sim_bundle.py`)

## Request
> <the request, verbatim>

## Transcript
<the fresh agent's messages and tool calls, as the client shows them>

## Results
- [x] a. `n2f check --scope asm://door`: no failure — <its summary line>
- [x] b. `n2f build && n2f check`: no failure — <its summary line>
- [x] c. file scope: every changed file is in the context — <the --verify output>
- [x] d. files opened: <the agent's list>; all in the context
```
A box left unticked (`- [ ]`) fails the test: write what happened instead, and fix the role or
the context before running it again.
