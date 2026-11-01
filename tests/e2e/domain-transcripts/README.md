# A step is a folder: the gadget simulation (v0.5 DoD 2, the count)

`FOUNDATION.md` §1.3 item 2 asks whether a fresh agent, given only the contract
(`docs/domains.md`), can add a domain without touching the core. A fresh agent gets the
contract's text, the path of a fresh copy of the repository and one scripted request: add a
second toy domain, `gadget`, with one of every kind of thing a domain brings, installed for a
test, and a test proving every registry sees it. It passes when its test passes, the toy's test
still passes, the number of files it changed under `src/napkin2factory/core/` is **0**, and it
opened no file there. CI does not run it (§6): an agent runs it once and saves the transcript
here as `gadget-<YYYY-MM-DD>.md`; `tests/e2e/test_domain_transcript.py` then checks the
transcript. This protocol is the same for any client.

## Who runs the fresh agent
- A client that can start a separate agent (a subagent, a background agent): start one with no
  history and give it only what step 3 lists.
- A client that cannot: open a new session with no history, in a new window, and paste the same
  message. The session that prepared the run (steps 1 and 2) and judges it (steps 4 and 5) is
  never the one that adds the domain.

## Steps
Run from the repository root (`<repo>`) with the environment set up (`uv sync`). `<tmp>` is any
new temporary folder outside the repository.

1. **Make a fresh copy of the repository** at the commit under test, in its own folder:
   ```
   git worktree add --detach <tmp>/n2f-domain main
   cd <tmp>/n2f-domain && UV_LINK_MODE=hardlink uv sync -q && git rev-parse HEAD
   ```
   Record the commit it prints (`<base>`). Check the toy's test passes there first:
   `uv run pytest tests/unit/test_domain_contract.py -q` (the baseline).
2. **Take the contract**: the text of `<tmp>/n2f-domain/docs/domains.md`. Record its size in
   bytes (`wc -c docs/domains.md`).
3. **Hand the fresh agent exactly this**, and nothing else from this session: the contract's
   text, the folder's absolute path `<tmp>/n2f-domain`, and the message below.
   ```
   You are adding a step to napkin2factory, a Python package, in the folder <tmp>/n2f-domain
   (a fresh copy of its repository; run everything there with `uv run …`). Below is the whole
   contract for adding one: docs/domains.md. Do not open any file under
   src/napkin2factory/core/: the contract says what you need from it. If you cannot finish
   without opening one, stop and say which file and why instead of opening it. Do not change
   any file under src/napkin2factory/core/. You may open any other file, including the toy
   domain and its test, which the contract tells you to copy.

   Put the domain in tests/fixtures/domains/gadget/, its product in
   tests/fixtures/products/gadget/ and its test in tests/unit/test_gadget_domain.py. Run
   `uv run pytest tests/unit/test_gadget_domain.py -q` until it passes, then
   `uv run pytest tests/unit/test_domain_contract.py -q` to show the toy still passes. When you
   are done, list every file you opened, and every file you created or changed.

   The request:
   <the request below, verbatim>

   <the contract's text>
   ```
4. **Judge the result** in the preparing session:
   ```
   cd <tmp>/n2f-domain
   uv run pytest tests/unit/test_gadget_domain.py tests/unit/test_domain_contract.py -q
   git diff --name-only <base> -- src/napkin2factory/core/ | wc -l
   git status --porcelain --untracked-files=all -- src/napkin2factory/core/ | wc -l
   git status --porcelain --untracked-files=all
   ```
   The two counts are the DoD 2 number: their sum must be 0. The last command lists every file
   the agent created or changed; compare it with the agent's own list. Read the agent's list
   of opened files and its tool calls in the transcript: no path under
   `src/napkin2factory/core/`. Read `tests/unit/test_gadget_domain.py`: it asserts each of the
   eleven things in the request through its registry (result e. below).
5. **Save the transcript** as `tests/e2e/domain-transcripts/gadget-<YYYY-MM-DD>.md` in the
   shape under "Transcript shape", record the outcome (the count, the bytes, what the contract
   lacked) in the milestone's decision entry, and remove the copy:
   `git worktree remove --force <tmp>/n2f-domain`. Every place the agent said the contract fell
   short is a fix to `docs/domains.md` before the next run.

## The scripted request
### Request
> Add a second toy domain named `gadget` (a tiny model family, one rule family, one verify
> kind, one check stage, one gate row, one report section, one doc helper, one vocabulary word,
> one interface kind, one process, one screen), installed for a test, with a test proving every
> registry sees it.

### Why this request
It is the toy domain again under new names: each item is one registry of the contract
(`docs/domains.md` §3), the toy (`tests/fixtures/domains/toy/`) has one of each, and the toy's
test (`tests/unit/test_domain_contract.py`) proves each. An agent that follows the contract
copies the toy, renames everything, and never needs the core. Names must not collide with the
toy's (the registry refuses a second verify kind or check stage of the same name), and the
gadget's test must pass beside the toy's in one run, so the contract's notes on unique names,
on loading the product inside `with installed(...)` and on running the CLI in-process are
exercised. Not measured yet: the time it takes and the size of the agent's context.

### Expected outcome
- [ ] a. `uv run pytest tests/unit/test_gadget_domain.py`: passes.
- [ ] b. `uv run pytest tests/unit/test_domain_contract.py`: still passes.
- [ ] c. Files changed under `src/napkin2factory/core/`: 0 (both counts of step 4).
- [ ] d. Files opened under `src/napkin2factory/core/`: none (the agent's list and its tool calls).
- [ ] e. The gadget's test asserts all eleven: a model family, a rule family, a verify kind, a
  check stage, a gate row, a report section, a doc helper, a vocabulary word, an interface
  kind, a process, a screen.

## Transcript shape
`test_domain_transcript.py` reads these headings and lines; keep them as written.
```
# Gadget domain simulation, <YYYY-MM-DD>

## Setup
- client and how the fresh agent was started (subagent, or new session)
- base: <commit> (`git rev-parse HEAD` in the fresh copy)
- contract: <bytes> bytes (`docs/domains.md`)

## Request
> <the request, verbatim>

## Transcript
<the fresh agent's messages and tool calls, as the client shows them>

## Results
- [x] a. the gadget test passes — <its pytest summary line>
- [x] b. the toy's test still passes — <its pytest summary line>
- [x] c. core files changed: 0 — <the two counts of step 4>
- [x] d. core files opened: none — <the agent's list of opened files>
- [x] e. every registry asserted — <the eleven, each with the test that asserts it>

## Where the contract fell short
<every place the agent asked for or guessed something the page did not say, or "nothing">
```
A box left unticked (`- [ ]`) fails the test: write what happened instead, fix
`docs/domains.md` (or the core, if the contract cannot be met without it, as its own task), and
run it again.
