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
OUT="$(mktemp -d -t n2f-kiln-napkin-out)"
echo "The shipped kiln already chose C-003; this demo rewinds that choice to replay the napkin stage."
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
$PY - <<'EOF'
from pathlib import Path

import yaml

sc = yaml.safe_load(Path("concepts/C-001.yaml").read_text(encoding="utf-8"))["screening"]
est, given = sc["estimates"], sc["given"]
low, high = est["cost_low"]["value"].removesuffix(" USD"), est["cost_high"]["value"]
heat, power = est["heat_up_time"]["value"], given["power"]["value"]
print("   C-001 tells two more stories, both in the numbers above:")
print(
    f"     cost (DEC-012): the owner hoped for about 1500 USD; screening's band is {low}–{high}"
    " (estimate), and it counts only the parts it can price, so the wish already sits inside"
    " a band that is not even complete"
)
print(
    f'     heat-up (DEC-004): the owner asked for "about four hours"; screening says {heat} at'
    f" {power} (estimate); DEC-004's 7 h is the planned margin on top of that, not the"
    " calculation"
)
EOF
echo "== the board: every direction side by side"
$N2F concept board
echo "== the owner sets the v0.1 look aside"
$N2F concept reject C-004 --reason "the owner did not like the v0.1 appearance (NAPKIN_STAGE §0)"
echo "== the owner picks C-003 as the design direction"
$N2F concept promote C-003 --by "Owner (demo)"
echo "== the factory carries on (quietly; everything it made is under build/)"
$N2F validate
$N2F lint
$N2F build --no-render --json >"$OUT/build.json"
$N2F check --json >"$OUT/checks.json"
$PY - "$OUT" <<'EOF'
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
built = json.loads((out / "build.json").read_text(encoding="utf-8"))
counts = json.loads((out / "checks.json").read_text(encoding="utf-8"))["summary"]
print(f"   built {len(built['ran'])} steps: parts, drawings, parts list, manuals, the report")
print(
    f"   checks: {counts.get('pass', 0)} OK, {counts.get('fail', 0)} need attention, "
    f"{counts.get('warn', 0)} worth a look, {counts.get('example', 0)} example sign-offs "
    "(not reviews)"
)
EOF
$N2F status
echo
echo "report           : $WORK/build/report/index.html"
echo "board            : $WORK/build/concepts/board.html"
echo "C-001 (red)      : $WORK/build/concepts/C-001/renders/styled-iso.png"
echo "C-003 (promoted) : $WORK/build/concepts/C-003/renders/styled-iso.png"
