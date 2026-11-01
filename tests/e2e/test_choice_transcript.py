"""v0.5 DoD 6 (the simulation): a choice raised after the first build (M7, S-132).

The protocol (``tests/e2e/intake-transcripts/choice-kiln.md``) is text and always checked: the
owner's six lines, the five pass criteria, the fallback for a client without subagents, the
rule it tests in the project manager's role, and that the choice it names is the kiln's (the
parts in the kiln, the option ids in the hardware rule).  The transcript
(``choice-kiln-*.md``) is written by an agent that runs the simulation; until one exists its
test skips with the reason, and once one exists it runs with no edit: the owner's lines are the
protocol's, verbatim, and every result is ticked.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from napkin2factory.templates import TEMPLATES_DIR
from tests.conftest import EXAMPLES, ROOT

HERE = ROOT / "tests" / "e2e" / "intake-transcripts"
PROTOCOL = HERE / "choice-kiln.md"
PM = TEMPLATES_DIR / "_common" / "roles" / "pm.md"
CHECK = "fastening://m6-standoff-25/m6x16-bolt"


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _section(text: str, heading: str) -> str:
    """The body of a heading's section, up to the next heading of the same or a higher level."""
    level = heading.split(" ", 1)[0]
    start = text.index(heading) + len(heading)
    nxt = re.search(rf"^#{{1,{len(level)}}} ", text[start:], re.MULTILINE)
    return text[start : start + nxt.start() if nxt else len(text)]


def _owner_lines(text: str) -> list[str]:
    """The owner's lines, ``**Owner (n):** …`` up to the next blank line, flattened."""
    body = _section(text, "## Owner's lines")
    return [_flat(m) for m in re.findall(r"\*\*Owner \(\d\):\*\* (.+?)(?:\n\n|\Z)", body, re.S)]


def test_protocol_says_how_to_run_it_with_any_client() -> None:
    text = _flat(PROTOCOL.read_text(encoding="utf-8"))
    for needle in (
        "cp -R examples/kiln <tmp>/kiln && rm -rf <tmp>/kiln/build",
        "n2f init .",
        "Do not build it",
        "a new session with no history",
        "subagent",
        "one at a time",
        "Do not sign off any requirement and do not release",
        f"n2f decide {CHECK} --pick shorter-bolts",
        "waiting_on_you",
    ):
        assert needle in text, needle
    expected = _section(PROTOCOL.read_text(encoding="utf-8"), "## Expected outcome")
    assert expected.count("- [ ]") == 5
    assert len(_owner_lines(PROTOCOL.read_text(encoding="utf-8"))) == 6


def test_the_rule_under_test_is_the_project_managers() -> None:
    """F13: the role says when to raise a choice, and how to record it."""
    sec = _flat(
        _section(PM.read_text(encoding="utf-8"), "## Choices: a check hands you a trade-off")
    )
    for needle in (
        "Never in the interview",
        "When the owner next touches that area",
        "or before the gate it holds",
        "One at a time, in the owner's words",
        "never show the check id",
        "n2f decide <check> --pick <option> --by",
        "A choice that holds a gate is always the owner's",
    ):
        assert needle in sec, needle


def test_the_choice_is_the_kilns() -> None:
    """The parts the check names are the kiln's, and the hardware rule offers both options."""
    parts = EXAMPLES / "kiln" / "model" / "parts"
    assert (parts / "m6-standoff-25.yaml").is_file() and (parts / "m6x16-bolt.yaml").is_file()
    rule = (ROOT / "src" / "napkin2factory" / "core" / "checks" / "hardware.py").read_text()
    assert '"shorter-bolts"' in rule and '"through-bolt"' in rule


def _transcripts() -> list[Path]:
    return sorted(HERE.glob("choice-kiln-*.md"))


@pytest.mark.parametrize("path", _transcripts() or [None], ids=lambda p: p.name if p else "none")
def test_transcript_records_the_run(path: Path | None) -> None:
    if path is None:
        pytest.skip(
            "no tests/e2e/intake-transcripts/choice-kiln-*.md yet: the DoD 6 simulation has not "
            "been run (choice-kiln.md beside it says how); this test runs once a transcript exists"
        )
    text = path.read_text(encoding="utf-8")
    for heading in ("## Setup", "## Owner's lines", "## Transcript", "## Results"):
        assert heading in text, heading
    assert "## Where the role fell short" in text
    assert _owner_lines(text) == _owner_lines(PROTOCOL.read_text(encoding="utf-8")), (
        "the transcript's owner lines are not the protocol's, verbatim"
    )
    assert _section(text, "## Transcript").strip(), "the transcript is empty"
    results = _section(text, "## Results")
    assert "- [ ]" not in results, "a result is not ticked: the run did not pass"
    lines = {ln[6:8]: _flat(ln) for ln in results.splitlines() if ln.startswith("- [x] ")}
    assert set(lines) >= {"a.", "b.", "c.", "d.", "e."}, lines
    assert "not in the interview" in lines["a."]
    assert "raised after the first build" in lines["b."]
    assert "not decided for the owner" in lines["c."]
    assert "recorded" in lines["d."] and "DEC-" in lines["d."]
    assert "decided afterwards" in lines["e."]
