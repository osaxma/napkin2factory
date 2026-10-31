# The napkin stage: concept screening

Concept cards (`concepts/C-xxx.yaml`, NAPKIN_STAGE §3) are cheap directions for the
product. `n2f concept build C-xxx` (or `--all`) turns one into rough shapes and a
**screening**: a handful of numbers and rule outcomes that say, in seconds, whether the
direction holds up. Screening is not verification — it is a third tier for ideas, and
everything it writes lives outside the build (`build/concepts/`, never in the manifest;
deleting `concepts/` changes no build output).

## What a build does

1. **Massing.** Each `massing:` line is a kit call run at massing fidelity (silhouettes:
   no holes, bends or fillets, but the same argument checks as a full build, so an
   impossible shape fails for real). `at: {x, y, z, rz}` places it; `material:` gives it
   a mass; `process_class:` picks its cost band (default: the generator's own process).
   Cards cannot refer into the model (`param://…`): write the number itself.
2. **Artifacts** under `build/concepts/C-xxx/`: `massing.glb` (one node per call,
   `concept://C-xxx/<as>`), `props.json`, `features.json`, `screening.json` and
   `renders/` (plain z-buffer pictures for checking shape, not for judging looks).
3. **Screening**, written back into the card's `screening:` block.

## The two labels

Every number carries a label, in the card, in JSON and on screen:

- **`computed`** — measured from the massing shapes: `width`, `depth`, `height` (the
  bounding box), `volume`, `mass` (only when every call declares a `material`), and
  `footprint_with_door_swing`.
- **`estimate`** — from the calc kit ([calckit.md](calckit.md)) fed with the card's
  `envelope` numbers: `heat_loss`, `skin_temperature`, `stored_heat`, `heat_up_time`
  (from `envelope.power`) or `required_power` (from `envelope.heat_up_time`),
  `insulation_mass`, `total_mass`, `current`, `circuit_class`, `cost_low`/`cost_high`,
  `lift_class`. Each names the calc-kit function it came from.

A missing input never becomes an invented number: the estimate is left out and a note says
what would unlock it. When the card is silent, screening states its defaults: room 25 degC,
skin film coefficient 5 W/m²K, emissivity 0.9, hot face 1200 degC; a bare
`insulation: 170 mm` is one ceramic-fiber-board layer (the kiln's values); layers named
`brick`/`K23` or `fiber` take the kiln's K23 and fiber-board values; `shell` layers grow
the box without resistance or stored heat. All of these are `[verify]`.

## The rules (`rulepacks/concept-v0.yaml`)

| rule | fails when |
|---|---|
| `fits-site-width` | width + the open door > `site.alcove_width`. A hinged door (`layout.door: hinged-left/right`) adds its own width beside the hinge (the `door` massing call, else `envelope.door_width`) |
| `fits-site-depth`, `fits-site-height` | depth/height exceed `site.alcove_depth`/`alcove_height` |
| `circuit-available` | the current × 1.2 headroom exceeds `site.circuit` (e.g. `240V-13A`) or every class on file for `site.region`; an unknown region only warns |
| `mass-vs-lift-class` (warning) | the mass needs more than a two-person lift, or more than `site.lift_class` |
| `blank-vs-stock-sheet` | a sheet-metal call's flat blank (open box: (L + 2H) × (W + 2H)) fits no stock sheet on file |
| `walls-fit-envelope` | chamber + 2 × insulation does not fit inside the `body` call |
| `controls-not-adjacent-hot-face` (warning) | controls sit on top or beside the door, in the hot air path |

A failing rule makes the card **red**; warnings never do. Red is information: the card
keeps its reasons, `n2f concept build` prints them under "this direction has problems:"
and still exits 0.
