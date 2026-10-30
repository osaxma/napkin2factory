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
| B-0010 | Stand standoffs, thermocouple hole and element tails are described, not modelled, in the kiln | M8 scope: installer/consumable items listed under "Open points for quotation" |
