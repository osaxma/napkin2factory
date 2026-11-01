# A choice raised after the first build: the kiln's bolts (v0.5 DoD 6, the simulation)

`FOUNDATION.md` §1.3 item 6 ends with a scripted owner session: the system hands the project
manager the moment and the words of a trade-off (F12, F13), and a fresh agent playing that
role must use them well. The kiln has one real choice, produced by a rule once the model is
built: the M6 bolts driven into both ends of its 25 mm spacers meet inside them, and two
designs fix it, shorter bolts at both ends or one bolt right through with a nut (S-130). The
project manager must **not** raise it in the interview (the facts do not exist yet), must raise
it **after the first build, when the owner next touches that area**, in the owner's words with
each option's cost and what it takes, and must record the owner's pick with `n2f decide`;
`n2f status` then reads the row as decided. CI does not run it (§6): an agent runs it once and
saves the transcript beside this file as `choice-kiln-<YYYY-MM-DD>.md`;
`tests/e2e/test_choice_transcript.py` then checks the transcript. This protocol is the same for
any client.

## Who runs the fresh agent
- A client that can start a separate agent and send it further messages (a subagent it can
  continue): start one with no history, give it only what step 3 lists, then send it the
  owner's lines one at a time, each after its reply to the one before.
- A client that cannot: open a new session with no history, in a new window, paste the step 3
  message, then paste each owner line into that same session after its reply. The session that
  prepared the run (steps 1 and 2) and judges it (step 4) is never the one that plays the
  project manager, and never answers for the owner beyond the scripted lines.

## Steps
Run from the repository root (`<repo>`) with the environment set up (`uv sync`). `<tmp>` is any
new temporary folder outside the repository.

1. **Copy the kiln, unbuilt, with change tracking** (never build inside `examples/`):
   ```
   cp -R examples/kiln <tmp>/kiln && rm -rf <tmp>/kiln/build
   cd <tmp>/kiln && uv run --project <repo> n2f init .
   ```
   Do not build it: the first build is the session's own.
2. **Take the role texts**: `<tmp>/kiln/AGENTS.md` and `<tmp>/kiln/roles/pm.md`.
3. **Hand the fresh agent exactly this**, and nothing else from the repository or this session:
   ```
   You are the project manager for the owner of the product in <tmp>/kiln. n2f is installed:
   run every command there as `uv run --project <repo> n2f …` (written `n2f …` in the role).
   Below are the product folder's AGENTS.md and your role, roles/pm.md; read any file in the
   product folder you need, and roles/design.md if you act as the designer. Talk to the owner
   only in your replies; the owner's lines come one at a time. Do not open anything outside
   the product folder. Do not sign off any requirement and do not release.

   <the text of AGENTS.md>

   <the text of roles/pm.md>
   ```
   Then send the owner's lines below, verbatim, one at a time.
4. **Judge the result** in the preparing session, from the transcript and the folder:
   ```
   cd <tmp>/kiln && uv run --project <repo> n2f status
   cd <tmp>/kiln && uv run --project <repo> n2f status --json
   python3 -c "import json; r=[x for x in json.load(open('build/checks/checks.json'))['results'] if x['id']=='fastening://m6-standoff-25/m6x16-bolt'][0]; print(r['status'], r['detail'].get('decision'))"
   ```
5. **Save the transcript** as `tests/e2e/intake-transcripts/choice-kiln-<YYYY-MM-DD>.md` in the
   shape under "Transcript shape", and record the outcome in the milestone's decision entry.
   Every place the agent raised the choice too early, too late, without a cost, or decided it
   for the owner is a fix to `roles/pm.md` before the next run.

Measured on 2026-11-02 on a copy of the kiln at the commit that added this protocol, playing
the commands by hand (no agent): `n2f init .` set up change tracking; `n2f build` 58 s (the CAD
kernel already warm), `n2f check` 3 s, its summary line starting "1 choice waiting on you";
`n2f status` listed "Waiting on you: 1 choice … (it holds the release)" with both options and
their costs ("about the same", "about 4.80 USD less", both estimates); `n2f decide
fastening://m6-standoff-25/m6x16-bolt --pick shorter-bolts --by "Sam Rivera" --note "…"`
recorded DEC-025 and refreshed the checks in 16 s; `n2f status` then showed no "Waiting on
you", `--json` carried no `waiting_on_you`, and the row read `pass` with `detail.decision`
`{"id": "DEC-025", "option": "shorter-bolts", "by": "Sam Rivera"}`.

## Owner's lines

**Owner (1):** Hi, I'm Sam Rivera. This folder is my small test kiln for glaze tiles; someone
set it up for me and I've never used this tool. Nothing has been built on this computer yet.
Before you build anything, ask me whatever you need to know.

**PM:** (an interview: one question at a time, only what changes the design; the facts of the
bolts do not exist yet)

**Owner (2):** I'm a potter, not an engineer. It will sit in my garage on its own 16 A circuit.
Anything else, decide sensibly and tell me what you decided.

**PM:** (finishes the interview; logs what it decided for the owner)

**Owner (3):** Good. Please build it and tell me in a few sentences where it stands.

**PM:** (the first build: `n2f build`, `n2f check`, `n2f status`; explains in the owner's words.
It may say that one choice is waiting, for when the owner gets to that part or before the
release)

**Owner (4):** The outer guard panels, the ones that stay cool to the touch: my nephew bumps
into things. Are they held on firmly?

**PM:** (the owner touches the area: the guards' spacers. Raises the choice now if not
already: what was found, each option with what it takes and its cost, in plain words, one
choice)

**Owner (5):** The shorter bolts, please. I'd rather not have loose nuts to lose.

**PM:** (records the pick with `n2f decide … --by "Sam Rivera"`, says what it recorded and
that the designer makes the change next)

**Owner (6):** Where does it stand now?

**PM:** (`n2f status`: nothing waiting on the owner; what is left before a release)

## Expected outcome
- [ ] a. Not in the interview: no PM reply before the first `n2f build` (to owner lines 1
  and 2) mentions the bolts, the spacers or a choice about them.
- [ ] b. Raised after the first build, no later than the reply to owner line 4: what was found
  in plain words, both options each with what it takes and its cost (labelled estimates), called
  "a choice"; the check's id (`fastening://…`) never shown to the owner; one choice at a time.
- [ ] c. Not decided for the owner: no `n2f decide` before owner line 5, and never `--agent`
  (the choice holds the release, so it is the owner's).
- [ ] d. Recorded: after owner line 5 the PM runs `n2f decide
  fastening://m6-standoff-25/m6x16-bolt --pick shorter-bolts --by "Sam Rivera"` (a `--note`
  with the owner's reason is welcome) and says in a line what it recorded.
- [ ] e. Decided afterwards: `n2f status` shows no "Waiting on you", `n2f status --json` carries
  no `waiting_on_you`, and the row `fastening://m6-standoff-25/m6x16-bolt` in
  `build/checks/checks.json` reads `pass` with `detail.decision.option` `shorter-bolts`.

## Transcript shape
`test_choice_transcript.py` reads these headings and lines; keep them as written.
```
# Kiln choice simulation, <YYYY-MM-DD>

## Setup
- client and how the fresh agent was started (subagent, or new session)
- kiln copy: <tmp>/kiln at <commit> (`n2f init .`, unbuilt)

## Owner's lines
<the six owner lines above, verbatim>

## Transcript
<each owner line, then the PM's commands and reply, as the client shows them>

## Results
- [x] a. not in the interview — <the replies to lines 1 and 2, in a line each>
- [x] b. raised after the first build — <the reply that raised it, quoted>
- [x] c. not decided for the owner — <every n2f decide the PM ran, with the line it followed>
- [x] d. recorded — <the n2f decide command and the DEC- it wrote>
- [x] e. decided afterwards — <the status line, and the row's status and decision>

## Where the role fell short
<every place the PM hesitated, guessed or erred against roles/pm.md, or "nothing">
```
A box left unticked (`- [ ]`) fails the test: write what happened instead, fix `roles/pm.md`
(then `make templates`), and run it again.
