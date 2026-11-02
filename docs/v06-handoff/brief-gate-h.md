# Review gate H — UX in the owner persona (v0.6)

Written by the second overseer from `docs/reviews/TEMPLATE.md` (standing rules + persona + the
UX set + ELECTRICAL_STAGE.md DoD 9). Fill `[commit]` and `[subject]` before handing it over;
hand the reviewer this text and nothing else.

---

You are a fresh-context reviewer for napkin2factory 0.6 ("the wiring": an electrical step a
product may need; the system declares the supply, devices and connections, then draws,
schedules and checks them) at `/Users/wakeel/napkin2factory`, branch `main`, reviewing commit
[commit] ("[subject]"). You have not seen the design conversation and are not told the
builders' conclusions. Your job is **review gate H: UX in the owner persona**.

Standing rules:
- Read-only. Change nothing in the repo; do not commit. You may run commands and write under
  `/tmp/n2f-gate-h/` (create it).
- Work on copies (`cp -R examples/kiln /tmp/n2f-gate-h/<name>`, or the `copy_product` helper in
  `tests/conftest.py`); never run `n2f build` inside `examples/`.
- Environment: macOS; `export PATH=$HOME/.local/bin:$PATH` before `uv`; `uv run n2f …`. No GNU
  `timeout`. A cold kiln build takes about 70 s. `docs/agent-guide.md` is the agent's manual for
  the commands (you are allowed it to drive the tool; judge only what the owner sees).
- Evidence: the exact command and the exact output text, or a file:line. Quote, do not
  paraphrase. Save captures (`*.txt`, `*.png`) under `/tmp/n2f-gate-h/`.
- A verdict per question: BLOCKER, CONCERN or OK; each blocker and concern with the text seen,
  what was wanted, the file:line, and a concrete fix.
- **Write your report file as you go** (append each answer when done) so a cut-off run leaves a
  partial report.

Persona: play a hobby potter with no engineering background, who has a project manager agent
run the tool for them and sees only what `n2f` prints, the report, the board and the package.
Read `README.md` as that person first. Do not read source code until your UX findings are
formed (afterwards only to point fixes at file:line).

Questions (turn each into steps on a copy):
1. **The later → in story.** `examples/kiln/demo-electrical.sh` replays it (run it on a copy as
   its header says; read what it prints). Then live it by hand on another copy: the kiln with
   its wiring left for later, released; a change request that adds the wiring; impact; approve;
   apply; build; check; release again. At each step: is it clear to the owner what the wiring
   is, that it was left out and is now in, what changed, and what is still a person's job?
2. **The cover line.** The package cover and the report's cover/scope lines for `later` and for
   `in`: does "left for later" say what is not included? Does the later Revision's cover say the
   wiring is now included? Does the difference page between the two releases say the wiring
   section was added, in plain words?
3. **The choice.** After the first build with wiring, the supply-headroom choice: how is it put
   to the owner (`n2f status`, the report's "waiting on you")? Does it give both options, what
   each takes and costs, and say who decides (a licensed electrician where the site wiring is
   concerned)? Decide it with `n2f decide` and read status after: does it read as decided?
   Is the choice ever raised before the facts exist (in a fresh interview, before a build)?
4. **Engineering vocabulary.** Every owner-facing line about the wiring (status, the report's
   Wiring section, the manual's wiring pages, warnings, refusals): quote any word a potter
   would not know without explanation (e.g. ampacity, cross-section, TN-S, AC-15, PE, net,
   terminal ids standing alone). Numbers: do they carry their label (given / computed /
   estimate) and units?
5. **Safety reads honestly.** Is it clear the wiring was not reviewed by a licensed electrician
   and that every marked point is theirs to decide? Is anything safety-relevant hidden behind a
   toggle (it must not be)?
6. **The Wiring section and the diagrams.** Open the report from `file://` (no console errors?).
   Do the diagrams look like something an owner could show an electrician, or like a debug
   image? Screenshot the Wiring section and one diagram.
7. **No wiring, no word.** Build the bracket (a product with no wiring) and read status and the
   report: does the word wiring or electrical appear anywhere? It must not.
8. **Errors.** Break the wiring on a copy (a connection to a terminal that does not exist; a
   device naming a part that does not exist; a removed cable entry still named by a circuit):
   does each refusal say in plain words what is wrong, which file, and what to do, with no
   stack trace?

Report: a one-paragraph verdict (READY / NOT READY), one section per question, then the
numbered blockers and concerns. Under 250 lines. Write it to `/tmp/n2f-gate-h/gate-h-report.md`
and return the same text as your final message.
