"""The repo's agent instructions: one text for every agent, naming no model or vendor."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
# File and folder names (CLAUDE.md, .claude/) appear in records of how things used to be;
# they are paths, not a model the text assumes, so they are exempt.
MODEL_WORDS = re.compile(
    r"(?<!\.)\b(claude|opus|fable|sonnet|haiku|gpt|gemini|codex|anthropic|openai)\b(?!\.md\b)",
    re.IGNORECASE,
)


def test_agents_md_is_the_only_instructions_file():
    # One generic file for every client (S-076); a CLAUDE.md copy would drift.
    assert (REPO / "AGENTS.md").is_file() and not (REPO / "CLAUDE.md").exists()


@pytest.mark.parametrize(
    "name", ["AGENTS.md", "STATUS.md", "BACKLOG.md", "README.md", "docs/agent-guide.md"]
)
def test_instructions_name_no_model(name: str):
    text = (REPO / name).read_text(encoding="utf-8")
    hits = [
        f"{no}: {m.group(0)}"
        for no, line in enumerate(text.splitlines(), start=1)
        for m in MODEL_WORDS.finditer(line)
    ]
    assert not hits, f"{name} names a model or vendor: {hits}"


GUIDE_URL = "https://raw.githubusercontent.com/osaxma/napkin2factory/main/docs/agent-guide.md"


def test_readme_is_for_people() -> None:
    # The README is for owners who work through their agent; commands and setup live in the
    # agent guide (S-074). A hidden comment at the very top routes agents.
    text = (REPO / "README.md").read_text(encoding="utf-8")
    assert text.startswith("<!--")
    comment = text.split("-->", 1)[0]
    assert "docs/agent-guide.md" in comment and "AGENTS.md" in comment
    body = text.split("-->", 1)[1]
    assert "```bash" not in body and "```sh" not in body
    commands = re.compile(r"^\s*(?:n2f|uv|pip|make|git)\s", re.MULTILINE)
    assert not commands.findall(body), "the README shows commands; they belong in the guide"


def test_prompts_point_at_the_guide() -> None:
    assert (REPO / "docs/agent-guide.md").is_file()
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert readme.count(GUIDE_URL) >= 3  # the hidden comment and both prompts
    product = REPO / "src/napkin2factory/templates/_common/AGENTS.md"
    assert GUIDE_URL in product.read_text(encoding="utf-8")


def test_no_per_client_files() -> None:
    # Generic for any client, here and in what n2f init writes (S-076, S-077).
    common = REPO / "src/napkin2factory/templates/_common"
    for root in (REPO, common, *(p for p in (REPO / "examples").iterdir() if p.is_dir())):
        for name in ("CLAUDE.md", ".claude", "GEMINI.md", ".cursor", ".codex"):
            assert not (root / name).exists(), f"{root.relative_to(REPO)}/{name}"
