# Schema policy: when a product's file format changes (F7)

Every product folder says which file format its files are written in: `schema: <n>` in
`n2f.yaml`. Every model is strict (an unknown key is an error, `core/model/base.py`), which is
right for catching typos and means any field change is felt by every product folder. This page
is the rule for changing the format. It is written once, here; `AGENTS.md` points at it.

## The rule

1. **Additive and optional: no bump.** A new field that is optional, with a default that
   reproduces the old behaviour exactly, does not change `schema`. Every v0.5 field is of this
   kind (F16). An old folder loads unchanged and the new field is absent from it.
2. **Anything else bumps it.** A rename, a removal, a changed meaning (a unit, a default, what
   a value selects), a field made required: bump `CURRENT` in
   `src/napkin2factory/core/model/migrate.py` by one, and in the same change ship
   - a migration registered there by `(from, to)`: `Migration(n, n + 1, title, run)`, where
     `run(root)` edits the files under the product folder in place and returns one plain-words
     line per change ("n2f.yaml: renamed …"), and `title` says what changed for the owner;
   - a fixture product of the *old* version under `tests/fixtures/schema/v<n>/`, kept for good
     (one folder per version that has existed; today `v1`, the bracket as of v0.4);
   - a test that the migration takes `v<n>` to the new version, and that the result loads;
   - the templates and `examples/` at the new version (run the migration on them).
3. **Aliases are a bridge, not a policy.** When a name changes, the old name may be read as an
   alias for one version (with a lint warning that names the new one, F8/F9), and the next
   format bump removes it with a migration.

## What the system does with it

| the folder says | `n2f init .` (the upgrade path) | every other command |
|---|---|---|
| the current format | nothing to update; sets up change tracking and missing agent files | runs |
| an older format with migrations installed | saves a snapshot of the folder as it is, applies each migration in order, writes the new `schema:`, saves a snapshot, prints what changed in plain words | stops: "this product's files are in an older file format …; run `n2f init .`" |
| an older format with no migration installed | stops, naming both formats | stops, as above |
| a newer format than this system reads | stops with a plain message ("saved by a newer napkin2factory … Update napkin2factory, then try again; nothing was changed"), touching nothing | stops with the same message, before any other validation |

`n2f init .` refuses nothing it can update, and the snapshot first means nothing is lost: the
owner can go back to the folder as it was. `n2f init . --json` reports `updated: {from, to,
steps, changes, snapshot_before}` (or `null`).

## Why

Before the maintainer's own products exist, breaking the format is free; afterwards it costs
real folders (B-0042, FOUNDATION F7). The fixture of every old version is what lets a later
system prove it still reads, and updates, what an earlier one wrote.

## Checklist for a format change

- [ ] Is the change additive with an old-behaviour default? Then stop here: no bump.
- [ ] `CURRENT` bumped; `Migration(n, n + 1, …)` registered in `core/model/migrate.py`.
- [ ] `tests/fixtures/schema/v<n>/` holds a product of the old format (copy it *before* the
      change).
- [ ] A test applies the migration to that fixture and loads the result.
- [ ] Templates (`src/napkin2factory/templates/`, then `make templates`) and `examples/` at the
      new format; product pins (S-083) and the agent guide updated if a command changed.
- [ ] A decision entry naming the change, the migration and the fixture.
