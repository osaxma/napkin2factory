#!/usr/bin/env bash
# Start one overseer for one wave 8 task and log it (README.md, coordinator.md step 3).
# OVERSEER_CMD comes from the launch prompt: a command that takes the prompt text as its last
# argument and runs one non-interactive session to the end. Kept out of this file so the
# repository names no model or client (AGENTS.md, S-076).
set -u
TASK="${1:?usage: run-overseer.sh T<n>}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
CARD="$HERE/tasks/$TASK/card.md"
LOGS=/Users/wakeel/n2f-wave8/logs
[ -f "$CARD" ] || { echo "no card: $CARD"; exit 2; }
[ -n "${OVERSEER_CMD:-}" ] || { echo "OVERSEER_CMD is not set"; exit 2; }
mkdir -p "$LOGS"
PROMPT="$LOGS/$TASK-prompt.md"
{ cat "$HERE/overseer.md"; echo; echo "<card>"; cat "$CARD"; echo "</card>"; } > "$PROMPT"
cd /Users/wakeel/napkin2factory || exit 2
echo "== $TASK overseer started $(date '+%F %T')" | tee -a "$LOGS/$TASK-overseer.log"
# shellcheck disable=SC2086
$OVERSEER_CMD "$(cat "$PROMPT")" >> "$LOGS/$TASK-overseer.log" 2>&1
rc=$?
echo "== $TASK overseer ended $(date '+%F %T') exit $rc" | tee -a "$LOGS/$TASK-overseer.log"
tail -n 8 "$LOGS/$TASK-overseer.log"
exit $rc
