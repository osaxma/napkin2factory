"""M5: the napkin protocol in the agent layer, checked without an LLM (NAPKIN_STAGE §5 M5).

The PM and design skills, the product ``CLAUDE.md``/``AGENTS.md`` and the scripted
simulation transcript are text; these tests pin what the protocol must say (the exact
commands, the honesty words, the no-edit rule), that the synced copies are byte-identical,
that the card the skill quotes is lint-clean, and that no git words reach the owner.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from napkin2factory.core.concepts import lint_concepts
from napkin2factory.templates import TEMPLATES_DIR
from tests.conftest import EXAMPLES, ROOT
from tests.unit.test_vocabulary import GIT_WORDS

COMMON = TEMPLATES_DIR / "_common"
PM = COMMON / ".claude" / "skills" / "n2f-pm" / "SKILL.md"
DESIGN = COMMON / ".claude" / "skills" / "n2f-design" / "SKILL.md"
CLAUDE = COMMON / "CLAUDE.md"
AGENTS = COMMON / "AGENTS.md"
TRANSCRIPT = ROOT / "tests" / "e2e" / "intake-transcripts" / "napkin-bench-kiln.md"
SYNCED_FILES = (
    ".claude/skills/n2f-pm/SKILL.md",
    ".claude/skills/n2f-design/SKILL.md",
    "CLAUDE.md",
    "AGENTS.md",
)


def _flat(text: str) -> str:
    """Collapse whitespace so a phrase wrapped across lines still matches."""
    return re.sub(r"\s+", " ", text)


def _section(text: str, heading: str) -> str:
    """The body of a ``## heading`` section, up to the next level-2 heading."""
    start = text.index(heading)
    nxt = text.find("\n## ", start + len(heading))
    return text[start : nxt if nxt != -1 else len(text)]


def test_pm_skill_has_the_napkin_stage_before_intake():
    text = PM.read_text(encoding="utf-8")
    napkin = text.index("## Napkin stage (before intake)")
    assert napkin < text.index("## Intake protocol (new product)")
    for kept in (  # every v0.1 section is still there
        "## Before anything",
        "## Question triage by consequence",
        "## Register adaptation",
        "## Safety floor (never adapted away)",
        "## Turning an ask into a change request",
        "## Explaining reports",
    ):
        assert kept in text, kept
    sec = _section(text, "## Napkin stage (before intake)")
    for heading in (
        "### When",
        "### Diverge first",
        "### Screen, then talk limitations from the data",
        "### Iterate cheaply",
        "### Interpretation cards",
        "### Promotion, in the owner's register",
        "### Safety floor at the napkin stage",
        "### Hand-over",
    ):
        assert heading in sec, heading


@pytest.mark.parametrize(
    "needle",
    [
        "n2f concept new",
        "--from C-00",
        "n2f concept build --all",
        "n2f concept board",
        "build/concepts/board.html",
        "styled-iso.png",
        "n2f concept show",
        "n2f concept lint",
        "n2f concept reject C-00x --reason",
        "n2f concept promote C-00",
        '--by "<owner name>"',
        "--override --reason",
        "concepts/refs/",
        "refs: [refs/",
        "stage: Napkin",
        "3 to 5 directions",
        "interpretation card",
        "[verify]",
        "computed",
        "estimate",
        "red card is information, not rejection",
        "Never hide a red card",
        "Limitations come only from `screening`",
        "Lock this in as the design direction? Changing the basic form later is a bigger "
        "change than tuning sizes.",
        "Images never become geometry",
        "Wait for the owner to correct it in words",
        "n2f-design",
        # review gate A / DoD 7 simulation fixes
        "**given** numbers are the owner's own inputs",
        "gets the same interpretation card as an image, in the same mini format",
        "become numbers only as `[verify]` values",
        "go in the card's `envelope` or `site`, not only in `notes`",
        "vary it across the directions",
        "is logged by you as its own `DEC-xxx` right after promotion",
        "set aside and kept on the record as alternatives",
        'Promotion saves a snapshot (it prints "snapshot saved")',
        "never say or imply that the owner rejected them",
        "state that consequence once and proceed; do not ask again",
        "is a trade-off they chose, not a problem with their idea",
        "a heat shield or a gap under the control box",
        "run `n2f status`, never a version-control command",
        "may already show Intake complete",
    ],
)
def test_pm_skill_napkin_section_says(needle: str):
    sec = _flat(_section(PM.read_text(encoding="utf-8"), "## Napkin stage (before intake)"))
    assert needle in sec, needle


def test_pm_skill_quotes_concept_verbs_that_exist():
    """Every ``n2f concept <verb>`` the skill quotes is a real verb of the CLI."""
    cli = (ROOT / "src" / "napkin2factory" / "cli" / "concept.py").read_text(encoding="utf-8")
    verbs = set(re.findall(r'@concept_app\.command\("(\w+)"\)', cli))
    assert {"new", "build", "board", "promote", "reject", "lint"} <= verbs
    for path in (PM, CLAUDE):
        quoted = set(re.findall(r"n2f concept (\w+)", path.read_text(encoding="utf-8")))
        assert quoted, f"{path.name} quotes no concept verbs"
        assert quoted <= verbs, quoted - verbs


def test_quoted_card_is_lint_clean(tmp_path: Path):
    """The card shape the PM skill and docs/napkin.md quote passes ``n2f concept lint``."""
    texts = [PM.read_text(encoding="utf-8"), (ROOT / "docs" / "napkin.md").read_text()]
    blocks = [re.search(r"```yaml\n(id: C-001\n.*?)```", t, re.S) for t in texts]
    assert all(blocks), "the card block is missing from the skill or docs/napkin.md"
    cards = {b.group(1) for b in blocks if b}
    assert len(cards) == 1, "the skill and docs/napkin.md quote different cards"
    card = cards.pop()
    (tmp_path / "concepts" / "refs").mkdir(parents=True)
    (tmp_path / "concepts" / "refs" / "sketch-01.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    (tmp_path / "concepts" / "C-001.yaml").write_text(card, encoding="utf-8")
    problems = lint_concepts(tmp_path)
    assert not problems.errors, [p.format() for p in problems.errors]
    assert not problems.warnings, [p.format() for p in problems.warnings]


@pytest.mark.parametrize(
    "needle",
    [
        "## After the napkin stage",
        "style.yaml",
        "role:",
        "rule://form-v0",
        "Never edit `concepts/` after promotion",
        "massing",
        "logged",
        "Form rows stay `needs your sign-off`",
    ],
)
def test_design_skill_after_the_napkin_stage(needle: str):
    assert needle in _flat(DESIGN.read_text(encoding="utf-8")), needle


def test_design_skill_no_edit_rule_names_the_status_fields():
    sec = _flat(_section(DESIGN.read_text(encoding="utf-8"), "## After the napkin stage"))
    assert "except the status fields" in sec
    assert "Never make a card an input to geometry" in sec


def test_product_claude_md_lists_concepts_style_and_napkin_verbs():
    text = CLAUDE.read_text(encoding="utf-8")
    assert text == AGENTS.read_text(encoding="utf-8"), "CLAUDE.md and AGENTS.md differ"
    where = _flat(_section(text, "## Where things are"))
    assert "`concepts/" in where and "style.yaml" in where and "concepts/refs/" in where
    roles = _flat(_section(text, "## Skills and roles"))
    for verb in ("new", "build --all", "board", "reject", "promote"):
        assert f"n2f concept {verb}" in roles, verb
    assert "interpretation card" in roles


@pytest.mark.parametrize("rel", SYNCED_FILES)
def test_synced_copies_are_byte_identical(rel: str):
    """``make templates`` would change nothing: every example carries the _common file."""
    src = (COMMON / rel).read_bytes()
    examples = sorted(p for p in EXAMPLES.iterdir() if p.is_dir())
    assert examples
    for ex in examples:
        assert (ex / rel).read_bytes() == src, f"examples/{ex.name}/{rel}: run `make templates`"
    for name in ("bracket", "enclosure"):
        copy = TEMPLATES_DIR / name / rel
        if copy.exists():
            assert copy.read_bytes() == src, f"templates/{name}/{rel}: run `make templates`"


OWNER_LINES = (
    "a small bench kiln for pottery glaze tests",
    "a box about as tall as it is wide, a bit deeper, door on the front hinged on the left, "
    "a slim control box hanging on the right side, four legs, rounded corners; the alcove "
    "is about 800 mm wide; 13 A plug in Saudi Arabia; budget around 1500 dollars",
    "the control box should be on top of the body, not the side, and the legs are shorter — "
    "the top of the kiln at about chest height",
    "which one fits my alcove?",
    "lock in the compact one",
)


def test_transcript_script_and_expected_outcome():
    text = TRANSCRIPT.read_text(encoding="utf-8")
    flat = _flat(text).lower()
    for line in OWNER_LINES:
        assert line.lower() in flat, line
    assert len(re.findall(r"\*\*Owner \(\d\):\*\*", text)) == 4
    for heading in ("## Owner's lines", "## Expected outcome", "## Transcript"):
        assert heading in text, heading
    expected = _flat(_section(text, "## Expected outcome"))
    for needle in (
        "interpretation card",
        "n2f concept lint",
        "n2f concept build --all",
        "red",
        "board.html",
        "Lock this in as the design direction?",
    ):
        assert needle in expected, needle
    assert expected.count("- [ ]") >= 6
    for needle in ("CLAUDE.md", "n2f-pm", "n2f init demo --template blank"):
        assert needle in text, needle


@pytest.mark.parametrize("path", [PM, DESIGN, CLAUDE, AGENTS, TRANSCRIPT])
def test_no_git_words(path: Path):
    text = path.read_text(encoding="utf-8").replace("never git words", "")
    hits = [m.group(0) for m in GIT_WORDS.finditer(text)]
    assert not hits, f"{path.relative_to(ROOT)}: {hits}"
