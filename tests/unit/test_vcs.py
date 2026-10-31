"""D31: every git failure is worded for the operator; raw git text never leaks."""

from __future__ import annotations

from pathlib import Path

import pytest

from napkin2factory.core.vcs import NOT_TRACKED, UNSAVED, Vcs, VcsError

GIT_WORDS = ("fatal:", "git ", "branch", "commit", "merge", "HEAD", "repository")


def _assert_persona(message: str) -> None:
    low = message.lower()
    for w in GIT_WORDS:
        assert w.lower() not in low, f"git vocabulary {w!r} leaked into: {message}"


def test_not_a_repo_path(tmp_path: Path):
    v = Vcs(tmp_path)
    assert not v.is_tracked()
    with pytest.raises(VcsError) as ei:
        v.require_repo_root()
    assert str(ei.value) == NOT_TRACKED
    _assert_persona(str(ei.value))
    assert ei.value.code == "not-a-repo"
    with pytest.raises(VcsError) as ei2:
        v.snapshot("x")
    _assert_persona(str(ei2.value))
    assert "not a git repository" in ei2.value.detail.lower()  # raw text kept on .detail only


def test_init_snapshot_clean_and_dirty(tmp_path: Path):
    v = Vcs(tmp_path)
    v.init()
    v.init()  # idempotent
    assert v.is_repo_root()
    (tmp_path / "a.txt").write_text("1")
    sha = v.snapshot("first")
    assert len(sha) == 40 and v.head() == sha
    assert v.is_clean()
    assert v.commit_date() >= "2026-01-01"
    (tmp_path / "a.txt").write_text("2")
    assert not v.is_clean()
    with pytest.raises(VcsError) as ei:
        v.require_clean()
    assert str(ei.value) == UNSAVED
    _assert_persona(str(ei.value))
    assert ei.value.code == "unsaved"


def test_nested_folder_is_not_root(tmp_path: Path):
    v = Vcs(tmp_path)
    v.init()
    (tmp_path / "a.txt").write_text("1")
    v.snapshot("first")
    inner = tmp_path / "inner"
    inner.mkdir()
    iv = Vcs(inner)
    assert iv.is_tracked() and not iv.is_repo_root()
    with pytest.raises(VcsError) as ei:
        iv.require_repo_root()
    _assert_persona(str(ei.value))
    assert ei.value.code == "not-root"


def test_tags_and_refs(tmp_path: Path):
    v = Vcs(tmp_path)
    v.init()
    (tmp_path / "a.txt").write_text("1")
    v.snapshot("first")
    assert v.tags() == [] and v.tag_for_head() is None
    v.tag("v1.0.0", "Revision v1.0.0")
    assert v.tags() == ["v1.0.0"] and v.tag_for_head() == "v1.0.0"
    assert v.ref_exists("v1.0.0") and not v.ref_exists("v9.9.9")
    with pytest.raises(VcsError) as ei:
        v.tag("v1.0.0", "again")
    assert "already exists" in str(ei.value) and "pick the next version" in str(ei.value)
    _assert_persona(str(ei.value))
    (tmp_path / "a.txt").write_text("2")
    v.snapshot("second")
    assert v.diff_names("v1.0.0", "HEAD") == ["a.txt"]


def test_snapshot_without_changes_returns_head(tmp_path: Path):
    v = Vcs(tmp_path)
    v.init()
    (tmp_path / "a.txt").write_text("1")
    first = v.snapshot("first")
    assert v.snapshot("nothing") == first


def test_worktree_roundtrip(tmp_path: Path):
    v = Vcs(tmp_path / "p")
    (tmp_path / "p").mkdir()
    v.init()
    (tmp_path / "p" / "a.txt").write_text("1")
    v.snapshot("first")
    v.tag("v1.0.0", "r")
    wt = tmp_path / "wt"
    v.worktree_add("v1.0.0", wt)
    assert (wt / "a.txt").read_text() == "1"
    v.worktree_remove(wt)
    assert not wt.exists()
    with pytest.raises(VcsError) as ei:
        v.worktree_add("v2.0.0", tmp_path / "wt2")
    _assert_persona(str(ei.value))


def _no_git_identity(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A machine where nobody ever configured git (S-011)."""
    for key in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "empty-gitconfig"))
    monkeypatch.setenv("HOME", str(tmp_path))


def _author(v: Vcs) -> str:
    return v._git("log", "-1", "--format=%an <%ae>").stdout.strip()


def test_unconfigured_identity_uses_product_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _no_git_identity(monkeypatch, tmp_path)
    root = tmp_path / "p"
    root.mkdir()
    (root / "n2f.yaml").write_text("product:\n  id: lamp\n  name: Desk lamp\n")
    v = Vcs(root)
    v.init()
    v.snapshot("first")
    assert _author(v) == "Desk lamp <n2f@localhost>"


def test_unconfigured_identity_without_manifest_uses_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _no_git_identity(monkeypatch, tmp_path)
    v = Vcs(tmp_path / "shelf")
    (tmp_path / "shelf").mkdir()
    v.init()
    (tmp_path / "shelf" / "a.txt").write_text("1")
    v.snapshot("first")
    assert _author(v) == "shelf <n2f@localhost>"


def test_configured_identity_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _no_git_identity(monkeypatch, tmp_path)
    (tmp_path / "empty-gitconfig").write_text("[user]\n\tname = Ada\n\temail = ada@example.com\n")
    root = tmp_path / "p"
    root.mkdir()
    (root / "n2f.yaml").write_text("product:\n  id: lamp\n  name: Desk lamp\n")
    v = Vcs(root)
    v.init()
    v.snapshot("first")
    assert _author(v) == "Ada <ada@example.com>"
