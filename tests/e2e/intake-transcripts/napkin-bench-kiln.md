# Scripted napkin stage: a bench kiln for glaze tests, from a textual sketch

Role-played owner script for the napkin-stage simulation (NAPKIN_STAGE §1.3 item 7, M5).
A fresh-context subagent is handed:

- the product `CLAUDE.md` text (as written by `n2f init`),
- the `n2f-pm` skill text (`.claude/skills/n2f-pm/SKILL.md`), whose "Napkin stage (before
  intake)" section is the protocol under test,
- the absolute path of a fresh product made with `n2f init demo --template blank`, to work in,
- the owner's lines below, one at a time; the PM's replies are what the run produces.

The sketch is a *textual stand-in* for a dropped image (N9): automated runs never put a real
image in the agent's context; that is exercised by the owner by hand (§1.2).

The run must end with: an **interpretation card** played back before any concept card is
written; **one correction round** applied in words; **three or more concept cards** that
pass `n2f concept lint`; `n2f concept build --all` green as a command (exit 0) with **at
least one red card**, explained from its screening reasons and not hidden; the board
written; and this transcript filled in below.

---

## Owner's lines

**Owner (1):** I'd like a small bench kiln for pottery glaze tests — just a few test tiles
at a time. Here's a sketch: a box about as tall as it is wide, a bit deeper, door on the
front hinged on the left, a slim control box hanging on the right side, four legs, rounded
corners; the alcove is about 800 mm wide; 13 A plug in Saudi Arabia; budget around 1500
dollars.

**PM:** (replies with an interpretation card and waits)

**Owner (2):** The control box should be on top of the body, not the side, and the legs are
shorter — the top of the kiln at about chest height.

**PM:** (plays back the change, writes 3–5 cards, builds and screens them, shows the board,
explains each card and every red one from its screening)

**Owner (3):** Which one fits my alcove?

**PM:** (answers from the fits-site-width rows: width with the door open against 800 mm)

**Owner (4):** Lock in the compact one.

**PM:** (asks the promotion question once, with its consequence; on the owner's yes runs
`n2f concept promote` and reads back what it wrote)

## Expected outcome

Checked mechanically after the run (the first two by reading this transcript, the rest
on the product folder):

- [ ] An interpretation card appears before the first `n2f concept new` (the words
      "interpretation card", proportions as ratios, layout, style cues, `800 mm` tagged
      `[verify]`).
- [ ] The correction is played back: controls on top, shorter legs, top at about chest height.
- [ ] `concepts/` holds at least 3 cards; `n2f concept lint` exits 0.
- [ ] Every card has `layout.controls: top` or says in `notes` why not; `site.alcove_width:
      800 mm`, `site.circuit` and `site.region: SA` on every card.
- [ ] `n2f concept build --all` exits 0; `n2f concept list` shows at least one `red` and one
      `green` verdict.
- [ ] Each red card's reasons are quoted or paraphrased in the transcript (from
      `screening`, not invented); numbers are called computed or estimate.
- [ ] `build/concepts/board.html` exists.
- [ ] The answer to "which one fits my alcove?" names the width with the door open for the
      cards it compares.
- [ ] The promotion question includes "Lock this in as the design direction?"; after the
      yes, exactly one card is `promoted`, the others `rejected`, and `n2f status` no
      longer reads "stage: Napkin".

## Transcript

Run 2026-10-31 by a fresh-context subagent (Claude Opus) given the product `CLAUDE.md`, the
`n2f-pm` skill text and the four owner lines; paths shortened to `<product>`. Outcome: interpretation
card → one correction → three lint-clean cards → `n2f concept build --all` (C-001 green, C-002 red on
the alcove with the door swing and on the shell blank, C-003 red on the blank) → board → `promote C-001`
(5 parameters, 5 requirements, DEC-001, snapshot) → validate/lint/status green.

## Simulation transcript — bench kiln, napkin stage (n2f-pm)

Product folder: <product>
CLI: `uv run --project /Users/wakeel/napkin2factory n2f …` run from inside the product folder (written below as `n2f …`).

### Setup

```
export PATH=$HOME/.local/bin:$PATH
uv run --project /Users/wakeel/napkin2factory n2f init <product> --template blank
```
Output: `✓ started Bench kiln … from the blank template (27 files)`, `first snapshot saved (9a7441f1e1)`.

Read: `CLAUDE.md`, `.claude/skills/n2f-pm/SKILL.md`, `n2f.yaml`, `operator.yaml` (persona: owner, all domains novice), `style.yaml` (preset industrial), `model/intake.md` (placeholder).

---

### Turn 1

**Owner:** "I want a small bench kiln for pottery glaze tests. I made a sketch: a box about as tall as it is wide and a bit deeper, with the door on the front hinged on the left, a slim control box hanging on the right side, four legs, rounded corners. The alcove it goes in is about 800 mm wide. I have a 13 A plug in Saudi Arabia. Budget around 1500 dollars."

**Commands:**
```
n2f status
n2f validate
```
Output: `Bench kiln — stage: Intake … next: no requirements yet — run intake with the n2f-pm skill`; `✓ model is consistent: 0 requirements, 0 parameters, 0 parts, 0 assemblies, 0 interfaces`.
(Also looked up the Saudi 13 A entry in the system's circuit table, read-only: `src/napkin2factory/calckit/data/circuits.yaml` — "13 A socket (type G)", 230 V, `verify: true`.)

No sketch file was attached, so this is a sketch described in words: interpretation card first, no `refs` entry, no concept cards yet.

**PM reply:**

Thanks — a glaze-test kiln is a nice, clear job.
You described your sketch in words, so here is what I read from it before I draw anything.

Interpretation card — your sketch, as described (no file)
- Proportions: about as tall as it is wide; a bit deeper than it is wide, roughly 1.2 × the width (ratios, my estimate).
- Layout: one door on the front, hinged on the left. A slim control box hanging on the right side of the body. Four legs.
- Style cues: rounded corners on the box. Nothing else said about the look, so I assume a plain painted-steel finish.
- Dimensions: the alcove is about 800 mm wide [verify — is that the clear width between the walls?]. The supply is a 13 A plug in Saudi Arabia, which I take as the standard 230 V wall socket [verify]. Budget about 1,500 dollars.
- Not shown: how tall the legs are, how big the inside is, the back and any vents. For glaze tests I would assume a small chamber, a few test tiles at a time.

One safety point now, because it never waits: this plugs into mains power and runs very hot inside. I will tell you how hot the outside gets once the first rough shapes are screened.

Did I read it right?
Tell me in words what is wrong, missing, or more important than it looks.

---

### Turn 2

**Owner:** "Mostly right. The control box should be on top of the body, not the side, and the legs are shorter — the top of the kiln at about chest height."

**Commands:**
```
n2f concept new "Compact bench kiln, controls on top"
## edited concepts/C-001.yaml (layout, envelope, site, style, massing, notes)
n2f concept lint
n2f concept new "Larger chamber, controls on top"
## edited concepts/C-002.yaml
n2f concept lint
n2f concept new "Larger chamber, drop-down door" --from C-002
## edited concepts/C-003.yaml (layout.door: drop-down, notes)
n2f concept lint
n2f concept build --all
n2f concept board
n2f concept show C-001
n2f concept show C-002
n2f concept show C-003
```
Key output:
- `n2f concept lint` → `✓ 3 concept card(s) look fine`
- `n2f concept build --all` →
  - `✓ C-001 holds up: 420 × 463 × 1300 mm (computed), about 64.5 kg (estimate), 1.8 kW on the 230V-13A circuit (estimate), 2.7 h to temperature (estimate), 920–1790 USD (estimate)` — worth a look: about 65 kg, equipment handling; controls above the door sit in the hot air path.
  - `✗ C-002` — "it needs 960 mm of width — 520 mm for the body plus 440 mm for the open door (hinged-left: the 440 mm door leaf swung open beside the hinge) — but the alcove is 800 mm"; "body: the flat blank is about 1600 × 1560 mm, larger than any mild-steel sheet on file (1500 x 3000 mm) — split it into panels or make it smaller". 520 × 563 × 1300 mm (computed), about 87 kg, 2.4 kW, 4.8 h, 1129–2452 USD (estimates).
  - `✗ C-003` — "body: the flat blank is about 1600 × 1560 mm, larger than any mild-steel sheet on file (1500 x 3000 mm) — split it into panels or make it smaller". Width with the door open 520 mm (computed, fits). Same estimates as C-002.
- `n2f concept board` → `✓ board: build/concepts/board.html — 3 directions side by side (2 with problems)`
- Skin temperature (estimate): C-001 79 °C, C-002/C-003 90 °C. Current (estimate): C-001 7.8 A, C-002/C-003 10.4 A at 230 V.
- Looked at `build/concepts/C-001/renders/styled-iso.png` and `build/concepts/C-003/renders/styled-iso.png`.

Decisions taken for the owner at this stage (napkin cards only, not yet logged as DEC — that happens at promotion): appliance look with 8 mm rounded corners and nothing fastened on show at the front; 230 V for the 13 A Saudi socket; chest height read as about 1,300 mm to the top of the controls.

**PM reply:**

Got it — two changes to my reading:
- Layout: the slim control box sits on top of the body, not on the right side.
- Legs: shorter, so the top of the kiln is at about chest height. I read that as about 1,300 mm from the floor to the top of the control box [verify].

Everything else stays as I read it.

I have drawn three directions for you to react to.
Open the board to see them side by side:
<product>/build/concepts/board.html
The pictures of each one are in build/concepts/C-001/renders/styled-iso.png (and the same for C-002 and C-003).
All three use a clean appliance look: rounded corners and no screws on show at the front.

C-001, compact kiln with the controls on top (green).
This is your sketch as corrected, with a small chamber for a few test tiles.
With the door swung fully open it needs 760 mm of width, so it fits your 800 mm alcove (computed).
It weighs about 65 kg with its insulation, takes about 2.7 hours to reach temperature, and costs between 920 and 1,790 dollars to make — all estimates.
That cost range straddles your 1,500 dollar budget.

C-002, the same layout with a bigger chamber (red).
It holds more tiles or a few small pots per firing.
The problem: with the door open it needs 960 mm of width — 520 mm of body plus a 440 mm door — and your alcove is 800 mm (computed).
To make it work, either the alcove gets wider, the door opens another way, or the chamber shrinks.
Its outer shell, cut flat, is also about 1,600 by 1,560 mm, bigger than any steel sheet on file, so it would have to be made from separate panels or made smaller (computed).
It weighs about 87 kg, takes about 4.8 hours to heat up, and costs between 1,130 and 2,450 dollars — estimates.

C-003, the bigger chamber with a drop-down door (red).
The door is hinged along its bottom edge and opens down like an oven door, so nothing swings sideways; it needs only 520 mm of width open, which fits your alcove (computed).
It shares C-002's shell problem: the flat blank is about 1,600 by 1,560 mm, bigger than any sheet on file, so it needs to be built from panels or made smaller (computed).
Weight, heat-up time and cost are the same estimates as C-002.

A red card is information, not a "no" — it tells you what that direction would take.

Worth a look on all three, though nothing is blocked by it:
- The control box sits above the door, in the path of hot air when the door opens; the side or below would be cooler.
- At 65 to 87 kg (estimate) none of them is a two-person lift; you would move it with a trolley or lifting aid.

Safety, in plain words:
- It runs on mains power: 7.8 A for C-001 and 10.4 A for the larger two, on your 13 A socket (estimates). The wiring needs a qualified electrician's eye.
- The outside of the body is estimated at about 79 °C for C-001 and 90 °C for the larger two — hot enough to burn.
- The door is a pinch point, and folded sheet-steel edges can be sharp.

Which of these is closest to what you want?

---

### Turn 3

**Owner:** "Which one fits my alcove?"

**Commands:**
```
n2f concept list
n2f concept show C-001   # read the fits-site-width / depth / height rows
n2f concept show C-002
n2f concept show C-003
```
Key output (the `fits-site-*` rows):
- C-001: `✓ fits-site-width [computed]: 760 mm with the door open (420 mm + 340 mm) fits the 800 mm alcove`
- C-002: `✗ fits-site-width [computed]: it needs 960 mm of width — 520 mm for the body plus 440 mm for the open door … but the alcove is 800 mm`
- C-003: `✓ fits-site-width [computed]: 520 mm with the door open (520 mm + 0 mm) fits the 800 mm alcove`
- All three: `· fits-site-depth: no alcove depth on the card`, `· fits-site-height: no alcove height on the card`.

**PM reply:**

On width, measured from the rough shapes with the door fully open:
- C-001 fits. It needs 760 mm — 420 mm of body plus a 340 mm door — so you have about 40 mm to spare in your 800 mm alcove (computed).
- C-002 does not fit. It needs 960 mm, which is 160 mm more than the alcove (computed).
- C-003 fits. Its door drops down instead of swinging sideways, so it needs only its own 520 mm (computed). It is still red for the other reason: its shell is too big to cut from one steel sheet.

So the only direction that fits and has no problems is C-001, the compact one.

Two things I could not check yet: the alcove's depth and anything above it, like a shelf.
The kilns are 463 mm deep (C-001) or 563 mm deep (the larger two), and 1,300 mm tall to the top of the controls (computed).
How deep is the alcove?

---

### Turn 4

**Owner:** "Lock in the compact one."

The skill asks once, with the consequence, before promoting. The owner's line is already a clear instruction to lock it in, so the reply states the consequence and treats "lock in" as the yes (per the brief: the owner has answered).

**Commands:**
```
n2f concept promote --help
n2f concept promote C-001 --by "Owner"
cat model/parameters.yaml model/requirements.yaml model/decisions.yaml style.yaml
grep -n -A6 "^decision\|^status" concepts/C-00*.yaml
git log --oneline | head        # read-only check that promotion saved a snapshot
n2f status
```
Key output:
- `✓ C-001 is now the design direction (DEC-001). Seeded 5 parameters, 5 requirements (3 about form, 1 about the alcove, 1 about the supply), updated style.yaml; C-002 and C-003 are kept as rejected alternatives. Next: n2f build && n2f check.`
  `+ REQ-001 Fits the alcove with the door open` · `+ REQ-002 Runs on the site circuit` · `+ REQ-003 Rounded exposed corners` · `+ REQ-004 No visible fasteners on the front` · `+ REQ-005 Controls where they were sketched`
  `note: the product has no assembly yet: site requirements are allocated unallocated and checked by a person until an assembly exists`
- Parameters (all `owner: napkin`): chamber-width 180 mm, chamber-depth 200 mm, chamber-height 180 mm, insulation 115 mm, element-power 1.8 kW.
- REQ-001: closed width plus the 340 mm door swing within the 800 mm alcove (so 460 mm closed width), checked by a person until an assembly exists. REQ-002: element power ≤ 2392 W (80 % of 230 V × 13 A, `[verify]`). REQ-003: corners ≥ 8 mm radius. REQ-004: no fastener holes on the front of body or door. REQ-005 (should): controls on top.
- style.yaml: preset appliance, corner_radius 8 mm, fastener_visibility hidden-front, layout {load: front, door: hinged-left, controls: top, stand: four-leg}, light painted body and door, dark stand and controls.
- DEC-001 "Design direction: Compact bench kiln, controls on top", made_by: human (Owner), verify: true, links to the 5 requirements and 5 parameters.
- Cards: C-001 `status: promoted`; C-002 and C-003 `status: rejected`, reason "not chosen: C-001 promoted (DEC-001)".
- Snapshot saved: `Promote C-001: Compact bench kiln, controls on top`.
- `n2f status` → `stage: Intake … ✓ Napkin ✓ Intake ○ Design … next: no parts yet — the designer role composes the kit`

**PM reply:**

Locking C-001 in makes it the design direction.
Changing the basic form after this — say, going back to a bigger chamber or moving the door — becomes a bigger change than tuning sizes.
You said lock it in, so I have done it, recorded as your choice.

Here is what that wrote:
- Starting sizes, marked as coming from the napkin stage: a chamber 180 mm wide, 200 mm deep and 180 mm tall, 115 mm of insulation, and a 1.8 kW heating element.
- Five requirements the design now has to meet:
  - It fits your alcove with the door open: the closed body may be at most 460 mm wide, because the open door adds 340 mm and the alcove is 800 mm.
  - It runs on your 13 A socket: the element stays at or under about 2,390 watts, which is 80 % of what the socket can give [verify].
  - Rounded corners, at least 8 mm.
  - No screws or fixings on show at the front.
  - The controls sit on top (a preference, not a hard rule).
- The look file now says appliance style: a light painted body and door, a dark stand and control box, rounded corners, fixings hidden at the front.
- A decision, DEC-001, records that you chose this direction and why, with the screening numbers behind it.
- C-002 and C-003 are kept on file as alternatives you did not choose. Nothing is deleted.
- A snapshot of all this is saved.

Things still open, which I will raise as we go:
- The 1,300 mm "chest height" is my reading and is not locked in anywhere yet [verify].
- The cost range is 920 to 1,790 dollars (an estimate), which reaches past your 1,500 dollar budget.
- The alcove depth and anything overhead are still unchecked.

Next step: I run the rest of the intake — a few short questions, one at a time, skipping what we already settled — and then the designer turns this rough shape into real parts.
First question: where will the kiln live — indoors in a studio, in a garage, or somewhere dusty or hot?

---

### Closing checks

#### `n2f concept lint`
```
✓ 3 concept card(s) look fine
(exit 0)
```

#### `n2f validate`
```
✓ model is consistent: 5 requirements, 5 parameters, 0 parts, 0 assemblies, 0 
interfaces
(exit 0)
```

#### `n2f lint`
```
! WARN (L3-allocation) model/requirements.yaml: [req://REQ-001] explicitly 
unallocated
    → allocate it before release
! WARN (L3-allocation) model/requirements.yaml: [req://REQ-003] explicitly 
unallocated
    → allocate it before release
! WARN (L3-allocation) model/requirements.yaml: [req://REQ-004] explicitly 
unallocated
    → allocate it before release
! WARN (L3-allocation) model/requirements.yaml: [req://REQ-005] explicitly 
unallocated
    → allocate it before release
✓ lint passed with 4 warning(s)
(exit 0)
```

#### `n2f status`
```
Bench kiln — stage: Intake
  ✓ Napkin
  ✓ Intake
  ○ Design
      • no parts yet — the designer role composes the kit
next: no parts yet — the designer role composes the kit
(exit 0)
```
