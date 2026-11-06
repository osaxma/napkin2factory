#!/usr/bin/env bash
# The design ECO loop, unattended: demo.sh, then ECR-005 (peephole with plug) made from the
# patch kept in changes/ECR-002.patch (D7), brought up to date with the bolts pick demo.sh made → v1.2.0.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SYSTEM="$(cd "$HERE/../.." && pwd)"
N2F="${N2F:-uv run --project $SYSTEM n2f}"
export N2F_OFFLINE="${N2F_OFFLINE:-1}"
# GNU mktemp needs a template ending in XXXXXX; BSD -t name is macOS-only (S-175).
export DEMO_DIR="${DEMO_DIR:-$(mktemp -d "${TMPDIR:-/tmp}/n2f-kiln-demo-design.XXXXXX")}"
"$HERE/demo.sh"
cd "$DEMO_DIR"

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

# ECR-002's patch was written against the shipped kiln, before demo.sh made the bolts pick:
# one line of its context (the door's bolts) moved since. The agent brings the patch up to date
# with the model, as it would for any change request written before another change (S-139).
python3 - <<'PY'
from pathlib import Path

p = Path("changes/ECR-002.patch")
text = p.read_text(encoding="utf-8")
old = "   - {part: part://m6x16-bolt, qty: 8}\n"
assert text.count(old) == 1, old
p.write_text(text.replace(old, "   - {part: part://m6x12-bolt, qty: 8}\n"), encoding="utf-8")
PY
$N2F snapshot -m "ECR-002's patch follows the bolts pick"

echo "== ECR-005 (design): start → make the edits (the kept patch) → impact → approve → rebuild → check"
$N2F ecr start --kind design --title "Add a peephole with a plug to the door" \
  --reason "The owner wants to see cones and glaze melt without opening the door." \
  --task "Add a peephole through the door, a ceramic plug as a bought part, the manufacturer note and the operation-manual safety line."
git apply changes/ECR-002.patch
$N2F ecr impact ECR-005
$N2F ecr approve ECR-005 --by "Owner (demo)"
$N2F build --no-render
$N2F check || true
resign_invalidated "ECR-005"
$N2F ecr close ECR-005
echo "== v1.2.0: release and diff"
redecide_bolts
$N2F release v1.2.0 --no-render --allow-example-signoffs
$N2F diff v1.1.0 v1.2.0
echo
echo "diff page     : $DEMO_DIR/build/site/diff/v1.1.0..v1.2.0/index.html"
echo "package       : $DEMO_DIR/build/release/kiln-v1.2.0.zip"
