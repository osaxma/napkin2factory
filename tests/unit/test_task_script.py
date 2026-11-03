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
    beta_trailers = run(repo, "git", "log", "-1", "--format=%(trailers)", "main").stdout
    assert "Task: beta" in beta_trailers
    assert "Task-started:" in beta_trailers
    assert "Task-conflicts: 0" in beta_trailers
    alpha_trailers = run(repo, "git", "log", "-1", "--format=%(trailers)", "main~1").stdout
    assert "Task: alpha" in alpha_trailers
    assert "Task-started:" in alpha_trailers
    assert "Task-conflicts: 0" in alpha_trailers
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
    assert run(two, "git", "config", "branch.task/two.conflicts").stdout.strip() == "1"
    again = task(two, "land", ok=False)
    assert "rebase is in progress" in again.stderr
    (two / "src" / "shared.py").write_text("VALUE = 'resolved'\n")
    run(two, "git", "add", "src/shared.py")
    run(two, "env", "GIT_EDITOR=true", "git", "rebase", "--continue")
    landed = task(two, "land")
    assert "Landed 1 commit(s)" in landed.stdout
    msg = run(repo, "git", "log", "-1", "--format=%B", "main").stdout
    assert "Task: two" in msg
    assert "Task-conflicts: 1" in msg


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
    alpha_msg = run(repo, "git", "log", "-1", "--format=%B", "main").stdout
    assert alpha_msg.count("Task: alpha") == 1
    assert alpha_msg.count("Task-started:") == 1
    assert alpha_msg.count("Task-conflicts: 0") == 1


def test_a_failed_gate_keeps_the_placeholders(repo: Path, tmp_path: Path) -> None:
    """A gate that fails after ids were given out puts the task's own commits back (S-109)."""
    task(repo, "new", "alpha", "goal of alpha")
    folder = repo / ".worktrees" / "alpha"
    add_decision(folder, "alpha")
    before = run(folder, "git", "rev-parse", "HEAD").stdout.strip()
    fake_make = tmp_path / "make"
    fake_make.write_text("#!/bin/sh\nexit 1\n")
    fake_make.chmod(0o755)
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
        "N2F_TASK_NO_SYNC": "1",
        "LAND_GATE": "check",
        "MAKE": str(fake_make),
    }
    done = subprocess.run(
        ["sh", str(TASK), "land"], cwd=folder, env=env, capture_output=True, text=True
    )
    assert done.returncode != 0 and "placeholders kept" in done.stderr + done.stdout
    assert run(folder, "git", "rev-parse", "HEAD").stdout.strip() == before
    assert f"## {S1} — alpha" in (folder / "DECISIONS.md").read_text()
    assert run(repo, "git", "log", "--format=%s", "main").stdout.splitlines() == ["Start"]


def test_the_default_gate_is_make_check_fast(repo: Path, tmp_path: Path) -> None:
    """With no LAND_GATE, landing runs `make check-fast` with placeholders refused (S-097)."""
    task(repo, "new", "alpha", "goal of alpha")
    folder = repo / ".worktrees" / "alpha"
    add_decision(folder, "alpha")
    calls = tmp_path / "calls"
    fake_make = tmp_path / "make"
    fake_make.write_text(f'#!/bin/sh\necho "$* $N2F_ALLOW_PLACEHOLDERS" >> {calls}\n')
    fake_make.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if k != "LAND_GATE"}
    env |= {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
        "N2F_TASK_NO_SYNC": "1",
        "MAKE": str(fake_make),
    }
    done = subprocess.run(
        ["sh", str(TASK), "land"], cwd=folder, env=env, capture_output=True, text=True
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert calls.read_text().splitlines() == ["check-fast 0"]
    assert (
        run(repo, "git", "log", "--format=%s", "main").stdout.splitlines()[0] == "Add alpha (S-002)"
    )


def test_check_fast_runs_no_end_to_end_test_and_no_example() -> None:
    """`make check-fast` is lint, types and the unit and smoke tests only (FOUNDATION §6)."""
    done = subprocess.run(
        ["make", "-n", "check-fast"], cwd=REPO, capture_output=True, text=True, check=True
    )
    tests = [line for line in done.stdout.splitlines() if "pytest" in line]
    assert len(tests) == 1 and "tests/smoke tests/unit " in tests[0], done.stdout
    assert "tests/e2e" not in done.stdout and "tests/golden" not in done.stdout
    assert "examples/" not in done.stdout.replace("ruff check src tests scripts examples", "")
    assert "--cov" not in tests[0] and '-m "not full"' in tests[0]


def test_cmd_new_records_started_and_fallback_to_author_date(repo: Path) -> None:
    task(repo, "new", "stamp1", "goal stamp1")
    folder1 = repo / ".worktrees" / "stamp1"
    started = run(repo, "git", "config", "branch.task/stamp1.started").stdout.strip()
    assert started.endswith("Z") and "T" in started
    (folder1 / "src" / "stamp1.py").write_text("X = 1\n")
    commit(folder1, "Commit 1")
    task(folder1, "land")
    msg1 = run(repo, "git", "log", "-1", "--format=%B", "main").stdout
    assert f"Task: stamp1\nTask-started: {started}\nTask-conflicts: 0" in msg1

    # Fallback when started config is absent: author date (UTC ISO) of the first task commit
    task(repo, "new", "stamp2", "goal stamp2")
    folder2 = repo / ".worktrees" / "stamp2"
    (folder2 / "src" / "stamp2.py").write_text("X = 2\n")
    commit(folder2, "Commit 2")
    run(repo, "git", "config", "--unset", "branch.task/stamp2.started")
    first_commit = run(folder2, "git", "rev-parse", "HEAD").stdout.strip()
    author_date = run(
        folder2,
        "env",
        "TZ=UTC",
        "git",
        "log",
        "-1",
        "--date=iso-strict-local",
        "--format=%ad",
        first_commit,
    ).stdout.strip()
    task(folder2, "land")
    msg2 = run(repo, "git", "log", "-1", "--format=%B", "main").stdout
    assert f"Task: stamp2\nTask-started: {author_date}\nTask-conflicts: 0" in msg2


def test_health_review_notice_threshold(repo: Path) -> None:
    task(repo, "new", "task1", "goal 1")
    (repo / ".worktrees" / "task1" / "src" / "t1.py").write_text("T = 1\n")
    commit(repo / ".worktrees" / "task1", "Work 1")
    # HEALTH_EVERY=2, so 1 task is below threshold: notice not printed
    out1 = run(repo / ".worktrees" / "task1", "env", "HEALTH_EVERY=2", "sh", str(TASK), "land")
    assert "A health review is due" not in out1.stdout

    task(repo, "new", "task2", "goal 2")
    (repo / ".worktrees" / "task2" / "src" / "t2.py").write_text("T = 2\n")
    commit(repo / ".worktrees" / "task2", "Work 2")
    # Now 2 tasks landed since docs/health/trend.csv: threshold reached
    out2 = run(repo / ".worktrees" / "task2", "env", "HEALTH_EVERY=2", "sh", str(TASK), "land")
    assert (
        "A health review is due: 2 tasks landed since the last one (docs/health/README.md)."
        in out2.stdout
    )

    # Touching docs/health/trend.csv resets the count
    (repo / "docs" / "health").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "health" / "trend.csv").write_text("rev,tasks\n")
    commit(repo, "Update trend.csv")

    task(repo, "new", "task3", "goal 3")
    (repo / ".worktrees" / "task3" / "src" / "t3.py").write_text("T = 3\n")
    commit(repo / ".worktrees" / "task3", "Work 3")
    # Only 1 task after trend.csv: below threshold again
    out3 = run(repo / ".worktrees" / "task3", "env", "HEALTH_EVERY=2", "sh", str(TASK), "land")
    assert "A health review is due" not in out3.stdout

    task(repo, "new", "task4", "goal 4")
    (repo / ".worktrees" / "task4" / "src" / "t4.py").write_text("T = 4\n")
    commit(repo / ".worktrees" / "task4", "Work 4")
    # 2 tasks after trend.csv: threshold reached
    out4 = run(repo / ".worktrees" / "task4", "env", "HEALTH_EVERY=2", "sh", str(TASK), "land")
    assert (
        "A health review is due: 2 tasks landed since the last one (docs/health/README.md)."
        in out4.stdout
    )


def test_land_refuses_undefined_decision_placeholder(repo: Path) -> None:
    """A task citing an undefined decision placeholder is refused and history is untouched."""
    task(repo, "new", "cite-undef-s", "cite undefined decision")
    folder = repo / ".worktrees" / "cite-undef-s"
    (folder / "src" / "alpha.py").write_text(f"# Uses {S1}\n")
    commit(folder, f"Use {S1}")
    before = run(folder, "git", "rev-parse", "HEAD").stdout.strip()
    done = task(folder, "land", ok=False)
    assert done.returncode != 0
    expected = (
        f"{S1} is cited but this task defines no {S1} entry in DECISIONS.md: "
        "cite the landed id of the entry you mean instead"
    )
    assert expected in done.stderr
    # History is untouched: task HEAD is unchanged and main did not move
    assert run(folder, "git", "rev-parse", "HEAD").stdout.strip() == before
    assert run(repo, "git", "log", "--format=%s", "main").stdout.splitlines() == ["Start"]


def test_land_refuses_undefined_backlog_placeholder(repo: Path) -> None:
    """A task citing an undefined backlog placeholder is refused and history is untouched."""
    task(repo, "new", "cite-undef-b", "cite undefined backlog item")
    folder = repo / ".worktrees" / "cite-undef-b"
    (folder / "src" / "alpha.py").write_text(f"# TODO({B1}): do something\n")
    commit(folder, f"Use {B1}")
    before = run(folder, "git", "rev-parse", "HEAD").stdout.strip()
    done = task(folder, "land", ok=False)
    assert done.returncode != 0
    expected = (
        f"{B1} is cited but this task defines no {B1} entry in BACKLOG.md: "
        "cite the landed id of the entry you mean instead"
    )
    assert expected in done.stderr
    # History is untouched: task HEAD is unchanged and main did not move
    assert run(folder, "git", "rev-parse", "HEAD").stdout.strip() == before
    assert run(repo, "git", "log", "--format=%s", "main").stdout.splitlines() == ["Start"]


def test_task_defining_and_citing_decision_lands_as_before(repo: Path) -> None:
    """A task defining and citing a decision placeholder lands as before."""
    task(repo, "new", "def-cite-s", "define and cite S")
    folder = repo / ".worktrees" / "def-cite-s"
    index = (
        f"| Gate 1 | Review gate 1 — outcome | recorded |\n| {S1} | custom decision | in force |\n"
    )
    text = (
        (folder / "DECISIONS.md")
        .read_text()
        .replace("| Gate 1 | Review gate 1 — outcome | recorded |\n", index)
    )
    entry = f"\n## {S1} — custom decision (2026-11-01)\nBody.\n"
    (folder / "DECISIONS.md").write_text(text + entry)
    (folder / "src" / "alpha.py").write_text(f"# Implements {S1}\n")
    commit(folder, f"Add custom ({S1})")
    done = task(folder, "land")
    assert "Landed 1 commit(s)" in done.stdout
    main_msg = run(repo, "git", "log", "-1", "--format=%B", "main").stdout
    assert "Add custom (S-002)" in main_msg
    assert "## S-002 — custom decision" in (repo / "DECISIONS.md").read_text()
    assert "# Implements S-002" in (repo / "src" / "alpha.py").read_text()


def test_task_defining_and_citing_backlog_lands_as_before(repo: Path) -> None:
    """A task defining and citing a backlog placeholder lands as before."""
    task(repo, "new", "def-cite-b", "define and cite B")
    folder = repo / ".worktrees" / "def-cite-b"
    backlog = (
        (folder / "BACKLOG.md")
        .read_text()
        .replace(
            "| B-0001 | First | S-001 |\n",
            f"| B-0001 | First | S-001 |\n| {B1} | custom item | S-001 |\n",
        )
    )
    (folder / "BACKLOG.md").write_text(backlog)
    (folder / "src" / "alpha.py").write_text(f"# TODO({B1}): finish item\n")
    commit(folder, f"Add item ({B1})")
    done = task(folder, "land")
    assert "Landed 1 commit(s)" in done.stdout
    main_msg = run(repo, "git", "log", "-1", "--format=%B", "main").stdout
    assert "Add item (B-0002)" in main_msg
    assert "| B-0002 | custom item | S-001 |" in (repo / "BACKLOG.md").read_text()
    assert "# TODO(B-0002): finish item" in (repo / "src" / "alpha.py").read_text()
