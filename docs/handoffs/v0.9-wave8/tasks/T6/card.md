task: T6
slug: w8-support-check
goal: a check finds parts that are not held up (B-0328)
kind: code
row: B-0328
allowed: src/napkin2factory/domains/mechanical/* tests/unit/test_w8_* DECISIONS.md BACKLOG.md docs/cli.md docs/agent-guide.md
tests: uv run pytest tests/unit/test_w8_support_check.py -q --no-header -x

## Review points (step 6: write ok or the problem for each)
1. The new stage lives in the mechanical domain (`domains/mechanical/`), registered like the interference stage, after it. No file under `src/napkin2factory/core/` changes.
2. Ground parts: the lowest box bottom of the assembly, within 0.5 mm. Connections: two parts' boxes share a face patch of at least 1 mm² (within 0.5 mm), or a declared interface names both and their boxes are 0.5 mm to 30 mm apart. A touch along an edge only is NOT a connection.
3. Every part with geometry must connect to a ground part; the result fails and names each part that does not, in plain words.
4. Parts without a STEP file are skipped, as in the interference check.
5. The worker's report states which examples were run and that each passes (bracket, enclosure, table, test-stand at least); if one fails, the worker explains why.
6. B-0328 moved to Closed with S-NEW-1.
