# Fresh-eyes review of the Napkin2Factory handoff

**Date:** 2026-10-30 · **Reviewed:** `napkin2factory-handoff.md` · **Companion:** `GRAND_PLAN.md` (every finding below is resolved there as a locked decision)

**Verdict:** the architecture is sound and unusually well-reasoned. "One canonical model, everything else compiled", "agents author / tools verify / humans arbitrate", BYOA, git-hidden solo mode, and the ruthless v1 cut are all right. The gaps cluster in two places: (1) wherever the doc says "agents author X" it treats X as solved, and the hardest X (CAD) is not; (2) the mechanics of the traceability graph, which is the ECO engine, are hand-waved. Findings are ordered by how much they would hurt if ignored.

---

## A. Would sink v1 if not addressed

### A1. LLM-authored CAD is the critical path and is under-specified
The entire value proposition rests on "a designer agent writes build123d code for a kiln". That is the least reliable step in the stack. Code-generated CAD works for simple prismatic parts and degrades fast with assemblies, mating features, and anything with bends. The doc discusses Class-A surfacing as a gap but not this.

**Resolution: a kit of parts.** The system ships a tested library of parametric generators (plate with hole pattern, sheet-metal enclosure with bends and flanges, tube/angle frame, L-bracket, panel with cutouts, block/layer, lid/door composite). Agents *compose* generators and drop to raw build123d only for the residue. Three side benefits fall out:
- The "10 minutes to a first silhouette" promise becomes plausible (compose a box, a frame, a door).
- Generators *know their own features*, so they emit DFM-relevant metadata (bend radii, hole-to-edge distances, flange lengths). Rule packs then operate on declared features and stay trivial and deterministic, instead of needing feature recognition on raw B-rep, which the open stack cannot do well.
- **Sheet-metal flat patterns by construction** (DXF with bend lines). The generator created the bends, so it can unfold them analytically. This is a real manufacturing deliverable the open stack otherwise cannot produce.

### A2. Designer agents have no eyes
The doc has verifier agents and deterministic checks, but nothing about the designer's inner loop. An agent writing CAD code must see what it built: multi-view renders, a section view, bounding box, volume, mass, per part. Without this the agent will ship a box named "kiln" and the verifier will pass it because the box has no interferences.

**Resolution:** `n2f build --part X` is a first-class fast path that emits PNG renders (four orthographic views plus isometric plus one section), a props JSON (bbox, volume, mass, centroid), and the feature list. The design skill instructs the agent to look at the renders before claiming done. Milestone acceptance for the build-out itself includes "open the render and look at it".

### A3. "Deterministic tools verify" still means someone writes the calcs and rules
For a kiln, the checks that matter (skin temperature, heat loss, element power, structural margin) are hand-calcs the same agent will write. That is grading your own homework one level down. A wrong rule pack is worse than none: it yields a green check matrix and false confidence.

**Resolution:** calcs are source files (`model/calcs/*.py`) with pint units, each with a cited formula and a test pinned to a hand-verified value. Rule packs ship with known-good and known-bad fixture parts. The verifier role reviews calcs specifically. Safety-flagged requirements can never auto-pass on a calc alone: release requires a human sign-off artifact. Reports state plainly: "calculations were produced by an AI system and have not been reviewed by a licensed engineer".

### A4. Two kinds of ECO are conflated
"Zero tokens for regeneration" holds only for *parametric* ECOs (change a value, rebuild, re-check). A *design* ECO (new requirement, topology change, "add a viewport to the door") needs agent authorship, and the impact report for it is partly a prediction. Manuals also contain prose that silently goes stale.

**Resolution:** the ECR schema has `kind: parametric | design`. Parametric ECRs are applied mechanically by `n2f ecr apply`. Design ECRs produce a task list for the designer agent and the impact report says which parts of the prediction are firm (graph-derived) and which are estimates. Document prose is source with templated values (`{{ P["wall-thickness"] }}`) and declared `depends_on`; stale sections are flagged and block release, never silently kept.

### A5. The traceability graph is hand-waved ("Snakemake-style")
Snakemake tracks files, not semantics. Which parameters a part's geometry actually used is only knowable at build time, unless you force static declarations, which rot immediately.

**Resolution: runtime-recorded dependencies.** The parameter accessor logs every read during a generator run; the build writes a dependency manifest per artifact; the next build invalidates on exactly the recorded inputs (sound by the usual dynamic-dependency argument: if a param change alters which other params are read, the changed param was itself read). Declared edges (`satisfies`, `interfaces`, `depends_on`) cover requirement↔parameter↔part↔document links. Impact is the union. Build a small hash-based DAG in-house (a few hundred lines) rather than depending on Snakemake: it is the heart of the product, must be tested in isolation, and must stay pure-Python for tier-0.

---

## B. Wrong or inconsistent in the doc

- **B1. CLI name.** §8 uses `factory init/ecr/impact/build/...`; §6 decides the binary is `n2f`. Lock `n2f`. The manifest becomes `n2f.yaml` rather than `factory.yaml`: one brand token everywhere, and "factory" collides with a generic word and a common code pattern.
- **B2. BOM validation via Octopart/Nexar/Digi-Key does not cover a kiln.** Firebrick, ceramic fiber board, Kanthal wire, and McMaster hardware are not in electronics distributors. McMaster has no public API. Those APIs need keys and accounts the author will not host. v1 resolution: tiered validation. Structural (COTS parts must have vendor, MPN, URL) → URL resolves (HTTP HEAD, offline-skippable) → a small curated catalog of common industrial supplies shipped with the system → external APIs later behind user-supplied keys. Unverified sources render as a visible warning in the BOM, never hidden.
- **B3. "Rebuilds identically in 2031" is not byte-identical.** OCCT output is not byte-stable across versions or platforms. Reproducibility must be defined geometrically (volume, bbox, surface area, tessellation hash at fixed deflection) and regression tests must compare that way. Pinned container by digest is v2; v1 reproducibility is a lockfile plus a pinned Python minor version.
- **B4. FreeCAD headless is not pip-installable**, so TechDraw drawings cannot be tier-0 and "zero-install" would break. v1 drawings are build123d SVG projections (hidden-line) with programmatic dimension callouts from named features and a title block. Proper GD&T drawings are an honest gap; the docs say so.
- **B5. "Verifier never saw the design conversation" cannot be guaranteed under BYOA.** Other clients may not spawn fresh contexts. The gate must be the deterministic `n2f check` enforced by the CLI and CI; agent roles are conventions layered on top. v1 should not build an orchestrator process at all: solo mode has no running orchestrator, the pipeline is `n2f build`'s DAG plus computed gates.
- **B6. Interfaces "as first-class contracts" have no mechanism.** An interface becomes a named coordinate frame plus a feature pattern (bolt pattern: count, diameter, spacing, fastener part) declared once. Generators on both sides consume it (agreement by construction) and the checker verifies that the features each party emitted match the contract.

---

## C. Missing entirely

- **C1. Safety and liability.** The tool generates designs for 1300 °C mains-powered equipment. Needs: `safety: true` on requirements (cannot auto-pass; requires a human sign-off file at release), a mandatory Safety section in every manual set, and a disclaimer in README and every report. MIT license is fine.
- **C2. The stage machine should be computed, not stored.** Stage (Intake → Design → Verify → Release) is derived from repo state by `n2f status`. No state file can drift, and "no agent can skip a stage" becomes a property of the tool rather than of prompts.
- **C3. 3D diff.** Stable node names make a cheap 3D diff possible: two viewers side by side with added/removed/changed parts colour-coded, driven by the IDs. The doc only mentions SVG drawing diffs.
- **C4. Requirement quality lint.** Intake is the most LLM-dependent stage and has no deterministic check. `n2f lint` enforces: every requirement has a measurable statement with units, a verification method, a category, and traces to at least one parameter or part (or is explicitly marked unallocated).
- **C5. Cost model data.** A "parametric cost model" needs rate tables nobody has. v1 is declared unit cost per part, quantity rollup, target comparison, and a cost delta in every ECR impact report. No oracles.
- **C6. Persona rendering is one HTML page with a toggle**, not two builds. Owner view leads with pictures, cost, and "what to tell the manufacturer"; engineer view leads with the check matrix and tolerances. Same data, different order and vocabulary.
- **C7. Vendor the viewer, and pick one with a scene-graph API.** The handoff's `<model-viewer>` has no public node access, so "click a part", "highlight what changed", and exploded views by node cannot be driven from the stable IDs. The plan uses three.js directly, pinned and vendored into a self-contained report that works from disk, for offline use and for the 2031 case (CDN links die).
- **C8. A graded test corpus.** The golden-regression idea exists; the corpus does not. v1 ships three example products: bracket (one part, three requirements), enclosure (four parts, one interface, sheet metal), kiln (the showcase). Tests run on all three.
- **C9. Resumability of the build-out itself.** The implementing agent needs a status journal and a decision log, mirroring the product's own philosophy, so that context resets during an unattended run lose nothing.

---

## D. Scope pressure
Even the "ruthless" v1 is large: product model, IDs, build graph, kit, checks, drawings, BOM, manuals, report, ECR flow, diff, release, Pages, Actions, PM skill, intake, persona, kiln. The plan orders milestones so that every milestone leaves a shippable, demoable state, and marks the tail (Actions/Pages templates, persona toggle polish, PM niceties) as droppable without touching the core loop.

---

## E. Toolchain verification (checked 2026-10-30)
- **build123d 0.12.0** on PyPI, published 2026-09-18. `export_step` confirmed in the release page; `export_gltf` and `ExportSVG` exist in the API but must be confirmed by the M0 smoke test. ([PyPI](https://pypi.org/project/build123d/0.12.0/))
- **cadquery-ocp 8.0.1.1.0** ships cp313 and cp314 wheels on Linux/macOS/Windows; the `cadquery-ocp-novtk` variant is the clearest path for 3.13/3.14. Pin Python 3.13 by default, allow 3.14. ([PyPI](https://pypi.org/project/cadquery-ocp/8.0.1.1.0/), [novtk](https://pypi.org/project/cadquery-ocp-novtk/8.0.1.1.0/), [OCP issue 200](https://github.com/CadQuery/OCP/issues/200))
- **typst (typst-py)** ships abi3 wheels; `typst.compile()` returns PDF/SVG/PNG bytes. Good for tier-0 PDF with no system dependencies. ([PyPI](https://pypi.org/project/typst), [docs](https://typst-py.readthedocs.io/en/latest/))
