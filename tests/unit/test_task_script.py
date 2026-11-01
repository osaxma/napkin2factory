"""scripts/task.sh and scripts/journal_ids.py in a throwaway repo: start, land, list, abandon."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TASK = REPO / "scripts" / "task.sh"
NEW = "-NEW"  # placeholders are spelled in pieces so this file holds none (test_journals)
S1, B1 = f"S{NEW}1", f"B{NEW}1"

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")

DECISIONS = """# Decisions

## Index

| id | decision | status |
|---|---|---|
| S-001 | First | in force |
| Gate 1 | Review gate 1 — outcome | recorded |

---

## S-001 — First (2026-11-01)
Body.

## Review gate 1 (architecture) — outcome (2026-11-01)
Body.
"""

BACKLOG = """# Backlog

## Open

| id | item | origin |
|---|---|---|
| B-0001 | First | S-001 |

## Closed

| id | item | closed |
|---|---|---|
"""


def run(cwd: Path, *args: str, ok: bool = True) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
        "N2F_TASK_NO_SYNC": "1",
        "LAND_GATE": "none",
    }
    done = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True)
    if ok:
        assert done.returncode == 0, done.stdout + done.stderr
    return done


def task(cwd: Path, *args: str, ok: bool = True) -> subprocess.CompletedProcess[str]:
    return run(cwd, "sh", str(TASK), *args, ok=ok)


def commit(cwd: Path, message: str) -> None:
    run(cwd, "git", "add", "-A")
    run(cwd, "git", "commit", "-q", "-m", message)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path.resolve() / "product"
    (root / "src").mkdir(parents=True)
    (root / "DECISIONS.md").write_text(DECISIONS)
    (root / "BACKLOG.md").write_text(BACKLOG)
    (root / "src" / "shared.py").write_text("VALUE = 1\n")
    (root / ".gitignore").write_text(".worktrees/\n")
    shutil.copy(REPO / ".gitattributes", root / ".gitattributes")
    run(root, "git", "init", "-q", "-b", "main")
    commit(root, "Start")
    return root


def add_decision(folder: Path, name: str) -> None:
    """Append a decision, its index row, a backlog row and a TODO, all with placeholders."""
    index = f"| Gate 1 | Review gate 1 — outcome | recorded |\n| {S1} | {name} | in force |\n"
    text = (
        (folder / "DECISIONS.md")
        .read_text()
        .replace("| Gate 1 | Review gate 1 — outcome | recorded |\n", index)
    )
    (folder / "DECISIONS.md").write_text(text + f"\n## {S1} — {name} (2026-11-01)\nOpens {B1}.\n")
    backlog = (
        (folder / "BACKLOG.md")
        .read_text()
        .replace(
            "| B-0001 | First | S-001 |\n",
            f"| B-0001 | First | S-001 |\n| {B1} | {name} | {S1} |\n",
        )
    )
    (folder / "BACKLOG.md").write_text(backlog)
    (folder / "src" / f"{name}.py").write_text(f"# TODO({B1}): finish {name}\n")
    commit(folder, f"Add {name} ({S1})")


def test_two_tasks_land_with_distinct_ids(repo: Path) -> None:
    for name in ("alpha", "beta"):
        task(repo, "new", name, f"goal of {name}")
    wt = {name: repo / ".worktrees" / name for name in ("alpha", "beta")}
    for name, folder in wt.items():
        add_decision(folder, name)

    listing = task(repo, "list").stdout
    assert "goal of alpha" in listing and "Add beta" in listing

    out = task(wt["alpha"], "land").stdout
    assert "Landed 1 commit(s)" in out and "make check" in out
    task(wt["beta"], "land")

    log = run(repo, "git", "log", "--format=%s", "main").stdout.splitlines()
    assert log == ["Add beta (S-003)", "Add alpha (S-002)", "Start"]  # messages rewritten too
    history = run(repo, "git", "log", "-p", "--format=%B", "main").stdout
    assert NEW not in history  # no landed commit ever held a placeholder (bisect-safe)
    assert run(repo, "git", "rev-list", "--merges", "--count", "main").stdout.strip() == "0"
    decisions = (repo / "DECISIONS.md").read_text()
    assert "## S-002 — alpha" in decisions and "## S-003 — beta" in decisions
    assert "| S-002 | alpha |" in decisions and "| S-003 | beta |" in decisions
    backlog = (repo / "BACKLOG.md").read_text()
    assert "| B-0002 | alpha | S-002 |" in backlog and "| B-0003 | beta | S-003 |" in backlog
    assert "TODO(B-0002)" in (repo / "src" / "alpha.py").read_text()
    assert "TODO(B-0003)" in (repo / "src" / "beta.py").read_text()
    tracked = run(repo, "git", "grep", "-l", "-e", NEW, ok=False)
    assert tracked.returncode == 1 and tracked.stdout == ""
    assert not wt["alpha"].exists() and not wt["beta"].exists()
    assert run(repo, "git", "branch", "--list", "task/*").stdout == ""
    assert "no open tasks" in task(repo, "list").stdout
    assert "task/" not in run(repo, "git", "config", "--list").stdout  # goals went with them


def test_land_refuses_unsaved_changes(repo: Path) -> None:
    task(repo, "new", "dirty", "a goal")
    folder = repo / ".worktrees" / "dirty"
    (folder / "src" / "shared.py").write_text("VALUE = 2\n")
    done = task(folder, "land", ok=False)
    assert done.returncode != 0 and "commit them" in done.stderr
    assert "UNSAVED CHANGES" in task(repo, "list").stdout


def test_land_refuses_wip_commits(repo: Path) -> None:
    task(repo, "new", "half", "a goal")
    folder = repo / ".worktrees" / "half"
    (folder / "src" / "shared.py").write_text("VALUE = 2\n")
    commit(folder, "WIP: half done\n\nDone: the value. Left: the docs. Verify: make check.")
    assert "WIP: half done" in task(repo, "list").stdout
    done = task(folder, "land", ok=False)
    assert done.returncode != 0 and "git reset --soft main" in done.stderr


def test_land_stops_on_conflict(repo: Path) -> None:
    for name in ("one", "two"):
        task(repo, "new", name, "change the value")
        folder = repo / ".worktrees" / name
        (folder / "src" / "shared.py").write_text(f"VALUE = '{name}'\n")
        commit(folder, f"Value {name}")
    task(repo / ".worktrees" / "one", "land")
    two = repo / ".worktrees" / "two"
    done = task(two, "land", ok=False)
    assert done.returncode != 0 and "git rebase --continue" in done.stderr
    assert "rebas" in run(two, "git", "status").stdout  # left in progress, for the agent to fix
    again = task(two, "land", ok=False)
    assert "rebase is in progress" in again.stderr


def test_new_and_abandon_guard_rails(repo: Path) -> None:
    assert "GOAL" in task(repo, "new", "x", "", ok=False).stderr
    assert "NAME" in task(repo, "new", "Bad Name", "goal", ok=False).stderr
    task(repo, "new", "drop", "a goal")
    folder = repo / ".worktrees" / "drop"
    (folder / "src" / "shared.py").write_text("VALUE = 3\n")
    commit(folder, "Doomed work")
    refused = task(repo, "abandon", "drop", ok=False)
    assert "Doomed work" in refused.stdout and "CONFIRM=1" in refused.stderr
    assert folder.exists()
    run(repo, "env", "CONFIRM=1", "sh", str(TASK), "abandon", "drop")
    assert not folder.exists()
    assert run(repo, "git", "branch", "--list", "task/*").stdout == ""


def test_land_starts_again_when_main_moves_mid_land(repo: Path, tmp_path: Path) -> None:
    """Beta lands while alpha's gate runs: alpha must retry with fresh ids, not reuse its own."""
    for name in ("alpha", "beta"):
        task(repo, "new", name, f"goal of {name}")
        add_decision(repo / ".worktrees" / name, name)
    # A stand-in for `make` that, the first time alpha's gate calls it, lands beta: main moves
    # after alpha has rebased and taken ids, exactly the window the retry exists for.
    marker = tmp_path / "beta-landed"
    fake_make = tmp_path / "make"
    fake_make.write_text(
        f"#!/bin/sh\n[ -e {marker} ] && exit 0\ntouch {marker}\n"
        f"cd {repo / '.worktrees' / 'beta'} && LAND_GATE=none sh {TASK} land >/dev/null\n"
    )
    fake_uv = tmp_path / "uv"
    fake_uv.write_text("#!/bin/sh\nexit 0\n")
    for tool in (fake_make, fake_uv):
        tool.chmod(0o755)
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
        "N2F_TASK_NO_SYNC": "1",
        "LAND_GATE": "fast",
        "MAKE": str(fake_make),
        "UV": str(fake_uv),
    }
    done = subprocess.run(
        ["sh", str(TASK), "land"],
        cwd=repo / ".worktrees" / "alpha",
        env=env,
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert marker.exists() and "main moved while landing" in done.stdout

    log = run(repo, "git", "log", "--format=%s", "main").stdout.splitlines()
    assert log == ["Add alpha (S-003)", "Add beta (S-002)", "Start"]
    decisions = (repo / "DECISIONS.md").read_text()
    assert decisions.count("## S-002 — ") == 1 and decisions.count("## S-003 — ") == 1
    assert "## S-002 — beta" in decisions and "## S-003 — alpha" in decisions
    backlog = (repo / "BACKLOG.md").read_text()
    assert "| B-0002 | beta | S-002 |" in backlog and "| B-0003 | alpha | S-003 |" in backlog
    assert NEW not in run(repo, "git", "log", "-p", "--format=%B", "main").stdout
