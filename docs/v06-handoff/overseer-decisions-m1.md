# Overseer decisions on `docs/v06-baseline.md` §5 (binding for M1 and M5)

Record these as ONE DECISIONS.md entry in M1 ("v0.6 M1: how the wiring model addresses
instances, upstream protection, entries by voltage band", ≤ 10 lines, with its index row), and
cite it where the code applies it. They amend E2 and E3 where they say so.

1. **Instances: connections name devices, not parts (amends E2, E3).** A connection end is
   `device://<id>#<terminal>`. Several device files may name one part when the part is placed
   more than once (two probes of one thermocouple part, five earth studs); `validate_refs`
   refuses more devices naming a part than the product places of it (count its occurrences in
   the assemblies; if a count cannot be had, a warn rather than an error), and refuses two
   devices naming a part placed once. `part://<id>#<terminal>` stays accepted as a shorthand
   when exactly one device names that part; when several do, it is an error naming them and
   asking for `device://`. A device may carry an optional `instance:` (free words, "the
   control probe") said in the diagram and schedule. One part is still one BOM line.
2. **Protection upstream (amends E3, E6).** `supply.yaml` may declare
   `protection: {upstream: "<owner words>", rating: 16 A}` (the site's device, not a part of
   the product) or `protection: part://<id>` (a protective device the product ships). A
   circuit's `protection:` is a part or device URI, or the word `supply` ("protected by the
   supply's device"). The E6 fail "a circuit with no protective device" passes for `supply`
   when the supply declares a rating; a warn then says the site's device and its rating are
   the electrician's to confirm. A circuit fed from another circuit (control from the power
   side) names the device that protects it, or `supply`.
3. **Missing parts** are M5's: the kiln gains bought, BOM-only parts for the box's earth
   terminal, a supply terminal block, the element tails' termination, the SSR heat sink and a
   control-circuit fuse (each with a source and `verified: false`); type K extension cable is
   a product conductor row (E3: a product may add rows). No invented ratings: unknown ones
   are `[verify]` notes.
4. **Cable entries by voltage band (refines E6).** The "mains and control through one entry"
   warn means: extra-low-voltage circuits (sensing, low-voltage control: a circuit whose supply
   or source is ≤ 50 V AC / 120 V DC, IEC 61140 bands `[verify]`) sharing an entry with
   mains-voltage conductors. A 230 V control conductor (the door interlock) through the same
   entry as the element's mains conductors is not warned. PE conductors may share any entry.
   M5 keeps the three holes DEC-024 fixed: mains supply in; element + interlock + bonding leads
   out; sensing out. When the glands become `cable-entry` interfaces the box's three `cutouts`
   leave its kit arguments (no hole cut twice).
5. **Earth paths through joints.** A conductive custom part reaches earth through a PE
   connection to its device or earth point, or through `bonded_via: [iface://<joint>]` in the
   circuits' earth list (a bolted or screwed joint): the latter is a warn ("a bolted joint as
   an earth path is a claim a licensed electrician verifies", E6). Parts that open (a lid, a
   door tray) get a flexible bonding lead in M5, not a `bonded_via`.
6. **Contact ratings.** A device may declare an optional `contact:` rating (`current`, and
   `category`: `resistive` / `AC-1` / `AC-15` / `DC-13` …). M3 warns when a contact switches a
   coil (a device whose role is `control` with `coil` terminals, or `load` with
   `inductive: true`) and its category is not `AC-15`/`DC-13` or is unknown: "a licensed
   electrician confirms the contact suits the coil". Never a fail.
7. **Terminals not sourced** stay `terminals: []` with a lint warn, never invented; a research
   pass is sourcing them for M5.
