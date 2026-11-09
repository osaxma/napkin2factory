"""``n2f concept switch`` (v0.8 M3a, R10): park one direction, bring another, all or nothing.

The product is a copy of the table example (C-002 promoted, C-001 and C-003 rejected, all
built), prebuilt once per session. C-001 is red, so switching to it needs ``--override``.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from napkin2factory.concepts.direction import (
    PRODUCT_PATHS,
    direction_paths,
    unnamed_entries,
)
from napkin2factory.concepts.promote import promote
from napkin2factory.concepts.switch import marker_name, switch
from napkin2factory.core import checkpoints as cps
from napkin2factory.core import concepts as cm
from napkin2factory.core.errors import GateBlocked, N2FError
from napkin2factory.core.vcs import Vcs
from tests.conftest import EXAMPLES, copy_product, n2f

pytestmark = pytest.mark.xdist_group("test_concept_switch")

OVERRIDE = ("--override", "--reason", "try the pine top")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return copy_product(EXAMPLES / "table", tmp_path / "table", prebuilt=True)


def status(root: Path, card: str) -> str:
    return cm.load_card(root, card).status


def go(root: Path, card: str, *extra: str) -> dict[str, object]:
    r = n2f("concept", "switch", card, "--json", *extra, cwd=root)
    assert r.returncode == 0, r.stdout + r.stderr
    data: dict[str, object] = json.loads(r.stdout)
    return data


def refuse(root: Path, *args: str) -> str:
    r = n2f("concept", "switch", *args, cwd=root)
    assert r.returncode == 3, r.stdout + r.stderr
    return r.stderr


# ---- the direction lists ---------------------------------------------------------------------


def test_direction_lists_name_domain_folders_and_find_unnamed() -> None:
    paths = direction_paths()
    assert "model/parts" in paths and "model/loads" in paths
    assert any(p.startswith("model/electrical") for p in paths)
    assert "model/decisions.yaml" in PRODUCT_PATHS
    tracked = [
        "model/parts/a.yaml",
        "model/requirements.yaml",
        "style.yaml",
        "demo.sh",
        "extras/x.txt",
        "model/odd/y.yaml",
        "model/stray.yaml",
    ]
    assert unnamed_entries(tracked) == ["extras", "model/odd", "model/stray.yaml"]


def test_the_example_products_have_no_unnamed_entries() -> None:
    for name in ("table", "test-stand", "bracket", "enclosure"):
        files = [
            str(p.relative_to(EXAMPLES / name))
            for p in (EXAMPLES / name).rglob("*")
            if p.is_file() and "build" not in p.parts
        ]
        assert unnamed_entries(files) == [], name


# ---- the two switches ------------------------------------------------------------------------


def test_switch_parks_current_seeds_target_and_undo_brings_it_back(root: Path) -> None:
    vcs = Vcs(root)
    before = vcs.snapshot_count()
    data = go(root, "C-001", *OVERRIDE)
    assert data["route"] == "seeded" and data["parked"] == "C-002"
    cp = data["checkpoint"]
    assert isinstance(cp, dict) and cp["number"] == before + 1
    assert vcs.snapshot_count() == before + 1  # one checkpoint for the whole switch
    assert vcs.read_ref(marker_name("C-002")) is not None
    assert status(root, "C-001") == "promoted" and status(root, "C-002") == "parked"
    parked = cm.load_card(root, "C-002")
    assert parked.built is not None and parked.built.event == "parked"
    assert parked.built.number == before and parked.decision is not None
    assert parked.decision.reason == f"parked when C-001 was chosen ({data['decision']})"
    target = cm.load_card(root, "C-001")
    assert target.built is None and target.decision is not None
    assert target.decision.dec == data["decision"]
    decs = (root / "model" / "decisions.yaml").read_text(encoding="utf-8")
    assert "This supersedes DEC-001." in decs and "dec://DEC-001" in decs
    assert any("stay in the model" in n for n in data["notes"])  # type: ignore[attr-defined]
    last = cps.read(vcs, limit=1)[0]
    assert (
        last.label
        == "Switched to C-001 (Four corner tube legs, no apron, 22 mm pine top); C-002 parked"
    )
    # undo puts C-002 back as the current direction
    r = n2f("undo", cwd=root)
    assert r.returncode == 0, r.stderr
    assert status(root, "C-002") == "promoted" and status(root, "C-001") == "rejected"


def test_switch_back_restores_the_parked_files_exactly(root: Path) -> None:
    keep = {
        p: p.read_bytes()
        for rel in ("model/parts", "model/parameters.yaml", "style.yaml", "model/assemblies")
        for p in ([root / rel] if (root / rel).is_file() else sorted((root / rel).rglob("*")))
        if p.is_file()
    }
    go(root, "C-001", *OVERRIDE)
    # the sketch's look replaced style.yaml; an owner edit to a part goes too
    (root / "model" / "parts" / "extra-part.yaml").write_text(
        "id: extra-part\nname: Extra part\n", encoding="utf-8"
    )
    data = go(root, "C-002")
    assert data["route"] == "restored" and data["parked"] == "C-001"
    for path, content in keep.items():
        assert path.read_bytes() == content, path
    assert not (root / "model" / "parts" / "extra-part.yaml").exists()
    assert status(root, "C-002") == "promoted" and status(root, "C-001") == "parked"
    assert cm.load_card(root, "C-002").built is None
    decs = (root / "model" / "decisions.yaml").read_text(encoding="utf-8")
    assert f"id: {data['decision']}" in decs
    assert re.search(r"Design direction back to .*\n(?s:.*)This supersedes DEC-\d+\.", decs)
    assert any("requirements changed since C-002" in s for s in data["stale"])  # type: ignore[attr-defined]


def test_unsaved_edits_are_saved_first(root: Path) -> None:
    (root / "model" / "intake.md").write_text("# edited\n", encoding="utf-8")
    data = go(root, "C-001", *OVERRIDE)
    assert data["saved_edits"] is not None


def test_fresh_promotes_the_sketch_even_with_a_parked_direction(root: Path) -> None:
    go(root, "C-001", *OVERRIDE)
    data = go(root, "C-002", "--fresh", *OVERRIDE)
    assert data["route"] == "seeded"
    assert status(root, "C-002") == "promoted"


def test_parking_a_rejected_card_keeps_its_rejection_reason(root: Path) -> None:
    """B-0282: parking appends "parked when …" after the reason the card already carried."""
    before = cm.load_card(root, "C-001").decision.reason
    assert before
    go(root, "C-001", *OVERRIDE)  # C-001 promoted; its rejection reason is kept (B-0282)
    data = go(root, "C-003", *OVERRIDE)  # parks C-001
    parked = cm.load_card(root, "C-001")
    assert parked.status == "parked" and parked.decision is not None
    assert parked.decision.reason == f"{before}. parked when C-003 was chosen ({data['decision']})"


def test_promoting_parks_a_forked_sibling_and_switch_restores_it(root: Path) -> None:
    """B-0289: a promotion sets a built (forked) sibling aside as `parked`, not `rejected`."""
    from napkin2factory.concepts.fork import fork_from_model

    fork_from_model(root)  # C-004: exploring, built (forked from C-002's built design)
    forked = cm.load_card(root, "C-004")
    assert forked.status == "exploring" and forked.built is not None
    assert forked.built.event == "forked"
    # switching to C-001 promotes it; the forked sibling C-004 is parked, not rejected
    data = go(root, "C-001", *OVERRIDE)
    parked = cm.load_card(root, "C-004")
    assert parked.status == "parked"
    assert parked.built is not None and parked.built.event == "parked"
    assert parked.built.checkpoint is not None and Vcs(root).ref_exists(parked.built.checkpoint)
    assert parked.decision is not None
    assert parked.decision.reason == f"parked when C-001 was chosen ({data['decision']})"
    # switching back to the parked forked card restores the built design it was forked from
    data2 = go(root, "C-004")
    assert data2["route"] == "restored"
    assert status(root, "C-004") == "promoted"


def test_switching_back_names_the_requirements_the_card_brought(root: Path) -> None:
    """B-0282: the restored switch names, in ``--json``, the requirements the card brought."""
    go(root, "C-001", *OVERRIDE)  # parks C-002 and seeds C-001's own requirements
    data = go(root, "C-002")
    assert data["route"] == "restored"
    assert {"id": "REQ-001", "title": "Light enough to move as planned"} in data[
        "seeded_requirements"
    ]
    assert all(set(r) == {"id", "title"} for r in data["seeded_requirements"])


def test_switching_back_text_names_the_requirements(root: Path) -> None:
    """B-0282: the restored switch's words name the card's requirements by id and title."""
    go(root, "C-001", *OVERRIDE)
    r = n2f("concept", "switch", "C-002", cwd=root)
    assert r.returncode == 0, r.stderr
    assert "REQ-001 (Light enough to move as planned)" in r.stdout


# ---- the refusals ------------------------------------------------------------------------------


def test_refuses_after_a_release(root: Path) -> None:
    Vcs(root).tag("v1.0.0", "released")
    assert "n2f ecr start --kind design" in refuse(root, "C-001", *OVERRIDE)
    assert status(root, "C-002") == "promoted"


def test_refuses_while_a_change_request_is_open(root: Path) -> None:
    base = cps.read(Vcs(root), limit=1)[0].id
    (root / "changes").mkdir(exist_ok=True)
    (root / "changes" / "ECR-009.yaml").write_text(
        "id: ECR-009\ntitle: Widen it\nstatus: draft\nkind: design\n"
        f"baseline: {{checkpoint: '{base}'}}\n",
        encoding="utf-8",
    )
    assert "n2f ecr abort ECR-009" in refuse(root, "C-001", *OVERRIDE)


def test_refuses_when_nothing_is_chosen_or_card_is_current(root: Path) -> None:
    assert "already the chosen direction" in refuse(root, "C-002")
    cm.update_card_status(root, "C-002", "exploring", {"reason": "x", "at": "2026-01-01"})
    Vcs(root).snapshot("edit")
    assert "n2f concept promote" in refuse(root, "C-001", *OVERRIDE)


def test_refuses_an_unknown_folder_and_names_it(root: Path) -> None:
    (root / "oddities").mkdir()
    (root / "oddities" / "x.txt").write_text("x", encoding="utf-8")
    Vcs(root).snapshot("odd")
    assert "oddities" in refuse(root, "C-001", *OVERRIDE)


def test_refuses_an_unsaved_unknown_folder_too(root: Path) -> None:
    """B-0280: a folder not yet saved is checked before the unsaved edits are saved."""
    (root / "oddities").mkdir()
    (root / "oddities" / "x.txt").write_text("x", encoding="utf-8")
    before = Vcs(root).snapshot_count()
    assert "oddities" in refuse(root, "C-001", *OVERRIDE)
    assert Vcs(root).snapshot_count() == before  # nothing was saved on the way


def test_a_red_target_is_named_by_its_failures(root: Path) -> None:
    """S-277: the refusal and the result say what the card fails, in `concept show` words."""
    card = cm.load_card(root, "C-001")
    assert card.screening is not None
    shown = [f"{(r.title or r.id).rstrip('.')}: {r.message}" for r in card.screening.failing]
    assert shown
    refused = " ".join(refuse(root, "C-001").split())  # the terminal wraps long lines
    assert all(line in refused for line in shown)
    data = go(root, "C-001", *OVERRIDE)
    assert data["failing"] == shown
    notes = data["notes"]
    assert any("still C-002's" in n for n in notes)  # type: ignore[attr-defined]


def test_switch_back_restores_from_the_recorded_checkpoint_without_a_marker(root: Path) -> None:
    """B-0281: with no ``refs/n2f/`` marker the switch restores from the card's checkpoint."""
    go(root, "C-001", *OVERRIDE)
    Vcs(root).delete_ref(marker_name("C-002"))
    data = go(root, "C-002")
    assert data["route"] == "restored"
    assert status(root, "C-002") == "promoted" and status(root, "C-001") == "parked"


def test_check_lists_a_never_promoted_directions_screening_failures(root: Path) -> None:
    """B-0290: ``n2f check`` lists the direction's own screening failures and fails."""
    from napkin2factory.concepts.switch import direction_failures, failing_words

    go(root, "C-001", *OVERRIDE)  # a napkin card, never promoted: its parts stay C-002's
    card = cm.load_card(root, "C-001")
    shown = failing_words(card)
    assert shown and shown == direction_failures(root)
    # check lists them under the new key and exits non-zero while one stands
    r = n2f("check", "--json", cwd=root)
    assert r.returncode == 5, r.stdout + r.stderr
    assert json.loads(r.stdout)["direction_failures"] == shown
    # switching back to the restored direction has its own parts back: nothing to list
    go(root, "C-002")
    assert direction_failures(root) == []


def test_refuses_a_parked_card_with_neither_marker_nor_checkpoint(root: Path) -> None:
    """B-0281: only when there is no marker and no recorded checkpoint does the refusal stay."""
    go(root, "C-001", *OVERRIDE)
    Vcs(root).delete_ref(marker_name("C-002"))
    cm.update_card_status(
        root,
        "C-002",
        "parked",
        built={
            "event": "parked",
            "checkpoint": "deadbeef" * 5,  # a saved state this folder does not hold
            "number": 0,
            "at": "2026-01-01T00:00:00",
        },
    )
    assert "--fresh" in refuse(root, "C-002", *OVERRIDE)
    assert status(root, "C-002") == "parked"


def test_a_clone_without_markers_switches_back_via_the_recorded_checkpoint(
    root: Path, tmp_path: Path
) -> None:
    """B-0281: a fresh copy has no ``refs/n2f/``, so the switch uses ``built.checkpoint``."""
    go(root, "C-001", *OVERRIDE)  # parks C-002 with its checkpoint on record
    remote = tmp_path / "online.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "-C", str(root), "remote", "add", "origin", str(remote)], check=True)
    Vcs(root).send_online("origin", "main")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(remote), str(clone)], check=True)
    assert Vcs(clone).read_ref(marker_name("C-002")) is None  # the clone carries no markers
    data = go(clone, "C-002")
    assert data["route"] == "restored"
    assert status(clone, "C-002") == "promoted" and status(clone, "C-001") == "parked"


def test_unscreened_or_red_target_is_refused_before_anything_changes(root: Path) -> None:
    before = Vcs(root).working_hash()
    refuse(root, "C-001")  # red without --override
    assert Vcs(root).working_hash() == before


def test_an_invalid_result_puts_everything_back(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    go(root, "C-001", *OVERRIDE)
    vcs = Vcs(root)
    before = vcs.working_hash()
    marker_before = vcs.read_ref(marker_name("C-001"))
    from napkin2factory.core import loader

    real = loader.validate
    calls = 0

    def broken(r: Path):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        product, problems = real(r)
        if calls > 1:
            problems.add(r / "model", "REQ-001", "a requirement checks a part that is gone", "fix")
        return product, problems

    monkeypatch.setattr(loader, "validate", broken)
    with pytest.raises(N2FError, match="does not fit"):
        switch(root, "C-002")
    assert vcs.working_hash() == before
    assert vcs.read_ref(marker_name("C-001")) == marker_before
    assert status(root, "C-001") == "promoted" and status(root, "C-002") == "parked"


def test_promote_names_switch_in_its_lockout(root: Path) -> None:
    with pytest.raises(GateBlocked, match=r"run `n2f concept switch C-001`"):
        promote(root, "C-001", override=True, reason="x")
    Vcs(root).tag("v1.0.0", "released")
    with pytest.raises(GateBlocked, match=r"n2f ecr start --kind design"):
        promote(root, "C-001", override=True, reason="x")


def test_owner_words_have_no_git_vocabulary(root: Path) -> None:
    r = n2f("concept", "switch", "C-001", *OVERRIDE, cwd=root)
    assert r.returncode == 0, r.stderr
    text = r.stdout + r.stderr
    assert not re.search(r"\b(branch|commit|merge|rebase|checkout|HEAD|ref|marker)\b", text)
