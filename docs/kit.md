# Kit of parts

Generators live in `src/napkin2factory/geometry/kit/<name>.py`, one per file. Each exposes
`ARGS` (a pydantic schema; lengths accept `"15 mm"`, pint quantities or bare millimetres)
and `generate(args, ctx) -> PartResult` (plus `massing(args, ctx)`, see below). Parts call
them declaratively:

```yaml
geometry:
  kit: enclosure
  args: {length: param://box-length, width: param://box-width, height: param://box-height,
         thickness: param://sheet-thickness, bend_radius: param://bend-radius, flange: 12 mm,
         cutouts: [{face: back, center: [0, 0], width: 40 mm, height: 20 mm, corner_radius: 3 mm}]}
```

| generator | makes | flat pattern | key args |
|---|---|---|---|
| `plate` | flat rectangle with a hole grid, corner radius | yes | width, depth (or fit_to{width,height}, reveal), thickness, corner_radius, holes{diameter,count_x,count_y,spacing_x,spacing_y,inset} |
| `panel` | flat sheet with explicit holes and cutouts | yes | width, height (or fit_to{width,height}, reveal), thickness, corner_radius, holes[], cutouts[] |
| `block` | rectangular solid (bricks, boards, COTS boxes) | no (cut list) | length, width, height, fillet, chamfer |
| `tube` | round/square hollow section or rod | no (cut list) | shape, size, wall, length, axis, corner_radius |
| `hole_pattern` | plate carrying a bolt pattern (shared math for interfaces) | yes | plate_width, plate_depth, thickness, pattern, count, diameter, spacing, pitch_circle, interface |
| `bracket_l` | L-bracket with one bend and holes per leg | yes, with bend line | length, height, width, thickness, bend_radius, holes{diameter,spacing,inset,count} |
| `enclosure` | open-top tray: four bent walls, optional lip, reliefs, cutouts, vent | yes, cross with bend lines | length, width, height, thickness, bend_radius, flange, relief, cutouts[], vent{face,pattern,count,size,pitch,inset} |
| `frame` | welded stand of square tube or angle: legs, top/bottom rails | no (cut list) | length, width, height, member{profile,size,wall}, top_rails, bottom_rails, bottom_rail_height, overhang |

## What a generator returns

`PartResult(shape, features, dims, flat_pattern, cut_list, props, notes, flat_map)`.
`features` (holes, patterns, bends, flanges, reliefs, cutouts, members, thickness) feed the
rule packs; `dims` become drawing callouts; `flat_pattern` becomes the flat view and the
DXF; `flat_map` maps a 3D point to the flat so interface holes land in the DXF (S-034).

## Massing fidelity

Every generator also exposes `massing(args, ctx)`; `kit.run` (and the `kit.plate(...)`
namespace a custom module receives) calls it when `KitContext.fidelity == "massing"`. It
exists for the napkin stage (`n2f concept build`, NAPKIN_STAGE N3): fast silhouettes for
screening, built by the same generators so nothing is duplicated.

- **Validation is identical.** `massing` runs the same argument checks as `generate`
  (sizes, fillet/chamfer fit, wall vs. footprint, hole and cutout placement, lip and relief
  rules), so an impossible composition fails for real, with the same message.
- **Geometry is primitives only** (`Box`, `Cylinder`, fuse/cut), in exactly the full
  part's frame, so a massing placement and a full placement coincide:

| generator | silhouette |
|---|---|
| `plate`, `panel` | box of the outer size; no holes, cutouts or corner radius |
| `block` | box; no fillet or chamfer |
| `tube` | the outer solid along `axis` (cylinder or square box), no bore |
| `hole_pattern` | the plate as a box; an interface is still resolved and checked, but only moves holes, so the plate is unchanged |
| `bracket_l` | two leg boxes fused at a sharp corner; no bend radius, no holes |
| `enclosure` | outer box minus the open-top cavity (walls and base keep `thickness`); no bends, reliefs, lip or cutouts — with a `flange` the silhouette stays `length × width × height` |
| `frame` | every member a solid `size × size` box where the full frame puts it, fused |

- **Result:** `features = Features(process, extra={"fidelity": "massing"})` (so
  `features.json` carries `fidelity: massing`), only the overall `dims`, no flat pattern,
  an empty cut list, `props` with `fidelity: massing` (enclosure adds its inner sizes), and
  the note `massing silhouette: features omitted`.

## Aesthetic parameters (`style.yaml`, N7)

Six parameters turn a welded box into a product. Each is an ordinary argument a part may
set; when it does not, a part **that opts in** takes the default from the product's
`style.yaml` (`n2f init --style industrial|appliance|lab` seeds it; a product without the
file gets `industrial`, whose shape cues are all no-ops).

**Opt-in rule (fixed).** Style defaults reach only parts whose `role:` is explicitly `body`,
`door`, `stand`, `controls` or `trim`. A part with no role, or role `lining`, `fastener` or
`default`, builds exactly as without a style whatever `style.yaml` says (refractory bricks
never grow fillets because the shell is rounded). **Default is unchanged:** with no style,
no role or `industrial`, every generator builds byte-identical geometry to v0.1 (the
generator goldens, `tests/golden/test_kit_aesthetics.py`, and the enclosure example's
`tess_hash` values hold it). Massing fidelity ignores every style default (the screenshot
rig still reads the palette). The part's own value always wins, even an explicit `0`; a
style default that does not fit the part (a radius larger than a side, an overhang that
leaves the ring off the legs) is skipped and the part's `notes` say why — a style never
breaks a build. Opted-in parts record a read of the geometry cues of `style.yaml`, so
editing them rebuilds exactly those parts; a palette edit rebuilds none.

| # | parameter | where | from `style.yaml` |
|---|---|---|---|
| 1 | edge radius scaling | `enclosure`, `bracket_l`: an unset `bend_radius` defaults to `thickness × radius_scale` (1.0 = today) | `radius_scale` |
| 2 | corner radius | `plate`/`panel` `corner_radius`, `block` `fillet` (vertical edges) when unset | `corner_radius` (0 mm) |
| 3 | chamfer | `block` `chamfer` (all edges) when neither fillet nor chamfer is set; a style sets 2 or 3, not both | `chamfer` (0 mm) |
| 4 | panel reveal | `panel`/`plate` `fit_to: {width, height}` cuts the part `reveal` smaller than its opening on each side (plate: height is depth); `reveal` arg, else the style's, else 2 mm. Without `fit_to` nothing changes | `reveal` (2 mm) |
| 5 | overhang | `frame` `overhang`: the top rails become a ring sitting on the legs and reaching `overhang` beyond them on every side, like a table top (bbox grows by 2·overhang in X and Y; square tube; ≤ size − wall) | `overhang` (0 mm) |
| 6 | vent / grille | `enclosure` `vent: {face: left|right|back, pattern: slots|holes, count, size, pitch, inset}`: ordinary cutouts `vent-1…` on that wall, so they reach `features.json`, the flat pattern and the rule checks; slots run the wall's flat height less 2·inset, holes sit in one row `inset` below its top | `vent_pattern` when the vent names none (`slots`) |

`fastener_visibility` stays in `style.yaml` only: holes come from interfaces, so it becomes a
form requirement at promotion (M4), not a kit parameter. Palette and finish by role are
read by the concept screenshot rig and the report viewer, never by geometry.

## Sheet-metal conventions (`_sheet.py`)

K-factor by r/t (0.33 … 0.50, nominal air-bending table, `[verify]` with the fabricator),
bend allowance = angle × (r + K·t), orthogonal bends only, reliefs at corners where bends
meet. Flat area × thickness matches the solid volume within ~0.5 % (the bend zones differ
slightly by construction).

## Custom geometry

When no generator fits: `geometry: {module: geometry/<id>.py}` with
`def build(P, I, kit) -> PartResult`. Read parameters through `P` and interfaces through `I`
(both record dependencies); compose `kit.plate(...)` etc. and union with build123d. Sibling
helper modules in `model/geometry/` may be imported; they are part of the code hash.

## Interfaces are applied by the build

Declare `interfaces: [iface://x]` on both parts; the build cuts the bolt pattern into each
in its own frame and records it. Generators never place interface holes themselves.
