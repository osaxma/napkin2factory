task: T5
slug: w8-quick-structure
goal: a quick change's impact shows the structure figures first (B-0327)
kind: code
row: B-0327
allowed: src/napkin2factory/ecr/* src/napkin2factory/cli/ecr.py src/napkin2factory/mcp/combined.py tests/unit/test_ecr*.py tests/unit/test_w8_* DECISIONS.md BACKLOG.md
tests: uv run pytest tests/unit/test_w8_quick_structure.py tests/unit/test_ecr_quick_failures.py -q --no-header -x

## Review points (step 6: write ok or the problem for each)
1. The impact of `ecr quick` (and `ecr impact`) lists the product's structure requirements first, each with before and after figures, the limit, and pass or fail in words.
2. The MCP `n2f_ecr` result keeps that order and does not cut those lines.
3. A product with no structure requirement gets one line saying the sag is not checked, and a `next` that says how to add one.
4. Nothing else in the impact changes order or content.
5. B-0327 moved to Closed with S-NEW-1.
