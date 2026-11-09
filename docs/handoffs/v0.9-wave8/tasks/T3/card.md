task: T3
slug: w8-overlap-frame
goal: the napkin overlap screen tests a frame kit's members (B-0323)
kind: code
row: B-0323
allowed: src/napkin2factory/concepts/screens/overlap.py tests/unit/test_screening*.py tests/unit/test_w8_* DECISIONS.md BACKLOG.md
tests: uv run pytest tests/unit/test_w8_overlap_frame.py tests/unit/test_screening.py tests/unit/test_screening_door_touch.py -q --no-header -x

## Review points (step 6: write ok or the problem for each)
1. A piece that passes through a frame member is reported as an overlap; a piece inside the frame's open space between members is not.
2. Each frame member's own box comes from the frame kit (`geometry/kit/frame.py`), not from the frame's whole silhouette.
3. Blocks, plates and tubes behave as before (the existing screening tests pass unchanged).
4. The overlap message names both pieces and the volume in words.
5. B-0323 moved to Closed with S-NEW-1.
