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

from napkin2factory.cli.checkpointing import checkpoint, open_change_request, save_edits_first
from napkin2factory.cli.undo import do_redo, do_rollback, do_undo
from napkin2factory.core import checkpoints as cps
from napkin2factory.core.vcs import Vcs, VcsError
from tests.conftest import n2f

FILES = ("model/notes.txt", "extra.txt")

Op = tuple[str, int, str]
OPS = st.lists(
    st.tuples(
        st.sampled_from(
            ["edit", "edit", "command", "undo", "undo", "redo", "rollback", "start", "close"]
        ),
        st.integers(0, 40),
        st.sampled_from(["a", "b", "c", ""]),
    ),
    max_size=7,
)


@pytest.fixture(scope="module")
def blank(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A blank tracked product, copied for each example."""
    folder = tmp_path_factory.mktemp("blank") / "prod"
    assert n2f("init", str(folder)).returncode == 0
    (folder / "model").mkdir(exist_ok=True)
    return folder


def _write_ecr(root: Path, status: str, baseline: str) -> None:
    (root / "changes").mkdir(exist_ok=True)
    (root / "changes" / "ECR-001.yaml").write_text(
        f"id: ECR-001\ntitle: Try it\nstatus: {status}\nkind: design\n"
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
            _write_ecr(root, "draft", baseline)
            checkpoint(root, "Started ECR-001")
        elif kind == "close" and open_change_request(root) is not None:
            save_edits_first(root)
            baseline = (root / "changes" / "ECR-001.yaml").read_text().split("'")[1]
            _write_ecr(root, "closed", baseline)
            checkpoint(root, "Closed ECR-001")
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
