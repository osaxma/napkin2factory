"""Gate B's scripted flow on the test stand (S-272): forward, backward, a change request, undo.

The plan (docs/stages/v0.8-bidirectional-iteration.md §6) runs this script in ``make check-full``;
the cold agents of the gate run the same steps from :func:`prepare_gate_b_start`.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import EXAMPLES, copy_product, n2f

os.environ.setdefault("N2F_OFFLINE", "1")
NO_SHOTS = {"N2F_NO_PLAYWRIGHT": "1"}
# the files that belong to a direction (plan §3), as they exist on the test stand
DIRECTION = ("model/parameters.yaml", "style.yaml")
DIRECTION_DIRS = (
    "model/parts",
    "model/assemblies",
    "model/geometry",
    "model/interfaces",
    "model/calcs",
    "model/docs",
    "model/electrical",
)

pytestmark = pytest.mark.full


def prepare_gate_b_start(dst: Path) -> Path:
    """A tracked copy of the test stand put back to "C-002 not yet promoted, model present".

    The smallest honest edit: card C-002 goes back to ``exploring`` without its recorded
    decision, and the promotion's decision (the first entry of ``model/decisions.yaml``) is
    removed. The model, the screenings and the build stay, so the first step is a promotion
    that seeds nothing new. The state is saved as the folder's starting checkpoint, so
    ``undo`` cannot step past it.
    """
    from napkin2factory.core.vcs import Vcs

    root = copy_product(EXAMPLES / "test-stand", dst, git=True, prebuilt=True)
    card = root / "concepts" / "C-002.yaml"
    text = card.read_text()
    text = text.replace("status: promoted\n", "status: exploring\n", 1)
    text = re.sub(r"^decision: \{dec: DEC-001.*\}\n", "", text, flags=re.M)
    card.write_text(text)
    decs = root / "model" / "decisions.yaml"
    dtext = decs.read_text()
    i = dtext.index("- id: DEC-001")
    j = dtext.index("- id: DEC-002")
    decs.write_text(dtext[:i] + dtext[j:])
    Vcs(root).snapshot("Gate B start")
    return root


def run(*args: str, cwd: Path, code: int = 0) -> Any:
    """Run ``n2f`` and check the exit code; the output is shown when it differs."""
    r = n2f(*args, cwd=cwd, env=NO_SHOTS)
    assert r.returncode == code, f"{args}: {r.returncode}\n{r.stdout}\n{r.stderr}"
    return r


def direction_files(root: Path) -> dict[str, bytes]:
    """Every file that belongs to a direction (plan §3), by relative path."""
    out: dict[str, bytes] = {}
    for rel in DIRECTION:
        p = root / rel
        if p.is_file():
            out[rel] = p.read_bytes()
    for d in DIRECTION_DIRS:
        for p in sorted((root / d).rglob("*")) if (root / d).is_dir() else []:
            if p.is_file():
                out[str(p.relative_to(root))] = p.read_bytes()
    return out


def checks(root: Path) -> dict[str, Any]:
    """``n2f check --json``, which exits 0 whatever the verdict (red is information)."""
    data: dict[str, Any] = json.loads(run("check", "--json", cwd=root).stdout)
    return data


def test_gate_b_flow(tmp_path: Path) -> None:
    """Forward, backward (fork, switch there and back), a change request, undo and redo."""
    root = prepare_gate_b_start(tmp_path / "test-stand")

    # 1. forward: promote, build, check; the model has 3 sub-assemblies
    out = run("concept", "promote", "C-002", cwd=root).stdout
    assert "C-002 is now the design direction (DEC-" in out
    run("build", cwd=root)
    data = checks(root)
    assert data["status"] == "ok"
    modules = {r["module"] for r in data["results"] if r.get("module")}
    assert {"base-console", "portal-gantry", "guard-shield"} <= modules
    top = (root / "model/assemblies/test-stand.yaml").read_text()
    assert top.count("asm://") == 3  # the three sub-assemblies

    # 2. fork-from-model: a new card whose numbers are labelled computed from the built design
    out = run("concept", "fork-from-model", cwd=root).stdout
    assert "C-004" in out and "forked from the built design" in out
    card = (root / "concepts/C-004.yaml").read_text()
    assert "based_on: C-002" in card
    assert "from the built design" in card.lower() or "built design" in card
    assert re.search(r"label: computed", card)
    before = direction_files(root)
    assert "model/parameters.yaml" in before and len(before) > 30

    # 3. backward: C-001 (a red card) needs the override the refusal names; then back, nothing lost
    refused = run("concept", "switch", "C-001", cwd=root, code=3)
    assert '--override --reason "…"' in refused.stderr
    assert "C-001 has problems" in refused.stderr
    out = run("concept", "switch", "C-001", "--override", "--reason", "Gate B trial", cwd=root)
    assert "C-001 (Single-column C-frame) is now the design direction" in out.stdout
    assert "C-002 (Twin-column portal) is parked" in out.stdout
    # S-277: the switch itself names what C-001 fails, and that the parts are still C-002's
    assert "the arm's tip deflects 1.82 mm (computed), beyond the 0.2 mm limit" in out.stdout
    assert "still C-002's" in out.stdout
    run("build", cwd=root)
    shown = run("concept", "show", "C-001", cwd=root).stdout
    assert "the arm's tip deflects 1.82 mm (computed), beyond the 0.2 mm limit" in shown
    out = run("concept", "switch", "C-002", cwd=root)
    assert "C-002 (Twin-column portal) is now the design direction" in out.stdout
    assert "C-001 (Single-column C-frame) is parked" in out.stdout
    assert direction_files(root) == before  # zero lost work

    # 4. a design change request, edited by hand, approved, edited again, closed
    out = run(
        "ecr",
        "start",
        "--kind",
        "design",
        "--title",
        "Raise the feet",
        "--task",
        "Raise the feet",
        cwd=root,
    ).stdout
    assert "started ECR-001 (design)" in out
    params = root / "model/parameters.yaml"
    params.write_text(
        params.read_text().replace("foot-height: {value: 10,", "foot-height: {value: 12,")
    )
    impact = run("ecr", "impact", cwd=root).stdout
    assert "model/parameters.yaml" in impact or "foot-height" in impact
    assert "saved to build/changes/ECR-001-impact.md" in impact
    run("ecr", "approve", "--by", "Gate B", cwd=root)
    params.write_text(
        params.read_text().replace("foot-height: {value: 12,", "foot-height: {value: 11,")
    )
    refused = run("ecr", "close", cwd=root, code=3)
    assert "the model changed since ECR-001 was approved" in refused.stderr
    # approving again first needs a fresh impact (the refusal says so)
    run("ecr", "impact", cwd=root)
    # closing also needs every requirement that waits for a person signed off; the refusal
    # lists them with the command (a cold agent meets this wall: see the S-272 entry)
    run("ecr", "approve", "--by", "Gate B", cwd=root)
    signed: list[str] = []
    for _ in range(4):  # a refusal lists what waits; one round may uncover a few more
        closed = n2f("ecr", "close", cwd=root, env=NO_SHOTS)
        waiting = re.findall(r"(REQ-\d+) needs a human sign-off", closed.stderr)
        if closed.returncode == 0:
            break
        assert closed.returncode == 3 and waiting, closed.stderr
        for rid in waiting:
            run(
                "signoff",
                rid,
                "--by",
                "Gate B",
                "--statement",
                "Reviewed for the Gate B trial",
                cwd=root,
            )
            signed.append(rid)
    assert closed.returncode == 0 and len(signed) >= 1, (signed, closed.stderr)
    out = closed.stdout
    assert "ECR-001" in out and "closed" in out.lower()

    # 5. an edit by hand, then undo and redo
    params.write_text(
        params.read_text().replace("foot-height: {value: 11,", "foot-height: {value: 13,")
    )
    out = run("undo", cwd=root).stdout
    assert "your unsaved edits were saved first" in out
    assert "foot-height: {value: 13," not in params.read_text()
    run("redo", cwd=root)
    assert "foot-height: {value: 13," in params.read_text()
    listing = run("checkpoints", "--all", cwd=root).stdout
    for words in (
        "Promoted C-002",
        "Forked C-004",
        "Switched to C-001",
        "Switched to C-002",
        "Started ECR-001",
        "Approved ECR-001",
        "edits since",
        "Undid:",
        "Redid:",
    ):
        assert words in listing, f"{words!r} missing from:\n{listing}"
    for w in ("commit", "branch", "git ", "HEAD"):
        assert w not in listing
