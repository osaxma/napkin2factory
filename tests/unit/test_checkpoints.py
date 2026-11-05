"""Checkpoint messages and the undo/redo plans derived from the log (v0.8 R3, S-246)."""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from napkin2factory.core import checkpoints as cp
from napkin2factory.core.checkpoints import Checkpoint, Vitals
from napkin2factory.core.vcs import SnapshotInfo, Vcs
from napkin2factory.core.vcs_store import split_trailers

# ---- the message ---------------------------------------------------------------------------


def test_message_shapes() -> None:
    assert cp.checkpoint_message("Promoted C-002") == "Promoted C-002"
    msg = cp.checkpoint_message(
        "Edited a part", Vitals("46.0 kg", "$340"), restores="a" * 40, undoes="b" * 40
    )
    assert msg == (
        "Edited a part\n\nCheckpoint-Mass: 46.0 kg\nCheckpoint-Cost: $340\n"
        f"Checkpoint-Restores: {'a' * 40}\nCheckpoint-Undoes: {'b' * 40}"
    )
    assert "Checkpoint-Mass" not in cp.checkpoint_message("x", Vitals(None, "$1"))
    assert cp.checkpoint_message("x", redoes="c") == "x\n\nCheckpoint-Redoes: c"


def test_message_flattens_labels_and_values() -> None:
    assert cp.checkpoint_message("one\ntwo\n\n  three ") == "one two three"
    assert cp.checkpoint_message("  \n") == "checkpoint"
    assert cp.checkpoint_message("x", Vitals("46\nkg", None)).endswith("Mass: 46 kg")


LABELS = [
    "Promoted C-002",
    "a: b",
    'say "hi"',
    "größe – 日本 😀",
    "#hash",
    "Key: v",
    "50% off",
    "{braces}",
]


@pytest.mark.parametrize("label", LABELS)
def test_message_round_trip_through_real_snapshots(tmp_path: Path, label: str) -> None:
    v = Vcs(tmp_path)
    v.init()
    (tmp_path / "a.txt").write_text(label, encoding="utf-8")
    made = cp.record(
        v, label, Vitals("46.0 kg", "$340"), restores="r" * 40, undoes="u" * 40, redoes="d" * 40
    )
    (read,) = cp.read(v)
    assert read == made
    assert read.label == label and read.number == 1
    assert read.vitals == Vitals("46.0 kg", "$340")
    assert (read.restores, read.undoes, read.redoes) == ("r" * 40, "u" * 40, "d" * 40)


def test_older_snapshots_without_trailers_are_checkpoints_too(tmp_path: Path) -> None:
    v = Vcs(tmp_path)
    v.init()
    for i in range(3):
        (tmp_path / "a.txt").write_text(str(i))
        v.snapshot(f"plain {i}")
    cps = cp.read(v)
    assert [c.label for c in cps] == ["plain 2", "plain 1", "plain 0"]
    assert [c.number for c in cps] == [3, 2, 1]
    assert all(c.vitals == Vitals() and c.restores is None for c in cps)
    # numbers do not change with a limit or as the history grows
    assert [(c.number, c.label) for c in cp.read(v, limit=2)] == [(3, "plain 2"), (2, "plain 1")]
    (tmp_path / "a.txt").write_text("more")
    assert cp.record(v, "plain 3").number == 4
    assert [c.number for c in cp.read(v)] == [4, 3, 2, 1]


def test_trailer_block_parsing() -> None:
    assert split_trailers("") == ("", {})
    assert split_trailers("K: v") == ("", {"K": "v"})
    assert split_trailers("Words: not trailers\nbecause this is prose") == (
        "Words: not trailers\nbecause this is prose",
        {},
    )
    assert split_trailers("text\n\nA: 1\nB-C: 2: 3") == ("text", {"A": "1", "B-C": "2: 3"})


def test_record_with_nothing_changed(tmp_path: Path) -> None:
    v = Vcs(tmp_path)
    v.init()
    (tmp_path / "a.txt").write_text("1")
    first = cp.record(v, "one")
    assert cp.record(v, "two") == first  # nothing to save: the latest, unchanged
    assert cp.record(v, "two", allow_empty=True).number == 2
    forced = cp.record(v, "back", restores=first.id)  # a restore is always recorded
    assert forced.number == 3 and forced.restores == first.id


def test_save_edits(tmp_path: Path) -> None:
    v = Vcs(tmp_path)
    v.init()
    assert cp.save_edits(v) is None  # nothing at all
    (tmp_path / "a.txt").write_text("1")
    cp.record(v, "Start {x}")
    assert cp.save_edits(v) is None  # clean
    (tmp_path / "a.txt").write_text("2")
    saved = cp.save_edits(v)
    assert saved is not None and saved.label == "edits since Start {x}" and saved.number == 2
    (tmp_path / "b.txt").write_text("new")
    assert cp.save_edits(v, "loose {last}") is not None
    assert cp.read(v)[0].label == "loose edits since Start {x}"


# ---- the stacks, on hand-built sequences ------------------------------------------------------


def _log(*specs: tuple[str, dict[str, str]]) -> list[Checkpoint]:
    """Checkpoints c1..cn (oldest first) from (label, trailers) with trailer ids as `cN`."""
    out = []
    for i, (label, extra) in enumerate(specs, 1):
        out.append(
            Checkpoint(
                id=f"c{i}",
                number=i,
                label=label,
                when=i,
                restores=extra.get("restores"),
                undoes=extra.get("undoes"),
                redoes=extra.get("redoes"),
            )
        )
    return out


def _ids(items: tuple[Checkpoint, ...]) -> list[str]:
    return [c.id for c in items]


def test_stacks_by_hand() -> None:
    plain = ("cmd", {})
    log = _log(plain, plain, plain)
    s = cp.stacks(log)
    assert _ids(s.done) == ["c1", "c2", "c3"] and s.redo == ()
    log = _log(plain, plain, plain, ("undo", {"undoes": "c3", "restores": "c2"}))
    s = cp.stacks(log)
    assert _ids(s.done) == ["c1", "c2"] and _ids(s.redo) == ["c3"]
    log = _log(
        plain,
        plain,
        plain,
        ("undo", {"undoes": "c3", "restores": "c2"}),
        ("undo", {"undoes": "c2", "restores": "c1"}),
    )
    assert _ids(cp.stacks(log).redo) == ["c3", "c2"]  # the last undone is on top
    plan = cp.redo_plan(log)
    assert plan is not None and plan.redoes.id == "c2" and plan.restores.id == "c2"
    log = log + [
        Checkpoint("c6", 6, "redo", 6, restores="c2", redoes="c2"),
    ]
    assert _ids(cp.stacks(log).done) == ["c1", "c2"] and _ids(cp.stacks(log).redo) == ["c3"]
    # a new command empties redo
    log = log + [Checkpoint("c7", 7, "cmd", 7)]
    s = cp.stacks(log)
    assert _ids(s.done) == ["c1", "c2", "c7"] and s.redo == () and cp.redo_plan(log) is None


def test_rollback_is_one_more_entry_and_is_undoable() -> None:
    log = _log(("a", {}), ("b", {}), ("c", {}), ("rollback", {"restores": "c1"}))
    assert _ids(cp.stacks(log).done) == ["c1", "c2", "c3", "c4"]
    plan = cp.undo_plan(log)
    assert plan is not None and plan.undoes.id == "c4" and plan.restores.id == "c3"


def test_input_order_does_not_matter() -> None:
    log = _log(("a", {}), ("b", {}), ("u", {"undoes": "c2", "restores": "c1"}))
    assert cp.stacks(log) == cp.stacks(list(reversed(log)))
    assert cp.undo_plan(log) is None  # one entry left: the first cannot be undone


def test_undo_stops_at_the_baseline() -> None:
    log = _log(("a", {}), ("baseline", {}), ("b", {}), ("c", {}))
    plan = cp.undo_plan(log, stop_at="c2")
    assert plan is not None and plan.undoes.id == "c4" and plan.restores.id == "c3"
    log += [Checkpoint("c5", 5, "u", 5, undoes="c4", restores="c3")]
    log += [Checkpoint("c6", 6, "u", 6, undoes="c3", restores="c2")]
    assert cp.undo_plan(log, stop_at="c2") is None  # c2 is the baseline: it stays
    assert cp.undo_plan(log) is not None  # without a stop, the baseline can be undone
    with pytest.raises(ValueError):
        cp.undo_plan(log, stop_at="nonesuch")


def test_undo_redo_on_an_empty_or_single_log() -> None:
    assert cp.undo_plan([]) is None and cp.redo_plan([]) is None
    assert cp.undo_plan(_log(("a", {}))) is None


# ---- properties on a simulated store -----------------------------------------------------------


class Sim:
    """A store of checkpoints with a tree (an int) each, driven only through the plans."""

    def __init__(self) -> None:
        self.cps: list[Checkpoint] = []
        self.trees: dict[str, int] = {}
        self.tree = 0
        self.add("start", 0)

    def add(self, label: str, tree: int, **trailers: str) -> Checkpoint:
        number = len(self.cps) + 1
        c = Checkpoint(f"s{number}", number, label, number, **trailers)  # type: ignore[arg-type]
        self.cps.append(c)
        self.trees[c.id] = tree
        self.tree = tree
        return c

    def log(self) -> list[Checkpoint]:
        return list(reversed(self.cps))  # newest first, as `read` returns it

    def command(self, tree: int) -> None:
        self.add("command", tree)

    def undo(self, stop_at: str | None = None) -> bool:
        plan = cp.undo_plan(self.log(), stop_at)
        if plan is None:
            return False
        self.add(
            "undo", self.trees[plan.restores.id], undoes=plan.undoes.id, restores=plan.restores.id
        )
        return True

    def redo(self) -> bool:
        plan = cp.redo_plan(self.log())
        if plan is None:
            return False
        self.add(
            "redo", self.trees[plan.restores.id], redoes=plan.redoes.id, restores=plan.restores.id
        )
        return True

    def rollback(self, k: int) -> None:
        target = self.cps[k % len(self.cps)]
        self.add("rollback", self.trees[target.id], restores=target.id)

    def state(self) -> tuple[int, list[str], list[str]]:
        s = cp.stacks(self.log())
        return self.tree, _ids(s.done), _ids(s.redo)

    def apply(self, op: str, n: int, stop_at: str | None = None) -> None:
        if op == "cmd":
            self.command(n)
        elif op == "undo":
            self.undo(stop_at)
        elif op == "redo":
            self.redo()
        else:
            self.rollback(n)


OPS = st.lists(
    st.tuples(st.sampled_from(["cmd", "cmd", "undo", "redo", "rollback"]), st.integers(0, 9)),
    max_size=30,
)
PROP = settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])


def _run(ops: list[tuple[str, int]]) -> Sim:
    sim = Sim()
    for op, n in ops:
        sim.apply(op, n)
    return sim


@PROP
@given(OPS)
def test_the_current_tree_is_the_top_of_the_done_stack(ops: list[tuple[str, int]]) -> None:
    sim = _run(ops)
    _, done, _ = sim.state()
    assert sim.tree == sim.trees[done[-1]]


@PROP
@given(OPS)
def test_redo_after_undo_is_the_identity(ops: list[tuple[str, int]]) -> None:
    sim = _run(ops)
    before = sim.state()
    if sim.undo():
        assert sim.redo()
        assert sim.state() == before


@PROP
@given(OPS)
def test_undo_after_redo_is_the_identity(ops: list[tuple[str, int]]) -> None:
    sim = _run(ops)
    before = sim.state()
    if sim.redo():
        assert sim.undo()
        assert sim.state() == before


@PROP
@given(OPS, st.integers(0, 40))
def test_a_rollback_leaves_every_earlier_state_reachable(
    ops: list[tuple[str, int]], k: int
) -> None:
    sim = _run(ops)
    earlier = [(c.id, sim.trees[c.id]) for c in sim.cps]
    before = sim.state()
    sim.rollback(k)
    assert [(c.id, sim.trees[c.id]) for c in sim.cps[: len(earlier)]] == earlier  # nothing lost
    # every earlier checkpoint's state can be entered again by a rollback to it...
    for ident, tree in earlier:
        probe = _run(ops)
        probe.rollback([c.id for c in probe.cps].index(ident))
        assert probe.tree == tree
    # ...and the rollback itself is undone by an undo
    assert sim.undo()
    assert sim.tree == before[0]


@PROP
@given(OPS, OPS)
def test_undo_never_passes_the_baseline(
    before: list[tuple[str, int]], after: list[tuple[str, int]]
) -> None:
    sim = _run(before)
    sim.command(99)
    baseline = sim.cps[-1]
    for op, n in after:
        sim.apply(op, n, stop_at=baseline.id)
    for _ in range(len(sim.cps) + 1):  # undo as far as allowed
        if not sim.undo(stop_at=baseline.id):
            break
    assert cp.undo_plan(sim.log(), baseline.id) is None
    _, done, _ = sim.state()
    assert baseline.id in done
    assert all(
        sim.cps[int(i[1:]) - 1].number >= baseline.number for i in done[done.index(baseline.id) :]
    )
    assert done[-1] == baseline.id
    assert sim.tree == 99


# ---- the whole thing on real git --------------------------------------------------------


def _text(root: Path) -> str:
    return (root / "a.txt").read_text()


def _undo(v: Vcs, stop_at: str | None = None) -> bool:
    cp.save_edits(v)
    plan = cp.undo_plan(cp.read(v), stop_at)
    if plan is None:
        return False
    v.restore(plan.restores.id)
    cp.record(v, f"undid {plan.undoes.label}", restores=plan.restores.id, undoes=plan.undoes.id)
    return True


def _redo(v: Vcs) -> bool:
    plan = cp.redo_plan(cp.read(v))
    if plan is None:
        return False
    v.restore(plan.restores.id)
    cp.record(v, f"redid {plan.redoes.label}", restores=plan.restores.id, redoes=plan.redoes.id)
    return True


def test_edit_save_undo_redo_on_real_git(tmp_path: Path) -> None:
    v = Vcs(tmp_path)
    v.init()
    (tmp_path / ".gitignore").write_text("build/\n")
    (tmp_path / "a.txt").write_text("v1")
    cp.record(v, "Start", Vitals("1.0 kg", None))
    (tmp_path / "a.txt").write_text("v2")
    (tmp_path / "b.txt").write_text("b2")
    cp.record(v, "Changed the part", Vitals("2.0 kg", "$5"))
    (tmp_path / "a.txt").write_text("v3")  # an edit made outside any command
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "out").write_text("kept")
    assert _undo(v)  # saves the edit as its own checkpoint, then undoes it
    labels = [c.label for c in cp.read(v)]
    assert labels[1] == "edits since Changed the part" and labels[0].startswith("undid edits")
    assert (_text(tmp_path), (tmp_path / "b.txt").exists()) == ("v2", True)
    assert _undo(v)
    assert (_text(tmp_path), (tmp_path / "b.txt").exists()) == ("v1", False)
    assert not _undo(v)  # the first checkpoint cannot be undone
    assert (tmp_path / "build" / "out").read_text() == "kept"
    assert _redo(v) and (_text(tmp_path), (tmp_path / "b.txt").exists()) == ("v2", True)
    assert _redo(v) and _text(tmp_path) == "v3"
    assert not _redo(v)
    assert v.is_clean()
    # undoing never rewrote anything: the history only grew
    assert [c.number for c in cp.read(v)] == list(range(7, 0, -1))
    # and a rollback to the very first state is itself undoable
    v.restore(cp.read(v)[-1].id)
    cp.record(v, "rolled back", restores=cp.read(v)[-1].id)
    assert _text(tmp_path) == "v1"
    assert _undo(v) and _text(tmp_path) == "v3"


def test_undo_inside_a_draft_stops_at_the_baseline(tmp_path: Path) -> None:
    v = Vcs(tmp_path)
    v.init()
    (tmp_path / "a.txt").write_text("v1")
    cp.record(v, "Start")
    (tmp_path / "a.txt").write_text("v2")
    baseline = cp.record(v, "Baseline")
    (tmp_path / "a.txt").write_text("v3")
    cp.record(v, "Draft edit")
    assert _undo(v, stop_at=baseline.id) and _text(tmp_path) == "v2"
    assert not _undo(v, stop_at=baseline.id) and _text(tmp_path) == "v2"
    assert _undo(v) and _text(tmp_path) == "v1"  # outside the request nothing stops it


def test_checkpoint_from_snapshot_ignores_unrelated_trailers() -> None:
    info = SnapshotInfo("x" * 40, (), 5, "L", "", {"Co-Authored-By": "someone", cp.KEY_COST: "$9"})
    c = Checkpoint.from_snapshot(info, 3)
    assert c.vitals == Vitals(None, "$9") and c.number == 3 and c.undoes is None
