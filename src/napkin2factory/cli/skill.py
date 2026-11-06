"""``n2f skill``: print the skill file, or write it where a client looks for skills (S-255).

The skill is a plain ``SKILL.md`` shipped inside the package. ``n2f init`` writes neither it
nor the MCP server's configuration (R14): the owner or the agent installs them on purpose.
"""

from __future__ import annotations

from pathlib import Path

import typer

from napkin2factory.cli.common import console

SKILL_NAME = "napkin2factory"
_SKILL_FILE = Path(__file__).resolve().parents[1] / "skill" / "SKILL.md"


def skill_text() -> str:
    """The text of the packaged ``SKILL.md``."""
    return _SKILL_FILE.read_text(encoding="utf-8")


def skill(
    write: Path | None = typer.Option(
        None,
        "--write",
        help="Skills folder to write into; makes <folder>/napkin2factory/SKILL.md.",
    ),
) -> None:
    """Print the napkin2factory skill, or write it into your client's skills folder."""
    text = skill_text()
    if write is None:
        typer.echo(text, nl=False)
        return
    target = write.expanduser() / SKILL_NAME / "SKILL.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    console.print(f"wrote {target}", highlight=False, soft_wrap=True)
