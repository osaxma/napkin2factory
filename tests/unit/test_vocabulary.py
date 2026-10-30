"""No git words in user-facing strings, templates, or schema field names (D22, §9)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from napkin2factory.core import model as model_pkg
from tests.conftest import ROOT

SRC = ROOT / "src" / "napkin2factory"
GIT_WORDS = re.compile(
    r"\b(branch|branches|commit|commits|committed|merge|merged|merging|PR|PRs|pull request"
    r"|rebase|checkout|HEAD)\b"
)
ALLOWED_FILES = {"vcs.py"}  # the wrapper holds git's own argv, by design


def _string_literals(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append((node.lineno, node.value))
        elif isinstance(node, ast.JoinedStr):
            for v in node.values:
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    out.append((node.lineno, v.value))
    return out


def _is_docstring_or_comment_only(text: str) -> bool:
    return False


@pytest.mark.parametrize(
    "path",
    sorted((SRC / "cli").glob("*.py"))
    + sorted((SRC / "core").glob("*.py"))
    + sorted((SRC / "ecr").glob("*.py"))
    if (SRC / "ecr").exists()
    else sorted((SRC / "cli").glob("*.py")) + sorted((SRC / "core").glob("*.py")),
)
def test_no_git_words_in_user_strings(path: Path):
    if path.name in ALLOWED_FILES:
        return
    offenders = [
        (ln, s)
        for ln, s in _string_literals(path)
        if GIT_WORDS.search(s) and not s.lstrip().startswith(("Co-Authored", "git ", "-c"))
    ]
    # Docstrings are developer-facing: skip literals that are a body's first statement.
    tree = ast.parse(path.read_text(encoding="utf-8"))
    doc_lines = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
            ):
                doc_lines.add(node.body[0].lineno)
    offenders = [(ln, s) for ln, s in offenders if ln not in doc_lines]
    assert not offenders, f"{path.relative_to(ROOT)}: {offenders}"


def test_schema_field_names_use_persona_vocabulary():
    for name in model_pkg.__all__:
        cls = getattr(model_pkg, name)
        fields = getattr(cls, "model_fields", None)
        if not fields:
            continue
        for fname in fields:
            assert not GIT_WORDS.search(fname), f"{name}.{fname}"


@pytest.mark.parametrize(
    "path", sorted((SRC / "templates").rglob("*.md")) + sorted((SRC / "templates").rglob("*.yaml"))
)
def test_templates_use_persona_vocabulary(path: Path):
    text = path.read_text(encoding="utf-8")
    # Product CLAUDE.md explains the mapping once ("never git words"); allow that sentence only.
    text = text.replace("never git words", "")
    hits = [m.group(0) for m in GIT_WORDS.finditer(text)]
    if path.parts[-2:] == ("workflows", "build.yml") or path.name in ("release.yml", "build.yml"):
        return  # CI yaml talks to GitHub, not to the owner
    assert not hits, f"{path.relative_to(ROOT)}: {hits}"
