"""The repo's agent instructions: one text for every agent, naming no model or vendor."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
# The file name CLAUDE.md (the copy of AGENTS.md) is not a model name, so it is exempt.
MODEL_WORDS = re.compile(
    r"\b(claude|opus|fable|sonnet|haiku|gpt|gemini|codex|anthropic|openai)\b(?!\.md\b)",
    re.IGNORECASE,
)


def test_agents_md_matches_claude_md():
    # Same convention as product repos (tests/e2e/test_init_validate.py).
    assert (REPO / "AGENTS.md").read_bytes() == (REPO / "CLAUDE.md").read_bytes()


@pytest.mark.parametrize("name", ["AGENTS.md", "STATUS.md", "BACKLOG.md"])
def test_instructions_name_no_model(name: str):
    text = (REPO / name).read_text(encoding="utf-8")
    hits = [
        f"{no}: {m.group(0)}"
        for no, line in enumerate(text.splitlines(), start=1)
        for m in MODEL_WORDS.finditer(line)
    ]
    assert not hits, f"{name} names a model or vendor: {hits}"
