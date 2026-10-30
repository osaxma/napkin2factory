# Backlog

Items dropped, deferred, or out of scope for v0.1, each with a reason. `src/` may reference
an id here in a `TODO(B-xxxx)` comment.

| id | item | reason / origin |
|---|---|---|
| B-0001 | Playwright Chromium unavailable fallback: HTML-parse checks only | Reserved for environments where the browser download fails; on this host Playwright installed and runs, so the fallback is a `pytest.skip` with reason (D30-style, never silent) |
| B-0002 | Vectorize the z-buffer rasterizer per mesh (currently a Python loop per triangle) | Measured at M2: five views of the enclosure base take <1 s; build123d import warm-up (~5 s) dominates. Revisit only if kiln renders exceed ~60 s |
| B-0003 | Python 3.14 support | Not tried; OCP novtk wheels exist for cp314 per REVIEW E but 3.13 is pinned (D2) |

## Non-goals carried from GRAND_PLAN §1.2 (v0.2+)
Electrical stage (KiCad), FEA/sim gates, MCP server, hosted anything, orchestrator process,
multi-agent runtime, upgrade migrations, manufacturer quote APIs, electronics distributor
APIs, GD&T-grade drawings, tolerance stack-up analysis, manufacturer capability profiles
beyond the schema, Class-A surfacing, Tauri wrapper, npm shim, share mode (`n2f publish`).
| B-0004 | Lock file for concurrent `n2f build` in one product folder | Gate-1 C5: two builds at once would race on the manifest (last writer wins). Rare for a solo tool; revisit with share mode |
| B-0005 | Interface check for assembly-level parties (`asm://` as a party) | Gate-1 note; v0.1 interfaces are part-to-part only (both examples and the kiln) |
| B-0006 | `validate.json` embeds absolute paths | Gate-1 note; harmless (build/ is local), tidy when the report links to it |
| B-0007 | Indent wrapped continuation lines in `n2f status`/impact output at 80 columns | Gate-2 C13; cosmetic, rich wraps without hanging indent |
| B-0008 | Hide URI prefixes (`part://`, `req://`) in owner-view tables and captions | Gate-2 C14/C15; the engineer view and files keep them |
| B-0009 | Design-time wording for inspection-type sign-offs (e.g. "the package requires deburring") vs post-manufacture gates | Gate-2 C4; needs a `when: design\|manufacture` field on manual verifies |
| B-0010 | ~~Stand standoffs, thermocouple hole and element tails are described, not modelled, in the kiln~~ | Closed by the gate-3 rework: standoffs, hinge post, latch keeper, controller mount, tail and thermocouple holes are modelled with interfaces |
| B-0011 | Multi-piece sheet-metal generator (wrap + end panels, closed corners) | Gate-3 shop read-through: deep trays cannot be brake-formed from one blank and the blanks exceed stock sheet widths; v0.1 notes allow the shop to split the one-piece development |
| B-0012 | Door-swing envelope as a geometry check (`asm://kiln#props.bbox` with the door at `door-swing`) | Gate-3 C1: the footprint requirement is evaluated closed; the owner's 800 mm alcove is exceeded by the open door (DEC-011, flagged for the owner) |
| B-0013 | K26 hot-face option for the kiln (element grooves run hotter than the chamber) | Gate-3 C9: K23 is 1260 degC class for a 1200 degC kiln; swapping `brick-conductivity`/`brick-density` and the part specs is a parametric change request |
| B-0014 | Tapered opening (reveal boards) to match the tapered door plug | Gate-3 B5/C14: the plug tapers 6° and the opening is straight, so the hot-end gap is packed with fiber blanket (consumable) |
| B-0015 | `n2f ecr close` should refuse while a requirement needs a sign-off, like `n2f release` does | Gate-4 note: close only blocks on failing checks |
| B-0016 | Warm the CAD kernel import during `n2f init` (or a post-install step) | Gate-4 B2: the first `import build123d` on a machine takes 1–2 min; v0.1 prints a notice before the stall |
| B-0017 | Section render clips triangles whole (`render.py` `section_z`), so large faces come out as slivers and the cut is hard to read on thick walls | Gate-3 rework; a true plane cut (OCCT section or per-triangle clipping) would fix it |
| B-0018 | `n2f validate` hides expression errors while reference errors are present (cascade suppression, S-012) | Gate-3 rework: thirteen bad expressions surfaced only after the reference errors were fixed; report both classes together |
