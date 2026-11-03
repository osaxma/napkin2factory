# Pre-v0.7 Housecleaning & Foundation Tidy-Up Plan (`pre-v0.7-todo.md`)

> [!NOTE]
> **Status (2026-11-03): done**
> - §1 (Replace blind token matching in `test_no_example_identifiers.py`): landed in S-185.
> - §2 (Repository root & `docs/` reorganization): landed in S-189; OWNER-TODO items (token rotation, PyPI environments) left to the owner.
> - §3.1 (Stop silent mild-steel density fallback): landed in S-186.
> - §3.2 (Stop silent `UnitError` swallowing, B-0163): landed in S-182.
> - §3.3 (Include electrical cables in BOM rollups, B-0128): landed in S-188.
> - §3.4 (Flag unpriced parts in ECR impact deltas): landed in S-187.
> - §4.1 (Runtime dependencies): Pillow landed in S-182; widening `requires-python` to `>=3.12` declined (rests on a wrong premise: `pyproject.toml` already says `>=3.13,<3.15` and B-0072 holds the Python plan).
> - §4.2 (Fix domain circular import B-0156 & rule output path validation B-0105): landed in S-182.
> - §4.3 (Split overgrown modules): landed in S-184 (B-0185 for the modules still over 550 lines).
> (v0.6.0 release landed in S-183.)

> [!IMPORTANT]
> **When to Execute:** Immediately **after** v0.6 is closed and tagged (`v0.6.0`), and **before** starting Track A (`v0.7`). Waiting until v0.6 lands avoids merge conflicts with the three active v0.6 worktrees (`gate-g-checks`, `seam-impact`, `wiring-disclaimer`).

---

## 1. Replace Blind Token Matching in [`test_no_example_identifiers.py`](../../tests/unit/test_no_example_identifiers.py)

### The Problem
Currently, [`test_no_example_identifiers.py`](../../tests/unit/test_no_example_identifiers.py#L140-L189) extracts every product name, part ID, parameter slug, and interface ID from `examples/*` and scans **every token in every file** under `src/napkin2factory/` (including HTML tags like `<table>`, English prose in docstrings/comments, CSS classes, and generic compound nouns like `top-rail` or `base-plate`).
- If an example is named `examples/table`, the test fails in 70 package files because `<table>` and `"gate table"` contain the word `table`.
- If an example names a part `base-plate` or `power-cord`, no comment or docstring in `src/napkin2factory/` can ever use that phrase.

### The Recommended Fix (Zero False Positives, 100% Leak Prevention)
Replace the blind full-text regex scanner with **three targeted structural checks** that test what `F9` (`S-128`) actually cares about—preventing product-specific vocabulary from leaking into the engine's schemas, screens, or rules:

1. **Check 1 — Schema & Screen Field Registration Guard (AST-based):**
   - Inspect only Python AST dictionary/attribute reads inside `src/napkin2factory/core/`, `src/napkin2factory/concepts/`, `src/napkin2factory/domains/`, and `src/napkin2factory/calckit/`.
   - Verify that any string key read from a concept card's `envelope` / `site` or a model's `parameters` is explicitly declared in a registered `Screen.fields` or `Domain` contract (never an undeclared example-specific key like `alcove_width`).
2. **Check 2 — Qualified URI & ID Guard (Not Plain English Nouns):**
   - Check that `src/napkin2factory/` (excluding `templates/`) never contains qualified example URIs (`part://<example-part>`, `asm://<example-asm>`, `ifc://<example-ifc>`, `elec://<example-dev>`) or example-only requirement/decision IDs (`REQ-024`, `DEC-021`, `ECR-001`), nor any path reference to `examples/<name>`.
   - Stop banning unqualified English product names (`table`, `stand`, `kiln`) in HTML templates, CSS, JS, and comments.
3. **Check 3 — Synthetic Minimal Fixture Test:**
   - Run `n2f validate`, `n2f lint`, `n2f build`, and `n2f check` on a minimal 1-part synthetic fixture in `tests/unit/` whose part, parameter, and product names are randomized (`prod_xyz`, `part_abc`). If core code ever assumes an example's identifier exists, the synthetic fixture fails deterministically.

**Outcome:** You can name Tier 1 `examples/table` (or `examples/workbench`), Tier 2 `examples/test-stand`, and use natural engineering words (`base-plate`, `top-rail`, `load-cell`) without ever fighting false positives again.

---

## 2. Repository Root & `docs/` Directory Organization

### The Problem
The repository root currently holds **14 Markdown files**, mixing evergreen entry points, historical stage plans, old version handoff reports, and temporary notes:
- Root previously: `README.md`, `AGENTS.md`, `STATUS.md`, `DECISIONS.md`, `BACKLOG.md`, `docs/stages/v0.1-grand-plan.md`, `docs/stages/v0.2-napkin-stage.md`, `docs/stages/v0.4-product-structure.md`, `docs/stages/v0.5-foundation.md`, `docs/stages/v0.6-electrical-stage.md`, `docs/handoffs/HANDOFF-REPORT-v0.1.md`, `docs/handoffs/HANDOFF-REPORT-v0.2.md`, `docs/handoffs/HANDOFF-REPORT-v0.4.md`, `docs/handoffs/HANDOFF-REPORT-v0.5.md`, `docs/history/v0.6-nightly-publish-tests.md`, `OWNER-TODO.md`.

### The Recommended Layout
Keep only the **5 canonical living files** (+ `LICENSE`) at the repository root, and organize everything else cleanly under `docs/`:

```text
/Users/wakeel/napkin2factory/
├── README.md                  # Owner-facing landing page
├── AGENTS.md                  # Developer & agent instructions (single source of truth)
├── STATUS.md                  # Current version, milestone & host state
├── DECISIONS.md               # Active architectural & gate decisions
├── BACKLOG.md                 # Open & closed work items
├── LICENSE
└── docs/
    ├── stages/                # Completed & active stage plans (moved from root)
    │   ├── v0.1-grand-plan.md         (was v0.1 GRAND_PLAN)
    │   ├── v0.2-napkin-stage.md       (was v0.2 NAPKIN_STAGE)
    │   ├── v0.4-product-structure.md  (was v0.4 PRODUCT_STRUCTURE)
    │   ├── v0.5-foundation.md         (was v0.5 FOUNDATION)
    │   └── v0.6-electrical-stage.md   (was v0.6 ELECTRICAL_STAGE)
    ├── roadmap/               # Forward-looking Track A–D plans (v0.7 → v1.0)
    │   ├── TRACK_A_EVERYDAY_BREADTH.md
    │   ├── TRACK_B_BIDIRECTIONAL_ITERATION.md
    │   ├── TRACK_C_PROGRESSIVE_WORKBENCH.md
    │   └── TRACK_D_AGENT_UBIQUITY.md
    ├── handoffs/              # Version close-out handoff reports (moved from root)
    │   ├── HANDOFF-REPORT-v0.1        (was v0.1 report)
    │   ├── HANDOFF-REPORT-v0.2
    │   ├── HANDOFF-REPORT-v0.4
    │   ├── HANDOFF-REPORT-v0.5
    │   └── HANDOFF-REPORT-v0.6
    ├── decisions/             # Archived decision logs by version (v0.1.md .. v0.6.md)
    ├── reviews/               # Gate review reports & visual artifacts
    └── reference/             # (or keep directly under docs/: agent-guide.md, cli.md, domains.md, ...)
```

- **Cleanup actions during move:**
  - Delete `FIX_CI_NIGHTLY.md` (already fixed in `abe64c9`, `S-177`) and remove its line from `.git/info/exclude`.
  - Complete and delete `OWNER-TODO.md` once the leaked GitHub token is rotated and PyPI tag protection is enabled.
  - Archive or remove `docs/v06-handoff/` once `docs/handoffs/HANDOFF-REPORT-v0.6.md` lands.
  - Update path references in `AGENTS.md`, `STATUS.md`, and `tests/` so all links resolve cleanly.

---

## 3. Accuracy & Silent-Fallback Fixes Before v0.7

1. **Stop Silent Mild-Steel Fallback (`geometry/materials.py:84`):**
   - In [`density_kg_m3`](../../src/napkin2factory/geometry/materials.py#L72-L84), an unrecognized material name currently logs a warning string and returns `DEFAULT_DENSITY = 7850.0` (mild steel). Fail `n2f check` (`materials` stage) whenever a custom part's material is neither in the material table nor given an explicit cited density.
2. **Stop Silent `UnitError` Swallowing (`B-0163`):**
   - In [`domains/electrical/checks/calcs.py`](../../src/napkin2factory/domains/electrical/checks/calcs.py#L207-L211), `_param_watts` catches `pint.DimensionalityError` and returns `None`, reporting `"has no rating"` instead of `"wrong unit dimensionality (expected power in W, got kg)"`. Surface unit mismatches explicitly.
3. **Include Electrical Cables in BOM Rollups (`B-0128`):**
   - Roll `build/wiring/cables.csv` costs/lengths into `build/bom/rollups.json` (or explicitly flag unpriced cables) so total BOM cost includes wiring.
4. **Flag Unpriced Parts in ECR Impact Deltas (Gate H C1):**
   - When `unit_price: None` on any added/changed part in an ECR, report `"cost delta: +$X.XX (+ N unpriced custom part(s))"` rather than a misleading `$0.00`.

---

## 4. Packaging, Security & Code Health Cleanup

1. **Fix Runtime Dependencies in [`pyproject.toml`](../../pyproject.toml#L18-L59):**
   - Add `pillow` to runtime `dependencies` (`B-0072`).
   - Widen `requires-python` from `>=3.12,<3.13` to `>=3.12,<3.15` (and update `packaging/n2f/pyproject.toml`).
2. **Fix Domain Circular Import (`B-0156`) & Rule Output Path Validation (`B-0105`):**
   - Ensure importing `napkin2factory.domains.electrical` before `napkin2factory.core.registry` does not raise a circular import error.
   - Validate in `core/graph/` that every `RuleDecl.outputs` path resolves inside `build/`.
3. **Split Overgrown Modules Back Under the 600-Line Target (`B10`):**
   - Split [`domains/electrical/model/__init__.py`](../../src/napkin2factory/domains/electrical/model/__init__.py) (978 lines), [`domains/electrical/checks/stage.py`](../../src/napkin2factory/domains/electrical/checks/stage.py) (870 lines), [`domains/electrical/outputs/diagram.py`](../../src/napkin2factory/domains/electrical/outputs/diagram.py) (855 lines), [`core/graph/impact.py`](../../src/napkin2factory/core/graph/impact.py) (813 lines), and [`report/builder.py`](../../src/napkin2factory/report/builder.py) (808 lines) into focused submodules before v0.7 adds new features to them.
