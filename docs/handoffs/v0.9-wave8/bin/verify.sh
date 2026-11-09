#!/usr/bin/env bash
# The mechanical gate for one wave 8 task (overseer.md step 5). Prints GATE: pass or GATE: fail.
set -u
TASK="${1:?usage: verify.sh T<n>}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
CARD="$HERE/tasks/$TASK/card.md"
field() { sed -n "s/^$1: *//p" "$CARD" | head -1; }
SLUG="$(field slug)"; ALLOWED="$(field allowed)"; TESTS="$(field tests)"
DIR="/Users/wakeel/napkin2factory/.worktrees/$SLUG"
export PATH="$HOME/.local/bin:$PATH" N2F_NO_ENGINE=1
fail=0; say() { echo "- $*"; }
[ -d "$DIR" ] || { echo "GATE: fail"; say "no task folder $DIR"; exit 1; }
cd "$DIR" || exit 1
[ -z "$(git status --porcelain)" ] || { say "uncommitted changes:"; git status --short | head; fail=1; }
n=$(git rev-list --count main..HEAD); [ "$n" -ge 1 ] || { say "no commit ahead of main"; fail=1; }
git log --format=%s main..HEAD | grep -q '^WIP' && { say "a WIP commit is on the branch (fold it before landing)"; fail=1; }
for f in $(git diff --name-only main...HEAD); do
  ok=0; for g in $ALLOWED; do [[ "$f" == $g ]] && ok=1; done
  [ $ok -eq 1 ] || { say "file outside the card's allowed list: $f"; fail=1; }
done
if git diff main...HEAD -- src | grep -E '^\+' | grep -E 'TODO|FIXME' | grep -vqE 'B-[0-9]{4}|B-NEW'; then
  say "a TODO/FIXME without a backlog id was added in src/"; fail=1; fi
core=$(git diff --name-only main...HEAD -- src/napkin2factory/core | tr '\n' ' ')
[ -n "$core" ] && say "core files touched (say so in the decision entry): $core"
make lint > /tmp/w8-lint-$TASK.log 2>&1 || { say "make lint failed:"; tail -n 15 /tmp/w8-lint-$TASK.log; fail=1; }
if [ -n "$TESTS" ]; then
  bash -c "$TESTS" > /tmp/w8-tests-$TASK.log 2>&1 || { say "tests failed: $TESTS"; tail -n 25 /tmp/w8-tests-$TASK.log; fail=1; }
fi
pkill -f 'from napkin2factory.cli.engine import serve_main' 2>/dev/null
[ $fail -eq 0 ] && echo "GATE: pass" || echo "GATE: fail"
exit $fail
