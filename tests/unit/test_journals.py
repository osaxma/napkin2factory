"""The journals stay consistent when tasks land side by side.

DECISIONS.md and BACKLOG.md merge with `merge=union` (.gitattributes), which can duplicate a
line both sides touched; and a task writes placeholder ids that landing replaces
(scripts/journal_ids.py). These checks catch both.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections import Counter
from pathlib import Path

import pytest
from scripts.journal_ids import (
    apply_trailers,
    collect_placeholders,
    dedupe_backlog,
    is_defined,
    parse_trailer,
    undefined_placeholders,
)

REPO = Path(__file__).resolve().parents[2]
ROW_ID = re.compile(r"^\|\s*([^|]+?)\s*\|")
# Spelled so this file is not itself a placeholder: S-NEW<digits> or B-NEW<digits>.
PLACEHOLDER = re.compile(rb"\b[SB]-NEW\d+")


def table_ids(text: str) -> list[str]:
    """Ids in the first column of the Markdown table rows in ``text`` (header rows skipped)."""
    ids = [m.group(1) for line in text.splitlines() if (m := ROW_ID.match(line))]
    return [i for i in ids if i != "id" and not set(i) <= set("-: ")]


def heading_id(heading: str) -> str | None:
    """The index id a DECISIONS.md `## ` heading stands for (None for the index itself)."""
    if m := re.match(r"(S-\d+) — ", heading):
        return m.group(1)
    if m := re.match(r"Review gate (\S+) ", heading):
        return f"Gate {m.group(1)}"
    word = heading.split()[0]
    return None if word == "Index" else word


def decisions() -> tuple[list[str], list[str]]:
    """Index-table ids of DECISIONS.md and entry-heading ids of it and the archived versions."""
    text = (REPO / "DECISIONS.md").read_text(encoding="utf-8")
    index = text.partition("\n---\n")[0]
    archived = sorted((REPO / "docs" / "decisions").glob("v*.md"))  # closed versions (S-104)
    every = [text, *(f.read_text(encoding="utf-8") for f in archived)]
    headings = [line[3:] for t in every for line in t.splitlines() if line.startswith("## ")]
    entries = [i for h in headings if (i := heading_id(h))]
    return table_ids(index), entries


def test_decision_index_matches_entries() -> None:
    index, entries = decisions()
    assert [i for i, n in Counter(index).items() if n > 1] == [], "index rows repeated"
    assert [i for i, n in Counter(entries).items() if n > 1] == [], "entries repeated"
    assert sorted(set(index) - set(entries)) == [], "index rows without an entry"
    assert sorted(set(entries) - set(index)) == [], "entries without an index row"


def test_backlog_ids_unique() -> None:
    text = (REPO / "BACKLOG.md").read_text(encoding="utf-8")
    open_part, _, closed_part = text.partition("\n## Closed")
    open_ids, closed_ids = table_ids(open_part), table_ids(closed_part)
    assert [i for i, n in Counter(open_ids + closed_ids).items() if n > 1] == []
    # a task branch's new rows carry placeholders until landing numbers them (S-097)
    form = r"B-(\d{4}|NEW\d+)" if placeholders_allowed() else r"B-\d{4}"
    assert all(re.fullmatch(form, i) for i in open_ids + closed_ids)


def placeholders_allowed() -> bool:
    """A task branch holds placeholders until it lands; main never does.

    N2F_ALLOW_PLACEHOLDERS=1 allows them, =0 forbids them (the landing gate); unset, they are
    allowed on any named branch but main (a detached checkout, as in CI, is checked).
    """
    flag = os.environ.get("N2F_ALLOW_PLACEHOLDERS")
    if flag in ("0", "1"):
        return flag == "1"
    head = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO, capture_output=True, text=True
    )
    return head.returncode == 0 and head.stdout.strip() not in ("main", "HEAD")


def test_no_placeholder_ids_on_main() -> None:
    if placeholders_allowed():
        pytest.skip("a task branch holds placeholder ids until make land assigns them")
    files = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO, capture_output=True, check=True
    ).stdout.split(b"\0")
    hits = [
        f.decode()
        for f in files
        if f
        and (REPO / f.decode()).is_file()
        and PLACEHOLDER.search((REPO / f.decode()).read_bytes())
    ]
    assert hits == [], f"placeholder journal ids left (make land assigns them): {hits}"


def test_parse_trailer() -> None:
    assert parse_trailer("Task=foo") == ("Task", "foo")
    assert parse_trailer("Task-started=2026-11-03T20:15:00Z") == (
        "Task-started",
        "2026-11-03T20:15:00Z",
    )
    assert parse_trailer("Task-conflicts=0") == ("Task-conflicts", "0")
    assert parse_trailer("Task: foo") == ("Task", "foo")
    with pytest.raises(ValueError, match="invalid trailer format"):
        parse_trailer("invalid_trailer_arg")


def test_apply_trailers() -> None:
    trailers = [
        ("Task", "my-slug"),
        ("Task-started", "2026-11-03T20:15:00Z"),
        ("Task-conflicts", "0"),
    ]
    # Single-line message
    res1 = apply_trailers("Subject line", trailers)
    assert (
        res1
        == "Subject line\n\nTask: my-slug\nTask-started: 2026-11-03T20:15:00Z\nTask-conflicts: 0\n"
    )

    # Multi-line message with body
    res2 = apply_trailers("Subject line\n\nBody paragraph.", trailers)
    expected_body = (
        "Subject line\n\n"
        "Body paragraph.\n\n"
        "Task: my-slug\n"
        "Task-started: 2026-11-03T20:15:00Z\n"
        "Task-conflicts: 0\n"
    )
    assert res2 == expected_body

    # Message with existing trailers: replaces matching keys in place, keeps others
    msg_with_trailers = (
        "Subject\n\n"
        "Signed-off-by: Author <a@example.com>\n"
        "Task: old-slug\n"
        "Task-started: 2026-11-01T00:00:00Z\n"
    )
    res3 = apply_trailers(msg_with_trailers, trailers)
    expected = (
        "Subject\n\n"
        "Signed-off-by: Author <a@example.com>\n"
        "Task: my-slug\n"
        "Task-started: 2026-11-03T20:15:00Z\n"
        "Task-conflicts: 0\n"
    )
    assert res3 == expected

    # Retry replaces values without duplicating
    res4 = apply_trailers(
        res3,
        [
            ("Task", "my-slug"),
            ("Task-started", "2026-11-03T20:15:00Z"),
            ("Task-conflicts", "1"),
        ],
    )
    expected_retry = (
        "Subject\n\n"
        "Signed-off-by: Author <a@example.com>\n"
        "Task: my-slug\n"
        "Task-started: 2026-11-03T20:15:00Z\n"
        "Task-conflicts: 1\n"
    )
    assert res4 == expected_retry


def test_journal_ids_stamps_trailers_without_placeholders(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    (repo / "file.txt").write_text("initial\n")
    subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "Initial commit"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "task/work"], cwd=repo, check=True)
    (repo / "file.txt").write_text("updated\n")
    subprocess.run(["git", "commit", "-q", "-am", "Task work"], cwd=repo, check=True)

    script = REPO / "scripts" / "journal_ids.py"
    cmd = [
        "python3",
        str(script),
        "--base",
        "main",
        "--trailer",
        "Task=work",
        "--trailer",
        "Task-started=2026-11-03T20:15:00Z",
        "--trailer",
        "Task-conflicts=0",
    ]
    done = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, check=True)
    assert done.returncode == 0
    msg = subprocess.run(
        ["git", "log", "-1", "--format=%B", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "Task: work" in msg
    assert "Task-started: 2026-11-03T20:15:00Z" in msg
    assert "Task-conflicts: 0" in msg

    # Second pass with updated trailer replaces it
    cmd_retry = [
        "python3",
        str(script),
        "--base",
        "main",
        "--trailer",
        "Task=work",
        "--trailer",
        "Task-started=2026-11-03T20:15:00Z",
        "--trailer",
        "Task-conflicts=1",
    ]
    done_retry = subprocess.run(cmd_retry, cwd=repo, capture_output=True, text=True, check=True)
    assert done_retry.returncode == 0
    msg_retry = subprocess.run(
        ["git", "log", "-1", "--format=%B", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert msg_retry.count("Task: work") == 1
    assert msg_retry.count("Task-conflicts:") == 1
    assert "Task-conflicts: 1" in msg_retry


def test_collect_placeholders() -> None:
    new = "-NEW"
    s1, s2, b1 = f"S{new}1", f"S{new}2", f"B{new}1"
    texts = {
        Path("a.py"): f"cite {s2} and {s1}",
        Path("b.py"): f"cite {b1} and {s1}",
    }
    assert collect_placeholders(texts) == [s1, s2, b1]


def test_is_defined_decision(tmp_path: Path) -> None:
    new = "-NEW"
    s1, s2, s3, s10 = f"S{new}1", f"S{new}2", f"S{new}3", f"S{new}10"
    (tmp_path / "DECISIONS.md").write_text(
        f"| id | decision |\n|---|---|\n| {s1} | First |\n\n## {s2} — Second\n"
    )
    # s1 defined by index row
    assert is_defined(tmp_path, s1)
    # s2 defined by heading
    assert is_defined(tmp_path, s2)
    # s3 not defined
    assert not is_defined(tmp_path, s3)
    # s10 not defined (s1 index row must not match s10)
    assert not is_defined(tmp_path, s10)


def test_is_defined_backlog(tmp_path: Path) -> None:
    new = "-NEW"
    b1, b2, b10 = f"B{new}1", f"B{new}2", f"B{new}10"
    (tmp_path / "BACKLOG.md").write_text(
        f"| id | item | origin |\n|---|---|---|\n"
        f"| {b1} | First | S-001 |\n| B-0001 | Other | {b2} |\n"
    )
    # the backlog placeholder is defined by a row that starts with it
    assert is_defined(tmp_path, b1)
    # b2 cited in column 3 (origin) is not defined by this task
    assert not is_defined(tmp_path, b2)
    # b10 not defined (b1 row must not match b10)
    assert not is_defined(tmp_path, b10)


def test_undefined_placeholders(tmp_path: Path) -> None:
    new = "-NEW"
    s1, s2, b1 = f"S{new}1", f"S{new}2", f"B{new}1"
    (tmp_path / "DECISIONS.md").write_text(f"## {s1} — Title\n")
    (tmp_path / "BACKLOG.md").write_text(f"| {b1} | Item |\n")
    assert undefined_placeholders(tmp_path, [s1, s2, b1]) == [s2]


def test_journal_ids_refuses_undefined_placeholder_cli(tmp_path: Path) -> None:
    new = "-NEW"
    s1 = f"S{new}1"
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    (repo / "DECISIONS.md").write_text("# Decisions\n")
    (repo / "file.txt").write_text("initial\n")
    subprocess.run(["git", "add", "DECISIONS.md", "file.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "Initial commit"], cwd=repo, check=True)

    subprocess.run(["git", "checkout", "-q", "-b", "task/work"], cwd=repo, check=True)
    (repo / "file.txt").write_text(f"updated citing {s1}\n")
    subprocess.run(["git", "commit", "-q", "-am", f"Task work citing {s1}"], cwd=repo, check=True)
    head_before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()

    script = REPO / "scripts" / "journal_ids.py"
    done = subprocess.run(
        ["python3", str(script), "--base", "main"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert done.returncode == 1
    expected_msg = (
        f"{s1} is cited but this task defines no {s1} entry in DECISIONS.md: "
        "cite the landed id of the entry you mean instead"
    )
    assert expected_msg in done.stderr
    head_after = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert head_before == head_after


def test_dedupe_backlog_removes_open_copy_when_in_both_tables() -> None:
    text = (
        "# Backlog\n\n"
        "## Open\n\n"
        "| id | item | origin |\n"
        "|---|---|---|\n"
        "| B-0001 | Open item 1 | S-001 |\n"
        "| B-0002 | Resolved item | S-002 |\n"
        "| B-0003 | Open item 3 | S-003 |\n\n"
        "## Closed\n\n"
        "| id | item | closed by |\n"
        "|---|---|---|\n"
        "| B-0002 | Resolved item | closed by S-004 |\n"
        "| B-0004 | Closed item 4 | closed by S-001 |\n"
    )
    result = dedupe_backlog(text)
    expected = (
        "# Backlog\n\n"
        "## Open\n\n"
        "| id | item | origin |\n"
        "|---|---|---|\n"
        "| B-0001 | Open item 1 | S-001 |\n"
        "| B-0003 | Open item 3 | S-003 |\n\n"
        "## Closed\n\n"
        "| id | item | closed by |\n"
        "|---|---|---|\n"
        "| B-0002 | Resolved item | closed by S-004 |\n"
        "| B-0004 | Closed item 4 | closed by S-001 |\n"
    )
    assert result == expected
    open_p, _, closed_p = result.partition("\n## Closed")
    ids = table_ids(open_p) + table_ids(closed_p)
    assert [i for i, n in Counter(ids).items() if n > 1] == []


def test_dedupe_backlog_leaves_duplicate_inside_open_untouched() -> None:
    text = (
        "# Backlog\n\n"
        "## Open\n\n"
        "| id | item | origin |\n"
        "|---|---|---|\n"
        "| B-0001 | Open item 1 | S-001 |\n"
        "| B-0001 | Duplicate item 1 | S-002 |\n"
        "| B-0002 | Open item 2 | S-003 |\n\n"
        "## Closed\n\n"
        "| id | item | closed by |\n"
        "|---|---|---|\n"
        "| B-0003 | Closed item 3 | closed by S-004 |\n"
    )
    result = dedupe_backlog(text)
    assert result == text
    open_p, _, closed_p = result.partition("\n## Closed")
    ids = table_ids(open_p) + table_ids(closed_p)
    assert [i for i, n in Counter(ids).items() if n > 1] == ["B-0001"]


def test_journal_ids_dedupes_backlog_cli(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    backlog_main = (
        "# Backlog\n\n"
        "## Open\n\n"
        "| id | item | origin |\n"
        "|---|---|---|\n"
        "| B-0001 | Item 1 | S-001 |\n"
        "| B-0002 | Item 2 | S-002 |\n\n"
        "## Closed\n\n"
        "| id | item | closed by |\n"
        "|---|---|---|\n"
    )
    (repo / "BACKLOG.md").write_text(backlog_main)
    subprocess.run(["git", "add", "BACKLOG.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "Initial backlog"], cwd=repo, check=True)

    subprocess.run(["git", "checkout", "-q", "-b", "task/work"], cwd=repo, check=True)
    backlog_task = (
        "# Backlog\n\n"
        "## Open\n\n"
        "| id | item | origin |\n"
        "|---|---|---|\n"
        "| B-0001 | Item 1 | S-001 |\n"
        "| B-0002 | Item 2 | S-002 |\n\n"
        "## Closed\n\n"
        "| id | item | closed by |\n"
        "|---|---|---|\n"
        "| B-0002 | Item 2 | closed by S-003 |\n"
    )
    (repo / "BACKLOG.md").write_text(backlog_task)
    subprocess.run(["git", "commit", "-q", "-am", "Close B-0002"], cwd=repo, check=True)

    script = REPO / "scripts" / "journal_ids.py"
    done = subprocess.run(
        ["python3", str(script), "--base", "main"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    assert done.returncode == 0
    content = (repo / "BACKLOG.md").read_text()
    open_p, _, closed_p = content.partition("\n## Closed")
    assert "B-0002" not in open_p
    assert "B-0002" in closed_p
    assert "B-0001" in open_p
    committed = subprocess.run(
        ["git", "show", "HEAD:BACKLOG.md"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert committed == content
