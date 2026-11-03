# Wiring (the `electrical` domain)

The agent's reference for a product's wiring, as `docs/kit.md` is for the part kit and
`docs/calckit.md` for the calc kit. It describes the domain as built in v0.6
(`src/napkin2factory/domains/electrical/`, registered through `docs/domains.md` and nothing
else). The domain's name is `electrical`, the key of `scope.electrical` in `n2f.yaml`; the
owner's word for it is **wiring** ("Wiring: done here").

## What it is, and what it is not

- **Wiring-level.** A supply, devices with ratings and terminals, connections between
  terminals, conductors from a cited table, protection, earthing, interlocks: what an
  appliance, a panel, a machine or a bench tool needs, and what an electrician reads to wire it.
- **No circuit boards.** No board layout, footprints or fab rules. A product that needs a
  board treats it as a bought part with terminals, like any controller.
- **Data is the source.** Everything is YAML under `model/electrical/`; building, checking and
  reading need no desktop tool. The text schematic (`<circuit>.kicad_sch`) is an export,
  never a source.
- **Advisory, never a licence.** The checks fail only on arithmetic and topology that is
  certain (a load above the supply, a conductor too thin for its current, a metal part with
  no path to earth, a circuit with no protection). Everything a wiring code would judge is a
  warning whose fix ends "a licensed electrician decides". Every safety requirement about the
  wiring stays a person's sign-off (`kind: manual`), and the report says the wiring was not
  reviewed by a licensed electrician.

Not in v0.6: three-phase rules, motors with starters, drives, DC power trees (the schema
takes `phases: 3` and `dc: true`; no rule reads them beyond the supply's terminals),
voltage-drop and short-circuit sums, claims of compliance with any wiring code, conductor
lines in the parts list (the domain's own `cables.csv` lists the cable to buy, S-145).

## The files

| file | URI | what it is |
|---|---|---|
| `model/electrical/supply.yaml` | `supply://supply` | the one supply the product plugs into |
| `model/electrical/devices/<id>.yaml` | `device://<id>` | a wired thing, naming the part it is |
| `model/electrical/circuits/<id>.yaml` | `circuit://<id>` | a list of connections, its protection, its earth paths |
| `model/electrical/conductors/<id>.yaml` | `conductor://<id>` | a conductor the calc kit's table lacks (optional) |
| `model/interfaces/<id>.yaml`, `kind: cable-entry` | `iface://<id>` | where wiring crosses a box: one hole, the circuits through it |

A device names its part (`part: part://<id>`): the part stays one line of the parts list and
the one thing the mechanical model places; the device file adds what the wiring needs. Every
field is optional for a product without wiring: no `model/electrical/` folder, no wiring row
or word anywhere.

## A complete small example

The smallest wired product (`tests/fixtures/electrical/minimal/`): a heater and a two-pole
switch in a plastic box, fed from a socket circuit through one cable gland. Besides its parts
(`box`, `gland`, `heater`, `switch`), its assembly and its parameters, the wiring is four files
and one interface:

```yaml
# model/electrical/supply.yaml: what it plugs into
voltage: 230 V
phases: 1
frequency: 50 Hz
rating: param://supply-rating          # 10 A: the circuit's rating, a parameter the owner gave
earthing: TN-S                         # an arrangement of the calc kit's earthing table
region: EU                             # the key into the calc kit's circuit and conductor tables
protection: {upstream: "the 10 A breaker of the socket circuit", rating: 10 A}
notes: A socket circuit; the electrician confirms its breaker and its earthing.
```

```yaml
# model/electrical/devices/heater.yaml
id: heater
part: part://heater
role: load
rating: {voltage: 230 V, power: 500 W}
terminals: [L, N, PE]
class: I
```

```yaml
# model/electrical/devices/switch.yaml: two poles, each a pair of terminals inside it
id: switch
part: part://switch
role: control
rating: {voltage: 250 V, current: 10 A}
terminals: ["1", "2", "3", "4"]
class: II
contact: {current: 10 A, category: AC-1}
through: [["1", "2"], ["3", "4"]]
```

```yaml
# model/electrical/circuits/heater.yaml
id: heater
purpose: power
name: Heater
protection: supply                     # the supply's own device protects it
connections:
  - {from: "supply://supply#L", to: "device://switch#1", conductor: cu-1p5-pvc, length: 0.4 m, via: iface://box-entry}
  - {from: "supply://supply#N", to: "device://switch#3", conductor: cu-1p5-pvc, length: 0.4 m, via: iface://box-entry}
  - {from: "device://switch#2", to: "device://heater#L", conductor: cu-1p5-pvc, length: 0.2 m}
  - {from: "device://switch#4", to: "device://heater#N", conductor: cu-1p5-pvc, length: 0.2 m}
  - {from: "supply://supply#PE", to: "device://heater#PE", conductor: cu-1p5-pvc, length: 0.5 m, via: iface://box-entry, colour: green-and-yellow}
notes: The switch breaks line and neutral.
```

```yaml
# model/interfaces/box-entry.yaml: the joint between the box and the wiring
id: box-entry
kind: cable-entry
parties: [part://box, part://gland]    # the box gets the hole; the gland sits in it
name: Supply cable into the box
description: The supply cable enters the box through the gland in its top.
frames:
  part://box: {origin: [0, 0, 40], normal: [0, 0, 1], x_axis: [1, 0, 0]}
  part://gland: {origin: [0, 0, 0], normal: [0, 0, 1], x_axis: [1, 0, 0]}
spec: {diameter: param://entry-hole, passes: [circuit://heater]}
```
Both `part://box` and `part://gland` list `iface://box-entry` under their `interfaces:`, as
for any joint. Its safety requirement ("A licensed electrician checks the wiring before the
box is first switched on") is `kind: manual`, `safety: true`, `tags: [electrical]`.

## Connection ends

A connection joins two terminals: `{from: <end>, to: <end>}`. An end is
`<scheme>://<id>#<terminal>` (S-154), parsed by the domain, so a terminal may be any name
without a space or `#` (`L`, `PE`, `A1`, `13`, `+`, `TC-`, `1/L1`):

| end | is |
|---|---|
| `device://<id>#<terminal>` | a device's terminal: the usual form |
| `part://<id>#<terminal>` | shorthand, only when exactly one device names that part |
| `supply://supply#<terminal>` | the supply's: `L`, `N`, `PE` for one phase; `L1`–`L3`, `N`, `PE` for three; `+`, `-`, `PE` for DC; or the supply's own `terminals:` |
| `asm://<module>#<terminal>` | a module supplied, not built here (`build: external`), reached only through one of its ports |

`n2f validate` refuses an end whose device does not exist or has no such terminal, naming the
file, the connection and the terminals the device has.

## The fields

**Supply** (`supply.yaml`): `voltage` (required), `phases` (1 or 3), `frequency`, `dc`,
`rating` (the supply circuit's current, a quantity or `param://`), `earthing` (TN-S, TN-C-S,
TT or IT, from `calckit/data/earthing.yaml`), `region` (EU, US, UK, SA, AU: the key into the
circuit and conductor tables), `protection` (the site's device, `{upstream: "<words>",
rating: 16 A}`, or `part://`/`device://` of a protective device the product ships),
`terminals`, `dedicated` (true: the supply circuit serves this product alone, which is how
the model records that pick of the supply-headroom choice, S-171) and `notes`.

**Device** (`devices/<id>.yaml`): `id`, `part` (required, must exist), `role` (`supply`,
`load`, `control`, `protection`, `sensor`, `earth`, `passthrough`), `rating` (`voltage`, and
`current` or `power`), `terminals` (the maker's markings; `[]` until read from the
datasheet, a warning, never invented), `class` (I, II, III), `instance` (words for one of
several placements of one part: several devices may name a part the assemblies place that
many times), `contact` (`current`, `category`: AC-1, AC-3, AC-12, AC-14, AC-15, DC-1, DC-12,
DC-13 or `resistive`), `coil` (the coil's two terminals), `inductive` (an inductive load),
`safety` (`interlock`: the load must not run while it is open; `limit`: it cuts the load
above a limit), `through` (the terminal pairs a current passes inside the device: a pole, a
contact, a fuse; the checks walk the wiring through them), `notes`. A `passthrough` (a
terminal block, a connector) joins its pairs always; any other device's pair is a contact,
and a device with a `coil` closes its contacts only while the coil is live.

**Circuit** (`circuits/<id>.yaml`): `id`, `purpose` (`power`, `control`, `sensing`,
`earth`), `name` (the owner's words), `protection` (`part://`, `device://` or `supply`),
`voltage` and `dc` (when the circuit works at another voltage than the supply, such as a
24 V DC sensor loop: the entry check reads it), `connections` (each `from`, `to`,
`conductor`, `length`, `via`, `colour`), `earth` (parts that reach earth through a joint:
`{part: part://<id>, bonded_via: [iface://<joint>]}`), `notes`.

**Conductor** (`conductors/<id>.yaml`, only for a conductor the calc kit lacks): `id`,
`label`, `csa`, `ampacity`, `ambient`, `basis`, `insulation`, `max_temp`, `kind` (`panel`,
`cord`, `high-temp`, `sensing`), `region`, `source` (required) and `verify` (true until a
person confirms the row). A sensing cable may leave `ampacity` out.

A connection's `conductor` is an id of `calckit/data/conductors.yaml` (EU `cu-0p75-pvc` …
`cu-4p0-pvc` and the `-silicone` rows; US `awg18-mtw` … and the `-sf2` rows) or of the
product's own rows; an id on neither is a validation error listing the known ones.

## Cable entries: the joint between the box and the wiring

A cable entry is an interface of kind `cable-entry`: the box (the party that gets the hole)
and the gland or bushing in it. Its spec is the bolt-pattern spec with one hole (S-144,
S-155):

```yaml
spec: {diameter: 20.5 mm, passes: [circuit://power, circuit://earth]}
```
- `count` is 1 (the default; any other number is refused: one entry per hole);
- `diameter` is the hole, a quantity or `param://`;
- there is no `pattern:` to write: the hole sits at the frame's origin; a `circle` pattern is
  refused with the fix;
- `passes` lists the circuits that cross here.

The core cuts the hole in every party that has a shape, matches the parties and lines the
joint up, as for a bolt pattern; a bought gland with no shape is skipped with the core's
sentence. Then the entry's own check runs: a circuit under `passes` that does not exist, or
that has no connection going `via` this entry, fails; an empty `passes` is worth a look.
Every connection that crosses the box names its entry with `via: iface://<id>`.

## A box supplied, not built here: a module with cable-entry ports

When the control box is bought wired (or another team builds it), the wiring's scope stays
`in` and the box is a stand-in sub-assembly, `build: external`, with no children and its
cable entries as its ports (`tests/fixtures/scope/external-box/`):

```yaml
# model/assemblies/control-box.yaml
id: control-box
rev: A
name: External control box
build: external
ports: [iface://mains-entry, iface://control-entry]
```
```yaml
# model/interfaces/mains-entry.yaml: the product's box to the stand-in
id: mains-entry
kind: cable-entry
parties: [part://box, asm://control-box]
name: Heater cable to the control box
description: The heater's cable leaves the box through the gland in its back, to the control box.
frames:
  part://box: {origin: [-60, 150, 150], normal: [0, 1, 0], x_axis: [1, 0, 0]}
spec: {diameter: param://mains-hole, passes: [circuit://power]}
```
A circuit reaches the stand-in by its terminals, `asm://control-box#L`, and only through one
of its ports (`via:`); anything else is a validation error naming the file, the port and the
circuit. Each circuit's diagram draws the box as a dashed boundary with its terminals and
nothing inside, said as every other surface says a stand-in: supplied, not built here.

## What a build writes

`n2f build` runs the `elec` family after the parts and before the manuals (`n2f build
--target elec` runs it and what it waits for). Under `build/electrical/`:

| file | what it is |
|---|---|
| `<circuit>/connections.json` | the circuit's record: devices, wires, entries, protection; everything below is drawn from it |
| `<circuit>/diagram.svg` | the wiring diagram: devices as labelled boxes in columns from the supply, each wire labelled "id · size · colour", cable entries as dashed boxes, a module supplied, not built here as a dashed boundary |
| `<circuit>/<circuit>.kicad_sch` | a text schematic export (never a source) |
| `schedule.csv` | one row per wire: wire, circuit, from, to, conductor, cross-section, length, colour, via |
| `labels.csv` | one terminal label per wire end (`<wire> <device>:<terminal>`) |
| `cables.csv` | the cable to buy: total length per conductor (one unknown length makes it "not given") |

A wire's colour is the connection's own, else the region's colour for PE, N or a line
terminal, else a control circuit's control colour, else "not given": never a guess. The
diagrams, `schedule.csv`, `labels.csv` and `cables.csv` go in the release package under
`electrical/` ("wiring diagrams, cable schedule, terminal labels").

## The checks

`n2f check` runs the `electrical` stage (after the interface checks) from
`checks/electrical-v0.yaml`. Rows are `elec-rule://<rule>@<thing>`, kind `electrical`:

| rule | status when it does not hold | what it checks |
|---|---|---|
| `supply-load` | fail | the power circuits' loads, added up, against the supply's rating |
| `conductor-current` | fail | each conductor's rated current (the table's ampacity) against its circuit's load current |
| `earth-path` | fail | each custom part of a conductive material reaches the supply's earth by a conductor, or names the joints that bond it to a part that does (a warn when its material is unknown); every device Class II or III: one pass row |
| `protection` | fail | each power and control circuit names a protective device whose rating is not below its load (`supply` passes when the supply has a rating) |
| `terminal-conductors` | fail | a terminal holding more conductors than its device allows; no device field declares the limit yet (B-0137), so it writes no row |
| `interlock-series` | warn | with the interlock open, does any load still get power? |
| `limit-independent` | warn | with the controller and what it drives stuck on, does opening the limit device still cut every load? |
| `entry-voltage` | warn | extra-low-voltage (≤ 50 V AC, ≤ 120 V DC) and mains conductors through one entry; earth may share any entry |
| `contact-category` | warn | a contact wired straight to a coil needs AC-15 or DC-13; to an inductive load AC-3, AC-15 or DC-13 |
| `earth-bonded` | warn | a part earthed only through bolted joints: a continuity test a person makes |
| `upstream-protection` | warn | the supply's protection is the site's device: the electrician confirms it and the earthing |
| `terminals-unsourced` | warn | a device whose terminals are not listed yet |
| `supply-headroom` | choice | room to spare on the supply's circuit (below) |

A fail names the part or the circuit and what to do. Every warn's fix ends "a licensed
electrician decides": a warning is never closed by an agent's word. A value the checks
cannot know (a load with no rating) is never a fail. Which materials conduct comes from the
domain's `checks/conduction.yaml` (keywords, `[verify]`).

## The `circuit` verify kind

A requirement can compare one of a circuit's figures:

```yaml
- id: REQ-003
  title: The heater circuit leaves room on the supply
  statement: The supply's rating exceeds the heater circuit's load by more than 0 A.
  category: electrical
  tags: [electrical]
  priority: must
  verify: {kind: circuit, target: "circuit://heater#props.supply_margin", op: ">", value: 0 A}
  allocation: [part://heater]
```
The figure is selected as `#props.<figure>` (S-167):

| figure | is |
|---|---|
| `#props.load_current` | the current the circuit's loads draw (A), from their rated power at the rated voltage (`calckit.power`) |
| `#props.supply_margin` | the supply's rating less every power circuit's load (A) |
| `#props.conductor_margin` | the smallest margin of the circuit's conductors over its load current (A) |
| `#props.earth_paths` | how many parts the circuit earths (a count) |

`value` is a quantity with its unit (`0 A`, `16 A`), never a `param://`: the core refuses it.
To compare against the supply's rating, select `supply_margin` and compare with `0 A`. An
unknown figure is "not checked", never a fail. A safety requirement is refused: the wiring's
safety is checked with `kind: manual`.

## The supply-headroom choice

When the power circuits' load is above half the supply's rating but still fits, the check
does not fail: it hands the owner a **choice** (E11, S-158, S-171). Half is NEC 210.23(A)(2)'s
share for equipment on a circuit that also supplies other loads (`[verify]`). The options:

- **`dedicated`**: keep the circuit for this product alone; nothing else may be plugged into
  it. What it takes: the electrician fits or confirms a circuit that serves the product alone,
  `dedicated: true` in `supply.yaml`, and the manual says so.
- **`larger`**: a larger circuit, the next class on file for the supply's region and voltage
  (`calckit/data/circuits.yaml`): room for a bigger load later. What it takes: the supply's
  rating becomes that class, and the electrician fits it with cable sized for it.

It holds nothing (`blocks: none`), and it exists only once the wiring is built: the load on
the circuit is not known before. With no larger class on file the row is a warning (one
option is no choice); with `dedicated: true` it passes. `n2f decide
elec-rule://supply-headroom@supply --pick <option> --by "<name>"` records the pick; the
designer then makes it in the model (`dedicated: true`, or the rating parameter raised),
builds and checks, and the row passes on the model itself. The project manager raises it
after the first build with wiring, never in the interview (`roles/pm.md`).

## Scope: in, later, external

`scope.electrical` in `n2f.yaml`, with the decision behind it:
- **`in`** ("done here"): everything above. With no wiring files yet, the Design row
  "Wiring" blocks: "nothing wired yet".
- **`later`** ("left for later (not designed here yet)"): the wiring's gate rows and its
  requirements (tagged `electrical`, or category `electrical`, or verify kind `circuit`) are
  left out of the gates with a note; safety ones still need their sign-off. Wiring files
  that exist anyway are a lint warning. The designer keeps the cable entries and the room the
  wiring will need. The report's Wiring section and the package cover say it is not included.
- **`external`** ("done elsewhere (supplied, not built here)"): the whole wiring is someone
  else's, and a stand-in with ports shows where it meets the product. For a bought, wired
  control box inside a product whose own wiring is designed here, keep `in` and make only the
  box `build: external` (above).

## The owner's view

- `n2f status`: under Design, **Wiring** ("2 devices, 1 circuit: all wired"; each load or
  control device no connection reaches is a blocker, "the Heater is not wired yet"); under
  Verify, **Wiring checks** ("6 checks: 5 OK, 1 for an electrician to confirm"). Neither row
  exists for a product with no wiring and no scope entry for it.
- The report's **Wiring** section (Product, after the joints): each circuit's diagram and its
  wires, the schedule, the cable to buy, the wiring check rows (failing first); for
  `later` or `external`, the scope line.
- `n2f check --scope asm://<unit>` keeps the circuit rows whose devices sit in that unit;
  `n2f context asm://<unit>` lists "Wiring in this module": the circuits that reach a device
  in it, their connections in owner words, and the cable entries on its parts or ports.
- `n2f doctor` lists `electrical` with its verify kind `circuit`, its check stage and its
  screen `supply`.
- Owner words: wiring, circuit, electrical device, conductor, cable entry, terminal, earth,
  interlock (`docs/vocabulary.md`). Rule ids and URIs stay in `--json` and the files.

## Manual helpers

A manual page (`model/docs/*.md`) may call (`owner/docs_helpers.py`):

| helper | gives |
|---|---|
| `circuit("<id>")` | the circuit: `.name`, `.purpose`, `.protection`, `.devices` (each `.name`, `.role`, `.terminals`), `.wires` (each `.id`, `.from_words`, `.to_words`, `.conductor`, `.csa`, `.length`, `.colour`, `.via`) and `.table` (the wires as a Markdown table); `{{ circuit("power") }}` prints its name |
| `cable_schedule()` | the rows of `schedule.csv` (`row.wire`, `row.from`, …) |
| `terminal_labels()` | the rows of `labels.csv` (`row.label`, `row.device`, `row.terminal`, …) |
| `cables_to_buy()` | the rows of `cables.csv` (`row.label`, `row.total_length_m`, …) |

```markdown
### {{ circuit("heater").name }}
Protected by {{ circuit("heater").protection }}.

{{ circuit("heater").table }}
```
Every read is recorded, so the page goes stale after a wiring edit and is fresh after one
build (the `elec` family runs before the manuals).

## The napkin screen

`circuit-available` (screen `supply`, phase `check`): a concept card's power
(`envelope.power`) against the circuit it plugs into (`site.circuit`, `230V-16A`), else the
usual circuits of its region (`site.region`). A card saying nothing of power or supply gets
no row.

## Where the numbers come from

Every number is in a cited row with `verify: true`:
- `calckit/data/conductors.yaml`: ampacity by region (EU: IEC 60204-1 Table 6, column B2 at
  40 °C; US: NFPA 79 Table 12.5.1, NEC 310.16, 402.5, 400.5(A)); silicone rows carry the PVC
  value as a floor (S-146);
- `calckit/data/earthing.yaml`: the earthing arrangements (IEC 60364-1 §312.2);
- `calckit/data/wire_colours.yaml`: colours by region and role (IEC 60445, HD 308, NEC);
- `calckit/data/circuits.yaml`: the supply circuit classes by region (the next class of the
  headroom choice);
- `checks/electrical-v0.yaml` (in the domain's package): the rules' own parameters (the
  extra-low-voltage band, the contact categories, the headroom fraction), each with its
  source; `checks/conduction.yaml`: which materials conduct, by keyword;
- `calckit.power`: a load's current from its power and voltage.

`make verify-list` prints the calc kit's tables; the domain's two files are not listed there
yet (B-0141, B-0138).

A device's ratings and terminals come from its datasheet, cited in the device file's
comments with `[verify]`; a product's own conductor row carries its `source`.

## Where it lives

`src/napkin2factory/domains/electrical/`: `model/` (the four families and `validate_refs`),
`interfaces/` (the `cable-entry` kind), `outputs/` (the `elec` rules, the diagram, the tables,
the text export), `checks/` (the stage, the rules, the nets, the verify kind), `owner/` (the
gate rows, the report section, the helpers, the words, the screen, the module context). The
third worked example of `docs/domains.md`, after the toy and the mechanical domain.
