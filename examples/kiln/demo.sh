#!/usr/bin/env bash
# The parametric ECO loop, unattended (GRAND_PLAN §1.3 item 4, D23).
# Copies the kiln example to a temporary folder, sets up change tracking, decides the choice
# the checks hold the release on (as the owner would), releases v1.0.0,
# runs ECR-001 (chamber height +50 mm) through impact → approve → apply → rebuild → check →
# re-sign (an EXAMPLE sign-off, labelled as such) → release v1.1.0, and builds the diff page.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SYSTEM="$(cd "$HERE/../.." && pwd)"
N2F="${N2F:-uv run --project $SYSTEM n2f}"
export N2F_OFFLINE="${N2F_OFFLINE:-1}"
WORK="${DEMO_DIR:-$(mktemp -d -t n2f-kiln-demo)}"
echo "== working copy: $WORK"
cp -R "$HERE/." "$WORK/"
rm -rf "$WORK/build"
cd "$WORK"
$N2F init . >/dev/null

# A change that moves what the bolts choice was decided on reopens it (it holds the release):
# the owner decides it again, the same way.
BOLTS=fastening://m6-standoff-25/m6x16-bolt
redecide_bolts() {
  if $N2F status --json | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if any(c['id']=='$BOLTS' for c in d.get('waiting_on_you', [])) else 1)"; then
    echo "== the change reopened the choice: the owner decides it again"
    $N2F decide "$BOLTS" --pick shorter-bolts --by "demo owner" \
      --note "Keeps the standoffs and panels as they are; no nut to reach once fitted."
  fi
}

# Re-sign every safety requirement whose EXAMPLE sign-off the change invalidated (labelled).
resign_invalidated() {
  local reason="$1"
  for req in $($N2F check --json 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(' '.join(r['id'].split('://')[1] for r in d['results'] if r['kind']=='requirement' and r['status']=='needs-human'))"); do
    echo "== re-sign $req (EXAMPLE sign-off, NOT a review)"
    $N2F signoff "$req" --by "Example Reviewer (not a real review)" --statement "Demo re-sign after $reason; a real reviewer must repeat this check." --example
  done
}

echo "== v1.0.0: build, check, release"
$N2F build --no-render
$N2F check
# The check offers a choice that holds the release (the bolts meet inside the bottom
# standoffs). The demo plays the owner and picks what a careful owner would: shorter bolts
# keep every part where it is and need no nut reached behind a fitted panel.
echo "== a choice is waiting on the owner: decide it"
$N2F decide "$BOLTS" --pick shorter-bolts --by "demo owner" \
  --note "Keeps the standoffs and panels as they are; no nut to reach once fitted."
$N2F release v1.0.0 --no-render --allow-example-signoffs
echo "== ECR-001: impact → approve → apply → rebuild → check"
$N2F ecr impact ECR-001
$N2F ecr approve ECR-001 --by "Owner (demo)"
$N2F ecr apply ECR-001
$N2F build --no-render
$N2F check || true   # safety sign-offs whose evidence changed are now needs-human
resign_invalidated "ECR-001"
$N2F ecr close ECR-001
echo "== v1.1.0: release and diff"
redecide_bolts
$N2F release v1.1.0 --no-render --allow-example-signoffs
$N2F diff v1.0.0 v1.1.0
echo
echo "impact report : $WORK/build/changes/ECR-001-impact.md"
echo "diff page     : $WORK/build/site/diff/v1.0.0..v1.1.0/index.html"
echo "package       : $WORK/build/release/kiln-v1.1.0.zip"
echo "site          : $WORK/build/site/index.html"
