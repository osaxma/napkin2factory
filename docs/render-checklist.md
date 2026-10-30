# Render checklist (what to look for before claiming a part or assembly is right)

Renders live in `build/parts/<id>/renders/` and `build/assemblies/<id>/renders/`:
`front.png` (looking along +Y), `top.png` (looking down −Z), `right.png` (looking along −X),
`iso.png`, and `section.png` (iso with everything above the mid-plane removed). They are
flat-shaded z-buffer rasters (D12): good enough to judge shape, not finish.

## Part
- [ ] **Silhouette**: does the iso read as the thing named (an L, a tray, a four-legged frame)?
- [ ] **Proportions**: compare `front`/`top`/`right` extents with `props.json` `bbox` and the parameters that drove them.
- [ ] **Features present**: holes where the YAML says, bends with visible radius, flanges on the right edges, cutouts on the right face.
- [ ] **Nothing extra**: no stray slivers, no doubled walls, no gap where a bend should join (a bend that did not union shows as a dark seam).
- [ ] **Orientation**: Z up, the part's declared frame (e.g. base plate at z=0) matches what the assembly module assumes.
- [ ] **Section**: wall thickness visible and uniform; cavities where expected; no solid where a cavity should be.

## Assembly
- [ ] **Everything placed**: count distinct colours/instances against `instance_counts`; a missing part is usually a wrong key in the module.
- [ ] **Contact, not overlap**: mating parts touch; interpenetration shows as z-fighting speckle or a part vanishing into another.
- [ ] **Stacking order**: layers (brick, fiber, shell) in the right sequence in `section.png`.
- [ ] **Scale sanity**: a fastener should look like a fastener next to a wall, not a bollard.
- [ ] **Exploded hint**: the `exploded.axis` in the YAML is the axis along which the viewer can pull the assembly apart; it should be the stacking axis.

## When it looks wrong
Fix the model, not the render. Re-run `n2f build --target geometry --part <id>` and look again.
Record what you saw in `STATUS.md` at milestone exits (M2, M5, M8).
