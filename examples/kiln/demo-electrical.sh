#!/usr/bin/env bash
# The wiring story, unattended (ELECTRICAL_STAGE E9, DoD 4; D23): the kiln designed with its
# wiring left for later, released v1.0.0; ECR-003 (a design change request with a patch, D7)
# adds the wiring; the supply-headroom choice it raises is decided as the project manager
# would; v1.1.0 is released with the wiring done here, and the diff page shows the Wiring
# section as added.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SYSTEM="$(cd "$HERE/../.." && pwd)"
N2F="${N2F:-uv run --project $SYSTEM n2f}"
export N2F_OFFLINE="${N2F_OFFLINE:-1}"
# GNU mktemp needs a template ending in XXXXXX; BSD -t name is macOS-only (S-175).
WORK="${DEMO_DIR:-$(mktemp -d "${TMPDIR:-/tmp}/n2f-kiln-demo-electrical.XXXXXX")}"
echo "== working copy: $WORK"
cp -R "$HERE/." "$WORK/"
rm -rf "$WORK/build"
cd "$WORK"
$N2F init . >/dev/null

HEADROOM=elec-rule://supply-headroom@supply
BOLTS=fastening://m6-standoff-25/m6x16-bolt

# Re-sign every safety requirement whose EXAMPLE sign-off a change invalidated (labelled).
resign_invalidated() {
  local reason="$1"
  for req in $($N2F check --json 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(' '.join(r['id'].split('://')[1] for r in d['results'] if r['kind']=='requirement' and r['status']=='needs-human'))"); do
    echo "== re-sign $req (EXAMPLE sign-off, NOT a review)"
    $N2F signoff "$req" --by "Example Reviewer (not a real review)" --statement "Demo re-sign after $reason; a real reviewer must repeat this check." --example
  done
}

# The status of one check row, by its id.
row_status() {
  $N2F check --json 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(next((r['status'] for r in d['results'] if r['id']=='$1'), 'absent'))"
}

# The shipped kiln is wired (its state before the change request, D23). The story starts from a
# copy whose wiring is left for later: the supply-headroom pick and its decision come out, then
# ECR-003's patch is taken back out of the model (the wiring model, the cable entries, the wiring
# parts, the wiring decision, the manual's wiring sections), and the scope says "later" again.
echo "== the wiring left for later: take ECR-003 back out of the copy"
python3 - <<'PY'
import re
import subprocess
from pathlib import Path

decs = Path("model/decisions.yaml")
text = decs.read_text(encoding="utf-8")
blocks = re.split(r"(?m)^(?=  - id: DEC-)", text)
kept = [b for b in blocks if "choice elec-rule://supply-headroom@supply" not in b]
assert len(kept) == len(blocks) - 1, "the shipped kiln has its supply-headroom decision"
decs.write_text("".join(kept), encoding="utf-8")
supply = Path("model/electrical/supply.yaml")
lines = supply.read_text(encoding="utf-8").splitlines(keepends=True)
picked = [ln for ln in lines if ln.startswith("dedicated:")]
assert len(picked) == 1, "the shipped kiln has the dedicated pick in its supply"
supply.write_text("".join(ln for ln in lines if ln not in picked), encoding="utf-8")
out = subprocess.run(["git", "apply", "-R", "changes/ECR-003.patch"], capture_output=True, text=True)
assert out.returncode == 0, out.stderr
assert not Path("model/electrical").exists()
assert "state: later" in Path("n2f.yaml").read_text(encoding="utf-8")
PY
$N2F snapshot -m "The wiring is left for later (DEC-024)"

echo "== v1.0.0: build, check, release with the wiring left for later"
$N2F build --no-render
$N2F check || true
# The bolts choice holds the release; the owner picks as in demo.sh, and the agent makes the
# pick in the model (a change request is for a released product).
echo "== a choice is waiting on the owner: decide it"
$N2F decide "$BOLTS" --pick shorter-bolts --by "demo owner" \
  --note "Keeps the standoffs and panels as they are; no nut to reach once fitted."
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
    "source: {vendor: McMaster-Carr, mpn: ISO 4762 M6 x 12, verified: false,\n"
    "  url: 'https://www.mcmaster.com/91290A/', note: the M6 x 16 family page}\n"
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
$N2F check || true
resign_invalidated "the bolts pick"
$N2F snapshot -m "Shorter bolts into the standoffs, as decided"
$N2F release v1.0.0 --no-render --allow-example-signoffs

# ECR-003's patch was written against the shipped kiln, before the bolts pick took the next
# decision number: the agent brings the patch up to date with the model, as demo-design.sh does
# for ECR-002 (S-139): the wiring decision takes the next free number, and its lines are added
# after the decisions the copy now has.
python3 - <<'PY'
import re
from pathlib import Path

p = Path("changes/ECR-003.patch")
patch = p.read_text(encoding="utf-8")
decs = Path("model/decisions.yaml").read_text(encoding="utf-8")
taken = {int(n) for n in re.findall(r"(?m)^  - id: DEC-(\d+)", decs)}
wiring = re.search(r"(?m)^\+  - id: (DEC-\d+)\n\+    date: [^\n]*\n\+    title: The wiring is designed here", patch).group(1)
nxt = f"DEC-{max(taken) + 1:03d}"
patch = patch.replace(wiring, nxt)
# the decisions hunk: the same added lines, after the last lines the file has now
head, sep, rest = patch.partition("diff --git a/model/decisions.yaml b/model/decisions.yaml\n")
body, nxt_diff, tail = rest.partition("\ndiff --git ")
added = [ln for ln in body.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
lines = decs.splitlines()
ctx = lines[-2:]
start = len(lines) - len(ctx) + 1
hunk = (
    "--- a/model/decisions.yaml\n+++ b/model/decisions.yaml\n"
    f"@@ -{start},{len(ctx)} +{start},{len(ctx) + len(added)} @@\n"
    + "".join(f" {c}\n" for c in ctx) + "".join(f"{a}\n" for a in added)
)
p.write_text(head + sep + hunk + ("diff --git " + tail if nxt_diff else ""), encoding="utf-8")
PY
$N2F snapshot -m "ECR-003's patch follows the bolts pick"

echo "== ECR-003 (design): add the wiring: impact → approve → apply patch → rebuild"
$N2F ecr impact ECR-003
$N2F ecr approve ECR-003 --by "Owner (demo)"
$N2F ecr apply ECR-003
$N2F build --no-render
$N2F check || true
# The wiring's first build raises the supply-headroom choice (E11): the project manager decides
# it conservatively, the dedicated circuit the rating label already states, and the agent makes
# the pick in the model (the supply serves the kiln alone).
status="$(row_status "$HEADROOM")"
if [ "$status" != "choice" ]; then
  echo "the supply-headroom choice was not raised (the row reads: $status)" >&2; exit 1
fi
echo "== the wiring raised a choice: the project manager decides it"
$N2F decide "$HEADROOM" --pick dedicated --by "demo project manager" \
  --note "The rating label already states a dedicated 16 A circuit; nothing else is plugged into it."
python3 - <<'PY'
from pathlib import Path

p = Path("model/electrical/supply.yaml")
text = p.read_text(encoding="utf-8")
assert "dedicated:" not in text
p.write_text(text.replace("region: EU\n", "region: EU\ndedicated: true\n", 1), encoding="utf-8")
PY
$N2F build --no-render
$N2F check || true
resign_invalidated "ECR-003"
status="$(row_status "$HEADROOM")"
if [ "$status" != "pass" ]; then
  echo "the supply-headroom row does not pass after the pick (it reads: $status)" >&2; exit 1
fi
$N2F ecr close ECR-003
echo "== v1.1.0: release with the wiring done here, and the diff"
$N2F release v1.1.0 --no-render --allow-example-signoffs
$N2F diff v1.0.0 v1.1.0
echo
echo "impact report : $WORK/build/changes/ECR-003-impact.md"
echo "diff page     : $WORK/build/site/diff/v1.0.0..v1.1.0/index.html"
echo "package       : $WORK/build/release/kiln-v1.1.0.zip"
