#!/usr/bin/env bash
# Write the worker brief for one wave 8 task to the run's log folder and print its path.
# The briefs in the repository spell the journal placeholder "S-NEW-1", because `make land`
# refuses a landed file that cites the real placeholder; the worker must write the real one.
set -u
TASK="${1:?usage: brief.sh T<n>}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
OUT="/Users/wakeel/n2f-wave8/logs/$TASK-worker.md"
mkdir -p "$(dirname "$OUT")"
P=S-NEW; sed -e "s/${P}-1/${P}1/g" "$HERE/tasks/$TASK/worker.md" > "$OUT"
echo "$OUT"
