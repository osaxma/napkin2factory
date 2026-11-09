task: T7
slug: w8-trial-sandbox
goal: the trial sandbox blocks package installs (outside the repository)
kind: outside
row: S-339 §6
allowed: 
tests: bash /Users/wakeel/n2f-trial/rerun/smoke.sh

## Review points (step 6: write ok or the problem for each)
1. `/Users/wakeel/n2f-trial/rerun/run.sh` sets the package-index variables for the agent before `sandbox-exec`.
2. `smoke.sh` has a new step proving `pip` and `uv` cannot install `napkin2factory` inside the sandbox, and it passes.
3. No file in the napkin2factory repository changed. No key printed. dsh not started.

## How to run this task (kind: outside)
Skip the task folder and `make land`. Run the worker with `--cwd /Users/wakeel/n2f-trial/rerun`
(step 4), then run the card's tests yourself and check the review points by reading `run.sh` and
`smoke.sh`. Finish with RESULT `done`, or `blocked`.
