"""v0.4 DoD 5: the one-module simulation's protocol and its transcript (M6, P12).

The protocol (``tests/e2e/module-transcripts/README.md``) is text and always checked: the
scripted request, the four pass criteria, the fallback for a client without subagents, and
that the commands it quotes exist.  The transcript (``door-*.md``) is written by an agent that
runs the simulation; until one exists, its test skips with the reason, and once one exists it
runs with no edit: the request is the README's, verbatim, and the four results are ticked.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.conftest import ROOT

HERE = ROOT / "tests" / "e2e" / "module-transcripts"
README = HERE / "README.md"
BUNDLE_SCRIPT = ROOT / "scripts" / "module_sim_bundle.py"


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
        "cp -R examples/kiln <tmp>/kiln",
        "uv run python scripts/module_sim_bundle.py <tmp>/kiln asm://door",
        "--verify <tmp>/kiln examples/kiln asm://door",
        "n2f check --scope asm://door",
        "a new session with no history",
        "subagent",
        "Open only the files the context lists",
        "list every file you opened",
        "Do not sign off any requirement",
    ):
        assert needle in text, needle
    expected = _section(README.read_text(encoding="utf-8"), "### Expected outcome")
    assert expected.count("- [ ]") == 4
    assert BUNDLE_SCRIPT.is_file()


def test_the_scripted_request_stays_inside_the_door() -> None:
    request = _request(README.read_text(encoding="utf-8"), "### Request")
    assert "10 mm wider and 10 mm taller" in request
    # the sizes it moves are the door's own, and the joint it changes closes inside the door
    from napkin2factory.core.build_units import BuildUnits
    from napkin2factory.core.loader import load_product
    from tests.conftest import EXAMPLES

    kiln = load_product(EXAMPLES / "kiln")
    for slug in ("door-standoff-inset", "door-standoff-spacing-x", "door-standoff-spacing-z"):
        scope = kiln.parameters[slug].scope
        assert scope is not None and scope.id == "door", slug
        assert not kiln.parameters[slug].export, slug
    assert BuildUnits(kiln).closing()["door-guard-standoff"] == "door"
    assert "iface://door-guard-standoff" not in {str(u) for u in kiln.assemblies["door"].ports}


def _transcripts() -> list[Path]:
    return sorted(HERE.glob("door-*.md"))


@pytest.mark.parametrize("path", _transcripts() or [None], ids=lambda p: p.name if p else "none")
def test_transcript_records_the_run(path: Path | None) -> None:
    if path is None:
        pytest.skip(
            "no tests/e2e/module-transcripts/door-*.md yet: the DoD 5 simulation has not been "
            "run (README.md in that folder says how); this test runs once a transcript exists"
        )
    text = path.read_text(encoding="utf-8")
    for heading in ("## Setup", "## Request", "## Transcript", "## Results"):
        assert heading in text, heading
    assert _request(text, "## Request") == _request(
        README.read_text(encoding="utf-8"), "### Request"
    ), "the transcript's request is not the README's, verbatim"
    assert re.search(r"bundle: [\d,]+ bytes", _section(text, "## Setup")), "bundle size missing"
    assert _section(text, "## Transcript").strip(), "the transcript is empty"
    results = _section(text, "## Results")
    assert "- [ ]" not in results, "a result is not ticked: the run did not pass"
    lines = {ln[6:8]: _flat(ln) for ln in results.splitlines() if ln.startswith("- [x] ")}
    assert set(lines) >= {"a.", "b.", "c.", "d."}, lines
    assert "n2f check --scope asm://door" in lines["a."] and "no failure" in lines["a."]
    assert "n2f check" in lines["b."] and "no failure" in lines["b."]
    assert "every changed file is in the context" in lines["c."]
    assert "files opened" in lines["d."]
