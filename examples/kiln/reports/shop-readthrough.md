# Shop read-through — kiln manufacturer package (Rev A draft)

> **Status of this read-through.** Written by the gate-3 reviewer against the Rev A draft as it
> stood at milestone M8 (2026-10-30). It is kept verbatim as the launch-day credibility artifact.
> The Rev A package was reworked afterwards: standoff, hinge-post, latch-keeper, controller-mount,
> element-tail and thermocouple holes are now in the DXFs; the hinges moved from the guard's lip to
> a bolted angle post; the door is a tray-and-guard plug door with 5 mm clearance and a 6° taper;
> the shells may be quoted as multi-piece weldments with closed corners (the one-piece flat is a
> reference development); the controller box has a lid, 45 +0.6/0 cutouts and gland holes; the
> notes no longer contradict the DXF. Still open for the shop: the K23 cut plan from standard bricks
> (large-format allowed), rigidizer on exposed fiber, and the powder-coat system (named in the notes,
> to be confirmed). Nobody at a real shop has read either version.

> Produced by an AI reviewer role-playing the two suppliers, for the launch-day package.
> Nobody at a real shop has read this package. The reviewer read only what a Revision
> would ship: `build/drawings/*.svg`, `build/drawings/*-flat.dxf`, `build/bom/bom.xlsx`,
> `build/docs/manufacturer-notes/page.pdf`, `build/docs/assembly/page.pdf` and the
> `manufacturer_notes` lines carried in the BOM. Date of reading: 2026-10-30.

---

## Sheet-metal shop

Quoting: `outer-shell` (1.5 mm CR4), `guard-shell` (1.0 mm CR4), `controller-box`
(1.0 mm CR4), `door-skin` (1.5 mm CR4 flat). Quantity 1 each.

### Could we quote?

**With questions** for the controller box and the door skin. **No** for the two shells as
drawn — not until the forming method and the hole questions below are settled. We would
not put a number on a one-piece 630 mm deep tray with no holes for its own standoffs and a
notes page that puts the hinge holes on a different part than the DXF does.

### Missing or ambiguous

**Outer shell (`outer-shell.svg`, `outer-shell-flat.dxf`)**

- The flat is a one-piece cross, 1770 × 1770 mm, in 1.5 mm. That does not come out of a
  1250 × 2500 or 1500 × 3000 sheet. We would need 2000-wide stock in CR4 1.5, which we do
  not hold and would have to buy as a full sheet for one part.
- 585 × 585 × 581.5 deep, four walls bent up 90° from one blank, then a 15 mm return lip
  bent outward at the open end on all four sides. The first two walls are fine. The third
  and fourth walls cannot be bent on a press brake: the two walls already standing (580 mm
  tall) hit the ram and the punch holder. No standard or gooseneck tooling is 580 mm tall.
  We would make this as a U-wrap plus two end panels, or four panels on a corner angle,
  joined with spot welds, rivets or clinches. The notes say "open corners with reliefs, do
  not weld". A 580 mm deep box with 3 × 3 mm corner reliefs and nothing joining the corners
  will not stay square or carry 40 kg of lining; tell us what corner joint you accept.
- The return lips: with open corners the lips do not meet. No corner detail (mitre, gap,
  overlap) is drawn. The lip is "DOWN 90°" on a 580 mm wall — on the multi-piece build we
  would bend the lip first; confirm the lip is outward on all four sides, including the
  bottom where the shell sits on standoffs.
- The notes page says: "Four Ø6.6 mm holes in the bottom wall and the hinge holes on the
  front lip are in the flat pattern." There are **no holes** in `outer-shell-flat.dxf` and
  none in the drawing (hole table absent). The eight holes described are in
  `guard-shell-flat.dxf`. Which part gets them? If the outer shell is meant to carry the
  door and bolt to the stand, send a new DXF.
- The guard "mounts on 25 mm standoffs over the inner shell, 16 off M6 × 25, supply from
  stock". There are no standoff holes in either the shell or the guard flat. Sixteen hole
  positions, on which walls, and from which side the bolt goes in (inside the shell, before
  the lining goes in?) — we need them in the DXF or we drill nothing.
- No holes for the element tails (two, through the shell, with ceramic bushes — size?), no
  Ø8 thermocouple hole in the back (the BOM note says "drilled by the installer" through a
  powder-coated 1.5 mm wall, which the installer will not thank you for), no earth stud, no
  cable entries. If these are "installer", say so on the drawing so the coat is not wasted.
- Finish: "high-temperature powder coat rated 200 degC minimum, black". Name a system
  (silicone-polyester or a product code) and a RAL. Inside and outside? The inside face
  sits against fiber board at ~110 °C and will never be seen. "Mask the hinge and mount
  holes" — you mask threads, not Ø6.6 clearance holes; clarify or we ignore it.
- Tolerance ISO 2768-m on a 585 mm formed box in 1.5 mm is ±0.8 mm over 400–1000 mm. We can
  hold it on the wrap; on a four-panel build the inside opening 582 × 582 is what matters
  to your fiber fit (you drew 2 mm clearance). Call out the 582 inside dims as the ones we
  must hit.
- K-factor 0.4 and bend allowance are in the JSON, not on the drawing or the DXF. Tell us
  whether to cut the DXF as-is or to re-develop from the STEP with our own tooling data.
  The notes promise STEP models in the Revision; make sure they ship.

**Guard shell (`guard-shell.svg`, `guard-shell-flat.dxf`)**

- Same forming problem, worse: 637 × 637 × 632.5 deep from one 1927 × 1927 blank in 1.0 mm.
  Same answer: multi-piece, and we need the corner joint you accept.
- Eight Ø6.6 holes are in the flat (good): four in the bottom at 552 × 547.5 for the stand,
  four on one lip at 50 mm pitch for the hinges. The hinge holes sit on a 15 mm × 1.0 mm
  lip, 7.5 mm from the lip edge: 4.2 mm of metal each side of a Ø6.6 hole, in 1 mm sheet,
  carrying an 11 kg door on two hinges. It will tear the first time the door is opened past
  90°. We will cut what you draw, but put it in writing that you know.
- The hole table says "X/Y from the lower-left corner of the view" with views named "front"
  and "top". Those are not flat-pattern coordinates and do not match the DXF orientation.
  We will take the DXF circles as truth; say so on the drawing.
- Four vent slots 300 × 20 with R5 in the side walls. In the DXF they are where they are;
  the assembly sheet says to fit the guard "so the vent slots are low at the sides". The
  slots are symmetric about the wall centre (±120 mm). There is no "low". Which way up?
  (In the 3D model the slots end up vertical, at mid-height.) If you want low inlets and
  high outlets, that is a different DXF.
- No standoff holes (see above). No cutout where the controller cable enters, no earth stud.
- Finish "powder coat, black" — RAL? Standard polyester is fine for a 60 °C guard if the
  guard really is 60 °C; the notes say the shell behind it is 110 °C.

**Controller enclosure (`controller-box.svg`, `controller-box-flat.dxf`)**

- Blank 515 × 435 in 1.0 mm, 200 × 120 × 150 tray, 10 mm return lips, R1 bends — fine,
  we can form this.
- It is an open-topped tray. No lid is drawn or in the BOM, and the assembly sheet says the
  relay sits on the base with mains wiring by an electrician. If a lid exists, we need it;
  if not, tell us that is intended.
- 46 × 46 cutout for a 48 × 48 instrument. The standard panel cutout for 48 × 48 DIN
  controllers is 45 (+0.6/0) square. 46 is over the top of that band; the bezel covers it
  but the clips may not grip 1 mm sheet. Confirm 46 or let us cut 45.2.
- 30 × 20 R3 cable entry in the base. No gland or grommet called out; a bare laser-cut edge
  in 1 mm against a mains cable is not acceptable — specify a grommet or a gland plate.
- No mounting holes or brackets. The interface says "hangs on brackets beside the guard with
  a 40 mm air gap". Who makes the brackets, and where are the holes in the box and in the
  guard?
- Label "Dedicated 16 A circuit. Installation by a licensed electrician only." is required
  on the box per the installation manual. No label artwork, size, material or position.

**Door skin (`door-skin.svg`, `door-skin-flat.dxf`)**

- 677 × 677 × 1.5 flat, R8 corners, 4 × Ø6.6 at 12.5 mm from the left edge on 50 mm pitch.
  Laser, deburr, coat. Easy — but:
- A flat 677 mm square of 1.5 mm with no return, no stiffener and an 11 kg plug on its back
  will drum and oil-can, and it is going to run hot (the notes say high-temperature coat,
  so you expect it to). Do you want a 15 mm return on all sides like the shells? That
  changes it from "cut-sheet" to a formed part and the price.
- How is the fiber/brick plug fixed to the skin? No studs, no holes, no washers, no
  adhesive callout. Four Ø6.6 hinge holes are the only features.
- No holes or keeper for the draw latch (Southco E6). The latch body sits on the skin, the
  keeper sits on the guard lip; neither has a hole pattern anywhere.
- The hinge in the BOM is a "weld-on" hinge (McMaster 1635A21). The skin and lip have bolt
  holes. Weld-on hinges do not have leaves with holes, and you cannot weld onto a powder
  coated 1.5 mm skin after coating. Which is it: bolt-on hinge with leaves, or weld before
  coat and mask?
- High-temperature powder coat on the door skin: same system question as the shell.

### Questions we would ask

1. Which part carries the hinges and the stand bolts — the guard (per DXF) or the outer
   shell (per notes)? Send the DXF that matches your answer.
2. May we build the two deep trays as multi-piece (wrap + ends, or four panels + corner
   angles) with spot welds or rivets? If not, how do you expect a 580–630 mm deep box to be
   brake-formed from one blank, and from what sheet size?
3. Positions, size and side-of-entry of the 16 standoff holes in both the shell and guard.
4. All penetrations: element tails (2), thermocouple (Ø8), earth studs, controller cable,
   controller mounting. Either in the DXF or marked "installer drills" on the drawing.
5. Powder coat: system/product, RAL, inside/outside, cure temperature, masking list.
6. Controller box: lid? Brackets? Gland? Cutout 46 or 45.2? Label artwork?
7. Door skin: plug fixing, latch and keeper hole patterns, hinge type (bolt-on vs weld-on),
   stiffening return or not.
8. Which dimensions are critical (we assume the 582 × 582 shell inside opening and the
   635 × 635 guard inside); the rest to ISO 2768-m.
9. Do the STEP files ship with the Revision? We would re-develop the flats from them.

### Verdict

**Controller box and door skin: quotable this week with the answers to Q6–Q7. Outer shell
and guard: not quotable as drawn — one-piece deep trays we cannot form, blanks wider than
stock sheet, standoff and penetration holes missing, and the notes contradict the DXF on
where the hinges go. Expect the shell price to double against your 180/160 USD estimate
once they become multi-piece, powder-coated, deburred weldments.**

---

## Refractory supplier

Quoting: K23 insulating firebrick cut pieces — `liner-slab` ×2 (328 × 328 × 64),
`liner-side` ×2 (64 × 328 × 200, 3 grooves), `liner-back` ×1 (200 × 64 × 200, 3 grooves),
`door-brick` ×1 (200 × 64 × 200); ceramic fiber board 1260 class — `fiber-slab` ×2
(578 × 578 × 125), `fiber-side` ×2 (328 × 578 × 125), `fiber-back` ×1 (328 × 328 × 125),
`door-fiber` ×1 (328 × 328 × 153).

### Could we quote?

**With questions.** Fiber boards and plain slabs we can price today as cut pieces. The
grooved liners and the door plug we can price only once we know the cut plan from standard
bricks and what tolerance and clearance you actually want, because nothing in this package
fits together at the sizes drawn.

### Missing or ambiguous

**K23 pieces (`liner-slab.svg`, `liner-side.svg`, `liner-back.svg`, `door-brick.svg`)**

- The decision sheet says the lining is "cut and grooved from standard 230 × 114 × 64 mm
  bricks". Every piece except the back liner is longer than 230 in at least one direction:
  the slabs are 328 × 328 (three bricks wide × 230 + 98 long, six pieces and five mortar
  joints each), the side liners 328 long (230 + 98). The BOM note on the door brick says
  "see cut list" — there is no cut list in the package. Tell us where the joints go, or
  tell us we may choose, or let us quote large-format K23 (e.g. 305 × 305 × 76 or
  230 × 230 × 64 splits) and cut single pieces.
- Grooves cross the 230/98 joint in the side liners. A mortar joint under an element groove
  is where the groove edge spalls first. Is that acceptable, or must each liner be one
  piece?
- Groove: depth 12 is dimensioned; the groove width is not (we read 12 from the notes). The
  first groove is not dimensioned from the bottom edge (we read 50 from the pitch). The
  grooves run through the full 328 length of the side liners, including the 64 mm at each
  end that is hidden behind the door brick and the back liner. Intentional (element return
  channels) or should they stop?
- Square groove corners. We cut with a saw and a router bit; a square-bottomed 12 × 12
  groove in K23 chips at the lips. Do you accept a round-bottomed groove or a 1–2 mm chamfer
  on the edges?
- Tolerance: "saw-cut faces ±2 mm" — fine, that is what we do. But: the 328 × 328 slabs sit
  in a 328 × 328 fiber opening; the 200 high side liners sit between two slabs 200 apart;
  the 200 × 200 door block slides into a 200 × 200 opening. Zero clearance everywhere,
  ±2 mm on both parts, plus "bed joints in refractory mortar" (1–3 mm per joint, not in the
  nominal sizes). It will not go together without site trimming. Who trims, and to what?
- The door block is a plug that goes in and out every firing. It is drawn with no
  clearance and no taper. Standard practice is 3–5 mm clearance per side and a taper so it
  clears the opening on the hinge swing. Also, 200 × 200 from 114-wide bricks is two pieces
  with a mortar joint, in a moving plug — it will crack across the joint. We would want to
  cut it from one large-format brick. Say which.
- Grade: Morgan K-23 is specified, 1260 °C class, for a 1200 °C kiln with the element in
  direct contact with the groove (element wire runs hotter than the chamber). Most people
  put K-26 in a cone-6/cone-8 kiln for that reason. We can quote both; tell us whether to.
- Two side liners: identical or handed? The grooves are symmetric so identical works, but
  the drawing shows one hand only and the assembly sheet does not say "turn one round".
- The Ø8 thermocouple hole through the back liner at chamber mid-height (BOM note) is not on
  the drawing. Nor are the element tail passages. Drilled by whom?
- Mortar: "refractory mortar, supply from stock". Air-set IFB mortar, how many kg? We will
  quote 1 tub unless told otherwise.

**Ceramic fiber board (`fiber-slab.svg`, `fiber-side.svg`, `fiber-back.svg`, `door-fiber.svg`,
`*-flat.dxf`)**

- Material "Kaowool 1260 board, 50 + 50 + 25 mm stack, 260 kg/m³". We stock 25 and 50 in
  1260 grade at 1200 × 1000; fine. Panels of 578 × 578 cut two to a board width. OK.
- Each panel is drawn as one slab 125 thick. Do we supply three loose boards per panel, or
  a laminated 125 mm block (bonded with what — rigidizer, mortar, nothing)? Loose boards
  change how the box stacks and how you cut the fit.
- Door fiber: "50 + 50 + 50 mm stack + strip" to make 153. What is the "strip" — 3 mm
  ceramic paper, a cut-down board offcut, blanket? Which side of the stack does it go?
- The drawings carry a "FLAT PATTERN (developed blank, t = 153.0 mm)" and a "-flat.dxf"
  for 125 and 153 mm boards. Boards are not bent; we assume this is a template artefact and
  will cut from the outline only. Confirm nothing in the DXF matters beyond the rectangle.
- Tolerance ISO 2768-c on board — we hold ±2 mm with a saw. Same zero-clearance problem:
  the fiber box is drawn 578 wide into a 582 shell (2 mm per side, good) but the brick box
  328 sits inside a 328 fiber opening (zero). See above.
- The front face of the fiber box (the ring between the 328 door plug and the 582 shell
  opening) is left exposed to the door gap and to the room when the door is open. Exposed
  1260 board sheds fiber and erodes with every door swing; do you want a rigidizer coat on
  the exposed faces, or a cover plate? Not our call, but we would raise it.
- The board behind the brick sees roughly 980 °C at the interface by your numbers. 1260
  grade board shrinks 2–3 % linear after a few hundred hours up there. No joint or shrink
  allowance is shown. Again, not ours to design, but say you know.
- No thermocouple hole in the back fiber board; no element tail passages.

### Questions we would ask

1. Cut plan: may we cut from large-format K23 (single pieces), or must it be 230 × 114 × 64
   standard bricks with mortar joints? If joints, where?
2. Groove width (12?), first-groove position (50?), end condition (through), corner radius
   allowed.
3. What clearance and taper do you want on the door block, and may it be one piece?
4. Who does the final fitting of the zero-clearance joints, and do the nominal sizes include
   or exclude mortar joints?
5. K-23 or K-26?
6. Fiber: three loose boards or a bonded 125 block; adhesive; what the 3 mm "strip" is.
7. Thermocouple hole and element passages in the back liner and back board — drill here or
   on site?
8. Mortar type and quantity; rigidizer on exposed board faces yes/no.
9. Packing: cut K23 with 12 mm groove lips does not travel well. Crate or collect?

### Verdict

**Boards and plain slabs: quotable today as cut pieces. Grooved liners and the door block:
quotable with an allowance for a cut plan we would have to make ourselves, and with a line
on the quote saying every brick-to-brick and brick-to-board joint in this package is drawn
at zero clearance and will need trimming on site. Expect the K23 cost to come in above the
40–55 USD per piece estimates once the joints and grooves are real.**
