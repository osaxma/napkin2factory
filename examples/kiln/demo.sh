#!/usr/bin/env bash
# The parametric ECO loop, unattended (GRAND_PLAN §1.3 item 4, D23).
# Copies the kiln example to a temporary folder, sets up change tracking, decides the choice
# the checks hold the release on (as the owner would), makes the pick in the model (as the
# owner's agent would: a decided pick holds the release until the model shows it), releases v1.0.0,
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
# The pick is not yet a design: until the model shows it, the release refuses (S-139).
if $N2F release v1.0.0 --no-render --allow-example-signoffs --dry-run; then
  echo "the release went through with the pick not yet made" >&2; exit 1
fi
# The owner's agent makes the change, as the designer would before a first release (a change
# request is for a released product): a new M6 x 12 bolt on the parts list, taken by the joints
# that put a bolt into each end of a 25 mm standoff, and the units' quantities with them.
echo "== the agent makes the pick: M6 x 12 bolts into both ends of each 25 mm standoff"
python3 - <<'PY'
from pathlib import Path

def swap(path, old, new):
    p = Path("model") / path
    text = p.read_text(encoding="utf-8")
    assert text.count(old) == 1, (path, old)
    p.write_text(text.replace(old, new), encoding="utf-8")

Path("model/parts/m6x12-bolt.yaml").write_text(
    "id: m6x12-bolt\nrev: A\nname: M6 x 12 socket-head cap screw\nkind: cots\n"
    "process: none\ngeometry: none\n"
    "source: {vendor: McMaster-Carr, mpn: ISO 4762 M6 x 12, verified: false}\n"
    "cost: {unit: 0.40 USD, basis: estimate, note: priced like the M6 x 16}\n",
    encoding="utf-8",
)
for name in ("guard-standoff-top", "guard-standoff-left", "guard-standoff-right",
             "door-guard-standoff"):
    swap(f"interfaces/{name}.yaml", "m6x16-bolt, per_hole: 2", "m6x12-bolt, per_hole: 2")
swap("assemblies/kiln.yaml", "  - {part: part://m6x16-bolt, qty: 38}\n",
     "  - {part: part://m6x16-bolt, qty: 14}\n  - {part: part://m6x12-bolt, qty: 24}\n")
swap("assemblies/door.yaml", "m6x16-bolt, qty: 8}", "m6x12-bolt, qty: 8}")
PY
$N2F build --no-render
$N2F check || true   # safety sign-offs whose evidence changed are now needs-human
resign_invalidated "the bolts pick"
$N2F snapshot -m "Shorter bolts into the standoffs, as decided"
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
