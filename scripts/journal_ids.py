"""Give a task's placeholder journal ids their real numbers at landing.

In a task branch, new decisions are written ``S-NEW<n>`` and new backlog rows ``B-NEW<n>``,
so two tasks never claim the same number. After the task is rebased onto ``main``, this
script replaces every placeholder with the next free id (the highest ``S-`` id in
DECISIONS.md or ``B-`` id in BACKLOG.md, plus one, in the placeholders' numeric order), in
every file the task changed, and commits the result as "Assign journal ids".

Run it from inside the task's folder: ``python3 scripts/journal_ids.py [--base main]``.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

PLACEHOLDER = re.compile(r"\b([SB])-NEW(\d+)(?!\d)")
REAL_ID = {"S": re.compile(r"\bS-(\d+)\b"), "B": re.compile(r"\bB-(\d+)\b")}
JOURNAL = {"S": "DECISIONS.md", "B": "BACKLOG.md"}
WIDTH = {"S": 3, "B": 4}


def git(*args: str, cwd: Path) -> str:
    """Run git in ``cwd`` and return its standard output; raise on failure."""
    done = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return done.stdout


def changed_text_files(root: Path, base: str) -> dict[Path, str]:
    """Return the text of every file the branch changed relative to ``base``."""
    names = git("diff", "--name-only", f"{base}...HEAD", cwd=root).splitlines()
    texts: dict[Path, str] = {}
    for name in names:
        path = root / name
        if not path.is_file():
            continue  # deleted by the task
        try:
            texts[path] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # binary
    return texts


def next_free(root: Path, prefix: str) -> int:
    """Return the next unused number for ``prefix`` from its journal (1 when it has none)."""
    journal = root / JOURNAL[prefix]
    if not journal.is_file():
        return 1
    found = [int(m) for m in REAL_ID[prefix].findall(journal.read_text(encoding="utf-8"))]
    return max(found, default=0) + 1


def assign(root: Path, texts: dict[Path, str]) -> dict[str, str]:
    """Map each placeholder found in ``texts`` to its real id."""
    found: dict[str, set[int]] = {"S": set(), "B": set()}
    for text in texts.values():
        for prefix, number in PLACEHOLDER.findall(text):
            found[prefix].add(int(number))
    mapping: dict[str, str] = {}
    for prefix, numbers in found.items():
        start = next_free(root, prefix)
        for offset, number in enumerate(sorted(numbers)):
            mapping[f"{prefix}-NEW{number}"] = f"{prefix}-{start + offset:0{WIDTH[prefix]}d}"
    return mapping


def main(argv: list[str] | None = None) -> int:
    """Rewrite the placeholders, commit, and print what became what."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="main", help="branch the task lands on")
    args = parser.parse_args(argv)
    root = Path(git("rev-parse", "--show-toplevel", cwd=Path.cwd()).strip())
    texts = changed_text_files(root, args.base)
    mapping = assign(root, texts)
    if not mapping:
        print("journal ids: no placeholders")
        return 0
    changed = []
    for path, text in texts.items():
        new = PLACEHOLDER.sub(lambda m: mapping[m.group(0)], text)
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed.append(str(path.relative_to(root)))
    git("add", "--", *changed, cwd=root)
    git("commit", "-q", "-m", "Assign journal ids", cwd=root)
    for old, new in mapping.items():
        print(f"journal ids: {old} -> {new}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
