# Render checklist (what to look for before claiming a part or assembly is right)

Renders live in `build/parts/<id>/renders/` and `build/assemblies/<id>/renders/`:
`front.png` (looking along +Y), `top.png` (looking down −Z), `right.png` (looking along −X),
`iso.png`, and `section.png` (iso cut by a horizontal plane: the part's mid-height, an
assembly's mass centroid; everything above it removed). They are flat-shaded z-buffer
rasters (D12): good enough to judge shape, not finish.

## Part
- [ ] **Silhouette**: does the iso read as the thing named (an L, a tray, a four-legged frame)?
- [ ] **Proportions**: compare `front`/`top`/`right` extents with `props.json` `bbox` and the parameters that drove them.
- [ ] **Features present**: holes where the YAML says, bends with visible radius, flanges on the right edges, cutouts on the right face.
- [ ] **Nothing extra**: no stray slivers, no doubled walls, no gap where a bend should join (a bend that did not union shows as a dark seam).
- [ ] **Orientation**: Z up, the part's declared frame (e.g. base plate at z=0) matches what the assembly module assumes.
- [ ] **Section**: wall thickness visible and uniform; cavities where expected; no solid where a cavity should be.
- [ ] **Section cut**: the cut face is drawn as a flat, darker, diagonally hatched region in the
  part's colour, bounded by straight edges where the plane meets the walls. A hollow part reads
  as a hatched band (the wall) around an unhatched, lit view down into the cavity; a solid part
  is hatched right across. No sawtooth slivers or triangles poking above the cut, and no hatch
  inside a cavity (hatch where you expected a hole means the cavity is not there; a missing
  hatch on a wall means the part is not a closed solid; check the scene notes).

## Assembly
- [ ] **Everything placed**: count distinct colours/instances against `instance_counts`; a missing part is usually a wrong key in the module.
- [ ] **Contact, not overlap**: mating parts touch; interpenetration shows as z-fighting speckle or a part vanishing into another.
- [ ] **Stacking order**: layers (brick, fiber, shell) in the right sequence in `section.png`: each
  layer is its own hatched band in its own colour, touching its neighbours with no white gap and
  no speckle between bands.
- [ ] **Scale sanity**: a fastener should look like a fastener next to a wall, not a bollard.
- [ ] **Exploded hint**: the `exploded.axis` in the YAML is the axis along which the viewer can pull the assembly apart; it should be the stacking axis.

## Product image (styled screenshot)
`build/concepts/C-xxx/renders/styled-iso.png` and `styled-front.png` (N6) are the pictures
an owner decides on. Judge them as a buyer would, not as an engineer:
- [ ] **Reads as an object someone might buy**: an appliance, an instrument, a piece of
  equipment — not a debug render or a stack of boxes in random colours.
- [ ] **Plausible materials**: every part wears its role's palette colour and finish from
  `style.yaml` (powder coat, painted, brushed steel…); no hash colours anywhere.
- [ ] **Neutral lighting with visible form**: the faces of a box are told apart by shading
  (front, side and top differ), parts sit on a soft contact shadow; nothing is blown out to
  pure white or crushed to black, and the palette hue survives (charcoal stays grey).
- [ ] **No z-fighting**: no speckle or stripes where parts touch or overlap (a door laid on a
  body must sit proud of it, not inside it).
- [ ] **Neutral background**: plain light grey, no gradient or colour; the body's silhouette
  stays readable against it (an off-white body needs the darker appliance background).
- [ ] **Accent used sparingly**: the accent colour marks controls or one detail, not the body.
- [ ] **Front view framed**: the door and controls are readable, the whole product in frame,
  little keystoning.
- [ ] **Iso framed with margin**: nothing cropped, the product fills most of the frame.
- [ ] If the image is the z-buffer fallback (`method: zbuffer-fallback`, the note in the
  card's screening notes), say so when showing it: it is a correctness picture, not a look.

## When it looks wrong
Fix the model, not the render. Re-run `n2f build --target geometry --part <id>` and look again.
Record what you saw in `STATUS.md` at milestone exits (M2, M5, M8).
