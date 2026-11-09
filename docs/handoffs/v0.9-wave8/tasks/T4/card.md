task: T4
slug: w8-seed-conflict
goal: promotion never seeds a requirement the card's own screening fails, and says so (B-0324)
kind: code
row: B-0324
allowed: src/napkin2factory/concepts/promote/* tests/unit/test_promote*.py tests/unit/test_w8_* DECISIONS.md BACKLOG.md
tests: uv run pytest tests/unit/test_w8_seed_conflict.py tests/unit/test_promote_seed.py tests/unit/test_promote_loads.py tests/unit/test_promote.py -q --no-header -x

## Review points (step 6: write ok or the problem for each)
1. A requirement whose limit the card's own screening figure already breaks is not written to the model.
2. The promotion result lists it under `conflicts`: requirement title, the limit, the card's figure, both with units, and a sentence for the owner.
3. The result's `next` (when there are conflicts) says to ask the owner whether to drop the limit or change the design, before building.
4. Requirements the card passes are seeded as before (existing promote tests unchanged).
5. B-0324 moved to Closed with S-NEW-1.
