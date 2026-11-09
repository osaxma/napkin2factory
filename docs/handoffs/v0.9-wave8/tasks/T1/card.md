task: T1
slug: w8-sync-validate
goal: n2f_sync gives a failed validate's problems whole (B-0325)
kind: code
row: B-0325
allowed: src/napkin2factory/mcp/* tests/unit/test_mcp*.py tests/unit/test_w8_* DECISIONS.md BACKLOG.md
tests: uv run pytest tests/unit/test_w8_sync_validate.py tests/unit/test_mcp.py -q --no-header -x

## Review points (step 6: write ok or the problem for each)
1. A failed validate inside `n2f_sync` returns a list `problems`, each with `file`, `field`, `message` and `fix` (empty string when the validator gives none), messages whole, never cut.
2. At most 20 problems, plus `more: <n>` when there are more.
3. `next.say` names the first problem's file and field and says to fix it and call n2f_sync again.
4. The general summariser (`compact()` in `mcp/combined.py`) is unchanged for other tools.
5. A test builds a model with two known validate problems and checks both come back whole.
6. B-0325 moved to Closed with S-NEW-1; one decision entry.
