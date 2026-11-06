"""``n2f checkpoints | undo | redo | rollback``, ``discard`` and the shared helper (v0.8 M1b).

Real git in tmp folders; the CLI runs in this process. The folder is a blank product from
``n2f init`` (no build, so vitals are "not measured"); a note file stands in for the model.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from napkin2factory.cli.checkpointing import (
    APPROVAL_HASH_EXCLUDE,
    checkpoint,
    open_change_request,
    save_edits_first,
    stale_after_restore,
)
from napkin2factory.core import checkpoints as cps
from napkin2factory.core.vcs import Vcs
from tests.conftest import n2f

NOTE = "notes.txt"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    folder = tmp_path / "prod"
    r = n2f("init", str(folder))
    assert r.returncode == 0, r.stderr
    return folder


def save(root: Path, text: str, label: str) -> None:
    """Write the note and save it as a checkpoint through the CLI."""
    (root / NOTE).write_text(text, encoding="utf-8")
    r = n2f("snapshot", "-m", label, cwd=root)
    assert r.returncode == 0, r.stderr


def note(root: Path) -> str | None:
    path = root / NOTE
    return path.read_text(encoding="utf-8") if path.exists() else None


def write_ecr(
    root: Path, ecr_id: str, status: str, baseline: str, model_hash: str | None = None
) -> None:
    approval = (
        f"approval: {{by: Owner, at: '2026-11-06T10:00:00', model_hash: '{model_hash}'}}\n"
        if model_hash
        else ""
    )
    (root / "changes").mkdir(exist_ok=True)
    (root / "changes" / f"{ecr_id}.yaml").write_text(
        f"id: {ecr_id}\ntitle: Widen it\nstatus: {status}\nkind: design\n"
        f"baseline: {{checkpoint: '{baseline}'}}\n{approval}",
        encoding="utf-8",
    )


# ---- the verbs ------------------------------------------------------------------------------


def test_two_step_undo_and_redo_with_checkpoints_listed(root: Path) -> None:
    save(root, "one", "Added one")
    save(root, "two", "Added two")  # checkpoints: #1 Start, #2 one, #3 two

    r = n2f("undo", cwd=root)
    assert r.returncode == 0, r.stderr
    assert 'undid #3 "Added two"; back to #2 "Added one"' in r.stdout
    assert "changed: notes.txt" in r.stdout and "(now checkpoint #4)" in r.stdout
    assert note(root) == "one"
    r = n2f("undo", cwd=root)
    assert 'back to #1 "Start of' in r.stdout and "removed: notes.txt" in r.stdout
    assert note(root) is None
    r = n2f("undo", cwd=root)
    assert r.returncode == 0 and "nothing to undo" in r.stdout

    listing = n2f("checkpoints", cwd=root).stdout
    first = listing.splitlines()[0]
    assert first.startswith("#5") and "Undid: Added one" in first and "the folder is here" in first
    assert "(undone)" in next(line for line in listing.splitlines() if line.startswith("#3"))
    assert "(not measured)" in listing

    r = n2f("redo", cwd=root)
    assert 'brought back #2 "Added one"' in r.stdout and note(root) == "one"
    r = n2f("redo", cwd=root)
    assert 'brought back #3 "Added two"' in r.stdout and note(root) == "two"
    r = n2f("redo", cwd=root)
    assert r.returncode == 0 and "nothing to redo" in r.stdout
    assert note(root) == "two"


def test_the_listing_defaults_to_twenty_and_all_shows_every_one(root: Path) -> None:
    for i in range(24):
        save(root, str(i), f"step {i}")
    shown = n2f("checkpoints", cwd=root).stdout
    assert shown.count("\n#") + shown.startswith("#") == 20 and "5 older ones" in shown
    data = json.loads(n2f("checkpoints", "--all", "--json", cwd=root).stdout)
    assert data["total"] == 25 and len(data["checkpoints"]) == 25
    assert data["checkpoints"][0]["number"] == 25 and data["checkpoints"][0]["current"]


def test_unsaved_edits_are_saved_first_so_undo_takes_them_out_and_redo_back(root: Path) -> None:
    save(root, "kept", "Kept")
    (root / NOTE).write_text("loose edit", encoding="utf-8")  # no command, no save
    r = n2f("undo", cwd=root)
    assert "your unsaved edits were saved first as #3" in r.stdout
    assert note(root) == "kept"
    assert "edits since #2 Kept" in n2f("checkpoints", cwd=root).stdout
    n2f("redo", cwd=root)
    assert note(root) == "loose edit"


def test_every_json_carries_the_new_checkpoints_id_and_number(root: Path) -> None:
    save(root, "one", "Added one")
    save(root, "two", "Added two")
    vcs = Vcs(root)
    for verb, args in (("undo", []), ("redo", []), ("rollback", ["1"])):
        out = json.loads(n2f(verb, *args, "--json", cwd=root).stdout)
        cp = out["checkpoint"]
        assert cp["id"] == vcs.head() and cp["number"] == vcs.snapshot_count()
        assert out["restored"]["number"] >= 1 and out["stale"] == []
    nothing = json.loads(n2f("redo", "--json", cwd=root).stdout)
    assert nothing["redone"] is False and nothing["checkpoint"]["id"] == vcs.head()
    snap = json.loads(n2f("snapshot", "-m", "x", "--json", cwd=root).stdout)
    assert snap["checkpoint"]["number"] == vcs.snapshot_count() or snap["changed"] is False


def test_a_folder_with_no_history_says_so_and_names_init(tmp_path: Path) -> None:
    folder = tmp_path / "copied"
    assert n2f("init", str(folder)).returncode == 0
    shutil.rmtree(folder / ".git")
    for verb in (["checkpoints"], ["undo"], ["redo"], ["rollback", "1"]):
        r = n2f(*verb, cwd=folder)
        assert r.returncode != 0 and "n2f init ." in r.stderr, verb


def test_rollback_to_a_checkpoint_is_itself_undoable_and_keeps_history(root: Path) -> None:
    save(root, "one", "Added one")
    save(root, "two", "Added two")
    before = [c.id for c in cps.read(Vcs(root))]
    r = n2f("rollback", "#2", cwd=root)
    assert 'rolled back to #2 "Added one"' in r.stdout and note(root) == "one"
    assert [c.id for c in cps.read(Vcs(root))][1:] == before  # nothing rewritten
    r = n2f("undo", cwd=root)
    assert note(root) == "two" and "Rolled back to #2" in r.stdout
    assert "no checkpoint #99" in n2f("rollback", "99", cwd=root).stderr
    assert "already matches" in n2f("rollback", "3", cwd=root).stdout


def test_rollback_to_a_released_revision_and_to_a_change_requests_start(root: Path) -> None:
    vcs = Vcs(root)
    save(root, "released state", "Released v1.0.0")
    vcs.tag("v1.0.0", "Revision v1.0.0")
    start = vcs.head()
    assert start is not None
    save(root, "later", "Later")
    write_ecr(root, "ECR-001", "closed", baseline=start)
    n2f("snapshot", "-m", "Closed ECR-001", cwd=root)
    save(root, "even later", "Even later")
    r = n2f("rollback", "v1.0.0", cwd=root)
    assert "rolled back to Revision v1.0.0" in r.stdout and note(root) == "released state"
    assert vcs.tags() == ["v1.0.0"] and vcs.revision_snapshot("v1.0.0") == start
    n2f("redo", cwd=root)  # a rollback is undone, not redone: redo has nothing to bring back
    n2f("undo", cwd=root)
    r = n2f("rollback", "ECR-001", cwd=root)
    assert "rolled back to before ECR-001 (Widen it)" in r.stdout
    assert note(root) == "released state"
    assert "not a checkpoint number" in n2f("rollback", "v9", cwd=root).stderr
    assert "no change request ECR-007" in n2f("rollback", "ECR-007", cwd=root).stderr


def test_an_open_change_request_stops_undo_and_refuses_rollback(root: Path) -> None:
    vcs = Vcs(root)
    save(root, "before", "Before")
    baseline = vcs.head()
    assert baseline is not None
    write_ecr(root, "ECR-001", "draft", baseline=baseline)
    n2f("snapshot", "-m", "Started ECR-001", cwd=root)  # the change request's start
    save(root, "edited in the request", "Edited")
    assert open_change_request(root) is not None

    assert n2f("undo", cwd=root).returncode == 0 and note(root) == "before"
    r = n2f("undo", cwd=root)  # at the start: the baseline's state is never reached
    assert r.returncode == 0 and "n2f ecr abort ECR-001" in r.stdout and note(root) == "before"
    r = n2f("rollback", "1", cwd=root)
    assert r.returncode != 0 and "n2f ecr abort ECR-001" in r.stderr
    assert note(root) == "before"
    n2f("redo", cwd=root)
    assert note(root) == "edited in the request"

    # approved but not closed counts as open too; once closed, undo is free again
    write_ecr(root, "ECR-001", "approved", baseline=baseline)
    assert open_change_request(root) is not None
    write_ecr(root, "ECR-001", "closed", baseline=baseline)
    assert open_change_request(root) is None


# ---- discard -------------------------------------------------------------------------------


def test_discard_is_undoable_and_redo_brings_the_edits_back(root: Path) -> None:
    save(root, "kept", "Kept")
    (root / NOTE).write_text("to be thrown away", encoding="utf-8")
    (root / "new.txt").write_text("new file", encoding="utf-8")
    r = n2f("discard", "--yes", cwd=root)
    assert r.returncode == 0, r.stderr
    assert "discarded changes in" in r.stdout and "matches checkpoint #2 again" in r.stdout
    assert "n2f redo" in r.stdout
    assert note(root) == "kept" and not (root / "new.txt").exists()
    assert Vcs(root).is_clean()
    r = n2f("redo", cwd=root)
    assert 'brought back #3 "edits discarded"' in r.stdout
    assert note(root) == "to be thrown away" and (root / "new.txt").read_text() == "new file"
    (root / NOTE).write_text("more", encoding="utf-8")
    again = n2f("discard", "--json", cwd=root)
    assert json.loads(again.stdout)["edits_saved_as"]["number"] == Vcs(root).snapshot_count() - 1


# ---- the helper ----------------------------------------------------------------------------


def test_save_edits_first_labels_them_and_does_nothing_when_clean(root: Path) -> None:
    assert save_edits_first(root) is None
    save(root, "kept", "Kept")
    assert save_edits_first(root) is None
    (root / NOTE).write_text("loose", encoding="utf-8")
    cp = save_edits_first(root)
    assert cp is not None and cp.label == "edits since #2 Kept" and cp.number == 3
    assert Vcs(root).is_clean() and save_edits_first(root) is None


def test_checkpoint_returns_the_newest_when_nothing_changed(root: Path) -> None:
    first = checkpoint(root, "No change")
    assert first.number == 1
    (root / NOTE).write_text("x", encoding="utf-8")
    second = checkpoint(root, "Added a note")
    assert second.number == 2 and second.label == "Added a note"
    assert second.vitals.mass is None  # no build: not measured


def test_open_change_request_takes_the_newest_and_its_start_checkpoint(root: Path) -> None:
    vcs = Vcs(root)
    save(root, "a", "A")
    base = vcs.head()
    assert base is not None
    assert open_change_request(root) is None
    write_ecr(root, "ECR-001", "draft", baseline=base)
    write_ecr(root, "ECR-002", "draft", baseline=base)
    save(root, "b", "B")  # the checkpoint right after the baseline
    start = next(c for c in cps.read(vcs) if c.number == 3)
    assert open_change_request(root) == ("ECR-002", start.id)


def test_stale_after_restore_names_an_approval_that_no_longer_matches(root: Path) -> None:
    vcs = Vcs(root)
    save(root, "a", "A")
    base = vcs.head()
    assert base is not None
    write_ecr(
        root,
        "ECR-001",
        "approved",
        baseline=base,
        model_hash=vcs.working_hash(APPROVAL_HASH_EXCLUDE),
    )
    n2f("snapshot", "-m", "Approved ECR-001", cwd=root)
    assert stale_after_restore(root) == []  # the hash covers the model without changes/
    save(root, "b", "B")
    lines = stale_after_restore(root)
    assert len(lines) == 1 and "ECR-001 (Widen it)" in lines[0] and "approve it again" in lines[0]
    # the report never rewrites the request: still approved with the old hash
    assert "status: approved" in (root / "changes" / "ECR-001.yaml").read_text()
