"""v0.8 M2b: live change requests, edited in place (R6, R7, R9, S-254).

Every flow runs on a prebuilt copy of the bracket (S-196), so the baseline copy and the
rebuilds are incremental.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from napkin2factory.core import checkpoints
from napkin2factory.core.vcs import Vcs
from napkin2factory.ecr.checkpointing import APPROVAL_HASH_EXCLUDE
from tests.conftest import EXAMPLES, copy_product, n2f
from tests.e2e.test_ecr import _no_git_words

os.environ.setdefault("N2F_OFFLINE", "1")

PARAMS = "model/parameters.yaml"
PART = "model/parts/l-bracket.yaml"
ASM = "model/assemblies/bracket.yaml"
PAD = """id: rubber-pad
rev: A
name: Rubber pad
kind: cots
process: none
material: {name: rubber, spec: "neoprene pad, 20 x 20 x 3 mm"}
geometry: none
source: {vendor: McMaster-Carr, mpn: "neoprene pad", url: "https://www.mcmaster.com/"}
lead_time: 3 d
mass: 0.010 kg
interfaces: []
satisfies: []
"""


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return copy_product(EXAMPLES / "bracket", tmp_path / "b", prebuilt=True, render=False)


def _run(*args: str, cwd: Path, ok: bool = True) -> Any:
    r = n2f(*args, cwd=cwd)
    if ok:
        assert r.returncode == 0, f"{args}: {r.stdout}\n{r.stderr}"
    _no_git_words(r.stdout + r.stderr)
    return r


def _json(*args: str, cwd: Path) -> dict[str, Any]:
    out: dict[str, Any] = json.loads(_run(*args, "--json", cwd=cwd).stdout)
    return out


def _edit(root: Path, rel: str, old: str, new: str) -> None:
    path = root / rel
    text = path.read_text()
    assert old in text, (rel, old)
    path.write_text(text.replace(old, new, 1))


def _ecr(root: Path, ecr_id: str = "ECR-001") -> dict[str, Any]:
    out: dict[str, Any] = yaml.safe_load((root / f"changes/{ecr_id}.yaml").read_text())
    return out


def _log(root: Path) -> list[checkpoints.Checkpoint]:
    """The checkpoints, oldest first."""
    return sorted(checkpoints.read(Vcs(root)), key=lambda c: c.number)


def test_start_saves_unsaved_edits_and_leaves_them_out_of_the_impact(root: Path) -> None:
    _edit(root, PARAMS, "hole-spacing:      {value: 36", "hole-spacing:      {value: 38")
    out = _json("ecr", "start", "--title", "Thicker steel", "--reason", "stiffer", cwd=root)
    assert out["id"] == "ECR-001" and out["status"] == "draft"
    log = _log(root)
    labels = [c.label for c in log]
    assert labels[-2] == "hole-spacing 36 mm → 38 mm" and (log[-2].since or "").startswith(
        "edits since"
    )
    assert labels[-1] == "Started ECR-001: Thicker steel"
    assert out["checkpoint"] == log[-1].id
    # the baseline is the checkpoint holding the unsaved edit; the start checkpoint follows it
    data = _ecr(root)
    assert data["baseline"]["checkpoint"] == log[-2].id == out["baseline"]
    assert Vcs(root).read_ref("ecr/ECR-001/baseline") == log[-2].id
    assert log[-1].number == log[-2].number + 1
    _edit(root, PARAMS, "bracket-width:     {value: 60", "bracket-width:     {value: 70")
    impact = _json("ecr", "impact", cwd=root)
    assert impact["objects"]["changed"] == ["param://bracket-width"]  # not hole-spacing
    assert impact["files"]["changed"] == [PARAMS]
    assert (
        impact["parameters"][0]["before"] == "60 mm" and impact["parameters"][0]["after"] == "70 mm"
    )
    assert impact["checkpoint"] == log[-1].id


def test_one_parameter_request_start_impact_approve_close(root: Path) -> None:
    started = _json(
        "ecr", "start", "--title", "Thicker", "--set", "param://bracket-width=70mm", cwd=root
    )
    assert started["edits"] and started["checkpoint"] != started["baseline"]
    assert "bracket-width:     {value: 70" in (root / PARAMS).read_text()  # comments kept
    assert re.search(r"set bracket-width to 70mm", _log(root)[-1].label)
    text = _run("ecr", "impact", cwd=root).stdout
    assert "Mass (computed): " in text and "→" in text and "Cost (estimate, " in text
    assert "Envelope (computed)" in text and "computed from the built design" not in text
    assert (root / "build/changes/ECR-001-impact.md").is_file()
    assert (root / "build/changes/ECR-001/baseline.json").is_file()
    impact = _json("ecr", "impact", "ECR-001", cwd=root)  # the cached baseline is reused
    assert impact["mass"]["delta"] > 0 and impact["mass"]["unit"] == "kg"
    assert impact["cost"]["complete"] is True and impact["cost"]["unpriced"] == []
    assert "part:l-bracket" in impact["rebuilt"]
    assert impact["envelope"]["asm://bracket"]["after"]
    assert _ecr(root)["impact"]["model_hash"] == impact["model_hash"]
    approved = _json("ecr", "approve", "--by", "Owner", "--note", "ok", cwd=root)
    assert approved["status"] == "approved"
    data = _ecr(root)
    vcs = Vcs(root)
    assert data["approval"]["model_hash"] == vcs.working_hash(exclude=APPROVAL_HASH_EXCLUDE)
    assert _log(root)[-1].label == "Approved ECR-001 by Owner"
    closed = _json("ecr", "close", cwd=root)
    assert closed["status"] == "closed" and closed["bumped"]["part://l-bracket"] == ["A", "B"]
    assert closed["checkpoint"] == _log(root)[-1].id
    assert _log(root)[-1].label == "Closed ECR-001: Thicker"
    assert _ecr(root)["status"] == "closed"
    assert "ECR-001" in (root / "CHANGELOG.md").read_text()
    assert "rev: B" in (root / PART).read_text()


def test_design_request_reports_added_and_changed_objects(root: Path) -> None:
    _run(
        "ecr",
        "start",
        "--title",
        "Add a pad",
        "--kind",
        "design",
        "--task",
        "Place a pad",
        cwd=root,
    )
    (root / "model/parts/rubber-pad.yaml").write_text(PAD)
    _edit(
        root,
        ASM,
        "  - {part: part://l-bracket, qty: 1}\n",
        "  - {part: part://l-bracket, qty: 1}\n  - {part: part://rubber-pad, qty: 2}\n",
    )
    _edit(root, PART, "finish: powder coat, black", "finish: powder coat, white")
    impact = _json("ecr", "impact", cwd=root)
    assert impact["objects"]["added"] == ["part://rubber-pad"]
    assert {"part://l-bracket", "asm://bracket"} <= set(impact["objects"]["changed"])
    assert "model/parts/rubber-pad.yaml" in impact["files"]["added"]
    assert impact["revs"] == {"rubber-pad": "A"}
    # the added part has no price: named, never a silent zero
    assert impact["cost"]["unpriced"] == ["part://rubber-pad"]
    assert impact["cost"]["newly_unpriced"] == ["part://rubber-pad"]
    assert impact["cost"]["complete"] is False
    text = (root / "build/changes/ECR-001-impact.md").read_text()
    assert "no price on 1 part(s)" in text and "`rubber-pad`" in text
    assert "Designer tasks" in text and "Place a pad" in text
    _run("ecr", "approve", "--by", "Owner", cwd=root)
    closed = _json("ecr", "close", cwd=root)
    assert closed["bumped"]["part://l-bracket"] == ["A", "B"]
    assert "part://rubber-pad" not in closed["bumped"]  # born in this request: stays at rev A
    assert "rev: A" in (root / "model/parts/rubber-pad.yaml").read_text()


def test_close_sees_edits_never_saved_b_0060(root: Path) -> None:
    _run("ecr", "start", "--title", "White", cwd=root)
    _edit(root, PART, "finish: powder coat, black", "finish: powder coat, white")  # unsaved
    assert Vcs(root).unsaved_files() == [PART]
    _run("ecr", "impact", cwd=root)
    _run("ecr", "approve", "--by", "Owner", cwd=root)
    # a further unsaved edit after the approval is seen by close, and refused
    _edit(root, PART, "lead_time: 5 d", "lead_time: 6 d")
    r = _run("ecr", "close", cwd=root, ok=False)
    assert r.returncode == 3 and "changed since ECR-001 was approved" in " ".join(r.stderr.split())
    assert "n2f ecr impact" in r.stderr and "n2f ecr approve" in r.stderr
    assert _ecr(root)["status"] == "approved"
    # review again: impact puts it back to draft, approve binds the new model, close passes
    _run("ecr", "impact", cwd=root)
    assert _ecr(root)["status"] == "draft" and "approval" not in _ecr(root)
    _run("ecr", "approve", "--by", "Owner", cwd=root)
    closed = _json("ecr", "close", cwd=root)
    # the finish edit was never saved by anyone before the request ran: still in the revision
    assert closed["bumped"]["part://l-bracket"] == ["A", "B"]


def test_approve_refuses_after_an_edit_since_the_impact(root: Path) -> None:
    _run("ecr", "start", "--title", "T", "--set", "param://bracket-width=70mm", cwd=root)
    r = _run("ecr", "approve", "--by", "x", cwd=root, ok=False)
    assert r.returncode == 3 and "no impact report yet" in " ".join(r.stderr.split())
    _run("ecr", "impact", cwd=root)
    _edit(root, PARAMS, "hole-spacing:      {value: 36", "hole-spacing:      {value: 37")
    r = _run("ecr", "approve", "--by", "x", cwd=root, ok=False)
    err = " ".join(r.stderr.split())
    assert r.returncode == 3 and "changed since the impact of ECR-001 was computed" in err
    assert "n2f ecr impact ECR-001" in err


def test_abort_restores_the_start_is_recorded_and_can_be_undone(root: Path) -> None:
    before = (root / PARAMS).read_text()
    start = _json("ecr", "start", "--title", "Never mind", cwd=root)
    _edit(root, PARAMS, "bracket-width:     {value: 60", "bracket-width:     {value: 80")
    (root / "model/notes.md").write_text("scratch\n")  # a new, unsaved file
    out = _json("ecr", "abort", "--reason", "too heavy", cwd=root)
    assert out["status"] == "aborted" and out["restored"] == start["checkpoint"]
    assert out["saved"] and out["checkpoint"] == _log(root)[-1].id
    assert (root / PARAMS).read_text() == before and not (root / "model/notes.md").exists()
    data = _ecr(root)
    assert data["status"] == "aborted" and data["aborted_reason"] == "too heavy"
    log = _log(root)
    assert (
        log[-1].label == "Aborted ECR-001: Never mind" and log[-1].restores == start["checkpoint"]
    )
    assert log[-2].label == "bracket-width 60 mm → 80 mm" and (log[-2].since or "").startswith(
        "edits since"
    )  # the aborted work is a checkpoint
    # undo = restore the checkpoint before the abort: the request and its edits come back
    plan = checkpoints.undo_plan(log)
    assert plan is not None and plan.undoes.id == log[-1].id and plan.restores.id == log[-2].id
    Vcs(root).restore(plan.restores.id)
    assert "bracket-width:     {value: 80" in (root / PARAMS).read_text()
    assert (root / "model/notes.md").is_file() and _ecr(root)["status"] == "draft"
    # and a new request can start once the first is gone
    _run("ecr", "abort", cwd=root)
    again = _run("ecr", "start", "--title", "Second", cwd=root)
    assert "ECR-002" in again.stdout


def test_one_open_request_at_a_time(root: Path) -> None:
    _run("ecr", "start", "--title", "First", cwd=root)
    r = _run("ecr", "start", "--title", "Second", cwd=root, ok=False)
    err = " ".join(r.stderr.split())
    assert r.returncode == 3 and "ECR-001 (First) is still open" in err
    assert "n2f ecr close ECR-001" in err and "n2f ecr abort ECR-001" in err
    assert not (root / "changes/ECR-002.yaml").exists()
    r = _run("ecr", "quick", "--set", "param://bracket-width=70mm", cwd=root, ok=False)
    assert r.returncode == 3 and "still open" in " ".join(r.stderr.split())
    assert "bracket-width:     {value: 60" in (root / PARAMS).read_text()


def test_removed_verbs(root: Path) -> None:
    for args in (("ecr", "new", "--title", "x"), ("ecr", "apply"), ("ecr", "reject", "ECR-001")):
        r = _run(*args, cwd=root, ok=False)
        plain = re.sub(r"\x1b\[[0-9;]*m", "", r.stderr)
        assert r.returncode == 2 and "no such command" in " ".join(plain.split()).lower()
    r = _run("ecr", "start", "--title", "x", "--patch", "changes/p.patch", cwd=root, ok=False)
    # CI forces colour, so the usage error splits "--patch" with escape codes.
    plain = re.sub(r"\x1b\[[0-9;]*m", "", r.stderr)
    assert r.returncode == 2 and "--patch" in " ".join(plain.split())


def test_impact_labels_every_figure(root: Path) -> None:
    """S-274: mass and envelope are computed, cost carries its parts' basis; no blanket heading."""
    _json("ecr", "start", "--title", "Thicker", "--set", "param://bracket-width=70mm", cwd=root)
    data = _json("ecr", "impact", cwd=root)
    assert data["mass"]["basis"] == "computed"
    assert data["cost"]["basis"] in {"estimate", "quote", "catalog"}
    assert data["envelope"] and all(e["basis"] == "computed" for e in data["envelope"].values())
    text = _run("ecr", "impact", cwd=root).stdout
    assert f"Cost ({data['cost']['basis']}, from the parts' declared unit costs)" in text
    requoted = data["cost"]["shape_changed_not_requoted"]
    if requoted:
        assert "Shape changed, price not re-quoted: " in text
        assert "(no change)" not in next(ln for ln in text.splitlines() if ln.startswith("- Cost"))


def test_quick(root: Path) -> None:
    r = _run("ecr", "quick", "--set", "param://bracket-width=70mm", "--reason", "stiffer", cwd=root)
    out = " ".join(r.stdout.split())
    assert "started ECR-001" in out and "Mass (computed):" in out
    assert "n2f ecr approve ECR-001 --by <name> && n2f ecr close ECR-001" in out
    assert "n2f ecr abort ECR-001" in out
    data = _ecr(root)
    assert data["status"] == "draft" and data["impact"]["mass"]["delta"] > 0
    assert data["reason"] == "stiffer" and data["title"] == "Set bracket-width to 70mm"
    _run("ecr", "abort", cwd=root)
    j = _json("ecr", "quick", "--set", "param://bracket-width=70mm", "--title", "Wider", cwd=root)
    assert j["id"] == "ECR-002" and j["checkpoint"] and j["mass"]["after"] > j["mass"]["before"]


def test_impact_with_no_change_and_a_broken_target(root: Path) -> None:
    _run("ecr", "start", "--title", "Nothing yet", cwd=root)
    r = _run("ecr", "impact", cwd=root)
    assert "Nothing in the model has changed" in r.stdout
    assert "(no change)" in r.stdout
    r = _run("ecr", "start", "--title", "y", "--set", "param://nope=1mm", cwd=root, ok=False)
    assert r.returncode == 3  # refused by the one-open rule first
    _run("ecr", "abort", cwd=root)
    r = _run("ecr", "start", "--title", "y", "--set", "param://nope=1mm", cwd=root, ok=False)
    assert r.returncode == 3 and "does not exist" in r.stderr
    assert not (root / "changes/ECR-002.yaml").exists()


def test_a_signoff_after_approval_does_not_unbind_it(root: Path) -> None:
    """The approval hash leaves out sign-offs (S-254 amends S-252): sign, then close."""
    _run("ecr", "quick", "--set", "param://bracket-width=70mm", cwd=root)
    _run("ecr", "approve", "--by", "Owner", cwd=root)
    approved = _ecr(root)["approval"]["model_hash"]
    _run("signoff", "REQ-001", "--by", "Owner", "--statement", "measured", cwd=root)
    assert list((root / "model/signoffs").glob("*.yaml"))
    assert Vcs(root).working_hash(exclude=APPROVAL_HASH_EXCLUDE) == approved
    closed = _json("ecr", "close", cwd=root)
    assert closed["status"] == "closed"


def test_a_change_request_id_is_never_reused_after_a_rollback(root: Path) -> None:
    """The next id is past every id the history knows, not only those in changes/ (S-273)."""
    _run("ecr", "quick", "--set", "param://bracket-width=70mm", cwd=root)
    _run("ecr", "approve", "--by", "Owner", cwd=root)
    _run("ecr", "close", cwd=root)
    first = next(c for c in _log(root) if c.label.startswith("Started ECR-001"))
    before = [c for c in _log(root) if c.number < first.number][-1]
    _run("rollback", f"#{before.number}", cwd=root)
    assert not (root / "changes/ECR-001.yaml").exists()
    started = _json("ecr", "start", "--title", "Again", cwd=root)
    assert started["id"] == "ECR-002"


def test_a_pasted_hash_cannot_forge_an_approval(root: Path) -> None:
    """Close needs the model of the approval's checkpoint, not just a matching hash (S-273)."""
    _run("ecr", "quick", "--set", "param://bracket-width=70mm", cwd=root)
    _run("ecr", "approve", "--by", "Owner", cwd=root)
    _edit(root, PARAMS, "hole-spacing:      {value: 36", "hole-spacing:      {value: 37")
    shown = _run("ecr", "show", "ECR-001", cwd=root).stdout
    assert "approved, but the model changed since" in " ".join(shown.split())
    assert "#" in shown and "started from checkpoint" not in shown
    forged = Vcs(root).working_hash(exclude=APPROVAL_HASH_EXCLUDE)
    path = root / "changes/ECR-001.yaml"
    path.write_text(re.sub(r"model_hash: \S+", f"model_hash: {forged}", path.read_text()))
    r = _run("ecr", "close", cwd=root, ok=False)
    assert r.returncode == 3 and "changed since ECR-001 was approved" in " ".join(r.stderr.split())


def test_impact_names_words_that_may_still_give_the_old_size(root: Path) -> None:
    """Gate L: free text holding a changed parameter's old size is named, and close warns."""
    _edit(root, PART, 'spec: "4 mm CR4 (DC01)"', 'spec: "120 x 60 x 4 mm CR4 plate"')
    _edit(root, PART, "Deburr all edges.", "Cut to 120 mm. Deburr all edges.")
    _run("ecr", "start", "--title", "Longer", "--set", "param://bracket-length=125mm", cwd=root)
    text = _run("ecr", "impact", cwd=root).stdout
    assert "Words that may still give the old size" in text
    assert "l-bracket" in text and "material.spec" in text and "manufacturer_notes" in text
    stale = _json("ecr", "impact", cwd=root)["stale_text"]
    assert {s["field"] for s in stale} == {"material.spec", "manufacturer_notes"}
    assert all(s["parameter"] == "bracket-length" and s["old"] == "120 mm" for s in stale)
    _run("ecr", "approve", "--by", "Owner", cwd=root)
    closed = _run("ecr", "close", cwd=root).stdout
    assert closed.count("words that may still give the old size") == 1
    assert "manufacturer_notes" in closed


def test_a_failing_change_says_so_with_figures_and_offers_abort(root: Path) -> None:
    """Gate L: no 'approve and close' for a change that fails; the figures are shown."""
    out = _run(
        "ecr", "quick", "--set", "param://bracket-length=200mm", "--title", "Too long", cwd=root
    ).stdout
    assert "REQ-001" in out and "figures: before" in out and "after" in out
    nxt = out.split("next:")[-1]
    assert "n2f ecr abort ECR-001" in nxt and "REQ-001" in nxt and "ecr close" not in nxt
    assert "n2f ecr abort ECR-001" in _run("ecr", "impact", cwd=root).stdout.split("next:")[-1]


def test_both_signoff_lists_come_from_the_check(root: Path) -> None:
    """Gate L: 'must be redone' is a signed requirement that now waits; never a static read."""
    from napkin2factory.ecr import live_impact

    block = live_impact._block  # the lists are derived there from the two builds' checks
    assert block is not None
    _run("ecr", "start", "--title", "x", "--set", "param://bracket-width=70mm", cwd=root)
    impact = _json("ecr", "impact", cwd=root)
    waiting = set(impact["signoffs_waiting"])
    assert set(impact["signoffs_invalidated"]) <= waiting


def test_status_names_an_open_request_and_its_next_step_s_new1(root: Path) -> None:
    """Gate L, B4: status names the open request; unsaved edits get plain next steps."""
    _run("ecr", "start", "--title", "Thicker", "--set", "param://bracket-width=70mm", cwd=root)
    nxt = _json("status", cwd=root)["next_step"]
    assert nxt.startswith("ECR-001 (Thicker) is draft: ")
    assert "n2f ecr impact ECR-001" in nxt and "n2f ecr abort ECR-001" in nxt
    _run("ecr", "abort", "ECR-001", cwd=root)
    _edit(root, PARAMS, "bracket-width:     {value: 60", "bracket-width:     {value: 61")
    text = json.dumps(_json("status", cwd=root))
    assert "save them as a checkpoint (`n2f snapshot`) or undo them (`n2f undo`)" in text
    assert "unsaved changes since the last snapshot" not in text
