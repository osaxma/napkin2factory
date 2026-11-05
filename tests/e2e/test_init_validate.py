"""``n2f init`` → ``n2f validate`` → ``n2f lint`` for every template, through the real CLI."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from napkin2factory.templates import TEMPLATE_NAMES, TEMPLATES_DIR
from tests.conftest import n2f

INSTALLED = [t for t in TEMPLATE_NAMES if (TEMPLATES_DIR / t).is_dir()]


@pytest.mark.parametrize("template", INSTALLED)
def test_init_then_validate_and_lint(tmp_path: Path, template: str):
    dest = tmp_path / "my-thing"
    r = n2f("init", str(dest), "--template", template, "--json", process=True)  # the entry point
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert payload["product"] == "my-thing" and payload["snapshot"]
    assert (dest / ".git").is_dir(), "init starts change tracking (D23)"
    assert (dest / "AGENTS.md").is_file() and not (dest / "CLAUDE.md").exists()  # S-076
    assert not (dest / ".claude").exists(), "roles live in roles/, for any client (S-077)"
    for rel in (
        "roles/pm.md",
        "roles/design.md",
        "roles/verifier.md",
        "roles/impact-analyst.md",
        ".github/workflows/build.yml",
    ):
        assert (dest / rel).is_file(), rel
    assert "id: my-thing" in (dest / "n2f.yaml").read_text()
    v = n2f("validate", cwd=dest, process=True)
    assert v.returncode == 0, v.stderr + v.stdout
    lint = n2f("lint", cwd=dest, process=True)
    assert lint.returncode == 0, lint.stderr + lint.stdout
    # vocabulary: user-facing output has no git words
    for out in (r.stdout, r.stderr, v.stdout, v.stderr, lint.stdout, lint.stderr):
        assert "commit" not in out and "branch" not in out, out


def test_init_hint_points_to_build_and_warns_about_the_kernel(tmp_path: Path):
    r = n2f("init", str(tmp_path / "hinted"), "--template", "blank")
    assert r.returncode == 0, r.stderr
    assert "next: sketch two directions — `n2f concept new" in r.stdout, r.stdout
    assert "or go straight to `n2f build`" in r.stdout and "CAD kernel" in r.stdout, r.stdout
    assert "AI client" in r.stdout
    # gate B, B6: no ten-character snapshot id for the owner
    assert re.search(r"first snapshot saved\s*$", r.stdout, re.MULTILINE), r.stdout


def test_init_refuses_to_overwrite_but_keeps_the_owners_files(tmp_path: Path):
    # The owner's brief may already sit in the folder; init refuses only a file it would write.
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "f").write_text("1")
    assert n2f("init", str(tmp_path / "x")).returncode == 0
    assert (tmp_path / "x" / "f").read_text() == "1"
    (tmp_path / "y").mkdir()
    (tmp_path / "y" / "AGENTS.md").write_text("mine")
    r = n2f("init", str(tmp_path / "y"))
    assert r.returncode == 1 and "AGENTS.md" in r.stderr
    assert (tmp_path / "y" / "AGENTS.md").read_text() == "mine"


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
