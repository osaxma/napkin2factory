"""Prepare and verify the one-module simulation (v0.4 DoD 5, M6; tests/e2e/module-transcripts/).

A fresh-context agent gets one Markdown file, the *bundle*, and nothing else from this
repository: the product's design role, the text of ``n2f context asm://<id>`` and the module's
geometry Python files that the context lists (inlined, because the context names them but
does not print them, S-114).  Afterwards, ``--verify`` compares the product copy the agent
worked in with an untouched original and says whether every file it changed is one the
context lists (DoD 5: "open no file outside the context it was given"; this checks the
edits, the transcript records what was opened).

Usage (from the repository root, with the package installed: ``uv run python …``):

    python scripts/module_sim_bundle.py <copy> asm://door [--out <bundle.md>]
    python scripts/module_sim_bundle.py --verify <copy> <original> asm://door [--json]

``<copy>`` is a built copy of the product (never ``examples/`` itself).  The bundle is written
next to the copy as ``<copy>-<id>-bundle.md`` unless ``--out`` says otherwise; its size in
bytes is printed.  ``--verify`` exits 0 when at least one file changed and every changed file
is in the context's list, 1 when a changed file is outside it, 2 when nothing changed.
``build/`` and caches are ignored.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

IGNORED_DIRS = {"build", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
IGNORED_NAMES = {".DS_Store"}


def _context(product_root: Path, module: str) -> dict[str, Any]:
    """The module's context as ``n2f context <module> --json`` prints it."""
    from napkin2factory.cli.build_asm import assembly_id
    from napkin2factory.core.context import module_context
    from napkin2factory.core.loader import load_product

    product = load_product(product_root)
    return module_context(product, assembly_id(product, module))


def make_bundle(copy: Path, module: str) -> str:
    """The bundle's Markdown: design role, context text, the listed geometry files."""
    from napkin2factory.core.context import render_text

    ctx = _context(copy, module)
    role = (copy / "roles" / "design.md").read_text(encoding="utf-8")
    parts = [
        f"# Working context for {ctx['module']} ({ctx['name']})",
        "",
        "Three parts: your role, the module's context (the output of "
        f"`n2f context {ctx['module']}`), and the geometry code the context lists.",
        "",
        "---",
        "",
        "# Part 1: your role (roles/design.md)",
        "",
        role.rstrip(),
        "",
        "---",
        "",
        f"# Part 2: `n2f context {ctx['module']}`",
        "",
        render_text(ctx).rstrip(),
        "",
        "---",
        "",
        "# Part 3: the geometry code the context lists",
    ]
    for rel in ctx["files"]:
        if not rel.endswith(".py"):
            continue
        parts += ["", f"## {rel}", "```python", (copy / rel).read_text(encoding="utf-8").rstrip()]
        parts.append("```")
    return "\n".join(parts) + "\n"


def _files(root: Path) -> dict[str, str]:
    """Relative path → content hash of every file under ``root``, build output left out."""
    out: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(p in IGNORED_DIRS for p in rel.parts) or path.name in IGNORED_NAMES:
            continue
        if path.is_file():
            out[rel.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def verify(copy: Path, original: Path, module: str) -> dict[str, Any]:
    """Which files differ between ``copy`` and ``original``, and whether the context lists them.

    The list is taken from the original (what the agent was given).  A file added or removed
    counts as changed.
    """
    listed = set(_context(original, module)["files"])
    a, b = _files(original), _files(copy)
    changed = sorted(p for p in set(a) | set(b) if a.get(p) != b.get(p))
    rows = [
        {
            "file": p,
            "change": "added" if p not in a else "removed" if p not in b else "edited",
            "in_context": p in listed,
        }
        for p in changed
    ]
    outside = [r["file"] for r in rows if not r["in_context"]]
    if not rows:
        verdict = "no file changed"
    elif outside:
        verdict = f"{len(outside)} changed file(s) outside the context"
    else:
        verdict = "every changed file is in the context"
    return {
        "module": module,
        "context_files": sorted(listed),
        "changed": rows,
        "outside": outside,
        "ok": bool(rows) and not outside,
        "verdict": verdict,
    }


def main(argv: list[str] | None = None) -> int:
    """Command line: write a bundle, or verify a copy against the original."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("--verify", action="store_true", help="compare <copy> with <original>")
    ap.add_argument("--out", type=Path, help="where to write the bundle")
    ap.add_argument("--json", action="store_true", help="--verify: print JSON")
    ap.add_argument("args", nargs="+", help="<copy> <asm> | --verify <copy> <original> <asm>")
    ns = ap.parse_args(argv)
    if ns.verify:
        if len(ns.args) != 3:
            ap.error("--verify takes <copy> <original> <asm>")
        copy, original, module = Path(ns.args[0]), Path(ns.args[1]), ns.args[2]
        res = verify(copy.resolve(), original.resolve(), module)
        if ns.json:
            print(json.dumps(res, indent=2))
        else:
            for r in res["changed"]:
                where = "in the context" if r["in_context"] else "OUTSIDE the context"
                print(f"{r['change']:8} {r['file']}  ({where})")
            print(res["verdict"])
        if not res["changed"]:
            return 2
        return 0 if res["ok"] else 1
    if len(ns.args) != 2:
        ap.error("a bundle takes <copy> <asm>")
    copy, module = Path(ns.args[0]).resolve(), ns.args[1]
    text = make_bundle(copy, module)
    out = ns.out or copy.parent / f"{copy.name}-{module.split('://', 1)[-1]}-bundle.md"
    out.write_text(text, encoding="utf-8")
    print(f"{out}: {len(text.encode('utf-8'))} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
