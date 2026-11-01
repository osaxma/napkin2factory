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
    """Index-table ids and entry-heading ids of DECISIONS.md."""
    text = (REPO / "DECISIONS.md").read_text(encoding="utf-8")
    index = text.partition("\n---\n")[0]
    headings = [line[3:] for line in text.splitlines() if line.startswith("## ")]
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
    assert all(re.fullmatch(r"B-\d{4}", i) for i in open_ids + closed_ids)


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
