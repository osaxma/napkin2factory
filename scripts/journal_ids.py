"""Give a task's placeholder journal ids their real numbers at landing.

In a task branch, new decisions are written ``S-NEW<n>`` and new backlog rows ``B-NEW<n>``,
so two tasks never claim the same number. After the task is rebased onto ``main``, this
script replaces every placeholder with the next free id (the highest ``S-`` id in
DECISIONS.md or ``B-`` id in BACKLOG.md, plus one, in the placeholders' numeric order), in
every commit of the task: the files each commit holds and its message. History is rewritten
commit by commit from the snapshots (no patches are replayed, so nothing can conflict), so no
placeholder ever reaches ``main`` and every landed commit passes the journal check on its own
(``git bisect`` relies on that).

Every placeholder the task cites must be defined at the task tip (an index row starting
``| S-NEW<n> |`` or a heading ``## S-NEW<n>`` in DECISIONS.md; a row starting ``| B-NEW<n> |``
in BACKLOG.md); citing an undefined placeholder stops landing before history is rewritten.

When ``--trailer KEY=VALUE`` is given, every task commit's message gets those trailers
(replacing an existing trailer of the same key, never duplicating), rewriting history even
when there are no placeholders.

Why: S-097 (placeholders), S-099 (every commit, messages included), S-190 (trailers),
S-195 (refuse cited but undefined placeholders).

Run it from inside the task's folder:
``python3 scripts/journal_ids.py [--base main] [--trailer KEY=VALUE ...]``.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

PLACEHOLDER = re.compile(r"\b([SB])-NEW(\d+)(?!\d)")
REAL_ID = {"S": re.compile(r"\bS-(\d+)\b"), "B": re.compile(r"\bB-(\d+)\b")}
JOURNAL = {"S": "DECISIONS.md", "B": "BACKLOG.md"}
WIDTH = {"S": 3, "B": 4}


def parse_trailer(arg: str) -> tuple[str, str]:
    """Parse a trailer argument in KEY=VALUE or KEY: VALUE format."""
    sep = "=" if "=" in arg else ":"
    key, found, value = arg.partition(sep)
    if not found or not key.strip():
        raise ValueError(f"invalid trailer format {arg!r}, expected KEY=VALUE")
    return key.strip(), value.strip()


def apply_trailers(
    message: str,
    trailers: list[tuple[str, str]],
    root: Path | None = None,
    env: dict[str, str] | None = None,
) -> str:
    """Stamp ``trailers`` on ``message`` using ``git interpret-trailers``.

    Why: S-190 (trailers via git interpret-trailers).
    """
    if not trailers:
        return message
    # Git same_token() prefix-matches tokens; protect Task from colliding with Task-* (S-190).
    protected_msg = re.sub(r"(?m)^Task:", "Task-name:", message)
    args = ["interpret-trailers", "--if-exists", "replace"]
    for k, v in trailers:
        key = "Task-name" if k.lower() == "task" else k
        args.extend(["--trailer", f"{key}: {v}"])
    run_env = {**os.environ, **(env or {})}
    done = subprocess.run(
        ["git", *args],
        cwd=root or Path.cwd(),
        input=protected_msg,
        env=run_env,
        check=True,
        capture_output=True,
        text=True,
    )
    return re.sub(r"(?m)^Task-name:", "Task:", done.stdout)


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


def placeholder_messages(root: Path, base: str) -> dict[Path, str]:
    """Return the task's commit messages, keyed like files, so their placeholders count too."""
    log = git("log", "--format=%B%x00", f"{base}..HEAD", cwd=root)
    return {Path(f"<message {i}>"): text for i, text in enumerate(log.split("\0"))}


def collect_placeholders(texts: dict[Path, str]) -> list[str]:
    """Return every placeholder found in ``texts``, sorted by prefix and number."""
    found: dict[str, set[int]] = {"S": set(), "B": set()}
    for text in texts.values():
        for prefix, number in PLACEHOLDER.findall(text):
            found[prefix].add(int(number))
    return [f"{p}-NEW{n}" for p in ("S", "B") for n in sorted(found[p])]


def is_defined(root: Path, placeholder: str) -> bool:
    """Return whether ``placeholder`` is defined at the task tip.

    Why: S-195 (rule: DECISIONS.md has index row or heading; BACKLOG.md has row).
    """
    prefix = placeholder[0]
    journal = root / JOURNAL.get(prefix, "")
    if not journal.is_file():
        return False
    text = journal.read_text(encoding="utf-8")
    row_pat = rf"^\s*\|\s*{re.escape(placeholder)}\s*\|"
    if prefix == "S":
        heading_pat = rf"^\s*##\s*{re.escape(placeholder)}(?!\d)\b"
        return bool(
            re.search(row_pat, text, re.MULTILINE) or re.search(heading_pat, text, re.MULTILINE)
        )
    if prefix == "B":
        return bool(re.search(row_pat, text, re.MULTILINE))
    return False


def undefined_placeholders(root: Path, placeholders: list[str]) -> list[str]:
    """Return placeholders from ``placeholders`` not defined at the task tip."""
    return [ph for ph in placeholders if not is_defined(root, ph)]


def rewrite_history(
    root: Path,
    base: str,
    mapping: dict[str, str],
    trailers: list[tuple[str, str]] | None = None,
) -> str:
    """Rebuild each commit after ``base`` with ``mapping`` and ``trailers`` applied.

    Returns the new tip.
    """

    def fix(text: str) -> str:
        return PLACEHOLDER.sub(lambda m: mapping.get(m.group(0), m.group(0)), text)

    commits = git("rev-list", "--reverse", f"{base}..HEAD", cwd=root).split()
    parent = git("rev-parse", base, cwd=root).strip()
    index = Path(git("rev-parse", "--absolute-git-dir", cwd=root).strip()) / "journal-ids-index"
    env = {"GIT_INDEX_FILE": str(index)}
    try:
        for commit in commits:
            git_env(root, env, "read-tree", commit)
            for name in git("diff", "--name-only", base, commit, cwd=root).splitlines():
                entry = git("ls-tree", commit, "--", name, cwd=root).split()
                if not entry or entry[1] != "blob":
                    continue  # deleted in this commit, or a submodule
                raw = subprocess.run(
                    ["git", "cat-file", "blob", entry[2]], cwd=root, check=True, capture_output=True
                ).stdout
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    continue  # binary
                if fix(text) != text:
                    blob = (
                        subprocess.run(
                            ["git", "hash-object", "-w", "--stdin"],
                            cwd=root,
                            input=fix(text).encode("utf-8"),
                            check=True,
                            capture_output=True,
                        )
                        .stdout.decode()
                        .strip()
                    )
                    git_env(root, env, "update-index", "--cacheinfo", f"{entry[0]},{blob},{name}")
            tree = git_env(root, env, "write-tree").strip()
            meta = git("log", "-1", "--format=%an%x00%ae%x00%ad%x00%B", commit, cwd=root)
            name, email, date, message = meta.split("\0", 3)
            author = {"GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email, "GIT_AUTHOR_DATE": date}
            msg = fix(message).rstrip("\n")
            if trailers:
                msg = apply_trailers(msg, trailers, root=root, env=env).rstrip("\n")
            parent = git_env(root, author, "commit-tree", tree, "-p", parent, "-m", msg).strip()
    finally:
        index.unlink(missing_ok=True)
    return parent


def git_env(root: Path, env: dict[str, str], *args: str) -> str:
    """Run git like :func:`git` with extra environment variables."""
    done = subprocess.run(
        ["git", *args],
        cwd=root,
        env={**os.environ, **env},
        check=True,
        capture_output=True,
        text=True,
    )
    return done.stdout


def main(argv: list[str] | None = None) -> int:
    """Rewrite the placeholders through the task's history and print what became what."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="main", help="branch the task lands on")
    parser.add_argument(
        "--trailer",
        action="append",
        default=[],
        help="trailer KEY=VALUE to stamp on each task commit message",
    )
    args = parser.parse_args(argv)
    root = Path(git("rev-parse", "--show-toplevel", cwd=Path.cwd()).strip())
    texts = changed_text_files(root, args.base) | placeholder_messages(root, args.base)
    placeholders = collect_placeholders(texts)
    missing = undefined_placeholders(root, placeholders)
    if missing:
        # Why: S-195 (refuse cited placeholders not defined by the task).
        for ph in missing:
            journal = JOURNAL[ph[0]]
            print(
                f"{ph} is cited but this task defines no {ph} entry in {journal}: "
                "cite the landed id of the entry you mean instead",
                file=sys.stderr,
            )
        return 1
    mapping = assign(root, texts)
    trailers = [parse_trailer(t) for t in args.trailer]
    if not mapping and not trailers:
        print("journal ids: no placeholders")
        return 0
    tip = rewrite_history(root, args.base, mapping, trailers=trailers)
    git("reset", "-q", "--hard", tip, cwd=root)
    for old, new in mapping.items():
        print(f"journal ids: {old} -> {new}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
