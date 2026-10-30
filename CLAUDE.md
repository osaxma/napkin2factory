# napkin2factory — rules for agents working on this (system) repository

This is the **system** repo: the `napkin2factory` package and its CLI `n2f`. Product
repos (what `n2f init` writes; see `examples/`) have their own `CLAUDE.md`.

## Read first
`GRAND_PLAN.md` (the contract) → `STATUS.md` (where we are) → `DECISIONS.md` →
`git log --oneline -30` → `make check`.

## Non-negotiables
- `make check` is green before every commit. Never commit `build/` or `examples/*/build/`.
- Branch `v0.1-build`; commit messages `M<n>: <what>`. Never force-push, never rewrite history.
- Do not edit `LICENSE`.
- No `TODO`/`FIXME` in `src/` without a `BACKLOG.md` id (`B-0001`).
- Public functions have docstrings (ruff `D`); `mypy --strict` on `napkin2factory.core`.
- No invented engineering numbers: cite the source in the calc file and tag `[verify]` in `DECISIONS.md`.
- No git vocabulary in user-facing strings or schema fields (`docs/vocabulary.md`): draft,
  snapshot, change request, released, Revision. All git calls go through `core/vcs.py` (D31).
- Every model read inside a build rule goes through the recording accessors (`P[...]`, `I[...]`, `part()`, `req()`, `bom`), never raw YAML (D5).
- The report is fully self-contained (`file://` safe, inline module script, embedded GLBs, ≤ 20 MB) (D13).

## Commands
```
uv sync                      # environment
uv run n2f --help            # CLI
make check                   # lint + types + tests (+ examples as milestones add them)
make check-full              # + kiln + demos + timing (N2F_TIMING=1)
make templates               # sync examples/{bracket,enclosure} → src/napkin2factory/templates/
make goldens REASON="..."    # regenerate golden props, logged
```

## Layout
See `GRAND_PLAN.md` §3.1. One kit generator per file under `geometry/kit/`; one CLI verb per
module under `cli/`; schemas under `core/model/`.
