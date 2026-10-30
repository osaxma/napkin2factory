#!/usr/bin/env bash
# The design ECO loop, unattended: demo.sh, then ECR-002 (peephole with plug) applied from its
# pre-authored patch (D7) → v1.2.0.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SYSTEM="$(cd "$HERE/../.." && pwd)"
N2F="${N2F:-uv run --project $SYSTEM n2f}"
export N2F_OFFLINE="${N2F_OFFLINE:-1}"
export DEMO_DIR="${DEMO_DIR:-$(mktemp -d -t n2f-kiln-demo-design)}"
"$HERE/demo.sh"
cd "$DEMO_DIR"

# Re-sign every safety requirement whose EXAMPLE sign-off the change invalidated (labelled).
resign_invalidated() {
  local reason="$1"
  for req in $($N2F check --json 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(' '.join(r['id'].split('://')[1] for r in d['results'] if r['kind']=='requirement' and r['status']=='needs-human'))"); do
    echo "== re-sign $req (EXAMPLE sign-off, NOT a review)"
    $N2F signoff "$req" --by "Example Reviewer (not a real review)" --statement "Demo re-sign after $reason; a real reviewer must repeat this check." --example
  done
}

echo "== ECR-002 (design): impact → approve → apply patch → rebuild → check"
$N2F ecr impact ECR-002
$N2F ecr approve ECR-002 --by "Owner (demo)"
$N2F ecr apply ECR-002
$N2F build --no-render
$N2F check || true
resign_invalidated "ECR-002"
$N2F ecr close ECR-002
echo "== v1.2.0: release and diff"
$N2F release v1.2.0 --no-render --allow-example-signoffs
$N2F diff v1.1.0 v1.2.0
echo
echo "diff page     : $DEMO_DIR/build/site/diff/v1.1.0..v1.2.0/index.html"
echo "package       : $DEMO_DIR/build/release/kiln-v1.2.0.zip"
