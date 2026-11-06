"""Trigger rates of the skill on the prompt set (road-to-v1.0 section 4.3, S-255).

A client decides whether to load a skill from its name and description alone, one user prompt
at a time. This script holds the two mechanical halves of measuring that:

  brief   write the brief for a judging model: the skill's name and description and the
          prompts, without the answers (``should_trigger`` and ``note`` stay out)
  rates   read the judgments (a mapping ``<prompt id>: yes|no``) and print the
          should-trigger rate and the should-not-trigger rate

The judging itself is done by a model of another vendor than the one that wrote the skill; the
decision entry records which. Judgments for an unlisted id, or a value other than yes or no,
are errors; a prompt without a judgment is named and left out of its rate.

    uv run python scripts/trigger_rates.py brief --out /private/tmp/brief.md
    uv run python scripts/trigger_rates.py rates judgments.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROMPTS = REPO_ROOT / "docs" / "reviews" / "prompt-set.yaml"
DEFAULT_SKILL = REPO_ROOT / "src" / "napkin2factory" / "skill" / "SKILL.md"


def load_skill(path: Path) -> tuple[str, str]:
    """The ``name`` and ``description`` in a skill file's front matter."""
    parts = path.read_text(encoding="utf-8").split("---\n", 2)
    if len(parts) < 3 or parts[0].strip():
        raise SystemExit(f"{path}: no front matter")
    front = yaml.safe_load(parts[1])
    return str(front["name"]), str(front["description"])


def load_prompts(path: Path) -> list[dict[str, Any]]:
    """The prompts of the set, each with ``id``, ``prompt`` and ``should_trigger``."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = data["prompts"]
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise SystemExit(f"{path}: a prompt id is used twice")
    for row in rows:
        if not isinstance(row.get("should_trigger"), bool) or not row.get("prompt"):
            raise SystemExit(f"{path}: {row.get('id')} needs a prompt and should_trigger")
    return rows


def make_brief(name: str, description: str, rows: list[dict[str, Any]]) -> str:
    """The brief for the judging model: the skill card and the bare prompts."""
    lines = [
        "<context>",
        "You act as an AI assistant client that holds a library of skills. For each skill you see",
        "only its name and description, never its body. When a user writes a message, you decide",
        "whether to load the skill before answering. You judge one message at a time, as if it",
        "were the only one you had seen; do not let one message change how you read another, and",
        "do not read any file in the workspace.",
        "",
        f"Skill name: {name}",
        f"Skill description: {description}",
        "</context>",
        "<task>For each user message below, decide if you would load this skill: yes or no.</task>",
        "<checklist>",
        "1. Judge every message listed below, each alone. Answer yes only if the skill's "
        "description fits what the user asks for.",
        "2. In your report, put the judgments in `findings` as a mapping from message id to "
        "the string yes or no, one entry per message, and nothing else in it.",
        "</checklist>",
        "<messages>",
    ]
    lines += [f"{r['id']}: {r['prompt']}" for r in rows]
    lines += [
        "</messages>",
        "<final_reminder>2 items; one yes or no for each of the "
        f"{len(rows)} ids; no file reading or writing.</final_reminder>",
    ]
    return "\n".join(lines) + "\n"


def compute(rows: list[dict[str, Any]], judgments: dict[str, str]) -> dict[str, Any]:
    """Counts of yes among the should-trigger and the should-not-trigger prompts."""
    known = {r["id"] for r in rows}
    stray = sorted(set(judgments) - known)
    if stray:
        raise SystemExit(f"judgments for ids not in the prompt set: {', '.join(stray)}")
    bad = {k: v for k, v in judgments.items() if v not in ("yes", "no")}
    if bad:
        raise SystemExit(f"judgments must be yes or no: {bad}")
    result: dict[str, Any] = {"missing": sorted(known - set(judgments))}
    for key, want in (("should_trigger", True), ("should_not_trigger", False)):
        judged = [r for r in rows if r["should_trigger"] is want and r["id"] in judgments]
        yes = [r["id"] for r in judged if judgments[r["id"]] == "yes"]
        no = [r["id"] for r in judged if judgments[r["id"]] == "no"]
        result[key] = {"prompts": len(judged), "yes": len(yes), "yes_ids": yes, "no_ids": no}
    return result


def _percent(part: int, whole: int) -> str:
    """``part`` of ``whole`` as a percentage, or ``n/a``."""
    return f"{100 * part / whole:.0f} %" if whole else "n/a"


def report(result: dict[str, Any]) -> str:
    """The two rates in words, with the ids that went the wrong way."""
    on, off = result["should_trigger"], result["should_not_trigger"]
    missed = on["no_ids"]
    lines = [
        f"should-trigger prompts loaded the skill:   {on['yes']}/{on['prompts']}"
        f" ({_percent(on['yes'], on['prompts'])})",
        f"should-not-trigger prompts loaded it:      {off['yes']}/{off['prompts']}"
        f" ({_percent(off['yes'], off['prompts'])})",
    ]
    if missed:
        lines.append(f"missed: {', '.join(missed)}")
    if off["yes_ids"]:
        lines.append(f"unwanted: {', '.join(off['yes_ids'])}")
    if result["missing"]:
        lines.append(f"no judgment for: {', '.join(result['missing'])}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Command line entry."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else "")
    sub = parser.add_subparsers(dest="verb", required=True)
    for verb in ("brief", "rates"):
        p = sub.add_parser(verb)
        p.add_argument("--prompts", type=Path, default=DEFAULT_PROMPTS)
        p.add_argument("--skill", type=Path, default=DEFAULT_SKILL)
        if verb == "brief":
            p.add_argument("--out", type=Path, required=True)
        else:
            p.add_argument("judgments", type=Path, help="YAML mapping of prompt id to yes or no")
    args = parser.parse_args(argv)
    rows = load_prompts(args.prompts)
    name, description = load_skill(args.skill)
    if args.verb == "brief":
        args.out.write_text(make_brief(name, description, rows), encoding="utf-8")
        print(f"wrote {args.out}")
        return 0
    judgments = yaml.safe_load(args.judgments.read_text(encoding="utf-8"))
    judgments = {
        str(k): ("yes" if v is True else "no" if v is False else str(v))
        for k, v in judgments.items()
    }
    result = compute(rows, judgments)
    print(f"skill: {name}")
    print(report(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
