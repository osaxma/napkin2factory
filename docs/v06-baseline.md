# v0.6 baseline: the kiln's electrical content before M1 (M0, S-147)

Surveyed by hand on 2026-11-02 on `main` at `7f4d8d0` (S-141), macOS host, from
`examples/kiln/model/` (`parts/*.yaml`, `docs/installation.md`, `docs/assembly.md`,
`docs/maintenance.md`, `decisions.yaml`, `requirements.yaml`, `parameters.yaml`,
`interfaces/`, `assemblies/`). Nothing in the kiln was changed. This is the evidence M5
(`stages/v0.6-electrical-stage.md` §5) types the kiln's wiring from; this file is outside the package, so
the kiln's ids are used freely. Every vendor fact below is `[verify]`: nobody has checked it
against the part in hand.

## 1. Baseline numbers

| what | figure | how |
|---|---|---|
| `make check-full` | **29 min 14 s** (v0.5's figure, S-140), not re-run | `git diff --stat 29951e2 7f4d8d0 -- src tests examples Makefile` prints nothing: the code at the v0.6 start is the code S-140 measured |
| kiln cold build | **69.1 s** wall (57.4 s user, 19.2 s sys), 64 rules rebuilt | a tracked copy (`tests.conftest.copy_product`) in a scratch folder, no `build/`, `uv run n2f build`, `/usr/bin/time -p` |
| kiln report | **3,796,445 bytes** (3.6 MiB) `build/report/index.html`; the limit is 20 MB (D13) | the same build |
| kiln model | 41 part files, 13 interfaces, 4 assemblies (`kiln`, `door`, `controls`, `lining`) | `ls` |
| electrical scope | `scope.electrical: later` (DEC-024) | `n2f.yaml` |

## 2. The powered and electrical parts

Terminal names are the device's own markings where a source gave them; where none could be
read, `terminals: []` and the reason (ELECTRICAL_STAGE §7, risk 3: never invent them).
**Sourcing note:** the makers' sites (`ia.omron.com`, `se.com`, `sensata.com`, Omron's and
Schneider's PDF hosts) refused automated reads (HTTP 403) on 2026-11-02, and the datasheet
PDFs that did download could not be read as text on the host. What is below is what could be
read: Omron's E5CC instruction sheet (text extracted), Omron's EU product page for the D4N,
a third-party pinout page for the D2425, distributor and search-engine excerpts of the makers'
datasheets, and the standards that fix terminal markings. **M5 must confirm every terminal
against the datasheet named in its row before typing it.**

| part id (qty) | what it is | maker / model (as the part file states it) | electrical rating | terminals (source) |
|---|---|---|---|---|
| `pid-controller` (1) | PID temperature controller, 48 × 48 DIN, drives the SSR | Omron E5CC-QX2ASM-800 | supply 100–240 VAC 50/60 Hz, ≈ 5.1 VA; control output 1 "voltage output (for driving SSR): 12 VDC ±20 %, 21 mA"; auxiliary outputs relay SPST-NO 250 VAC 3 A resistive; default input type K thermocouple; terminals take bare wire AWG 24–18 (0.205–0.823 mm²) or M3 crimps ≤ 5.8 mm wide, two per terminal at most (Omron E5CC instruction sheet, `files.omron.eu/downloads/latest/manual/en/1654637-7_e5cc_instruction_sheet_en.pdf`) | **`[]` — not read.** The sheet's terminal diagram is a graphic. A search-engine excerpt of Omron's E5CC quick start guide (H36I, 2013, an earlier E5CC) gives control output 1-2, alarms 7-8-9-10, power 11-12, thermocouple 5-6, polarity not given; it is not the -800's sheet. Confirm against Omron H179 (E5CC-800 datasheet) `[verify]` |
| `limit-controller` (1) | over-temperature limit controller, latching (manual reset), on its own thermocouple | Omron E5CC-RX2ASM-800 | as above, but control output 1 is a relay: "SPST-NO 250 VAC, 3 A (resistive load)", 100,000 operations (same sheet). The contactor coil is an inductive load: the sheet gives no AC-15 rating, and the coil's VA is not on file `[verify]` | **`[]` — not read** (as above). Which output holds the contactor (control output 1 or a latching auxiliary output) is a configuration choice DEC-014 leaves to the electrician |
| `contactor` (1) | 3-pole contactor, two poles used, 25 A, 230 V coil | Schneider Electric LC1D25P7 (TeSys D) | AC-3 25 A at ≤ 440 V; coil 230 VAC 50/60 Hz; auxiliary contacts 1 NO + 1 NC (Schneider datasheet as excerpted by distributors: RS 394-9683, device.report copies) | `A1, A2` (coil); `1/L1, 2/T1, 3/L2, 4/T2, 5/L3, 6/T3` (main poles); `13, 14` (NO aux); `21, 22` (NC aux) — the IEC 60947-4-1 / EN 50012 marking every TeSys D carries; not read from Schneider's own sheet `[verify]` |
| `ssr` (1) | solid-state relay, switches the element | Crydom D2425 (Sensata) | load 24–280 VAC, 25 A; control 3–32 VDC; zero-cross SCR output, SPST-NO (element14 / RS listings). Its heat-sink derating at the element's 10.9 A was not read `[verify]` | `1, 2` (load), `3, 4` (control input) — components101.com's pinout (third-party); which of 3 and 4 is `+` was not read `[verify]` |
| `door-switch` (1, loose) | door safety switch, positive-opening, roller lever | Omron D4N-1120 | "Pg13.5 (1-conduit), 1NC/1NO (snap-action)", roller lever, terminal block, bottom entry (`industrial.omron.eu/en/products/D4N-1120`); 10 A thermal, 3 A at 240 VAC (AC-15) per a search excerpt of Omron's D4N datasheet `[verify]` | **`[]` — not read.** Omron states the numbering follows EN 50013; the exact pairs for the 1NC/1NO snap-action block were not read `[verify]` |
| `thermocouple` (2) | type K, 8 mm ceramic sheath; one for the PID, one for the limit | "generic kiln supplier", K-8MM-CERAMIC-1200 | a sensor: microvolts, no rating | `+`, `-` — the polarity every type K has (IEC 60584-1: NiCr leg positive); the probe's head or lead colours are the supplier's (IEC 60584-3 green `+` / white `-`; ANSI MC96.1 yellow / red) `[verify]` |
| `heating-element` (1) | Kanthal A1 1.6 mm coil, wound on site | Kanthal A1-1.6mm | 2500 W at 230 V (`element-power`, `mains-voltage`): 10.87 A, 21.2 Ω cold (`calc://element.current`, `calc://element.resistance`) | **`[]`**: bare wire; its two tails leave the back wall through the two ceramic bushes. Where and how they terminate is not modelled (§5) |
| `m20-gland` (3) | M20 nylon cable gland, IP68 | "generic electrical wholesaler", M20-GLAND | passes cables; its clamping range is not on file `[verify]` | `[]` (a pass-through, no terminals) |
| `earth-stud` (5) | M6 earth stud with serrated washers | "generic electrical wholesaler", M6-EARTH-STUD | an earth connection point | `[]` (generic part; one connection point, not a marked terminal) |
| `rating-label` (1) | rating and warning label on the box front | local engraving shop, LABEL-KILN-RATING-01 | none: it states "Dedicated 16 A circuit at 230 V. Installation by a licensed electrician only." | not a device |
| `controller-box` (1) | the controls' enclosure, 1.0 mm mild steel, powder coated | custom (sheet metal) | conductive: needs an earth path (it has its own stud) | not a device; three Ø20.5 mm gland holes in its base |
| `controller-lid` (1) | its lid, 1.0 mm mild steel, powder coated | custom (cut sheet) | conductive: needs an earth path (it has **no** stud; four self-tapping screws into the coated box) | not a device |

`ceramic-bush` (2) carries the element tails through the back wall; it is an insulator, not a
device. No part on file is a terminal block, an earth terminal, a supply cable, a protective
device, an isolator or a heat sink (§5).

### 2.1 Terminals sourced after the survey (copied by M5 from `docs/v06-handoff/terminals.md`)

Read on 2026-11-02 by rendering the makers' PDF pages to images and viewing the drawings (the
makers' sites still refused automated reads). Every row is `[verify]`: nobody has checked it
against the part in hand, and three of the four documents came through third-party hosts.

| part | terminals, as the drawing marks them | source |
|---|---|---|
| `pid-controller` (E5CC-QX2ASM-800) | supply 100–240 VAC on **11, 12** (no L/N marking; "no polarity" is printed only under the 24 V version); control output 1, voltage for an SSR (12 VDC, 21 mA), **1 (+), 2 (−)**; auxiliary output 1 **9, 10**; auxiliary output 2 **7, 8**; thermocouple **6 (+), 5 (−)**; 3 and 4 grey (do not wire) `[verify]` | Omron datasheet "E5CC-800/E5CC-B-800/E5CC-U-800", p. 10 "External Connections", screw terminal blocks, via baa.vn and cdn.eicom.ru (no revision printed; cites user's manual H174, not obtained) |
| `limit-controller` (E5CC-RX2ASM-800) | as above, but control output 1 is a relay contact on **1, 2** ("SPST-NO, 250 VAC, 3 A (resistive load)", 100,000 operations); auxiliary outputs SPST-NO 250 VAC 3 A resistive. **No inductive (AC-15, cos φ 0.4) rating found** in the datasheet: the contactor's coil on this contact is unrated `[verify]` | the same page and specification table |
| `door-switch` (D4N-1120) | 1NC/1NO snap-action, direct opening: **NO 13, 14; NC 31, 32**; "Only NC contacts 31-32 have an approved direct opening mechanism"; AC-15 3 A at 240 V (Ie/Ue), DC-13 0.27 A at 250 V `[verify]` | Omron "D4N Miniature Safety Limit Switch", pp. G-220, G-224, G-227 (the maker's own host, files.omron.eu; no revision shown) |
| `ssr` (D2425) | load (output) **1, 2**, no polarity; control (input) **3 (+), 4 (−)**, 3–32 VDC `[verify]` | Crydom "Series 1, 10-90 Amp, 120/240 Vac", FastFax 151, Rev. 102104 (2003), p. 2, via Octopart (an old revision; the current Sensata sheet could not be fetched) |

Not found: the E5CC-800 user's manual H174; whether 11–12 prefers L on one side; the current
Sensata D2425 sheet. The contactor's markings stay those of §2's table (IEC 60947-4-1 /
EN 50012, not read from Schneider's own sheet) `[verify]`.

## 3. The intended connections, as the kiln's documents describe them

The documents give the topology in words; none gives a terminal, a conductor or a length.

- **Supply** (`installation.md` "Power", DEC-006, REQ-008): a dedicated 16 A circuit at 230 V
  single-phase, installed by a licensed electrician, with a residual-current device and a local
  isolator within the operator's reach. All three are the site's, not parts of the kiln.
  Frequency and earthing arrangement are stated nowhere (EU is the region of DEC-006's title;
  50 Hz follows from it `[verify]`).
- **Power circuit** (DEC-014, REQ-018, the contactor's name and notes): supply → the
  contactor's two used poles (line and neutral broken together) → the solid-state relay, in
  series with the contactor → the element → back. "In series with the solid-state relay"
  (contactor notes); the SSR "switches the element" (`installation.md`).
- **Control circuit** (DEC-010, DEC-014, REQ-009, REQ-018, the door switch's and the PID's
  notes): the contactor's coil is held by the limit controller's latching output **and** the
  door switch, in series ("the door switch is in the same contactor coil circuit"; "drops the
  contactor and cuts element power whenever the door is not closed"). The PID's output drives
  the SSR's control input. Both controllers take 230 V for their own supply.
- **Sensing circuit** (the thermocouple's notes, `maintenance.md`): two type K probes through
  the back wall at mid-height; the control probe to the PID, the limit probe to the limit
  controller. They run through the "thermocouple leads" gland.
- **Earth** (`installation.md` "Earth bonding", REQ-019, DEC-023): one stud each on the inner
  shell, the guard, the door guard, the stand and the controller box, on bare metal; "an earth
  lead from each stud to the earth terminal in the controller box"; each below 0.1 Ω to that
  terminal (REQ-019's verify note).

### Which circuit passes each gland

The three holes are `cutouts` in the box's kit arguments (`controller-box.yaml`, face `base`,
`param://gland-hole` 20.5 mm), not interfaces yet.

| cutout label | centre on the base (mm) | carries (the part's notes, `installation.md`) | circuit |
|---|---|---|---|
| `gland-mains` | (-80, -35) | mains in: L, N, PE of the supply cable | power + earth |
| `gland-element` | (0, -35) | element out: the two element conductors | power |
| `gland-thermocouples` | (80, -35) | the two thermocouple pairs | sensing |
| — | — | **the door switch's cable** (230 V, in the coil circuit): no gland is named for it | control |
| — | — | **the four bonding leads** to the shell, guard, door guard and stand studs: no gland is named | earth |

### Which part each earth stud bonds

| stud (listed in) | bonds | metal parts reaching earth only through it, by a bolted joint |
|---|---|---|
| shell (`asm://kiln`, 1 of 3) | `outer-shell` | — |
| guard (`asm://kiln`, 2 of 3) | `guard-shell` | `hinge-post` (`iface://guard-hinge-post`), `latch-keeper` (`iface://guard-latch-keeper`) |
| stand (`asm://kiln`, 3 of 3) | `stand` | — |
| door guard (`asm://door`) | `door-guard` | `door-tray` (`iface://door-guard-standoff`, steel standoffs and bolts) |
| controller box (`asm://controls`) | `controller-box` | `controller-lid` (`iface://controller-lid-seat`, self-tapping screws into powder coat) |

Custom conductive parts: 9 (`outer-shell`, `guard-shell`, `stand`, `door-guard`,
`door-tray`, `hinge-post`, `latch-keeper`, `controller-box`, `controller-lid`); 5 have a stud,
4 do not. Under E6 each of the 4 needs a `bonded_via: iface://…` claim (a warn a person
verifies) or a stud of its own. REQ-019 names the 5 with studs and not the lid, the tray, the
post or the keeper.

## 4. Proposed devices and circuits for M5 (the shapes of ELECTRICAL_STAGE §3)

A starting point, not a design: every terminal marked `# [verify]` must be confirmed against
the datasheet named in §2, and `null` lengths are M5's to measure from the placed geometry.
Conductors are ids of `calckit/data/conductors.yaml` (S-146). Device ids name the part they
are; see §5 for the two thermocouples and the five studs.

```yaml
# model/electrical/supply.yaml
voltage: 230 V
phases: 1
frequency: 50 Hz                   # [verify] not stated in the kiln; EU per DEC-006
rating: param://circuit-rating     # 16 A
earthing: TT                       # [verify] not stated; the manual asks for an RCD, which TT relies on; the electrician says which
region: EU
protection: null                   # the 16 A protective device, the RCD and the isolator are the site's (§5)

# model/electrical/devices/*.yaml
- {id: pid-controller, part: part://pid-controller, role: control, class: II,
   rating: {voltage: 230 V, power: 5.1 VA},
   terminals: []}                  # candidates "1","2" (out 1), "5","6" (TC), "11","12" (supply): not read, §2
- {id: limit-controller, part: part://limit-controller, role: protection, class: II,
   rating: {voltage: 230 V, power: 5.1 VA},
   terminals: []}                  # as the PID; its relay output is 250 VAC 3 A resistive
- {id: contactor, part: part://contactor, role: control,
   rating: {voltage: 230 V, current: 25 A},
   terminals: [A1, A2, L1, T1, L2, T2, L3, T3, "13", "14", "21", "22"]}   # [verify] IEC 60947-4-1 marking (1/L1 → L1)
- {id: ssr, part: part://ssr, role: control,
   rating: {voltage: 280 V, current: 25 A},
   terminals: ["1", "2", "3", "4"]}                                       # [verify] which of 3/4 is +
- {id: door-switch, part: part://door-switch, role: control,
   rating: {voltage: 240 V, current: 3 A},
   terminals: []}                  # 1NC/1NO, EN 50013 numbering, pairs not read
- {id: thermocouple, part: part://thermocouple, role: sensor, terminals: ["+", "-"]}   # x2, §5
- {id: heating-element, part: part://heating-element, role: load, class: I,
   rating: {voltage: 230 V, power: param://element-power},
   terminals: []}                  # bare tails; M5 decides the termination, §5
- {id: earth-stud, part: part://earth-stud, role: earth, terminals: []}                 # x5, §5
- {id: m20-gland, part: part://m20-gland, role: passthrough, terminals: []}            # x3 → cable entries (E4)

# model/electrical/circuits/power.yaml
id: power
purpose: power
protection: null                   # the site's 16 A device (§5)
connections:
  - {from: supply#L, to: part://contactor#L1, conductor: cu-2p5-pvc, length: null, via: iface://<entry-mains>}
  - {from: supply#N, to: part://contactor#L2, conductor: cu-2p5-pvc, length: null, via: iface://<entry-mains>}
  - {from: part://contactor#T1, to: part://ssr#1, conductor: cu-2p5-pvc, length: null}            # [verify] SSR 1/2
  - {from: part://ssr#2, to: part://heating-element#<tail-1>, conductor: cu-2p5-silicone, length: null, via: iface://<entry-element>}
  - {from: part://heating-element#<tail-2>, to: part://contactor#T2, conductor: cu-2p5-silicone, length: null, via: iface://<entry-element>}
  - {from: supply#PE, to: <box earth terminal>, conductor: cu-2p5-pvc, length: null, via: iface://<entry-mains>}  # green-and-yellow
  - {from: <box earth terminal>, to: earth-stud@controller-box, conductor: cu-2p5-pvc, length: null}
  - {from: <box earth terminal>, to: earth-stud@outer-shell, conductor: cu-2p5-pvc, length: null, via: iface://<entry-?>}
  - {from: <box earth terminal>, to: earth-stud@guard-shell, conductor: cu-2p5-pvc, length: null, via: iface://<entry-?>}
  - {from: <box earth terminal>, to: earth-stud@door-guard, conductor: cu-2p5-pvc, length: null, via: iface://<entry-?>}
  - {from: <box earth terminal>, to: earth-stud@stand, conductor: cu-2p5-pvc, length: null, via: iface://<entry-?>}
notes: the contactor breaks line and neutral; the SSR switches the line in series with it (DEC-014)

# model/electrical/circuits/control.yaml
id: control
purpose: control
protection: null                   # the site's 16 A device unless M5 adds a control fuse (§5)
connections:
  # 230 V AC coil path: line → limit output → door switch NC → coil → neutral (DEC-014, REQ-009)
  - {from: part://contactor#L1, to: part://limit-controller#<out-a>, conductor: cu-0p75-pvc, length: null}   # line side, before the poles
  - {from: part://limit-controller#<out-b>, to: part://door-switch#<nc-a>, conductor: cu-0p75-pvc, length: null, via: iface://<entry-?>}
  - {from: part://door-switch#<nc-b>, to: part://contactor#A1, conductor: cu-0p75-pvc, length: null, via: iface://<entry-?>}
  - {from: part://contactor#A2, to: supply#N, conductor: cu-0p75-pvc, length: null}
  # controller supplies, 230 V AC
  - {from: supply#L, to: part://pid-controller#<supply-a>, conductor: cu-0p75-pvc, length: null}
  - {from: supply#N, to: part://pid-controller#<supply-b>, conductor: cu-0p75-pvc, length: null}
  - {from: supply#L, to: part://limit-controller#<supply-a>, conductor: cu-0p75-pvc, length: null}
  - {from: supply#N, to: part://limit-controller#<supply-b>, conductor: cu-0p75-pvc, length: null}
  # 12 V DC drive to the SSR
  - {from: part://pid-controller#<out1+>, to: part://ssr#3, conductor: cu-0p75-pvc, length: null}   # [verify] 3 = +
  - {from: part://pid-controller#<out1->, to: part://ssr#4, conductor: cu-0p75-pvc, length: null}
notes: 0.75 mm² is the largest bare conductor the controllers' terminals take (AWG 18, Omron sheet)

# model/electrical/circuits/sensing.yaml
id: sensing
purpose: sensing
protection: null                   # a sensor circuit carries no supply current
connections:
  - {from: thermocouple@control#+, to: part://pid-controller#<tc+>, conductor: <type K extension cable>, length: null, via: iface://<entry-thermocouples>}
  - {from: thermocouple@control#-, to: part://pid-controller#<tc->, conductor: <type K extension cable>, length: null, via: iface://<entry-thermocouples>}
  - {from: thermocouple@limit#+, to: part://limit-controller#<tc+>, conductor: <type K extension cable>, length: null, via: iface://<entry-thermocouples>}
  - {from: thermocouple@limit#-, to: part://limit-controller#<tc->, conductor: <type K extension cable>, length: null, via: iface://<entry-thermocouples>}
```

Element current against the conductors (arithmetic M2's checks will repeat): 10.87 A on
`cu-2p5-pvc` (17.4 A at 40 °C, method B2) and on `cu-2p5-silicone` (the same floor) passes
with 1.6× margin; 10.87 A against the 16 A circuit is 68 % (DEC-004), the supply-headroom
choice's territory (E11).

## 5. What the survey found that M1 and M5 must decide

1. **One part, several instances.** `thermocouple` (qty 2), `earth-stud` (qty 5) and
   `m20-gland` (qty 3) are one part file each, but each instance is wired differently. E2
   refuses two devices naming one part, and a connection `part://x#+` cannot say which probe.
   M1 must give connections a way to address an instance (connections naming `device://`
   ids, several devices per part up to the part's quantity, or one part file per instance);
   the proposal above writes `thermocouple@control` and `earth-stud@outer-shell` as
   stand-ins. Not decided here.
2. **The supply's protective device is not a part.** The 16 A device, the RCD and the
   isolator are the site's (`installation.md`); E3's `protection: part://…` has nothing to
   name, and E6's "a circuit with no protective device fails" would fail the kiln. M1 needs a
   way to say "protected upstream by the site" (a supply-level protection that is not a part).
3. **Parts the wiring needs that are not on file:** an earth terminal in the box (the manual
   names one); a supply terminal block or the supply cable's entry point; a connection for
   the element tails at the back wall (bare Kanthal tails into high-temperature cable);
   type K extension cable (no row in the conductor table: a product row, E3); a heat sink
   for the SSR at 10.9 A (derating not read); optionally a control-circuit fuse.
4. **Cable entries.** Three glands, five cable runs leaving the box (mains, element,
   thermocouples, the door switch, the four bonding leads). The door switch (230 V control)
   and the bonding leads have no named entry; putting the door switch through the
   thermocouple gland mixes mains-voltage control with sensing (an E6 warn). A fourth hole
   changes the metalwork DEC-024 kept fixed. The switch's own entry is Pg13.5, not M20.
   When the cutouts become `cable-entry` interfaces (E4), the three `cutouts` entries must
   leave the box's kit arguments, or the box gets each hole twice.
5. **Earth paths.** 4 of the 9 custom metal parts reach earth only through a bolted or
   screwed joint (§3); REQ-019 does not name them.
6. **The limit controller's relay switches an inductive coil** on a resistive 3 A rating;
   the coil's VA and the relay's AC-15 rating are not on file `[verify]`.
7. **Terminals not sourced:** both controllers and the door switch (`[]` above). M5 cannot
   type the control and sensing circuits until someone reads Omron H179 (E5CC-800) and the
   D4N datasheet; until then those devices stay `terminals: []` with the lint warn (§7, risk 3).
