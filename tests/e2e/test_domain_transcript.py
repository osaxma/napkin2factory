"""v0.5 DoD 2 (second half): the gadget simulation's protocol and its transcript (M7, S-132).

The protocol (``tests/e2e/domain-transcripts/README.md``) is text and always checked: the
scripted request names one of every registry, the count is the one DoD 2 asks for, the agent is
handed the contract alone with the fallback for a client without subagents, and every registry
the request names is a field of the contract.  The transcript (``gadget-*.md``) is written by an
agent that runs the simulation; until one exists its test skips with the reason, and once one
exists it runs with no edit: the request is the README's, verbatim, every result is ticked and
the count is zero.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest

from napkin2factory.core.domain import Domain
from tests.conftest import ROOT

HERE = ROOT / "tests" / "e2e" / "domain-transcripts"
README = HERE / "README.md"
CONTRACT = ROOT / "docs" / "domains.md"

#: The request's items and the ``Domain`` field each one fills (docs/domains.md §3).
ITEMS = {
    "a tiny model family": "families",
    "one rule family": "rule_families",
    "one verify kind": "verify_kinds",
    "one check stage": "check_stages",
    "one gate row": "gate_rows",
    "one report section": "report_sections",
    "one doc helper": "doc_helpers",
    "one vocabulary word": "vocabulary",
    "one interface kind": "interface_kinds",
    "one process": "processes",
    "one screen": "screens",
}


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _section(text: str, heading: str) -> str:
    """The body of a heading's section, up to the next heading of the same or a higher level."""
    level = heading.split(" ", 1)[0]
    start = text.index(heading) + len(heading)
    nxt = re.search(rf"^#{{1,{len(level)}}} ", text[start:], re.MULTILINE)
    return text[start : start + nxt.start() if nxt else len(text)]


def _request(text: str, heading: str) -> str:
    """The quoted request (``> …`` lines) under ``heading``."""
    quoted = [ln[1:].strip() for ln in _section(text, heading).splitlines() if ln.startswith(">")]
    return _flat(" ".join(quoted))


def test_protocol_says_how_to_run_it_with_any_client() -> None:
    text = _flat(README.read_text(encoding="utf-8"))
    for needle in (
        "git worktree add --detach <tmp>/n2f-domain main",
        "git rev-parse HEAD",
        "Do not open any file under src/napkin2factory/core/",
        "Do not change any file under src/napkin2factory/core/",
        "list every file you opened",
        "git diff --name-only <base> -- src/napkin2factory/core/ | wc -l",
        "git status --porcelain --untracked-files=all -- src/napkin2factory/core/ | wc -l",
        "a new session with no history",
        "subagent",
        "<the contract's text>",
        "uv run pytest tests/unit/test_gadget_domain.py",
    ):
        assert needle in text, needle
    expected = _section(README.read_text(encoding="utf-8"), "### Expected outcome")
    assert expected.count("- [ ]") == 5
    assert CONTRACT.is_file()


def test_the_request_names_one_of_every_registry() -> None:
    request = _request(README.read_text(encoding="utf-8"), "### Request")
    assert "named `gadget`" in request and "installed for a test" in request
    fields = {f.name for f in dataclasses.fields(Domain)}
    for item, field in ITEMS.items():
        assert item in request, item
        assert field in fields, field  # each item is a registry the contract offers


def test_the_contract_carries_what_the_agent_needs() -> None:
    """The page the agent gets alone: install, test registration, the test to copy, the count."""
    text = _flat(CONTRACT.read_text(encoding="utf-8"))
    for needle in (
        "INSTALLED",
        "with installed(",
        "Load the product inside the block",
        "Run the CLI in-process",
        "Names are unique across domains",
        "tests/unit/test_domain_contract.py",
        "test_every_registry_sees_the_toy",
        "git diff --name-only <base> -- src/napkin2factory/core/",
        "## 9. Not registrable in v0.5",
    ):
        assert needle in text, needle
    for heading in (
        "### 3.1 Model families",
        "### 3.2 Build rule families",
        "### 3.3 Verify kinds",
        "### 3.4 Check stages",
        "### 3.5 Gate rows",
        "### 3.6 Report sections",
        "### 3.7 Doc helpers",
        "### 3.8 Vocabulary",
        "### 3.9 Interface kinds",
        "### 3.10 Open sets",
        "### 3.11 Screens",
    ):
        assert heading in text, heading


def _transcripts() -> list[Path]:
    return sorted(HERE.glob("gadget-*.md"))


@pytest.mark.parametrize("path", _transcripts() or [None], ids=lambda p: p.name if p else "none")
def test_transcript_records_the_run(path: Path | None) -> None:
    if path is None:
        pytest.skip(
            "no tests/e2e/domain-transcripts/gadget-*.md yet: the DoD 2 simulation has not been "
            "run (README.md in that folder says how); this test runs once a transcript exists"
        )
    text = path.read_text(encoding="utf-8")
    for heading in ("## Setup", "## Request", "## Transcript", "## Results"):
        assert heading in text, heading
    assert "## Where the contract fell short" in text
    assert _request(text, "## Request") == _request(
        README.read_text(encoding="utf-8"), "### Request"
    ), "the transcript's request is not the README's, verbatim"
    setup = _section(text, "## Setup")
    assert re.search(r"base: [0-9a-f]{7,40}", setup), "the base commit is missing"
    assert re.search(r"contract: [\d,]+ bytes", setup), "the contract's size is missing"
    assert _section(text, "## Transcript").strip(), "the transcript is empty"
    results = _section(text, "## Results")
    assert "- [ ]" not in results, "a result is not ticked: the run did not pass"
    lines = {ln[6:8]: _flat(ln) for ln in results.splitlines() if ln.startswith("- [x] ")}
    assert set(lines) >= {"a.", "b.", "c.", "d.", "e."}, lines
    assert "passes" in lines["a."] and "still passes" in lines["b."]
    assert "core files changed: 0" in lines["c."]
    assert "core files opened: none" in lines["d."]
    assert "every registry asserted" in lines["e."]
