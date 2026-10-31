# How napkin2factory works

## One canonical model, everything else compiled

A product is a folder of text (`model/`): requirements, parameters, parts, assemblies,
interfaces, decisions, manuals, calcs. `n2f build` compiles it into `build/`: 3D models,
drawings, flat patterns, bill of materials, manuals, a check matrix and one self-contained
report page. Nothing under `build/` is ever edited by hand; a change is an edit to the
model followed by a rebuild of exactly what the edit invalidates.

## Stable identity: URIs

Everything has a URI (`part://outer-shell`, `req://REQ-003`, `param://wall-thickness`,
`iface://shell-frame-mount`, `doc://installation#safety`, `calc://thermal.skin_temperature`,
`bom://rollups#total_cost`). Generators carry URIs into every output: GLB node names,
drawing element ids, BOM rows, manual anchors, check rows. `<uri>#dotted.path` selects a
field or a computed property (D24). `n2f validate` fails if any URI does not resolve.

## Recorded dependencies

Inside a build rule every model read goes through a recording accessor: `P["x"]` for
parameters, `I["x"]` for interfaces, `part("x").name` in manuals. The build graph stores
the read set and a key per rule; the next build reruns a rule only when something it read
changed (D5). That is why `n2f impact` can say exactly which drawings, documents, checks and
sign-offs a proposed edit touches before anything changes.

## The kit of parts

Agents compose tested parametric generators (plate, bracket_l, enclosure, frame, panel,
block, tube, hole_pattern) rather than writing raw CAD. Generators know their own features
(bends, flanges, holes, reliefs), so manufacturability rules are simple checks over
declared features, and sheet-metal flat patterns come out by construction.

## Interfaces

An interface is a named frame plus a feature pattern shared by two parts (bolt pattern or
mating face). The build applies the pattern to both parties, so they agree by
construction, and `n2f check` verifies the recorded patterns match (D16).

## Checks are the gate

`n2f check` evaluates every requirement by its declared method, runs rule packs over
features, checks interfaces, interference and instance counts, and reports a matrix. A
`fail` blocks closing a change request and releasing. Safety requirements can never pass by
computation alone: they need a human sign-off bound to the evidence hashes current at
signing, and revert to `needs-human` when any evidence changes (D9, D25).

## The change loop

File a change request → read its impact report → approve → apply (the model changes, a
snapshot is taken) → rebuild → check → close (revisions bump, changelog grows) → release
(Revision tag, manufacturer ZIP, frozen site version) → diff page between Revisions with
drawing overlays, BOM delta and side-by-side 3D.

## Agents author, tools verify, humans arbitrate

The repository installs the roles: a project-manager skill talks to the owner and files
change requests; a designer skill composes the kit and looks at renders; a verifier agent
reviews calcs and writes under `reports/` only. `n2f check` is the gate regardless of which
AI client (or none) is driving (D6).

## Safety floor

The disclaimer appears on every report, manual and package. Hazards are stated in plain
words to every reader. Example products ship sign-offs flagged `example: true`, which the
report labels "EXAMPLE SIGN-OFF, NOT A REVIEW".
