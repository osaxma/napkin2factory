"""``n2f init`` → ``n2f validate`` → ``n2f lint`` for every template, through the real CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from napkin2factory.templates import TEMPLATE_NAMES, TEMPLATES_DIR
from tests.conftest import n2f

INSTALLED = [t for t in TEMPLATE_NAMES if (TEMPLATES_DIR / t).is_dir()]


@pytest.mark.parametrize("template", INSTALLED)
def test_init_then_validate_and_lint(tmp_path: Path, template: str):
    dest = tmp_path / "my-thing"
    r = n2f("init", str(dest), "--template", template, "--json")
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert payload["product"] == "my-thing" and payload["snapshot"]
    assert (dest / ".git").is_dir(), "init starts change tracking (D23)"
    assert (dest / "CLAUDE.md").read_text() == (dest / "AGENTS.md").read_text()
    for rel in (
        ".claude/skills/n2f-pm/SKILL.md",
        ".claude/skills/n2f-design/SKILL.md",
        ".claude/agents/n2f-verifier.md",
        ".github/workflows/build.yml",
    ):
        assert (dest / rel).is_file(), rel
    assert "id: my-thing" in (dest / "n2f.yaml").read_text()
    v = n2f("validate", cwd=dest)
    assert v.returncode == 0, v.stderr + v.stdout
    lint = n2f("lint", cwd=dest)
    assert lint.returncode == 0, lint.stderr + lint.stdout
    # vocabulary: user-facing output has no git words
    for out in (r.stdout, r.stderr, v.stdout, v.stderr, lint.stdout, lint.stderr):
        assert "commit" not in out and "branch" not in out, out


def test_init_refuses_non_empty(tmp_path: Path):
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "f").write_text("1")
    r = n2f("init", str(tmp_path / "x"))
    assert r.returncode == 1 and "not empty" in r.stderr


def test_validate_outside_a_product_is_actionable(tmp_path: Path):
    r = n2f("validate", cwd=tmp_path)
    assert r.returncode == 1
    assert "n2f init" in r.stderr and "fatal" not in r.stderr.lower()


def test_validate_json_reports_problems(tmp_path: Path):
    from tests.conftest import FIXTURES

    r = n2f("validate", "--json", cwd=FIXTURES / "invalid" / "bad-uri-target")
    assert r.returncode == 1
    payload = json.loads(r.stdout)
    assert payload["ok"] is False and payload["problems"][0]["file"]
