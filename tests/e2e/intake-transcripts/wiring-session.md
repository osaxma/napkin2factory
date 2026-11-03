# The wiring's choice raised at the right time: the warming box (v0.6 DoD 7, the simulation)

`docs/stages/v0.6-electrical-stage.md` §1.3 item 7 ends with a scripted owner session: once the wiring is first
built, the supply-headroom check (E11) finds the load above half of the circuit it plugs into
and offers the owner a choice: keep the circuit for this product alone, or have a larger
circuit fitted. The project manager must **not** raise it in the interview (the wiring, and so
the load on the circuit, does not exist in the model yet), must raise it **after the first build
with wiring**, in the owner's words with what each option takes and means, and must decide it
**only with the owner's answer**, recorded with `n2f decide --by "<the owner>"` (F13; the owner
asks to be asked about anything electrical, so the delegation rule for a choice that holds
nothing does not apply). CI does not run it: an agent runs it once and saves the transcript beside
this file as `wiring-session-<YYYY-MM-DD>.md`. This protocol is the same for any client.

**The product** is `tests/fixtures/scope/external-box`, a warming box for dough (a heater and
a probe in a cabinet whose control box is bought wired and stands in as two cable entries),
taken back to the state where its wiring was left for later, with a change request that adds it
(the shape of the kiln's `demo-electrical.sh`, E9). Not the kiln: when this was written the
wired kiln had not landed, and on its EU 16 A circuit the conductor tables hold no larger
class, so its headroom row is a warning, not a choice (S-158, S-170). Here the heater draws
1200 W at 230 V, 5.2 A of a 10 A socket circuit, and the larger class on file is 16 A.

## Who runs the fresh agent
- A client that can start a separate agent and send it further messages (a subagent it can
  continue): start one with no history, give it only what step 3 lists, then send it the
  owner's lines one at a time, each after its reply to the one before.
- A client that cannot: open a new session with no history, in a new window, paste the step 3
  message, then paste each owner line into that same session after its reply. The session that
  prepared the run (steps 1 and 2) and judges it (step 4) is never the one that plays the
  project manager, and never answers for the owner beyond the scripted lines.

## Steps
Run from the repository root with the environment set up (`uv sync`); `<repo>` is its absolute
path. The commands are POSIX `sh` (macOS and Linux; `perl` and `git` are on both).

1. **Make the product**: a tracked copy of the fixture with its wiring taken out, the wiring
   kept as a change request's patch, nothing built (the session's builds are its own):
   ```sh
   REPO=<repo>; TMP=$(mktemp -d); echo "$TMP"
   cp -R "$REPO/tests/fixtures/scope/external-box" "$TMP/box" && rm -rf "$TMP/box/build"
   cd "$TMP/box"
   uv run --project "$REPO" n2f init .
   # the wiring left for later: no model/electrical, no circuit through the entries, the scope
   rm -rf model/electrical
   perl -pi -e 's/passes: \[[^\]]*\]/passes: []/' model/interfaces/mains-entry.yaml model/interfaces/control-entry.yaml
   perl -pi -e 's/electrical: \{state: in, decision: DEC-001\}/electrical: {state: later, decision: DEC-003}/' n2f.yaml
   # what puts it back, as the change request's patch
   mkdir -p changes
   git --no-pager diff --no-color --no-ext-diff --src-prefix=a/ --dst-prefix=b/ -R > changes/wiring.patch
   printf '%s\n' '  - id: DEC-003' '    date: 2026-11-02' '    title: The wiring comes later' \
     '    context: The cabinet was designed before its control box was chosen.' \
     '    decision: Build the cabinet first; wire it once the control box is chosen.' \
     '    made_by: human' '    disclosed: true' >> model/decisions.yaml
   uv run --project "$REPO" n2f validate
   uv run --project "$REPO" n2f ecr new --kind design --title "Add the wiring" \
     --reason "The control box is chosen; a friend who is an electrician drew up the wiring of the heater and the probe to it." \
     --patch changes/wiring.patch --by "Dana Whitfield"
   uv run --project "$REPO" n2f snapshot -m "The wiring left for later; its change request filed"
   uv run --project "$REPO" n2f status
   ```
   Expect: `n2f validate` says the model is consistent; `ECR-001 (design): Add the wiring` is
   filed; `n2f status` shows "Wiring: left for later (not designed here yet) — The wiring
   comes later (DEC-003)" and "Waiting on you" nowhere. The block runs as written, with or
   without the list's indentation.
2. **Take the role texts**: `$TMP/box/AGENTS.md` and `$TMP/box/roles/pm.md`.
3. **Hand the fresh agent exactly this**, with `<tmp>` and `<repo>` written out, and nothing else
   from the repository or this session:
   ```
   You are the project manager for the owner of the product in <tmp>/box. n2f is installed:
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
   ```sh
   cd "$TMP/box" && uv run --project "$REPO" n2f status
   cd "$TMP/box" && uv run --project "$REPO" n2f status --json | python3 -c "import json,sys; print('waiting_on_you' in json.load(sys.stdin))"
   python3 -c "import json; r=[x for x in json.load(open('build/checks/checks.json'))['results'] if x['id']=='elec-rule://supply-headroom@supply'][0]; print(r['status'], '|', r['message'], '|', r['detail'].get('decision'))"
   grep -n "supply-headroom" model/decisions.yaml
   ```
5. **Save the transcript** as `tests/e2e/intake-transcripts/wiring-session-<YYYY-MM-DD>.md` in the
   shape under "Transcript shape", and record the outcome in M7's decision entry. Every place
   the agent raised the choice too early, too late, without what each option takes, or decided
   it for the owner is a fix to `roles/pm.md` (then `make templates`) before the next run.

Measured on 2026-11-02 at the commit that added this protocol, playing the project manager's
commands by hand (no agent; the roles were v0.5's, M7 adds their wiring text): step 1 took
5 s; `n2f ecr impact`, `n2f ecr approve ECR-001 --by "Dana Whitfield"` and `n2f ecr apply
ECR-001` applied the patch; the first build with wiring took 7 s and `n2f check` 1.5 s, its
summary starting "1 choice waiting on you"; `n2f status` listed "Waiting on you: 1 choice —
Room to spare on the supply's circuit (it holds nothing; an agent may decide it and say so)",
"5.2 A of the 10 A circuit (the Heater: 5.2 A, computed from 1200 W at 230 V): more than half
of it", option 1 "a dedicated 10 A circuit; nothing else may be plugged into it" and option 2
"a 16 A dedicated circuit: room for a bigger load later; the electrician fits thicker cable",
each with what it takes and its `n2f decide elec-rule://supply-headroom@supply --pick …`
line. `n2f decide … --pick larger --by "Dana Whitfield"` records a `DEC-` (`made_by: human`)
in 5 s. With the pick made in the model (`param://supply-rating` 16 A, then build and check)
the row reads `pass`, "5.2 A of the 16 A circuit: no more than half of it, so the circuit has
room to spare.", nothing waiting on the owner. Picking `dedicated` instead leaves a Design
caveat "decided in DEC-…, not yet in the design" that no model edit clears (B-0149); the
script's owner picks the larger circuit, so the run does not depend on it.

## Owner's lines

**Owner (1):** Hi, I'm Dana Whitfield. This folder is my warming box: a cabinet that keeps
bread dough warm while it rises. Someone set it up for me and I've never used this tool. The
cabinet itself is designed, but its wiring was left for later. Before you change anything,
ask me whatever you need to know.

**PM:** (an interview: one question at a time, only what changes the design; the wiring is
not in the model yet, so neither is the load on the circuit)

**Owner (2):** I bake at home; I'm not an engineer. It will plug into a kitchen socket, and the
breaker for that socket says 10 A. Anything about the electrics or what it plugs into, ask me
before you decide it. Anything else, decide sensibly and tell me what you decided.

**PM:** (finishes the interview; logs what it decided for the owner; nothing electrical
decided)

**Owner (3):** Good. There's a change request in the folder to add the wiring; a friend of
mine who is an electrician drew it up. I approve it: please put it in, build everything, and
tell me in a few sentences where it stands.

**PM:** (`n2f ecr impact`, `n2f ecr approve ECR-001 --by "Dana Whitfield"`, `n2f ecr apply`,
the first build with wiring, `n2f check`, `n2f status`; explains in the owner's words. The
facts now exist and the owner is in the area and asked to be asked: it raises the choice now,
or says one electrical choice is waiting and raises it in full at the latest in its next reply)

**Owner (4):** Does it matter what else is plugged in on that socket? The kettle is on it
sometimes.

**PM:** (raises the choice in full if not already: what was found, both options with what each
takes and what it means for the kettle and for a bigger heater later, plainly, as a choice;
does not decide)

**Owner (5):** Then I'd rather have the bigger circuit put in. My friend can fit it.

**PM:** (records the pick with `n2f decide elec-rule://supply-headroom@supply --pick larger
--by "Dana Whitfield"`, says what it recorded and what changes next; it may make the change in
the model as the designer, or say the designer will)

**Owner (6):** Where does it stand now?

**PM:** (`n2f status`: nothing waiting on the owner; what is left before a release, the
electrician's sign-off among it)

## Expected outcome
- [ ] a. Not in the interview: no PM reply before the first build with wiring (the build after
  `n2f ecr apply`) mentions the room left on the circuit, "more than half", a dedicated
  circuit or a larger circuit, or offers any choice about the supply. Asking which socket or
  breaker the box plugs into is a fact question and is allowed.
- [ ] b. Raised after the first build with wiring, in full no later than the reply to owner
  line 4: the load against the circuit in plain words (5.2 A of the 10 A circuit, more than
  half), both options each with what it takes and what it means (nothing else on that socket,
  so not the kettle; or a 16 A circuit with thicker cable, fitted by the electrician, room for
  a bigger heater later), called a choice and left to the owner; the check's id
  (`elec-rule://…`) never shown to the owner; numbers labelled as computed where given.
- [ ] c. Not decided for the owner: no `n2f decide` on the supply choice before owner line 5,
  and never `--agent` (the owner asked to be asked about anything electrical).
- [ ] d. Recorded with the owner's answer: after owner line 5 the PM runs `n2f decide
  elec-rule://supply-headroom@supply --pick larger --by "Dana Whitfield"` (a `--note` with the
  owner's reason, the kettle, is welcome) and says in a line what it recorded; the `DEC-` it
  wrote reads `made_by: human` in `model/decisions.yaml`.
- [ ] e. Decided afterwards: `n2f status` shows no "Waiting on you" and `n2f status --json`
  carries no `waiting_on_you`; the row `elec-rule://supply-headroom@supply` in
  `build/checks/checks.json` reads `pass` with `detail.decision.option` `larger`, or, when the
  PM (acting as the designer before any release) has already made the pick in the model
  (the supply's rating 16 A, built and checked), `pass` with the message "5.2 A of the 16 A
  circuit: no more than half of it, …" (both forms, as S-136 amended criterion e).

## Transcript shape
Keep these headings and lines as written, so a test can read them like
`test_choice_transcript.py` reads the kiln's.
```
# Wiring session simulation, <YYYY-MM-DD>

## Setup
- client and how the fresh agent was started (subagent, or new session)
- product: <tmp>/box from tests/fixtures/scope/external-box at <commit> (step 1, unbuilt)

## Owner's lines
<the six owner lines above, verbatim>

## Transcript
<each owner line, then the PM's commands and reply, as the client shows them>

## Results
- [x] a. not in the interview — <the replies to lines 1 and 2, in a line each>
- [x] b. raised after the first build with wiring — <the reply that raised it, quoted>
- [x] c. not decided for the owner — <every n2f decide the PM ran, with the line it followed>
- [x] d. recorded with the owner's answer — <the n2f decide command and the DEC- it wrote>
- [x] e. decided afterwards — <the status line, and the row's status and message or decision>

## Where the role fell short
<every place the PM hesitated, guessed or erred against roles/pm.md, or "nothing">
```
A box left unticked (`- [ ]`) fails the run: write what happened instead, fix `roles/pm.md`
(then `make templates`), and run it again.
