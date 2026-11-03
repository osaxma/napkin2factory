# Electrician read-through: the kiln's wiring package (v0.6 gate G, Part 1, 2026-11-03)

A fresh-context reviewer playing a licensed electrician read only the kiln's release package (v1.0.0, built at f67dc06) and its `build/electrical/` outputs, never the model or the code. The full gate report, with the engineering review and the verdict, is `docs/reviews/v0.6-gate-g.md`.


*Read as a licensed electrician (230 V single phase, domestic and light commercial) handed only the release package `kiln-v1.0.0.zip` (unpacked to
`/tmp/n2f-gate-g/package/v1.0.0/`) and the build's `build/electrical/`. Made from a copy of `examples/kiln` at f67dc06: `n2f build`, `n2f check` (exit
0: "6 example sign-offs (not reviews) · 316 OK · 5 not checked · 88 worth a look"), the bolts pick made in the model, then `n2f release v1.0.0
--allow-example-signoffs` ("EXAMPLE SIGN-OFFS: this Revision is a demonstration, not a reviewed design").*

**What I was given.** `electrical/` has four diagrams (power, control, earth, sensing), `schedule.csv` (30 wires), `labels.csv` (60 sleeve labels) and
`cables.csv` (4 cable lines). The installation manual repeats the schedule per circuit, the cable to buy, the labels, a list "What the electrician
decides" and the first-firing tests. Wire counts agree everywhere: 11 control + 8 earth + 7 power + 4 sensing = 30 ("Each of the 30 wires carries a
sleeve"); cable totals re-add exactly (2.5 mm² PVC 0.2+5.6+1.6 = 7.4 m; 0.75 mm² 4.0 m; silicone 2.4 m; Type K 4.8 m).

### 1. Could I wire it from this package alone? Mostly, with guesses at about a dozen points. CONCERN
Walked terminal by terminal:
- **Power.** supply L/N → supply block L/N (power-1/2, 2.5 mm² brown/blue, "Mains in") → contactor 1/L1 and 3/L2 (power-3/4) → 2/T1 → SSR 1 (power-5)
  → SSR 2 → element A (power-6, 2.5 mm² silicone brown); 4/T2 → element B (power-7, silicone blue). Traceable. Guesses:
  - **What "the supply" is.** `schedule.csv`: `power-1,power,the supply terminal L,...,cu-2p5-pvc,2.5,0.3,brown,Mains in`. That is a 0.3 m single core
    leaving the box. The supply lead or fixed cable (type, 3G2.5 flex or not, plug or hard-wired to the isolator, strain relief) is not specified
    anywhere. The manual says "a local isolator within reach" and also "Nothing else may be plugged into that circuit", so plug or fixed wiring is
    left open.
  - **The element end.** power-6/7 land on "Heating element coil ... terminal A/B", but the BOM has a "High-temperature connector for the element
    tails, 2-way ceramic" and two ceramic bushes that the schedule never mentions. The manual leaves "the cover over the element tails' connector at
    the back" to me, and there is no cover part in the BOM: that is a live terminal at the back of the kiln with nothing designed over it.
  - **Terminal crowding.** Supply block N takes five conductors (power-2, power-4 at 2.5 mm²; control-3, control-5, control-9 at 0.75 mm²), L takes
    three, fuse terminal 2 takes three, and the earth bar's one "PE" terminal takes seven 2.5 mm² leads (earth-1…7). No terminal block in the BOM has
    a rating or clamp count ("generic electrical wholesaler TERMINAL-BLOCK-2P", no cost, no rating). I would fit a distribution block and a multi-way
    earth bar.
- **Control.** fuse 1 ← block L (control-1, 2.5 mm²); fuse 2 → PID 11, limit 11, door switch 31 (control-2/4/6, red); block N → PID 12, limit 12, coil
  A2 (blue); door 32 → limit 1 → limit 2 → coil A1; PID 1/2 → SSR 3/4. Traceable. Guesses:
  - **Fuse rating**: "The control fuse's rating, from the contactor coil's and the controllers' draw" is left to me; the BOM says only
    "FUSE-HOLDER-5X20".
  - **SSR drive polarity**: control-10 and control-11 are both **blue** (the DC-control colour) and PID 1 or 2 is not marked + or −; the SSR's 3/4 are
    polarised. The diagram titles this whole circuit "230 V AC", though this pair is the controller's DC output.
  - **Gland positions**: the box drawing has three Ø20.5 holes B1, B2, B3 but no entry names; the manual says only that the door-switch pair uses "the
    middle gland". Which of B1/B3 is "Mains in" and which is "Thermocouple leads in" is not stated.
  - **Door switch mounting**: the assembly sheet lists it "bought, loose", and "The door switch's mounting" is mine to decide. No bracket and no
    actuator position are given.
- **Sensing.** probe + → controller 6, − → 5, Type K extension, green +/white − (the IEC colours). Clear. "Cross-section: not given" is acceptable for
  thermocouple cable.
- **Routing outside the box.** One M20 gland ("Element, door switch and earth leads out") carries 2 silicone cores, 2 door-switch cores and 4
  green-and-yellow cores: 8 loose single cores. A gland does not seal on loose cores, and single-insulated H05V-K/H07V-K cores outside an enclosure
  need a sheath or conduit. No route, sleeving or temperature along the route is given for the leads running to the back of a 1200 °C kiln.

### 2. Do the diagrams, schedule, labels, cable list and manual agree? Yes on topology; 6 mismatches. CONCERN
Diagrams, `schedule.csv`, `labels.csv` and the manual's tables agree wire for wire (same ids, ends, sizes, colours, entries). The mismatches:
1. **The cable to buy has no colours.** `cables.csv`: `cu-2p5-pvc,2.5 mm² PVC,2.5,"PVC, 70 °C (H07V-K class)",7.4,...`. That one line covers 5.6 m
   green-and-yellow, 1.1 m brown and 0.7 m blue (my sum from the schedule). 0.75 mm² is red and blue, and silicone is brown and blue. I buy single
   core by colour. The manual's version also drops the insulation class ("2.5 mm² PVC: 7.4 m (14 wires)").
2. **The element tail connector and bushes** are in the BOM but not in any diagram or the schedule.
3. **The earth test misses parts it claims.** The manual's bonding text gives every part a stud, "the lid and the door tray ... bonded by a flexible
   lead". The first-firing earth test (REQ-019) lists only "inner shell, guard, door guard, stand, controller box", so the lid, the door tray, the
   hinge post and the latch keeper are never measured.
4. **The power circuit's protection** is "Protected by the supply's own protective device." in the manual, but the diagram says "Protected by: the
   breaker of the site's dedicated circuit, with its residual-current device". Neither gives a rating; only `checks.json` says "(rated 16 A)".
5. **The door-switch route is named two ways.** The installation manual says "through the middle gland" and the report says "leaves the box with the
   element's cable". The entry is the same but the gland is not identified on the drawing.
6. **Names.** "Contactor, … 230 V coil terminal 1/L1" reads as a coil terminal; the labels' tags ("contactor:A1") appear on no diagram.

### 3. Protection, interlock, limit device. Breaks the load as drawn; two safety points are ambiguous. CONCERN
- **The upstream device** is the site's 16 A breaker with an RCD. Its type and RCD sensitivity are left to me ("its breaker and residual-current
  device"). That is fine, because it is my call. The given reason, "the drawings assume a TT installation because they ask for a residual-current
  device", does not follow: RCDs are fitted on TN systems too.
- **The fuse in the box** protects the control circuit only. Its rating is not given (see 1).
- **Door interlock and limit.** Both are in series in the coil feed (fuse 2 → door 31-32 → limit 1-2 → A1). Opening either drops the contactor, which
  opens both L (1/L1–2/T1) and N (3/L2–4/T2) to the element. As drawn, **yes, both break the load on both poles.**
- **Ambiguous safety points:**
  - **The limit device's contact.** The check itself warns: "The Over-temperature limit controller ... contact switches the coil of the Contactor ...
    and is rated resistive; such a contact needs AC-15 or DC-13." The manual says "confirm it with the maker, or let it drive a relay rated for a
    coil". The package also never says which output of that controller (control output 1-2 or an alarm output) is the latching trip, how it is
    configured to latch, or whether 1-2 is closed when healthy. The cut-out depends on that configuration.
  - **One switching device for both safety functions.** The contactor alone serves the door and the over-temperature function, with no
    auxiliary-contact monitoring (13-14 and 21-22 are unused). A welded contactor plus a shorted SSR defeats both. The package does not say whether
    this single channel was a deliberate choice.

### 4. Earthing. Every custom metal part has a stated path; the bolted ones are flagged. OK (with item 2.3)
The earth diagram and schedule run a 2.5 mm² green-and-yellow lead from the bar to a stud on the box, lid, guard, inner shell, stand and door guard,
and from the door guard to the door tray. The two bolted-only parts are flagged in the package's `checks.json`: "The Hinge post (steel angle) reaches
earth only through Hinge post onto the guard ... What to do: test the joint's earth continuity, or run an earth conductor to the part; a licensed
electrician decides." (also the latch keeper). The installation manual says the same: "the electrician tests that joint". Two gaps: that joint test is
missing from the first-firing test list (item 2.3), and earth-7 (1.6 m to the door guard, which swings) has no stated flexible loop across the hinge.
"Flexible lead" is said only for the lid and the tray.

### 5. Advice or a claim of compliance? Mostly advice; three sentences overclaim. CONCERN
No sentence claims code compliance. The wiring section says plainly "This wiring was not reviewed by a licensed electrician: a licensed electrician
wires the product to local code". The manual says "The terminal numbers are read from the makers' datasheets; confirm each against the part in hand."
Overclaims (unmeasured states written as facts; the sign-offs are EXAMPLES):
- Safety manual: "The inner shell, the guard, the door guard, the stand and the controller box are each bonded to protective earth with a resistance
  below 0.1 ohm to the earth terminal."
- Safety manual: "The controller enclosure hangs on 40 mm standoffs ... and its inside stays below 50 degC."
- `checks.json` conductor-current@power: "every conductor is rated for it". That is true of a table column whose installation method and ambient the
  package never names; the check reads "2.5 mm² PVC, rated 17.4 A".
- The package README, the drawings and the manuals' disclaimer say "not reviewed by a licensed **engineer**". Only the report's Wiring section says
  licensed *electrician*. The four diagram SVGs carry no disclaimer at all (`grep -c licensed electrical/*/diagram.svg` → 0 each), so a printed
  diagram travels without one.

### 6. What I would ring the manufacturer about before starting
1. The supply lead: cable type and size, plug or hard-wired, and the gland or strain relief for "Mains in".
2. The control fuse rating, and the coil draw of the contactor it was sized from.
3. Which limit-controller output is the latching trip, its contact rating for a coil (AC-15), its configuration (latching, trip 1250 °C), and whether
   a coil-rated interposing relay is intended.
4. The PID's SSR output polarity (terminal 1 or 2 is +), marked on the diagram.
5. Which gland hole (B1, B2, B3) is which entry; how 8 single cores pass one M20 gland; the sheath or conduit for the runs to the door switch, the
   studs and the element tails.
6. The element tails: the connector's position, the cover over it (not in the BOM), and the temperature there, given that the silicone is rated 180
   °C.
7. The door switch bracket and actuator position, so that the door opening opens 31-32.
8. Terminal block and earth bar ratings and clamp counts (5 conductors on N, 7 on PE).
9. The ampacity basis: which installation method and ambient give "2.5 mm² PVC, rated 17.4 A".
10. Earth tests for the lid, the door tray, the hinge post and the latch keeper, and the flexible loop across the door hinge.
11. Whether one unmonitored contactor for both safety functions was deliberate; the earthing system assumed (TN-S, TN-C-S or TT), stated as such rather than inferred from the RCD.

