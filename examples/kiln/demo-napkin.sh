#!/usr/bin/env bash
# The napkin stage, unattended (NAPKIN_STAGE §1.3 item 5, D23).
# Copies the kiln example to a temporary folder and rewinds its napkin stage (the shipped kiln
# already chose C-003), then: four concept directions built and screened → the board → one red
# direction with its reasons → C-004 set aside → C-003 promoted (its numbers reconcile with the
# model already there) → the factory loop carries on: validate, lint, build, check.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SYSTEM="$(cd "$HERE/../.." && pwd)"
N2F="${N2F:-uv run --project $SYSTEM n2f}"
PY="${PY:-uv run --project $SYSTEM python}"
export N2F_OFFLINE="${N2F_OFFLINE:-1}"
WORK="${DEMO_DIR:-$(mktemp -d -t n2f-kiln-napkin)}"
echo "== working copy: $WORK"
cp -R "$HERE/." "$WORK/"
rm -rf "$WORK/build"
cd "$WORK"

echo "== rewind the napkin stage: every direction open again, the promotion's additions removed"
$PY - <<'EOF'
from pathlib import Path

from napkin2factory.core.yamlio import dump_roundtrip, load_roundtrip

root = Path(".")
for card in sorted((root / "concepts").glob("C-*.yaml")):
    doc = load_roundtrip(card)
    doc["status"] = "exploring"
    doc["screening"] = None
    doc["decision"] = None
    dump_roundtrip(card, doc, explicit_null=True)
reqs_path = root / "model" / "requirements.yaml"
reqs = load_roundtrip(reqs_path)
before = len(reqs["requirements"])
reqs["requirements"] = [
    r for r in reqs["requirements"] if not str(r.get("source", "")).startswith("concept C-003")
]
dump_roundtrip(reqs_path, reqs)
decs_path = root / "model" / "decisions.yaml"
decs = load_roundtrip(decs_path)
kept = [d for d in decs["decisions"] if "concepts/C-003.yaml" not in (d.get("sources") or [])]
dropped = len(decs["decisions"]) - len(kept)
decs["decisions"] = kept
dump_roundtrip(decs_path, decs)
print(
    f"   4 cards open again; {before - len(reqs['requirements'])} requirement(s) and "
    f"{dropped} decision from the earlier promotion removed (parameters and style.yaml kept)"
)
EOF
$N2F init . >/dev/null

echo "== where we are"
$N2F status
echo "== build and screen every direction (red is information, not a stop)"
$N2F concept build --all
echo "== the board: every direction side by side"
$N2F concept board
echo "== the owner sets the v0.1 look aside"
$N2F concept reject C-004 --reason "the owner did not like the v0.1 appearance (NAPKIN_STAGE §0)"
echo "== the owner picks C-003 as the design direction"
$N2F concept promote C-003 --by "Owner (demo)"
echo "== the factory carries on"
$N2F validate
$N2F lint
$N2F build --no-render
$N2F check
$N2F status
echo
echo "board            : $WORK/build/concepts/board.html"
echo "C-001 (red)      : $WORK/build/concepts/C-001/renders/styled-iso.png"
echo "C-003 (promoted) : $WORK/build/concepts/C-003/renders/styled-iso.png"
