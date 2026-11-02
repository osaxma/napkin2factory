# Review gate G — engineering, a licensed electrician reading the package (v0.6)

Written by the second overseer from `docs/reviews/TEMPLATE.md` (standing rules + the
engineering set + ELECTRICAL_STAGE.md DoD 9). Fill `[commit]` and `[subject]` before handing
it over; hand the reviewer this text and nothing else.

---

You are a fresh-context reviewer for napkin2factory 0.6 ("the wiring": an electrical domain
that declares a product's supply, devices, terminals and connections, then draws, schedules,
counts and checks them) at `/Users/wakeel/napkin2factory`, branch `main`, reviewing commit
[commit] ("[subject]"). You have not seen the design conversation and are not told the
builders' conclusions. Your job is **review gate G: engineering**, in two parts, in order.

Standing rules:
- Read-only. Change nothing in the repo; do not commit. You may run commands and write under
  `/tmp/n2f-gate-g/` (create it).
- Work on copies. Copy a product before building it (`cp -R examples/kiln /tmp/n2f-gate-g/kiln`,
  then `git init` there if a command asks for change tracking; or
  `uv run python -c "from tests.conftest import copy_product; …"`); never run `n2f build` inside
  `examples/`.
- Environment: macOS; `export PATH=$HOME/.local/bin:$PATH` before `uv`; run the CLI as
  `uv run n2f …` from the repo root with the product path, or from inside the copy with
  `uv run --project /Users/wakeel/napkin2factory n2f …`. No GNU `timeout`. A cold kiln build
  takes about 70 s. `docs/agent-guide.md` §"Command reference" says how to build, check and
  release.
- Evidence for every answer: the exact command and the exact output text, or a file:line.
  Quote, do not paraphrase.
- A verdict per question: BLOCKER (must be fixed before release), CONCERN (goes to the backlog)
  or OK. Each blocker and concern: the exact text or behaviour seen, what was wanted, the
  file:line where it lives, and a concrete fix.
- Commit often is not your concern (read-only), but **write your report file as you go** (append
  each part when done) so a cut-off run leaves a partial report.

## Part 1 — the electrician's read-through (persona; package only)
Build the kiln copy, run its checks, and produce its manufacturer package (a release, e.g.
`n2f release v1.0.0`, or whatever the guide says produces the package a shop receives). Unpack
it into `/tmp/n2f-gate-g/package/`. **From then on, for Part 1, read only
`/tmp/n2f-gate-g/package/` and the copy's `build/electrical/`; never the `model/` files, the
source code, or the repo docs.**
Play a licensed electrician (domestic and light-commercial installations, 230 V single phase,
familiar with appliance wiring, contactors, solid-state relays, thermocouples, earth bonding)
who has been handed this package to wire the kiln's control box and connect it to the site
supply. Answer, with evidence from the package:
1. Could you wire it from this package alone? Walk the power, control and sensing circuits
   terminal by terminal from the diagrams and the schedule; note every point where you would
   have to guess (a terminal not named, a conductor size or colour missing, a route unclear).
2. Do the diagrams, the cable schedule, the terminal labels and the cables-to-buy list agree
   with each other and with the installation manual? List every mismatch.
3. Is the protection clear (the supply's upstream device, any fuse in the box, the limit device,
   the door interlock)? Would the interlock and the limit device actually break the load as
   drawn? Is anything a safety function that the package leaves ambiguous?
4. Earthing: is every exposed metal part's path to earth stated, and is a claimed path through
   a bolted joint marked as something you must verify?
5. Do the warnings and notes read as an engineer's advice that leaves the code judgment to you,
   or do any read as a claim of compliance? Quote any sentence that overclaims.
6. What would you ring the manufacturer about before starting? (The list a real electrician
   would make.)
Save Part 1 as its own section; the overseer keeps it as `examples/kiln/reports/electrician-readthrough.md`
(like `shop-readthrough.md` there), so write it so it stands alone.

## Part 2 — engineering and honesty (the repo)
Now read the repo: `ELECTRICAL_STAGE.md` §0–§2 (what was promised), `docs/electrical.md`,
`src/napkin2factory/domains/electrical/`, `src/napkin2factory/calckit/data/` (the wiring tables),
`tests/fixtures/electrical/`.
7. Are the conductor, earthing and wire-colour tables cited, each row `verify: true`, and shown
   by `make verify-list`? Are the ampacities used as the table says (the right column for the
   installation method; a silicone conductor judged at which temperature)? Any number with no
   source?
8. Are the load current and power computed from the calc kit's `power` pack and dimensionally
   right (units checked, wrong units raise)? Recompute the kiln's load current and the supply
   margin by hand and compare.
9. Do the checks catch what they claim? On copies of the fixtures or the kiln, cause each and
   quote the message: a load above the supply rating, a conductor below the table's
   cross-section, a custom metal part with no path to earth, a circuit with no protective
   device (each must fail, naming the part, the circuit and what to do); an interlock that does
   not break the load path, control and mains conductors through one cable entry (each must
   warn and say a licensed electrician decides).
10. Is anything presented as verified that is only computed? Are the electrical safety
    requirements a person's sign-off (`needs-human`) everywhere, and does the disclaimer say the
    wiring was not reviewed by a licensed electrician?
11. Are the safety requirements complete for the kiln's electrical hazards (shock, overcurrent,
    overtemperature, the door opened while live, loss of earth)? Name any missing.
12. Does the domain name any example's part, parameter, requirement or decision (F9: generic
    words only, "the switching device", "the limit device", …)? Does it read model data only
    through the recording accessors (`ctx.proxy`, `sctx.proxy`, `h.proxy`)?

Report: a one-paragraph verdict (READY / NOT READY), Part 1 (questions 1–6), Part 2 (7–12),
then the numbered blockers and concerns. Under 250 lines. Write it to
`/tmp/n2f-gate-g/gate-g-report.md` and return the same text as your final message.
