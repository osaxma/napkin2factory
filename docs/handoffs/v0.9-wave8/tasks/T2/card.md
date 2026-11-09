task: T2
slug: w8-switch-missing
goal: concept switch refuses a missing or broken model/parameters.yaml plainly (B-0326)
kind: code
row: B-0326
allowed: src/napkin2factory/concepts/switch.py src/napkin2factory/cli/concept_switch.py tests/unit/test_concept_switch.py tests/unit/test_w8_* DECISIONS.md BACKLOG.md
tests: uv run pytest tests/unit/test_w8_switch_missing.py tests/unit/test_concept_switch.py -q --no-header -x

## Review points (step 6: write ok or the problem for each)
1. A missing `model/parameters.yaml` makes `n2f concept switch` exit 1 with an `N2FError` (never `engine_internal`, never exit 70).
2. The message names the file; `next` says how to put it back (`n2f undo --dir <folder>`) and to run the switch again.
3. A model problem that blocks the switch (validate fails) is reported once, with the file, field and message of the first problem, and `next` = `n2f validate --json --dir <folder>`.
4. The check runs before anything is moved or written (in the preflight).
5. Tests cover: missing file, unreadable YAML, a validate problem.
6. B-0326 moved to Closed with S-NEW-1.
