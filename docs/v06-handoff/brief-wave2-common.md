# Wave 2 (M2, M3, M4 at once): what the three tasks share

Three subagents fill the stubs M1 left in `src/napkin2factory/domains/electrical/`
(landed at 9bd5b3f; read DECISIONS S-153, S-154, S-155 first, then the package). Each owns ONE
subfolder: M2 `outputs/`, M3 `checks/`, M4 `owner/`. Nobody edits `__init__.py`, `model/`,
`interfaces/` or another task's subfolder. Your subfolder's `__init__.py` holds your
registrations: you may refine their arguments there (that is your file), but a new schema
field in `model/` or a new top-level `Domain` field is a registration change: stop, commit
`WIP:` naming what you need, and report. If you need a helper another subfolder will write,
write your own private one in your subfolder (duplication is cheaper than a collision).

## The build files (M2 writes them; M3 and M4 read them; this is the contract between you)
All under `build/electrical/` (the `elec` family's `output_dir`). Rules:
- `elec:<circuit id>` — one per circuit: writes `<circuit>/connections.json` and
  `<circuit>/diagram.svg`; `produces="circuit://"`, so a read of `circuit://<id>` is this
  rule's `output_hash` = `sha256_json(<the connections.json record>)` (any change of a
  connection, device, conductor, entry or the circuit's words changes it).
- `elec:_schedule` — one aggregate rule (an underscore id can never be a circuit slug), after
  every `elec:<circuit>`: writes `schedule.csv`, `labels.csv`, `cables.csv`; produces the key
  `rule:elec-schedule` (its `output_hash` over the three files' rows).
`<circuit>/connections.json`:
```json
{"circuit": "power", "name": "owner words", "purpose": "power", "voltage_v": 230.0,
 "protection": {"ref": "supply|part://…|device://…", "words": "the site's 16 A device"},
 "devices": [{"uri": "device://heater", "part": "part://heater", "name": "<the part's name>",
              "instance": null, "role": "load", "terminals": ["A", "B"]}],
 "wires": [{"id": "power-1", "from": "device://switch#2", "from_words": "<name> terminal 2",
            "to": "device://heater#A", "to_words": "…", "conductor": "<conductor id>",
            "conductor_label": "…", "csa_mm2": 2.5, "length_m": 0.8, "colour": "brown",
            "via": "iface://entry", "via_words": "<the entry's name>"}],
 "entries": [{"uri": "iface://entry", "name": "…", "external": false}],
 "boundary": [{"assembly": "asm://…", "words": "to the external box: L, N, PE, …"}]}
```
CSV columns (header row, UTF-8, one row per wire, in circuit then wire order):
`schedule.csv`: `wire,circuit,from,to,conductor,cross_section_mm2,length_m,colour,via`;
`labels.csv`: `label,device,terminal,wire,circuit` (one per wire end: the shop's terminal
labels); `cables.csv`: `conductor,label,cross_section_mm2,insulation,total_length_m,wires`
("the cable to buy": a total per conductor type; an unknown length makes the total read
"not given", never a guess). Numbers in the JSON are plain floats in the stated unit or
`null`.

## Who computes what
- M3 owns every number judged: load current, supply margin, conductor current and margin,
  earth paths (`checks/calcs.py`, from the calc kit's `power` pack and `calckit.wiring`). It
  reads the model through `sctx.proxy`, and the `circuit://<id>` keys (M2's outputs) through
  `CheckStage.reads` for evidence. It does not read M2's files to compute.
- M2 computes no current; it lays out and tabulates (cross-sections and colours come from
  `calckit.wiring`).
- M4 shows: the Wiring section embeds M2's diagrams and tables and the check rows of kind
  `electrical` from `build/checks/checks.json`; the doc helpers read M2's files and record
  the keys (`circuit://<id>`, `rule:elec-schedule`) with `h.log.add`. M4 develops against
  the stubs; whoever lands last makes the three fit (the land gate runs every test).
- Generic words only, everywhere in the package and fixtures (F9 guard): no example ids.

## Shared test fixture
`tests/fixtures/electrical/minimal/` (M1's) is read-only for all three; copy it into your own
fixture folders when you need a variant.
