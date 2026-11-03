"""Unit tests for scripts/health.py."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from scripts import health

REPO = Path(__file__).resolve().parents[2]


def _init_git_repo(path: Path) -> None:
    """Initialize a git repo with standard identity in path."""
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    # Initial commit so HEAD exists
    base = path / "base.txt"
    base.write_text("initial\n", encoding="utf-8")
    subprocess.run(["git", "add", "base.txt"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=path, check=True)


def _commit_stamped(
    repo: Path,
    rel_path: str,
    content: str,
    slug: str,
    started_iso: str,
    commit_iso: str,
    conflicts: int = 0,
) -> str:
    file_path = repo / rel_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", rel_path], cwd=repo, check=True)
    msg = (
        f"Commit for {slug}\n\n"
        f"Task: {slug}\n"
        f"Task-started: {started_iso}\n"
        f"Task-conflicts: {conflicts}\n"
    )
    env = {
        "GIT_AUTHOR_NAME": "Test User",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_AUTHOR_DATE": commit_iso,
        "GIT_COMMITTER_NAME": "Test User",
        "GIT_COMMITTER_EMAIL": "test@example.com",
        "GIT_COMMITTER_DATE": commit_iso,
    }
    subprocess.run(["git", "commit", "-m", msg], cwd=repo, check=True, env=env)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def test_collision_overlapping_tasks_sharing_file(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)

    # Task A: active 10:00 to 10:30, touches src/widget.py
    sha_a = _commit_stamped(
        repo,
        rel_path="src/widget.py",
        content="widget v1\n",
        slug="task-alpha",
        started_iso="2026-11-03T10:00:00Z",
        commit_iso="2026-11-03T10:30:00Z",
        conflicts=0,
    )

    # Task B: active 10:15 to 10:45, touches src/widget.py (overlaps in time with A)
    sha_b = _commit_stamped(
        repo,
        rel_path="src/widget.py",
        content="widget v2\n",
        slug="task-beta",
        started_iso="2026-11-03T10:15:00Z",
        commit_iso="2026-11-03T10:45:00Z",
        conflicts=2,
    )

    res = health.measure_collisions(repo, [sha_a, sha_b])
    assert res.collisions == 1
    assert len(res.pairs) == 1
    pair = res.pairs[0]
    assert pair["tasks"] == ["task-alpha", "task-beta"]
    assert pair["shared_files"] == ["src/widget.py"]
    assert res.task_conflicts == 2
    assert res.unstamped_commits == 0


def test_collision_sharing_only_decisions_not_detected(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)

    # Task A touches DECISIONS.md
    sha_a = _commit_stamped(
        repo,
        rel_path="DECISIONS.md",
        content="Decision A\n",
        slug="task-alpha",
        started_iso="2026-11-03T10:00:00Z",
        commit_iso="2026-11-03T10:30:00Z",
    )

    # Task B touches DECISIONS.md (overlapping time)
    sha_b = _commit_stamped(
        repo,
        rel_path="DECISIONS.md",
        content="Decision B\n",
        slug="task-beta",
        started_iso="2026-11-03T10:15:00Z",
        commit_iso="2026-11-03T10:45:00Z",
    )

    res = health.measure_collisions(repo, [sha_a, sha_b])
    assert res.collisions == 0
    assert res.pairs == []


def test_collision_non_overlapping_in_time_not_detected(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)

    # Task A: 10:00 to 10:30
    sha_a = _commit_stamped(
        repo,
        rel_path="src/widget.py",
        content="widget v1\n",
        slug="task-alpha",
        started_iso="2026-11-03T10:00:00Z",
        commit_iso="2026-11-03T10:30:00Z",
    )

    # Task B: 11:00 to 11:30 (starts after Task A finished)
    sha_b = _commit_stamped(
        repo,
        rel_path="src/widget.py",
        content="widget v2\n",
        slug="task-beta",
        started_iso="2026-11-03T11:00:00Z",
        commit_iso="2026-11-03T11:30:00Z",
    )

    res = health.measure_collisions(repo, [sha_a, sha_b])
    assert res.collisions == 0
    assert res.pairs == []


def test_trailer_parsing_formats():
    multi_line = "Subject\n\nTask: my-task\nTask-started: 2026-11-03T12:00:00Z\nTask-conflicts: 3\n"
    p1 = health.parse_task_trailers(multi_line)
    assert p1 is not None
    assert p1["task"] == "my-task"
    assert p1["task_conflicts"] == 3

    single_line = (
        "Subject\n\nTask: my-task / Task-started: 2026-11-03T12:00:00Z / Task-conflicts: 1"
    )
    p2 = health.parse_task_trailers(single_line)
    assert p2 is not None
    assert p2["task"] == "my-task"
    assert p2["task_conflicts"] == 1

    unstamped = "Plain commit with no trailers\n"
    assert health.parse_task_trailers(unstamped) is None


def test_long_module_measure(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    short_file = src / "short.py"
    short_file.write_text("x = 1\n" * 100, encoding="utf-8")
    long_file = src / "long.py"
    long_file.write_text("y = 1\n" * 600, encoding="utf-8")

    count, files = health.measure_long_modules(tmp_path, threshold=550)
    assert count == 1
    assert len(files) == 1
    assert files[0]["path"] == "src/long.py"
    assert files[0]["lines"] == 600


def test_layer_imports_measure(tmp_path: Path):
    core = tmp_path / "core"
    core.mkdir()
    (core / "clean.py").write_text("import math\n", encoding="utf-8")
    (core / "seam.py").write_text(
        "from napkin2factory.domains import INSTALLED\n", encoding="utf-8"
    )
    (core / "violator.py").write_text(
        "import napkin2factory.domains.electrical\n", encoding="utf-8"
    )

    domains = tmp_path / "domains"
    elec = domains / "electrical"
    elec.mkdir(parents=True)
    (elec / "clean.py").write_text(
        "from napkin2factory.domains.electrical import clean\n", encoding="utf-8"
    )

    mech = domains / "mechanical"
    mech.mkdir(parents=True)
    (mech / "violator.py").write_text(
        "from napkin2factory.domains.electrical import clean\n", encoding="utf-8"
    )

    res = health.measure_layer_imports(tmp_path)
    # The package root import of INSTALLED in seam.py is allowed (DECISIONS E10)
    assert len(res.core_to_domains) == 1
    assert "core/violator.py:1" in res.core_to_domains[0]
    assert len(res.cross_domain) == 1
    assert "domains/mechanical/violator.py:1" in res.cross_domain[0]


def test_registry_installed_seam_allowed(tmp_path: Path):
    core = tmp_path / "core"
    core.mkdir()
    (core / "registry.py").write_text(
        "def ensure():\n    from napkin2factory.domains import INSTALLED\n",
        encoding="utf-8",
    )
    (core / "bad.py").write_text(
        "from napkin2factory.domains.electrical import foo\n",
        encoding="utf-8",
    )
    domains = tmp_path / "domains"
    (domains / "electrical").mkdir(parents=True)

    res = health.measure_layer_imports(tmp_path)
    assert len(res.core_to_domains) == 1
    assert "core/bad.py:1" in res.core_to_domains[0]
    assert not any("registry.py" in loc for loc in res.core_to_domains)


def test_real_repo_layer_imports_clean():
    res = health.measure_layer_imports(REPO)
    assert res.core_to_domains == []
    assert res.cross_domain == []


def test_open_backlog_measure(tmp_path: Path):
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(
        "# Backlog\n\n"
        "## Open\n\n"
        "| id | item | reason |\n"
        "|---|---|---|\n"
        "| B-0001 | Item 1 | Reason 1 |\n"
        "| B-0002 | Item 2 | Reason 2 |\n\n"
        "## Closed\n\n"
        "| id | item | reason |\n"
        "|---|---|---|\n"
        "| B-0003 | Item 3 | Reason 3 |\n",
        encoding="utf-8",
    )
    assert health.measure_open_backlog(tmp_path) == 2


def test_main_json_valid(capsys: pytest.CaptureFixture[str]):
    ret = health.main(["--json"])
    assert ret == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "date" in data
    assert "sha" in data
    assert "measures" in data
    measures = data["measures"]
    assert "long_modules" in measures
    assert "collisions" in measures
    assert "e10_seam_commits" in measures
    assert "layer_imports" in measures
    assert "todo_fixme_lines" in measures
    assert "verify_rows" in measures
    assert "tests" in measures
    assert "coverage" in measures
    assert "open_backlog" in measures


def test_main_plain_table(capsys: pytest.CaptureFixture[str]):
    ret = health.main([])
    assert ret == 0
    out = capsys.readouterr().out
    assert "Measure" in out
    assert "Value" in out
    assert "Modules over 550 lines" in out
