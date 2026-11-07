"""Property tests for undo, redo and rollback on real git (v0.8 R2, definition of done 2).

Random sequences of edits, command checkpoints, undo, redo, rollback and a change request
opening and closing run against a real folder. After each step the invariants hold:

* redo right after an undo gives the folder it had before the undo (the identity);
* undo right after a redo gives the folder it had before the redo;
* every checkpoint ever made stays readable by its id, with the folder it had;
* an undo inside an open change request never goes before the request's start, and a
  rollback is refused while it is open.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from napkin2factory.cli.undo import do_redo, do_rollback, do_undo
from napkin2factory.concepts.promote import promote
from napkin2factory.concepts.switch import switch
from napkin2factory.core import checkpoints as cps
from napkin2factory.core import concepts as cm
from napkin2factory.core.errors import GateBlocked
from napkin2factory.core.loader import load_product
from napkin2factory.core.vcs import Vcs, VcsError
from napkin2factory.ecr.checkpointing import checkpoint, open_change_request, save_edits_first
from napkin2factory.ecr.live import abort, next_ecr_id
from tests.conftest import n2f

FILES = ("model/docs/notes.txt", "extra.txt")

Op = tuple[str, int, str]
OPS = st.lists(
    st.tuples(
        st.sampled_from(
            [
                "edit",
                "edit",
                "command",
                "undo",
                "undo",
                "redo",
                "rollback",
                "start",
                "close",
                "abort",
                "switch",
            ]
        ),
        st.integers(0, 40),
        st.sampled_from(["a", "b", "c", ""]),
    ),
    max_size=8,
)


def _card_yaml(cid: str, title: str, length: int) -> str:
    return (
        f"id: {cid}\n"
        f"title: {title}\n"
        "status: exploring\n"
        "refs: []\n"
        "layout: {}\n"
        "site: {}\n"
        "massing:\n"
        "  - {kit: block, as: body, material: aluminum,"
        f" args: {{length: {length} mm, width: 60 mm, height: 10 mm}}}}\n"
        "notes: ''\n"
        "screening:\n"
        "  given: {}\n"
        "  computed: {}\n"
        "  estimates: {}\n"
        "  rules: []\n"
        "  verdict: green\n"
        "  at: '2026-11-06T10:00:00'\n"
        "decision: null\n"
    )


@pytest.fixture(scope="module")
def blank(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A blank tracked product with two screened concepts (C-001 promoted), copied per example."""
    folder = tmp_path_factory.mktemp("blank") / "prod"
    assert n2f("init", str(folder)).returncode == 0
    (folder / "model").mkdir(exist_ok=True)
    (folder / "concepts").mkdir(exist_ok=True)
    (folder / "concepts" / "C-001.yaml").write_text(
        _card_yaml("C-001", "First concept", 100), encoding="utf-8"
    )
    (folder / "concepts" / "C-002.yaml").write_text(
        _card_yaml("C-002", "Second concept", 120), encoding="utf-8"
    )
    promote(folder, "C-001", by="Owner", snapshot=False)
    shutil.rmtree(folder / ".git")
    vcs = Vcs(folder)
    vcs.init()
    vcs.snapshot("Start of prod")
    return folder


def _write_ecr(root: Path, ecr_id: str, status: str, baseline: str) -> None:
    (root / "changes").mkdir(exist_ok=True)
    (root / "changes" / f"{ecr_id}.yaml").write_text(
        f"id: {ecr_id}\ntitle: Try it\nstatus: {status}\nkind: design\n"
        f"baseline: {{checkpoint: '{baseline}'}}\n",
        encoding="utf-8",
    )


def _run(root: Path, ops: list[Op]) -> None:
    vcs = Vcs(root)
    seen: dict[str, str] = {c.id: vcs.tree_of(c.id) for c in cps.read(vcs)}

    def remember() -> None:
        for c in cps.read(vcs, limit=3):
            seen.setdefault(c.id, vcs.tree_of(c.id))

    for kind, n, text in ops:
        if kind == "edit":
            path = root / FILES[n % len(FILES)]
            if text == "":
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text * (n + 1), encoding="utf-8")
        elif kind == "command":
            save_edits_first(root)
            checkpoint(root, f"Command {n}")
        elif kind == "start" and open_change_request(root) is None:
            save_edits_first(root)
            baseline = cps.read(vcs, limit=1)[0].id
            ecr_id = next_ecr_id(load_product(root))
            _write_ecr(root, ecr_id, "draft", baseline)
            checkpoint(root, f"Started {ecr_id}")
        elif kind == "close" and (found := open_change_request(root)) is not None:
            save_edits_first(root)
            baseline = (root / "changes" / f"{found[0]}.yaml").read_text().split("'")[1]
            _write_ecr(root, found[0], "closed", baseline)
            checkpoint(root, f"Closed {found[0]}")
        elif kind == "abort" and (found := open_change_request(root)) is not None:
            abort(load_product(root), found[0])
            assert open_change_request(root) is None
        elif kind == "switch":
            target_id = "C-002" if cm.load_card(root, "C-001").status == "promoted" else "C-001"
            was_open = open_change_request(root) is not None
            try:
                switch(root, target_id, by="Owner")
            except GateBlocked:
                assert was_open
            else:
                assert not was_open
        elif kind == "undo":
            save_edits_first(root)
            found = open_change_request(root)
            tree_before = vcs.working_hash()
            step = do_undo(root)
            if step.reason is None:
                assert step.shown is not None
                if found:  # never before the request's start
                    start = next(c for c in cps.read(vcs) if c.id == found[1])
                    assert step.shown.number >= start.number
                assert vcs.is_clean()
                back = do_redo(root)  # redo right after undo is the identity
                assert back.reason is None and vcs.working_hash() == tree_before
                again = do_undo(root)  # and undo right after that redo is the identity again
                assert again.reason is None and vcs.working_hash() == step_tree(vcs, step)
        elif kind == "redo":
            save_edits_first(root)
            tree_before = vcs.working_hash()
            step = do_redo(root)
            if step.reason is None:
                tree_after = vcs.working_hash()
                undone = do_undo(root)  # undo right after a redo is the identity
                if undone.reason is None:
                    assert vcs.working_hash() == tree_before
                    do_redo(root)
                    assert vcs.working_hash() == tree_after
        elif kind == "rollback":
            log = cps.read(vcs)
            target = log[n % len(log)]
            was_open = open_change_request(root) is not None
            try:
                do_rollback(root, str(target.number))
            except VcsError as exc:
                assert exc.code == "change-request-open" and was_open
            else:
                assert not was_open
        remember()
    # every checkpoint ever made is still there, with the folder it had
    log_ids = {c.id for c in cps.read(vcs)}
    for ident, tree in seen.items():
        assert ident in log_ids and vcs.tree_of(ident) == tree


def step_tree(vcs: Vcs, step: object) -> str:
    """The tree the folder had right before the undo that produced ``step`` restored its state."""
    # the undo restored ``step.shown``'s tree; undoing it again after a redo returns there
    return vcs.tree_of(step.shown.id)  # type: ignore[attr-defined]


@settings(max_examples=10, deadline=None)
@given(OPS)
def test_restores_are_identities_and_never_lose_a_checkpoint(blank: Path, ops: list[Op]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "prod"
        shutil.copytree(blank, root, symlinks=True)
        _run(root, ops)


def test_abort_and_concept_switch_preserve_undo_redo_invariants(
    blank: Path, tmp_path: Path
) -> None:
    root = tmp_path / "prod"
    shutil.copytree(blank, root, symlinks=True)
    _run(
        root,
        [
            ("edit", 0, "a"),
            ("switch", 0, "a"),
            ("undo", 0, "a"),
            ("redo", 0, "a"),
            ("switch", 1, "b"),
            ("start", 2, "a"),
            ("edit", 1, "b"),
            ("switch", 0, "a"),
            ("abort", 0, "a"),
            ("undo", 0, "a"),
            ("abort", 0, "a"),
            ("rollback", 0, "a"),
        ],
    )
