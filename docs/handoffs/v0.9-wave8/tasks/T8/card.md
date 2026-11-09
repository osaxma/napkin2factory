task: T8
slug: w8-switch-reseed-design
goal: a design note for re-seeding the model on a concept switch (B-0329), no code
kind: doc
row: B-0329
allowed: docs/handoffs/v0.9-b0329-design.md
tests: test -s docs/handoffs/v0.9-b0329-design.md

## Review points (step 6: write ok or the problem for each)
1. Only `docs/handoffs/v0.9-b0329-design.md` is added; no code changes.
2. It answers each question in the brief with file and function names from the code, and marks every guess as a guess.
3. It is at most 120 lines and ends with a short list of the tests the change would need.
4. B-0329 stays open (this is a proposal for review).

## How to run this task (kind: doc)
Follow the procedure as for code (task folder, worker, gate, land). The gate's lint and the doc
test are enough. The land runs the usual gate. Finish with RESULT `landed`.
