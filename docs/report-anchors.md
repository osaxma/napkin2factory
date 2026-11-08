# The report's links: what an agent can hand an owner

The report is one file, `build/report/index.html`, shown in five lenses (Workbench, Drawings,
Build, Checks, History) with a tree, a 3D view and an inspector in the Workbench (v0.9 M3a,
decisions V2 and V6). A link opens the page at a lens and an object.

## The deep link

```
build/report/index.html#lens=build&select=part://top-board
```

- `lens=` is one of `workbench`, `drawings`, `build`, `verification` (the tab called Checks) or
  `history`; `checks` also works. `select=` is the URI of anything in the product: a part, an
  assembly, an interface, a requirement, a rule check, a document, or a domain's object.
  Either part may be left out: `#select=part://top-board` opens the Workbench with that part
  selected; `#lens=drawings` opens that lens and keeps the selection.
- Write the URI as it is. The encoded form (`part%3A%2F%2Ftop-board`) is read the same way.
- The selection shows in the inspector whichever lens is open, and in the tree and the 3D view
  when the Workbench is. A URI the build has no entry for gets the inspector's honest answer,
  "This build records nothing for <uri>.", never a guess.
- The page rewrites its own address as the owner picks things, so the address bar is always a
  link back to what they are looking at.

## Anchors (the older form)

Every id below is a link target: `index.html#drawing-top-board` opens the lens that holds it
and scrolls to it, leaving the selection alone. `#overview` (and `#stage`, `#waiting`,
`#scope`, `#choice-<n>`) open the Workbench with the product selected, where the product's own
view lives. An unknown anchor opens the Workbench. Ids inside embedded drawings (SVG) are not
anchors. `tests/unit/test_workbench_page.py` checks every row against a built report: a row
marked "always" is on the table's or the electrical fixture's page, in the lens named; a row
marked "when ..." is checked in that lens whenever it is on the page; and no id outside this
list and the page's own controls is on the page.

| Id | Lens | On the page |
|---|---|---|
| `overview` | `workbench` | always |
| `stage` | `workbench` | always |
| `waiting` | `workbench` | when choices wait on the owner |
| `choice-<n>` | `workbench` | when choices wait on the owner |
| `scope` | `workbench` | when the scope has lines |
| `model` | `workbench` | always |
| `interfaces` | `workbench` | always |
| `iface-<id>` | `workbench` | always |
| `joints` | `workbench` | when the product has sub-assemblies |
| `joint-<interface id>` | `workbench` | when the product has sub-assemblies |
| `drawings` | `drawings` | always |
| `drawing-<part id>` | `drawings` | always |
| `wiring` | `drawings` | when the product has wiring |
| `wiring-<circuit id>` | `drawings` | when the product has wiring |
| `wiring-diagram-<circuit id>` | `drawings` | when the product has wiring |
| `parts` | `build` | always |
| `part-<part id>` | `build` | always |
| `bom` | `build` | always |
| `cost-notes` | `build` | when a price carries a note |
| `build` | `build` | always |
| `step-<unit id>` | `build` | always |
| `sheet-<unit id>` | `build` | when the unit has a sheet |
| `safety` | `verification` | always |
| `requirements` | `verification` | always |
| `req-<requirement id>` | `verification` | always |
| `rules` | `verification` | always |
| `signoffs` | `verification` | when a requirement is signed |
| `signoff-<requirement id>` | `verification` | when a requirement is signed |
| `manuals` | `verification` | when there is a manual beyond the safety page |
| `doc-<document id>` | `verification` | always |
| `check-views` | `verification` | when check renders exist |
| `parameters` | `history` | always |
| `param-<parameter slug>` | `history` | always |
| `decisions` | `history` | always |
| `dec-<decision id>` | `history` | when there are decisions |
| `changes` | `history` | when there are change requests |
| `ecr-<change request id>` | `history` | when there are change requests |
| `directions` | `history` | when the folder has concept cards |
| `h-<section id>` | `the section's lens` | always |

`h-<section id>` is a section's heading (`h-requirements` heads `requirements`); the `#` beside
each heading links to the section. A domain's own section adds its own ids the same way; list
them here when a domain ships one that agents should link to.
