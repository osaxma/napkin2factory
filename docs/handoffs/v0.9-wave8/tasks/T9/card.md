task: T9
slug: w8-close
goal: close wave 8: handoff, STATUS line, wave entry with make check on main
kind: code
row: close
allowed: docs/handoffs/v0.9-overseer.md STATUS.md DECISIONS.md
tests: test -s /Users/wakeel/n2f-wave8/check.txt

## Review points (step 6: write ok or the problem for each)
1. The handoff's 'Where it stands' has a wave 8 line with each task's outcome (landed, done, blocked and why), from `/Users/wakeel/n2f-wave8/state.md`.
2. 'In flight' lists every task folder that `make tasks` still shows (parked tasks), each with its goal; otherwise 'Nothing'.
3. 'Next, in order' starts with: the review of wave 8 by the maintainer's reviewer, then the parked tasks, then B-0329 from its design note, then the third persona run, then M6.
4. The decision entry `S-NEW-1` records the `make check` result on main from `/Users/wakeel/n2f-wave8/check.txt` (passed, skipped, failed, time), the count of `core/` files touched in v0.9, and the wave's commits.
5. Nothing else changes.

## Before the worker (T9 only)
In the main folder, run `make check` and keep its last lines:
`cd /Users/wakeel/napkin2factory && PATH=$HOME/.local/bin:$PATH make check > /Users/wakeel/n2f-wave8/check-full.log 2>&1; echo "exit $?" >> /Users/wakeel/n2f-wave8/check-full.log; tail -n 15 /Users/wakeel/n2f-wave8/check-full.log > /Users/wakeel/n2f-wave8/check.txt`
It takes 8 to 12 minutes; wait for it. Then follow the procedure from step 3. If make check
failed, still run the worker: the entry records the failure, and 'Next, in order' puts fixing it
first.
