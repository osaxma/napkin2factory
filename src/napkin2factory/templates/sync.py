"""``make templates``: keep examples and templates identical (decision D19).

1. Copy ``templates/_common`` into every example (CLAUDE.md, AGENTS.md, skills, workflows).
2. Copy ``examples/bracket`` and ``examples/enclosure`` into ``templates/``.
``tests/unit/test_templates.py`` asserts the result is in sync.
"""

from __future__ import annotations

import filecmp
import shutil
import sys
from pathlib import Path

from napkin2factory.templates import TEMPLATES_DIR

SYSTEM_ROOT = TEMPLATES_DIR.parents[2]
EXAMPLES_DIR = SYSTEM_ROOT / "examples"
SYNCED = ("bracket", "enclosure")
IGNORE = shutil.ignore_patterns("build", "__pycache__", ".git", "*.pyc", ".DS_Store")


def _copy(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=IGNORE)


def sync() -> None:
    """Perform the two copies."""
    common = TEMPLATES_DIR / "_common"
    for example in sorted(p for p in EXAMPLES_DIR.iterdir() if p.is_dir()):
        _copy(common, example)
    for name in SYNCED:
        src = EXAMPLES_DIR / name
        if not src.is_dir():
            continue
        dst = TEMPLATES_DIR / name
        if dst.exists():
            shutil.rmtree(dst)
        _copy(src, dst)


def differences() -> list[str]:
    """Paths that differ between examples/templates and the common files."""
    out: list[str] = []
    common = TEMPLATES_DIR / "_common"
    for example in sorted(p for p in EXAMPLES_DIR.iterdir() if p.is_dir()):
        out.extend(_diff_tree(common, example, f"examples/{example.name}", subset=True))
    for name in SYNCED:
        src, dst = EXAMPLES_DIR / name, TEMPLATES_DIR / name
        if src.is_dir():
            out.extend(_diff_tree(src, dst, f"templates/{name}"))
    return out


def _diff_tree(a: Path, b: Path, label: str, subset: bool = False) -> list[str]:
    out: list[str] = []
    if not b.exists():
        return [f"{label}: missing"]
    cmp = filecmp.dircmp(a, b, ignore=["build", "__pycache__", ".git", ".DS_Store"])
    _walk(cmp, label, out, subset)
    return out


def _walk(cmp: filecmp.dircmp, label: str, out: list[str], subset: bool) -> None:
    for f in cmp.diff_files:
        out.append(f"{label}/{f}: differs")
    for f in cmp.left_only:
        out.append(f"{label}/{f}: missing")
    if not subset:
        for f in cmp.right_only:
            out.append(f"{label}/{f}: extra")
    for name, sub in cmp.subdirs.items():
        _walk(sub, f"{label}/{name}", out, subset)


if __name__ == "__main__":
    sync()
    diffs = differences()
    print("templates synced" if not diffs else "\n".join(diffs))
    sys.exit(0 if not diffs else 1)
