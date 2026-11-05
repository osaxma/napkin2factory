"""R1's store primitives on real git in temp folders: no product build (S-246)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from napkin2factory.core.vcs import FileChange, Vcs, VcsError

GIT_WORDS = ("fatal:", "git ", "branch", "commit", "merge", "head", "repository")


def _git(where: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=where, capture_output=True, text=True, check=True
    ).stdout.strip()


def _bare_git(remote: Path, *args: str) -> str:
    """Read a bare repository with `--git-dir`, never `cwd=` (S-177, safe.bareRepository)."""
    return subprocess.run(
        ["git", f"--git-dir={remote}", *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _write(root: Path, rel: str, text: str | bytes) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding="utf-8")


def _tree(root: Path) -> dict[str, bytes]:
    """Every file of the folder except `.git` and `build/` (what a snapshot would save)."""
    out: dict[str, bytes] = {}
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != ".git" and not (Path(dirpath) == root and d == "build")]
        for name in files:
            p = Path(dirpath) / name
            out[p.relative_to(root).as_posix()] = p.read_bytes()
    return out


@pytest.fixture
def v(tmp_path: Path) -> Vcs:
    root = tmp_path / "prod"
    root.mkdir()
    _write(root, ".gitignore", "build/\n")
    vcs = Vcs(root)
    vcs.init()
    return vcs


def _assert_persona(message: str) -> None:
    low = message.lower()
    for w in GIT_WORDS:
        assert w not in low, f"git vocabulary {w!r} leaked into: {message}"


# ---- snapshots, read_file, tree_of ---------------------------------------------------------


def test_snapshots_empty_before_the_first(v: Vcs) -> None:
    assert v.snapshots() == []
    assert v.snapshot_count() == 0


def test_snapshots_newest_first_with_trailers(v: Vcs) -> None:
    _write(v.root, "a.txt", "1")
    first = v.snapshot("First: one")
    _write(v.root, "a.txt", "2")
    second = v.snapshot('Say "hi" – größe 日本\n\nKey-One: a value\nOther: x: y')
    infos = v.snapshots()
    assert [i.id for i in infos] == [second, first]
    assert infos[1].parents == () and infos[0].parents == (first,)
    assert infos[0].label == 'Say "hi" – größe 日本'
    assert infos[0].trailers == {"Key-One": "a value", "Other": "x: y"}
    assert infos[0].body == ""
    assert infos[1].label == "First: one" and infos[1].trailers == {}
    assert infos[0].when >= infos[1].when > 1_700_000_000
    assert [i.id for i in v.snapshots(limit=1)] == [second]
    assert v.snapshots(first)[0].id == first
    assert v.snapshot_count() == 2 and v.snapshot_count(first) == 1


def test_snapshot_body_and_trailers_split(v: Vcs) -> None:
    _write(v.root, "a.txt", "1")
    v.snapshot("Label\n\nSome words about it.\n\nK: v")
    (info,) = v.snapshots()
    assert info.body == "Some words about it." and info.trailers == {"K": "v"}


def test_snapshots_unknown_state_is_an_owner_error(v: Vcs) -> None:
    _write(v.root, "a.txt", "1")
    v.snapshot("x")
    for bad in ("nonesuch", "-x", ""):
        with pytest.raises(VcsError) as ei:
            v.snapshots(bad)
        assert ei.value.code == "no-such-state"
        _assert_persona(str(ei.value))


def test_read_file_and_tree_of(v: Vcs) -> None:
    _write(v.root, "a.txt", "one")
    _write(v.root, "sub/b.bin", b"\x00\xff\xfe binary")
    s1 = v.snapshot("one")
    _write(v.root, "a.txt", "two")
    (v.root / "sub" / "b.bin").unlink()
    s2 = v.snapshot("two")
    assert v.read_file(s1, "a.txt") == b"one" and v.read_file(s2, "a.txt") == b"two"
    assert v.read_file(s1, "sub/b.bin") == b"\x00\xff\xfe binary"
    assert v.read_file(s2, "sub/b.bin") is None
    assert v.read_file(s1, "sub") is None and v.read_file(s1, "nope.txt") is None
    with pytest.raises(VcsError):
        v.read_file("nonesuch", "a.txt")
    with pytest.raises(VcsError) as ei:
        v.read_file(s1, "../x")
    assert ei.value.code == "bad-path"
    assert v.tree_of(s1) != v.tree_of(s2)
    assert v.tree_of(s1) == _git(v.root, "rev-parse", f"{s1}^{{tree}}")
    with pytest.raises(VcsError):
        v.tree_of("nonesuch")


# ---- diff_working -----------------------------------------------------------------------


def test_diff_working_every_kind(v: Vcs) -> None:
    _write(v.root, "keep.txt", "k")
    _write(v.root, "change.txt", "old")
    _write(v.root, "gone.txt", "g")
    _write(v.root, "dir/inner.txt", "i")
    s = v.snapshot("base")
    assert v.diff_working(s) == []
    _write(v.root, "change.txt", "new")
    (v.root / "gone.txt").unlink()
    _write(v.root, "untracked.txt", "u")  # never added: still counts
    _write(v.root, "dir/new.txt", "n")
    _write(v.root, "build/out.txt", "ignored")
    expected = [
        FileChange("change.txt", "changed"),
        FileChange("dir/new.txt", "added"),
        FileChange("gone.txt", "removed"),
        FileChange("untracked.txt", "added"),
    ]
    assert v.diff_working(s) == expected
    # exactly the set the next snapshot would save
    nxt = v.snapshot("next")
    assert v.diff_working(s) == expected and v.diff_working(nxt) == []
    assert sorted(v.diff_names(s, nxt)) == sorted(c.path for c in expected)


def test_diff_working_non_ascii_and_mode(v: Vcs) -> None:
    _write(v.root, "größe 日本.txt", "x")
    _write(v.root, "run.sh", "#!/bin/sh\n")
    s = v.snapshot("base")
    _write(v.root, "größe 日本.txt", "y")
    (v.root / "run.sh").chmod(0o755)
    assert v.diff_working(s) == [
        FileChange("größe 日本.txt", "changed"),
        FileChange("run.sh", "changed"),
    ]


def test_diff_working_against_an_earlier_state(v: Vcs) -> None:
    _write(v.root, "a.txt", "1")
    s1 = v.snapshot("one")
    _write(v.root, "b.txt", "2")
    v.snapshot("two")
    assert v.diff_working(s1) == [FileChange("b.txt", "added")]
    with pytest.raises(VcsError):
        v.diff_working("nonesuch")


# ---- working_hash -----------------------------------------------------------------------


def test_working_hash_stable_changes_and_leaves_the_store_alone(v: Vcs) -> None:
    _write(v.root, "a.txt", "1")
    s = v.snapshot("one")
    assert v.working_hash() == v.tree_of(s)  # a clean folder hashes as the last snapshot
    _write(v.root, "a.txt", "2")
    _write(v.root, "new.txt", "n")
    _write(v.root, "build/x", "ignored")
    status_before = _git(v.root, "status", "--porcelain", "--untracked-files=all")
    index_before = (v.root / ".git" / "index").read_bytes()
    h = v.working_hash()
    assert h == v.working_hash() != v.tree_of(s)
    assert _git(v.root, "status", "--porcelain", "--untracked-files=all") == status_before
    assert (v.root / ".git" / "index").read_bytes() == index_before
    assert v.head() == s
    assert [p.name for p in (v.root / ".git").glob("n2f-store-*")] == []
    _write(v.root, "build/y", "ignored too")  # ignored files do not count
    assert v.working_hash() == h
    nxt = v.snapshot("next")  # ...and it is the tree the next snapshot gets
    assert v.tree_of(nxt) == h


def test_working_hash_sees_a_same_size_edit_in_the_same_second(v: Vcs) -> None:
    _write(v.root, "a.txt", "aaaa")
    v.snapshot("one")
    first = v.working_hash()
    _write(v.root, "a.txt", "bbbb")
    assert v.working_hash() != first


def test_working_hash_equal_folders_equal_hashes(tmp_path: Path) -> None:
    hashes = []
    for name in ("one", "two"):
        root = tmp_path / name
        root.mkdir()
        vcs = Vcs(root)
        vcs.init()
        _write(root, "a.txt", "same")
        _write(root, "d/b.txt", "same too")
        hashes.append(vcs.working_hash())
    assert hashes[0] == hashes[1]


def test_working_hash_before_the_first_snapshot(v: Vcs) -> None:
    empty = v.working_hash()
    _write(v.root, "a.txt", "1")
    assert v.working_hash() != empty


# ---- restore ------------------------------------------------------------------------------


def _history(v: Vcs) -> tuple[str, str]:
    _write(v.root, "a.txt", "a1")
    _write(v.root, "dir/b.txt", "b1")
    _write(v.root, "other/c.txt", "c1")
    s1 = v.snapshot("one")
    _write(v.root, "a.txt", "a2")
    (v.root / "dir" / "b.txt").unlink()
    _write(v.root, "dir/new.txt", "n2")
    _write(v.root, "other/c.txt", "c2")
    _write(v.root, "extra/deep/x.txt", "x2")
    s2 = v.snapshot("two")
    return s1, s2


def test_restore_full_round_trip_has_the_states_tree(v: Vcs) -> None:
    s1, s2 = _history(v)
    _write(v.root, "unsaved.txt", "u")  # untracked, not ignored: part of what a snapshot saves
    _write(v.root, "build/out.bin", "keep me")
    changed = v.restore(s1)
    assert _tree(v.root) == {
        ".gitignore": b"build/\n",
        "a.txt": b"a1",
        "dir/b.txt": b"b1",
        "other/c.txt": b"c1",
    }
    assert (v.root / "build" / "out.bin").read_text() == "keep me"
    assert not (v.root / "extra").exists()  # folders it leaves empty go too
    assert {(c.path, c.status) for c in changed} == {
        ("a.txt", "changed"),
        ("dir/b.txt", "removed"),
        ("dir/new.txt", "added"),
        ("other/c.txt", "changed"),
        ("extra/deep/x.txt", "added"),
        ("unsaved.txt", "added"),
    }
    assert v.head() == s2  # it moves nothing
    assert v.working_hash() == v.tree_of(s1)
    back = v.snapshot("back to one")
    assert v.tree_of(back) == v.tree_of(s1) and v.head() == back
    # and forwards again
    v.restore(s2)
    assert v.working_hash() == v.tree_of(s2)
    assert v.restore(s2) == []


def test_restore_scoped_touches_only_the_given_paths(v: Vcs) -> None:
    s1, _ = _history(v)
    before = _tree(v.root)
    changed = v.restore(s1, ["dir", "a.txt"])
    after = _tree(v.root)
    assert after["a.txt"] == b"a1" and after["dir/b.txt"] == b"b1"
    assert "dir/new.txt" not in after
    assert after["other/c.txt"] == before["other/c.txt"] == b"c2"  # out of scope
    assert after["extra/deep/x.txt"] == b"x2"
    assert sorted(c.path for c in changed) == ["a.txt", "dir/b.txt", "dir/new.txt"]
    # a prefix is whole path parts: "dir" does not match "directory/..."
    _write(v.root, "directory/z.txt", "z")
    v.restore(s1, ["dir"])
    assert (v.root / "directory" / "z.txt").exists()


def test_restore_never_touches_build_even_if_the_state_names_it(v: Vcs) -> None:
    s1, _ = _history(v)
    _write(v.root, "build/a/b.bin", "artifact")
    v.restore(s1)
    assert (v.root / "build" / "a" / "b.bin").read_text() == "artifact"


def test_restore_replaces_a_file_by_a_folder_and_back(v: Vcs) -> None:
    _write(v.root, "thing", "a file")
    s1 = v.snapshot("file")
    (v.root / "thing").unlink()
    _write(v.root, "thing/inner.txt", "now a folder")
    s2 = v.snapshot("folder")
    v.restore(s1)
    assert (v.root / "thing").read_text() == "a file"
    v.restore(s2)
    assert (v.root / "thing" / "inner.txt").read_text() == "now a folder"


def test_restore_keeps_binary_files_and_the_executable_bit(v: Vcs) -> None:
    _write(v.root, "run.sh", "#!/bin/sh\n")
    (v.root / "run.sh").chmod(0o755)
    _write(v.root, "d.bin", b"\x00\x01\xff")
    s1 = v.snapshot("one")
    _write(v.root, "d.bin", b"changed")
    (v.root / "run.sh").unlink()
    v.restore(s1)
    assert (v.root / "d.bin").read_bytes() == b"\x00\x01\xff"
    assert os.access(v.root / "run.sh", os.X_OK)


def test_restore_rejects_bad_input(v: Vcs) -> None:
    _write(v.root, "a.txt", "1")
    s = v.snapshot("one")
    with pytest.raises(VcsError):
        v.restore("nonesuch")
    for bad in ("../x", "/etc"):
        with pytest.raises(VcsError) as ei:
            v.restore(s, [bad])
        assert ei.value.code == "bad-path"
        _assert_persona(str(ei.value))


# ---- named refs ---------------------------------------------------------------------------


def test_refs_set_read_list_delete(v: Vcs) -> None:
    _write(v.root, "a.txt", "1")
    s1 = v.snapshot("one")
    _write(v.root, "a.txt", "2")
    s2 = v.snapshot("two")
    assert v.read_ref("parked/C-002") is None and v.list_refs() == {}
    v.set_ref("parked/C-002", s1)
    v.set_ref("ecr/ECR-003/baseline", "@")
    assert v.read_ref("parked/C-002") == s1 and v.read_ref("ecr/ECR-003/baseline") == s2
    assert v.list_refs() == {"ecr/ECR-003/baseline": s2, "parked/C-002": s1}
    assert v.list_refs("parked") == {"parked/C-002": s1}
    assert v.list_refs("ecr/ECR-003/") == {"ecr/ECR-003/baseline": s2}
    assert v.list_refs("park") == {}  # whole parts only
    v.set_ref("parked/C-002", s2)  # move
    assert v.read_ref("parked/C-002") == s2
    v.delete_ref("parked/C-002")
    v.delete_ref("parked/C-002")  # idempotent
    assert v.read_ref("parked/C-002") is None
    assert _git(v.root, "for-each-ref", "--format=%(refname)") == (
        "refs/heads/main\nrefs/n2f/ecr/ECR-003/baseline"
    )
    # a marker keeps its state alive
    _git(v.root, "gc", "-q", "--prune=now")
    assert v.read_file(s2, "a.txt") == b"2"


@pytest.mark.parametrize(
    "name",
    [
        "",
        "/abs",
        "a/../b",
        "a//b",
        "a b",
        "a:b",
        "-x",
        ".hidden",
        "a/.b",
        "a.lock",
        "a/",
        "x~1",
        "x\\y",
    ],
)
def test_ref_names_are_validated(v: Vcs, name: str) -> None:
    _write(v.root, "a.txt", "1")
    s = v.snapshot("one")
    for call in (
        lambda: v.set_ref(name, s),
        lambda: v.read_ref(name),
        lambda: v.delete_ref(name),
    ):
        with pytest.raises(VcsError) as ei:
            call()
        assert ei.value.code == "bad-marker"
        _assert_persona(str(ei.value))


def test_ref_target_must_be_a_state_and_names_cannot_overlap(v: Vcs) -> None:
    _write(v.root, "a.txt", "1")
    s = v.snapshot("one")
    with pytest.raises(VcsError) as ei:
        v.set_ref("parked/C-1", "nonesuch")
    assert ei.value.code == "no-such-state"
    v.set_ref("parked/C-1", s)
    with pytest.raises(VcsError) as ei2:
        v.set_ref("parked", s)
    assert ei2.value.code == "marker-conflict"
    _assert_persona(str(ei2.value))


# ---- markers and the online copy ----------------------------------------------------------


def test_publish_sends_its_line_and_tags_but_no_marker(v: Vcs, tmp_path: Path) -> None:
    _write(v.root, "a.txt", "1")
    s1 = v.snapshot("one")
    v.tag("v1.0.0", "Revision v1.0.0")
    _write(v.root, "a.txt", "2")
    v.snapshot("two")
    v.set_ref("parked/C-002", s1)
    v.set_ref("ecr/ECR-003/baseline", "@")
    remote = tmp_path / "online.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    _git(v.root, "remote", "add", "origin", str(remote))
    v.send_online("origin", "main")
    assert _bare_git(remote, "rev-parse", "main") == v.head()
    assert _bare_git(remote, "tag", "--list") == "v1.0.0"
    assert _bare_git(remote, "for-each-ref", "--format=%(refname)").splitlines() == [
        "refs/heads/main",
        "refs/tags/v1.0.0",
    ]


def test_a_fresh_copy_has_no_markers_and_says_so_quietly(v: Vcs, tmp_path: Path) -> None:
    _write(v.root, "a.txt", "1")
    s1 = v.snapshot("one")
    v.set_ref("parked/C-002", s1)
    remote = tmp_path / "online.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    _git(v.root, "remote", "add", "origin", str(remote))
    v.send_online("origin", "main")
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", str(remote), str(clone))
    other = Vcs(clone)
    assert other.list_refs() == {}
    assert other.read_ref("parked/C-002") is None  # no exception: the caller reports the gap
    assert [i.label for i in other.snapshots()] == ["one"]
